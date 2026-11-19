"""Collect K-pop news candidates from RSS / YouTube feeds into data/candidates.json.

No AI here: this only gathers headlines, links, times and thumbnails as leads.
Claude reads the file later, judges, verifies and writes original copy.
"""
import hashlib
import html
import re
import sys
from datetime import timedelta
from email.utils import parsedate_to_datetime

import feedparser
import requests

from common import DATA, ROOT, iso, load_json, now_utc, parse_iso, save_json

KEEP_HOURS = 72
MAX_ITEMS = 600
UA = "Mozilla/5.0 (compatible; kpop-cardnews-collector/1.0; +https://github.com)"
TAG_RE = re.compile(r"<[^>]+>")


def clean(text, n=300):
    text = html.unescape(TAG_RE.sub(" ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:n]


def entry_time(e):
    for key in ("published_parsed", "updated_parsed"):
        t = e.get(key)
        if t:
            from datetime import datetime, timezone
            return datetime(*t[:6], tzinfo=timezone.utc)
    for key in ("published", "updated"):
        if e.get(key):
            try:
                return parsedate_to_datetime(e[key])
            except Exception:
                pass
    return now_utc()


def entry_image(e):
    for key in ("media_thumbnail", "media_content"):
        for m in e.get(key) or []:
            if m.get("url"):
                return m["url"]
    for l in e.get("links") or []:
        if l.get("rel") == "enclosure" and str(l.get("type", "")).startswith("image"):
            return l.get("href")
    return None


def fetch(source):
    if source["type"] == "youtube":
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={source['channel_id']}"
    else:
        url = source["url"]
    r = requests.get(url, headers={"User-Agent": UA}, timeout=25)
    r.raise_for_status()
    feed = feedparser.parse(r.content)
    items = []
    for e in feed.entries:
        link = e.get("link")
        if not link:
            continue
        img = entry_image(e)
        if source["type"] == "youtube" and e.get("yt_videoid"):
            img = f"https://i.ytimg.com/vi/{e['yt_videoid']}/maxresdefault.jpg"
        items.append({
            "id": hashlib.sha1(link.encode()).hexdigest()[:12],
            "title": clean(e.get("title"), 200),
            "link": link,
            "source": source["name"],
            "kind": "official_video" if source["type"] == "youtube" else "article",
            "lang": source.get("lang", "ko" if source["type"] == "youtube" else ""),
            "published": iso(entry_time(e)),
            "summary": clean(e.get("summary") or e.get("description")),
            "image": img,
        })
    return items


def main():
    cfg = load_json(ROOT / "config/sources.json", {"sources": []})
    path = DATA / "candidates.json"
    existing = {c["id"]: c for c in load_json(path, [])}
    status = {}
    added = 0
    for src in cfg["sources"]:
        try:
            items = fetch(src)
            new = [i for i in items if i["id"] not in existing]
            for i in new:
                i["collected"] = iso(now_utc())
                existing[i["id"]] = i
            added += len(new)
            status[src["name"]] = {"ok": True, "items": len(items), "new": len(new), "checked": iso(now_utc())}
        except Exception as ex:  # one broken feed must not stop the others
            status[src["name"]] = {"ok": False, "error": str(ex)[:200], "checked": iso(now_utc())}
            print(f"[warn] {src['name']}: {ex}", file=sys.stderr)

    cutoff = now_utc() - timedelta(hours=KEEP_HOURS)
    kept = [c for c in existing.values() if parse_iso(c["published"]) >= cutoff]
    kept.sort(key=lambda c: c["published"], reverse=True)
    save_json(path, kept[:MAX_ITEMS])
    save_json(DATA / "source_status.json", status)
    print(f"added {added}, total {len(kept[:MAX_ITEMS])}")


if __name__ == "__main__":
    main()
