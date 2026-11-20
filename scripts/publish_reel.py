"""Roundup reel: string the posts from the latest publishing batch into one 9:16 video and post it as a Reel.

Runs right after the hourly publish job has posted its batch (up to 4 posts, one per hour). It
  1. collects the posts published in the last 5 h that no earlier reel has covered (needs >= 2),
  2. orders them so the most eye-catching story leads (post.json `hook` 1-10 set by the editor,
     otherwise a category heuristic),
  3. renders templates/reel.py to an MP4,
  4. waits for the usual publishing gap (min_publish_interval_minutes) and honours the pause,
     the action-block cooldown, the publishing quota and the duplicate check, like publish.py,
  5. attaches music through Instagram's Audio API: the song named in the lead story
     (post.json `song`, or a quoted title in a music headline) by the lead artist, else another
     song by that artist; if Instagram's catalog has neither, the next story's artist is tried,
  6. uploads the video (resumable upload, no public URL needed) and publishes it.

usage:
  python scripts/publish_reel.py                 # normal run (Actions, after publish)
  python scripts/publish_reel.py --test [dirs]   # render + audio search + upload, NO publish;
                                                 # writes data/reel_test_result.json
  python scripts/publish_reel.py --local dirs    # render only, no Instagram calls
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from common import (DATA, KST, POSTED, ROOT, iso, now_utc, parse_iso, queue_posts,  # noqa: E402
                    save_json, settings)
from publish import (IG, blocked_until, find_on_instagram, is_block_error, posted_index,  # noqa: E402
                     set_block)

sys.path.insert(0, str(ROOT / "templates"))
import reel  # noqa: E402

REELS = ROOT / "reels"
BATCH_HOURS = 5
MAX_STORIES = 4
MAX_WAIT_MIN = 80

CATEGORY_HOOK = {"COMEBACK": 8, "MV": 8, "RELEASE": 7, "TEASER": 7, "DEBUT": 7, "CHART": 7, "AWARD": 7,
                 "MUSIC SHOW": 6, "TOUR": 6, "CONCERT": 6, "OFFICIAL": 6, "FANMEETING": 5, "AD": 5,
                 "TV": 5, "MAGAZINE": 4, "NEWS": 5}
MUSIC_CATEGORIES = {"COMEBACK", "MV", "RELEASE", "TEASER", "DEBUT", "CHART", "AWARD", "MUSIC SHOW"}


# ---------- batch ----------

def find_post_dir(pid):
    for base in [POSTED] + [ROOT / "queue"]:
        for d in base.glob(f"**/{pid}"):
            if (d / "post.json").exists():
                return d
    return None


def latest_batch():
    rows = posted_index()
    covered, last_reel = set(), ""
    for r in rows:
        if r.get("kind") == "reel":
            covered.update(r.get("covers") or [])
            last_reel = max(last_reel, r.get("published_at") or "")
    since = now_utc() - timedelta(hours=BATCH_HOURS)
    ids = [r["id"] for r in rows
           if r.get("kind") != "reel" and r.get("id") not in covered and r.get("published_at")
           and parse_iso(r["published_at"]) > since and r["published_at"] > last_reel]
    return [d for d in (find_post_dir(i) for i in ids[-MAX_STORIES:]) if d]


def load(d, handle):
    post = json.loads((d / "post.json").read_text(encoding="utf-8"))
    created = parse_iso(post["created_at"]) if post.get("created_at") else datetime.now(KST)
    post["date"] = created.astimezone(KST).strftime("%b %d, %Y").upper()
    post["handle"] = handle
    photo = d / "photo.jpg"
    post["photo"] = photo.resolve().as_uri() if photo.exists() else None
    return post


def hook(post):
    try:
        return float(post["hook"])
    except (KeyError, TypeError, ValueError):
        return CATEGORY_HOOK.get(post.get("category", ""), 5)


def order(posts):
    """Lead with the most eye-catching story; ties keep publishing order."""
    return sorted(posts, key=lambda p: -hook(p))


# ---------- music ----------

def norm(s):
    return re.sub(r"[^0-9a-z가-힣]", "", (s or "").lower())


def song_hint(post):
    """(title or None, artist) the reel music should come from."""
    if "song" in post and not post["song"]:      # editor said: no song for this story
        return None, ""
    s = post.get("song") or {}
    artist = s.get("artist") or post.get("artist") or post.get("group") or ""
    title = s.get("title")
    if not title and post.get("category") in MUSIC_CATEGORIES:
        m = re.search(r"'([^']{2,40})'", post.get("headline", ""))
        title = m.group(1) if m else None
    return title, artist


def search_audio(ig, uid, query):
    data = ig.call("GET", "ig_audio", audio_type="music", user_id=uid, search_query=query)
    if isinstance(data, list):
        return data
    return data.get("audio") or data.get("data") or []


def pick_music(ig, uid, posts, log):
    for rank, post in enumerate(posts):
        title, artist = song_hint(post)
        na = norm(artist)
        if len(na) < 2:
            continue
        queries = ([f"{artist} {title}"] if title else []) + [artist]
        same_artist = []
        for q in queries:
            try:
                res = search_audio(ig, uid, q)
            except Exception as ex:
                log.append({"query": q, "error": str(ex)[:300]})
                continue
            log.append({"query": q, "results": [{k: a.get(k) for k in ("audio_id", "title", "display_artist")}
                                                for a in res[:5]]})
            for a in res:
                da = norm(a.get("display_artist"))
                if not da or not (na in da or da in na):
                    continue
                if title and norm(title) and norm(title) in norm(a.get("title")):
                    return a, post, "named song" if rank == 0 else f"named song of story {rank + 1}"
                same_artist.append(a)
            if same_artist:
                break
        if same_artist:
            return same_artist[0], post, "artist's song" if rank == 0 else f"artist's song of story {rank + 1}"
    return None, None, "no matching music in Instagram's catalog"


# ---------- caption ----------

def caption_for(posts, handle):
    when = datetime.now(KST)
    nums = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    lines = [f"📰 K-pop roundup · {when.strftime('%b %d').upper()} — {posts[0]['headline']}", ""]
    lines += [f"{nums[i]} {p['headline']}" for i, p in enumerate(posts)]
    lines += ["", "Full story on each in our latest posts 👆 Follow for K-pop news straight from Korean sources."]
    tags, seen = [], set()
    for p in posts:
        t = "#" + re.sub(r"[^0-9A-Za-z가-힣]", "", p.get("group", ""))
        if len(t) > 1 and t.lower() not in seen:
            seen.add(t.lower()); tags.append(t)
    tags += ["#kpop", "#kpopnews", "#kpoproundup"]
    return "\n".join(lines + ["", " ".join(tags[:10])])[:2200]


# ---------- instagram ----------

def wait_video(ig, cid, minutes=10):
    end = time.time() + minutes * 60
    while time.time() < end:
        s = ig.call("GET", cid, fields="status_code,status")
        if s.get("status_code") == "FINISHED":
            return
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"video container {cid}: {s}")
        time.sleep(10)
    raise RuntimeError(f"video container {cid} not ready after {minutes} min")


def create_and_upload(ig, uid, video, caption, audio_id, ai_label, thumb_ms):
    params = dict(media_type="REELS", upload_type="resumable", caption=caption, share_to_feed="true",
                  thumb_offset=str(thumb_ms))
    if ai_label:
        params["is_ai_generated"] = "true"
    if audio_id:
        params["audio_configuration"] = json.dumps({"audio_id": str(audio_id), "audio_volume": 100,
                                                    "video_volume": 1})
    c = ig.call("POST", f"{uid}/media", **params)
    cid = c["id"]
    uri = c.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{cid}"
    data = Path(video).read_bytes()
    r = requests.post(uri, data=data, timeout=300, headers={
        "Authorization": f"OAuth {ig.token}", "offset": "0", "file_size": str(len(data))})
    if r.status_code >= 400:
        raise RuntimeError(f"video upload failed {r.status_code}: {r.text[:300]}")
    wait_video(ig, cid)
    return cid


def make_container(ig, uid, video, caption, audio, ai_label, n, log):
    thumb = int((reel.STORY * 0.6) * 1000)          # lead story with its headline fully in
    try:
        return create_and_upload(ig, uid, video, caption, audio and audio["audio_id"], ai_label, thumb), audio
    except Exception as ex:
        if not audio or is_block_error(str(ex)):
            raise
        log.append({"music_attach_error": str(ex)[:300]})
        print(f"[warn] container with music failed ({ex}); retrying without music", file=sys.stderr)
        return create_and_upload(ig, uid, video, caption, None, ai_label, thumb), None


# ---------- main ----------

def wait_for_gap(cfg):
    gap = cfg.get("min_publish_interval_minutes", 0)
    last = max((r.get("published_at") or "" for r in posted_index()), default="")
    if not gap or not last:
        return True
    wait = gap * 60 - (now_utc() - parse_iso(last)).total_seconds()
    if wait > MAX_WAIT_MIN * 60:
        print(f"next slot is {wait / 60:.0f} min away; skipping this reel")
        return False
    if wait > 0:
        print(f"waiting {wait / 60:.0f} min for the publishing gap")
        time.sleep(wait)
    return True


def gate(cfg):
    paused = cfg.get("publish_paused_until")
    if paused and parse_iso(paused) > now_utc():
        print(f"publishing paused until {paused}; no reel")
        return False
    until = blocked_until()
    if until:
        print(f"publishing blocked until {until}; no reel")
        return False
    return True


def main():
    args = sys.argv[1:]
    mode = args[0] if args and args[0].startswith("--") else "--run"
    dirs = [Path(a).resolve() for a in args[1:]] if mode != "--run" else []
    cfg = settings()
    handle = cfg.get("handle", "@kpop.quokka")

    if mode == "--run":
        if not gate(cfg):
            return
        dirs = latest_batch()
    elif not dirs:   # --test without dirs: newest rendered queue posts
        dirs = [d for d, p in queue_posts() if p.get("rendered") and (d / "photo.jpg").exists()][-MAX_STORIES:]
    if len(dirs) < 2:
        print(f"only {len(dirs)} new post(s) in this batch; no reel")
        return

    posts = order([load(d, handle) for d in dirs])
    reel_id = datetime.now(KST).strftime("%Y%m%d-%H%M") + "-roundup"
    out_dir = REELS / reel_id
    out_dir.mkdir(parents=True, exist_ok=True)
    video = reel.render(posts, handle, out_dir / "reel.mp4")
    print(f"rendered {video} ({reel.duration(len(posts)):.1f}s): " + " | ".join(p["id"] for p in posts))
    if mode == "--local":
        return

    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        print("[dry-run] IG_ACCESS_TOKEN not set; rendered only")
        return
    ig = IG(token, cfg.get("graph_version", ""))
    uid = os.environ.get("IG_USER_ID") or cfg.get("ig_user_id")
    caption = caption_for(posts, handle)
    log = []
    audio, lead, why = pick_music(ig, uid, posts, log)
    music = {k: audio.get(k) for k in ("audio_id", "title", "display_artist")} if audio else None
    print(f"music: {music} ({why})")
    meta = {"id": reel_id, "covers": [p["id"] for p in posts], "order_hooks": [hook(p) for p in posts],
            "music": music, "music_reason": why, "music_search": log, "caption": caption}

    if mode == "--test":
        probes = []
        req = json.loads((DATA / "reel_test_request.json").read_text())
        for q in req.get("probe_queries") or (None, "christmas"):
            try:
                kw = dict(audio_type="music", user_id=uid)
                if q:
                    kw["search_query"] = q
                res = search_audio(ig, uid, q) if q else ig.call("GET", "ig_audio", **kw).get("audio", [])
                probes.append({"query": q, "hits": [f"{a.get('display_artist')} - {a.get('title')}" for a in res[:6]]})
            except Exception as ex:
                probes.append({"query": q, "error": str(ex)[:300]})
        meta["audio_probes"] = probes
        if req.get("probe_only"):
            save_json(DATA / "reel_test_result.json", meta); print(json.dumps(probes, ensure_ascii=False)[:3000]); return
        try:
            cid, used = make_container(ig, uid, video, caption, audio, cfg.get("ai_label", True), len(posts), log)
            meta.update(test_container=cid, test_status="FINISHED (not published)", music_attached=bool(used))
        except Exception as ex:
            meta.update(test_error=str(ex)[:500])
        meta["tested_at"] = iso(now_utc())
        save_json(DATA / "reel_test_result.json", meta)
        print(json.dumps(meta, ensure_ascii=False, indent=1)[:3000])
        return

    if not wait_for_gap(cfg) or not gate(cfg):
        save_json(out_dir / "reel.json", {**meta, "status": "skipped"})
        return
    try:
        lim = ig.call("GET", f"{uid}/content_publishing_limit", fields="quota_usage,config")
        row = (lim.get("data") or [{}])[0]
        total = (row.get("config") or {}).get("quota_total")
        if total and row.get("quota_usage", 0) >= total:
            print(f"publishing limit reached ({row['quota_usage']}/{total}); no reel")
            return
    except Exception as ex:
        print(f"[warn] limit check failed: {ex}", file=sys.stderr)

    probe = {"caption": caption}
    try:
        found = find_on_instagram(ig, uid, probe)
    except Exception:
        found = None
    if not found:
        try:
            cid, used = make_container(ig, uid, video, caption, audio, cfg.get("ai_label", True), len(posts), log)
            meta["music_attached"] = bool(used)
            media_id = ig.call("POST", f"{uid}/media_publish", creation_id=cid)["id"]
            try:
                link = ig.call("GET", media_id, fields="permalink").get("permalink")
            except Exception:
                link = None
            found = (media_id, link)
        except Exception as ex:
            msg = str(ex)
            print(f"[error] reel failed: {msg}", file=sys.stderr)
            time.sleep(20)
            try:
                found = find_on_instagram(ig, uid, probe)
            except Exception:
                found = None
            if not found:
                if is_block_error(msg):
                    print(f"Instagram action block: cooldown until {set_block(msg)}", file=sys.stderr)
                save_json(out_dir / "reel.json", {**meta, "status": "failed", "error": msg[:500]})
                sys.exit(1)

    media_id, link = found
    meta.update(status="published", media_id=media_id, permalink=link, published_at=iso(now_utc()))
    save_json(out_dir / "reel.json", meta)
    with (POSTED / "index.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"id": reel_id, "kind": "reel", "news_key": reel_id, "covers": meta["covers"],
                            "headline": f"Roundup: {posts[0]['headline']}", "music": music,
                            "published_at": meta["published_at"], "permalink": link}, ensure_ascii=False) + "\n")
    print(f"published reel {reel_id}: {link}")


if __name__ == "__main__":
    main()
