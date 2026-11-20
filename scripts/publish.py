"""Publish the oldest approved post in queue/ to Instagram (one post per run).

Needs secrets: IG_ACCESS_TOKEN (required), IG_USER_ID (optional; looked up if missing).
Without a token it only reports what it would publish (dry run).
"""
import json
import os
import shutil
import sys
import time

import requests

from common import (DATA, FAILED, POSTED, iso, load_json, now_utc, parse_iso, queue_posts, raw_url,
                    save_json, settings)

MAX_ATTEMPTS = 3
BLOCK_FILE = DATA / "publish_block.json"
BLOCK_HOURS = 6


def is_block_error(msg):
    """Instagram action block / rate limit: 2207051, code 4/9/17/32/613, or 'request limit'."""
    m = msg.lower()
    return ("2207051" in m or "request limit" in m or "행동이 차단" in msg
            or any(f'"code": {c},' in m for c in (4, 9, 17, 32, 613)))


def blocked_until():
    b = load_json(BLOCK_FILE, {}) or {}
    until = b.get("until")
    if until and parse_iso(until) > now_utc():
        return until
    return None


def set_block(reason):
    from datetime import timedelta
    until = iso(now_utc() + timedelta(hours=BLOCK_HOURS))
    save_json(BLOCK_FILE, {"until": until, "reason": reason[:300], "set_at": iso(now_utc())})
    return until


def posted_index():
    path = POSTED / "index.jsonl"
    rows = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def caption_key(caption):
    return " ".join((caption or "").split())[:80]


def find_on_instagram(ig, uid, post, hours=48):
    """Return (media_id, permalink) if this caption is already on the account. Raises if lookup fails."""
    want = caption_key(post.get("caption", ""))
    if not want:
        return None
    data = ig.call("GET", f"{uid}/media", fields="id,caption,permalink,timestamp", limit=25).get("data", [])
    for m in data:
        if caption_key(m.get("caption", "")) == want:
            return m["id"], m.get("permalink")
    return None


class IG:
    def __init__(self, token, version=""):
        self.token = token
        # Instagram-login tokens ("IG...") use graph.instagram.com;
        # Facebook/system-user tokens ("EAA...", never expire) use graph.facebook.com.
        host = "graph.facebook.com" if token.startswith("EAA") else "graph.instagram.com"
        self.base = f"https://{host}" + (f"/{version}" if version else "")

    def call(self, method, path, **params):
        params["access_token"] = self.token
        r = requests.request(method, f"{self.base}/{path}", params=params, timeout=60)
        data = r.json() if r.content else {}
        if r.status_code >= 400 or "error" in data:
            raise RuntimeError(json.dumps(data.get("error", data), ensure_ascii=False)[:500])
        return data

    def wait_ready(self, container_id, tries=20):
        for _ in range(tries):
            s = self.call("GET", container_id, fields="status_code").get("status_code")
            if s == "FINISHED":
                return
            if s in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"container {container_id} status {s}")
            time.sleep(3)
        raise RuntimeError(f"container {container_id} not ready")


def drop_stale(max_hours):
    """News older than max_hours is no longer news: move it to rejected/ instead of posting."""
    from common import REJECTED, parse_iso
    for d, post in list(queue_posts()):
        if post.get("created_at") and (now_utc() - parse_iso(post["created_at"])).total_seconds() > max_hours * 3600:
            post["status"] = "stale"
            save_json(d / "post.json", post)
            REJECTED.mkdir(exist_ok=True)
            shutil.move(str(d), str(REJECTED / d.name))
            print(f"dropped stale post {d.name}")


def drop_duplicate_news():
    """Never publish the same news_key twice."""
    from common import REJECTED
    keys = {r.get("news_key") for r in posted_index() if r.get("news_key")}
    for d, post in list(queue_posts()):
        if post.get("news_key") in keys and post.get("status") == "approved":
            post["status"] = "duplicate"
            save_json(d / "post.json", post)
            REJECTED.mkdir(exist_ok=True)
            shutil.move(str(d), str(REJECTED / d.name))
            print(f"dropped {d.name}: news_key already published")


def pick():
    for d, post in queue_posts():
        if post.get("approved") and post.get("rendered") and post.get("status") == "approved" \
                and post.get("photo_used"):
            return d, post
    return None, None


def publish(ig, uid, d, post, ai_label):
    urls = [raw_url(f"queue/{d.name}/{i}.jpg") for i in range(1, post["rendered"] + 1)]
    caption = post.get("caption", "")[:2200]
    label = {"is_ai_generated": "true"} if ai_label else {}
    if len(urls) == 1:
        c = ig.call("POST", f"{uid}/media", image_url=urls[0], caption=caption, **label)["id"]
    else:
        kids = []
        for u in urls:
            kid = ig.call("POST", f"{uid}/media", image_url=u, is_carousel_item="true")["id"]
            ig.wait_ready(kid)
            kids.append(kid)
        c = ig.call("POST", f"{uid}/media", media_type="CAROUSEL", children=",".join(kids),
                    caption=caption, **label)["id"]
    ig.wait_ready(c)
    media_id = ig.call("POST", f"{uid}/media_publish", creation_id=c)["id"]
    try:  # the post is live at this point; a failed permalink lookup must not cause a retry
        link = ig.call("GET", media_id, fields="permalink").get("permalink")
    except Exception as ex:
        print(f"[warn] permalink lookup failed: {ex}", file=sys.stderr)
        link = None
    return media_id, link


def record_published(d, post, media_id, link):
    post.update(status="published", media_id=media_id, permalink=link, published_at=iso(now_utc()))
    save_json(d / "post.json", post)
    month = POSTED / post["published_at"][:7]
    month.mkdir(parents=True, exist_ok=True)
    shutil.move(str(d), str(month / d.name))
    with (POSTED / "index.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({k: post.get(k) for k in
                            ("id", "news_key", "group", "category", "headline", "published_at", "permalink")},
                           ensure_ascii=False) + "\n")
    print(f"published {d.name}: {link}")


def main():
    cfg = settings()
    drop_stale(cfg.get("max_post_age_hours", 36))
    drop_duplicate_news()

    paused = cfg.get("publish_paused_until")
    if paused and parse_iso(paused) > now_utc():
        print(f"publishing paused until {paused} (settings.json publish_paused_until)")
        return
    until = blocked_until()
    if until:
        print(f"publishing blocked: cooldown until {until} (data/publish_block.json)")
        return
    gap = cfg.get("min_publish_interval_minutes", 0)
    last = max((r.get("published_at") or "" for r in posted_index()), default="")
    if gap and last:
        since = (now_utc() - parse_iso(last)).total_seconds() / 60
        if since < gap:
            print(f"interval limit: last post {since:.0f} min ago, need {gap} min")
            return

    token = os.environ.get("IG_ACCESS_TOKEN")
    d, post = pick()
    if not token:
        print(f"[dry-run] IG_ACCESS_TOKEN not set; would publish {d.name if d else 'nothing'}")
        return
    ig = IG(token, cfg.get("graph_version", ""))
    uid = os.environ.get("IG_USER_ID") or cfg.get("ig_user_id") \
        or ig.call("GET", "me", fields="user_id")["user_id"]
    if not d:
        acct = ig.call("GET", uid, fields="username")
        print(f"connected as @{acct.get('username')}; no approved post waiting")
        return

    try:
        lim = ig.call("GET", f"{uid}/content_publishing_limit", fields="quota_usage,config")
        row = (lim.get("data") or [{}])[0]
        total = (row.get("config") or {}).get("quota_total")
        if total and row.get("quota_usage", 0) >= total:
            print(f"publishing limit reached ({row['quota_usage']}/{total}); try later")
            return
    except Exception as ex:
        print(f"[warn] limit check failed: {ex}", file=sys.stderr)

    # Already on the account (e.g. an earlier "failed" call that actually went through)?
    try:
        found = find_on_instagram(ig, uid, post)
    except Exception as ex:
        print(f"[warn] pre-publish duplicate check failed: {ex}", file=sys.stderr)
        found = None
    if found:
        print(f"{d.name} is already on Instagram; recording instead of posting again")
        record_published(d, post, *found)
        return

    try:
        media_id, link = publish(ig, uid, d, post, cfg.get("ai_label", True))
    except Exception as ex:
        msg = str(ex)
        post["attempts"] = post.get("attempts", 0) + 1
        post["last_error"] = msg
        print(f"[error] publish {d.name} failed (attempt {post['attempts']}): {msg}", file=sys.stderr)
        # Instagram sometimes posts even when it returns an error: check before any retry.
        time.sleep(20)
        try:
            found = find_on_instagram(ig, uid, post)
        except Exception as ex2:
            found = None
            post["status"] = "needs_check"
            print(f"[error] could not verify whether it was posted ({ex2}); holding as needs_check",
                  file=sys.stderr)
        if found:
            print("it was actually posted despite the error; recording it")
            save_json(d / "post.json", post)
            record_published(d, post, *found)
            return
        if is_block_error(msg):
            until = set_block(msg)
            print(f"Instagram action block: no publishing until {until}", file=sys.stderr)
        save_json(d / "post.json", post)
        if post.get("status") == "approved" and post["attempts"] >= MAX_ATTEMPTS:
            FAILED.mkdir(exist_ok=True)
            shutil.move(str(d), str(FAILED / d.name))
        sys.exit(1)

    record_published(d, post, media_id, link)


if __name__ == "__main__":
    main()
