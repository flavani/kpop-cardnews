"""Render card images for queue posts that have no images yet.

For each queue/<id>/post.json without rendered cuts:
  - download the photo (if any) to queue/<id>/photo.jpg
  - render 1-3 content cuts + the common outro cut with templates/night_gradient.py to queue/<id>/1.jpg ...
  - set status: pending_review (mode=review) or approved (mode=auto)
"""
import io
import sys
from datetime import datetime

import requests
from PIL import Image
from playwright.sync_api import sync_playwright

from common import KST, ROOT, parse_iso, queue_posts, save_json, settings

sys.path.insert(0, str(ROOT / "templates"))
import night_gradient  # noqa: E402

UA = "Mozilla/5.0 (compatible; kpop-cardnews/1.0)"


def fetch_photo(url, dest):
    """Download and normalise to JPEG. Returns True on success."""
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
        if min(im.size) < 400:          # too small to look decent on a 1080 card
            return False
        im.save(dest, "JPEG", quality=92)
        return True
    except Exception as ex:
        print(f"[warn] photo download failed {url}: {ex}", file=sys.stderr)
        return False


def card_data(d, post, cfg):
    created = parse_iso(post.get("created_at")) if post.get("created_at") else datetime.now(KST)
    data = dict(post)
    data["handle"] = cfg.get("handle", "")
    data["date"] = created.astimezone(KST).strftime("%b %d, %Y").upper()
    photo = d / "photo.jpg"
    if post.get("photo") and (photo.exists() or fetch_photo(post["photo"], photo)):
        data["photo"] = photo.resolve().as_uri()
    else:
        data["photo"] = None
    return data


def main():
    cfg = settings()
    todo = [(d, p) for d, p in queue_posts() if not p.get("rendered")]
    if not todo:
        print("nothing to render")
        return
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        page = br.new_page(viewport={"width": 1080, "height": 1350})
        for d, post in todo:
            try:
                data = card_data(d, post, cfg)
                files = night_gradient.render(data, d, "cut", page=page)
                for i, f in enumerate(files, 1):           # cut_1.jpg -> 1.jpg
                    f.replace(d / f"{i}.jpg")
                for h in d.glob("cut_*.html"):
                    h.unlink()
                post["rendered"] = len(files)
                post["photo_used"] = bool(data["photo"])
                if post.get("status") in (None, "draft"):
                    post["status"] = "approved" if cfg.get("mode") == "auto" else "pending_review"
                post["approved"] = post["status"] == "approved"
                save_json(d / "post.json", post)
                print(f"rendered {d.name}: {len(files)} cuts")
            except Exception as ex:
                print(f"[error] {d.name}: {ex}", file=sys.stderr)
        br.close()


if __name__ == "__main__":
    main()
