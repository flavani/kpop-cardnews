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

from common import FAILED, POSTED, iso, now_utc, queue_posts, raw_url, save_json, settings

MAX_ATTEMPTS = 3


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


def pick():
    for d, post in queue_posts():
        if post.get("approved") and post.get("rendered") and post.get("status") == "approved":
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
    link = ig.call("GET", media_id, fields="permalink").get("permalink")
    return media_id, link


def main():
    cfg = settings()
    drop_stale(cfg.get("max_post_age_hours", 36))
    token = os.environ.get("IG_ACCESS_TOKEN")
    d, post = pick()
    if not token:
        print(f"[dry-run] IG_ACCESS_TOKEN not set; would publish {d.name if d else 'nothing'}")
        return
    ig = IG(token, cfg.get("graph_version", ""))
    uid = os.environ.get("IG_USER_ID") or cfg.get("ig_user_id") \
        or ig.call("GET", "me", fields="user_id")["user_id"]
    if not d:
        # Still verify the connection so a broken token shows up as a failed run.
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

    try:
        media_id, link = publish(ig, uid, d, post, cfg.get("ai_label", True))
    except Exception as ex:
        post["attempts"] = post.get("attempts", 0) + 1
        post["last_error"] = str(ex)
        save_json(d / "post.json", post)
        print(f"[error] publish {d.name} failed (attempt {post['attempts']}): {ex}", file=sys.stderr)
        if post["attempts"] >= MAX_ATTEMPTS:
            FAILED.mkdir(exist_ok=True)
            shutil.move(str(d), str(FAILED / d.name))
        sys.exit(1)

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


if __name__ == "__main__":
    main()
