import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "queue"
POSTED = ROOT / "posted"
REJECTED = ROOT / "rejected"
FAILED = ROOT / "failed"
DATA = ROOT / "data"
KST = timezone(timedelta(hours=9))


def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(p)


def settings():
    return load_json(ROOT / "config/settings.json", {})


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def queue_posts():
    """Yield (dir, post) for every post in queue/, oldest id first."""
    for d in sorted(p for p in QUEUE.iterdir() if p.is_dir()):
        post = load_json(d / "post.json")
        if post:
            yield d, post


def repo_slug():
    return os.environ.get("GITHUB_REPOSITORY", "")


def raw_url(rel_path, ref="main"):
    return f"https://raw.githubusercontent.com/{repo_slug()}/{ref}/{rel_path}"
