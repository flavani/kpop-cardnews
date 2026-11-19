"""Night Gradient card-news template (1080x1350, 1-3 content cuts + common outro cut).

post = {
  "handle": "@kpop.daily",
  "category": "COMEBACK",
  "headline": "LUMINA, 12월 2일 미니 4집으로 컴백",
  "highlight": "LUMINA",            # optional: part of headline shown in accent
  "sub": "...",                     # optional
  "date": "2026.11.19",
  "photo": "path/or/url.jpg",       # optional: falls back to brand gradient
  "focus": "50% 30%",               # optional: background-position of the subject
  "credit": "Photo: OO엔터테인먼트",
  "source": "출처: OO엔터테인먼트 공식 발표",
  "info":   {"title": "컴백 한눈에 보기", "rows": [["발매", "..."], ...]},   # optional cut
  "points": {"title": "이번 컴백 포인트", "items": ["...", ...]},          # optional cut
}
"""
import html
from pathlib import Path

FONT_DIR = (Path(__file__).parent / "fonts").resolve()   # Pretendard *.otf (downloaded in CI)

TOKENS = """
:root{
  --w:1080px; --h:1350px;
  --pad-x:80px; --pad-top:72px; --pad-bottom:80px;
  --accent:#ff2e88;          /* brand pink: pills, markers */
  --accent-text:#ff7ab3;     /* pink for text on dark (>=4.5:1 on scrim) */
  --ink:#ffffff;
  --ink-2:rgba(255,236,245,.88);   /* secondary, tinted toward the accent */
  --ink-3:rgba(255,228,240,.70);   /* meta */
  --rule:rgba(255,220,236,.18);
  --night:#0d0a1a;
}
"""

FONTS = "".join(
    f"@font-face{{font-family:'Pretendard';src:url('file://{FONT_DIR}/Pretendard-{w}.otf');font-weight:{n};}}"
    for w, n in [("Medium", 500), ("SemiBold", 600), ("Bold", 700), ("ExtraBold", 800), ("Black", 900)])

BASE = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:var(--w);height:var(--h)}
body{position:relative;overflow:hidden;background:var(--night);color:var(--ink);
  font-family:'Pretendard',sans-serif;word-break:keep-all;overflow-wrap:anywhere;
  -webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums}
.photo{position:absolute;inset:0;background-size:cover;background-repeat:no-repeat}
.brand-bg{position:absolute;inset:0;background:
  radial-gradient(70% 55% at 25% 20%,#5b2a6e 0%,transparent 70%),
  radial-gradient(60% 50% at 85% 45%,#24306e 0%,transparent 70%),
  linear-gradient(170deg,#1c1336,#0d0a1a)}

/* header: identical position on every cut */
.head{position:absolute;top:var(--pad-top);left:var(--pad-x);right:var(--pad-x);
  display:flex;justify-content:space-between;align-items:center;
  font-size:30px;font-weight:600;letter-spacing:-.01em;color:var(--ink)}
.head .page{color:var(--ink-2);font-weight:500}

.pill{display:inline-flex;align-items:center;height:52px;padding:0 22px;border-radius:26px;
  background:var(--accent);color:#fff;font-size:26px;font-weight:800;letter-spacing:.06em}
"""

COVER = """
/* scrim: top for the header, eased ramp at the bottom for text */
.scrim{position:absolute;inset:0;background:
  linear-gradient(180deg,rgba(8,6,16,.68) 0,rgba(8,6,16,.32) 150px,rgba(8,6,16,0) 300px),
  linear-gradient(180deg,rgba(8,6,16,0) 34%,rgba(8,6,16,.30) 46%,rgba(8,6,16,.62) 58%,
                  rgba(8,6,16,.86) 72%,rgba(8,6,16,.95) 100%)}
.body{position:absolute;left:var(--pad-x);right:var(--pad-x);bottom:var(--pad-bottom)}
h1{font-size:92px;font-weight:900;line-height:1.2;letter-spacing:-.03em;text-wrap:balance;
  text-shadow:0 2px 24px rgba(0,0,0,.35)}
h1 em{font-style:normal;color:var(--accent-text)}
.sub{margin-top:28px;font-size:38px;font-weight:500;line-height:1.45;color:var(--ink-2);
  letter-spacing:-.01em;text-wrap:pretty;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.meta{margin-top:48px;padding-top:32px;border-top:2px solid var(--rule);
  display:flex;align-items:center;gap:24px;font-size:28px;font-weight:500;color:var(--ink-3)}
.meta .credit{margin-left:auto;font-size:26px}
"""

INNER = """
.photo.blur{inset:-80px;filter:blur(48px) saturate(1.15)}
.veil{position:absolute;inset:0;background:
  linear-gradient(180deg,rgba(13,10,26,.86),rgba(13,10,26,.93))}
.body{position:absolute;left:var(--pad-x);right:var(--pad-x);top:150px;bottom:150px;
  display:flex;flex-direction:column;justify-content:center;padding-bottom:48px}
h2{font-size:72px;font-weight:900;line-height:1.2;letter-spacing:-.03em;margin-bottom:48px;text-wrap:balance}
.rows{border-top:2px solid var(--rule)}
.row{display:grid;grid-template-columns:200px 1fr;gap:32px;align-items:baseline;
  padding:44px 0;border-bottom:2px solid var(--rule)}
.row dt{font-size:34px;font-weight:700;color:var(--accent-text)}
.row dd{font-size:44px;font-weight:700;line-height:1.3;letter-spacing:-.02em}
.items{list-style:none;border-top:2px solid var(--rule)}
.items li{display:flex;gap:28px;padding:48px 0;border-bottom:2px solid var(--rule);
  font-size:46px;font-weight:700;line-height:1.4;letter-spacing:-.02em}
.items li::before{content:'';flex:none;width:18px;height:18px;border-radius:50%;background:var(--accent);
  margin-top:calc((1.4em - 18px) / 2)}
.foot{position:absolute;left:var(--pad-x);right:var(--pad-x);bottom:var(--pad-bottom);
  display:flex;justify-content:space-between;gap:24px;font-size:26px;font-weight:500;color:var(--ink-3)}
"""

PROFILE = (Path(__file__).parent / "assets" / "profile.png").resolve()

# Common closing cut appended to every post: follow / comment / save-share prompts.
OUTRO_TEXT = {
    "tagline": "K-pop news, straight from Korean sources",
    "actions": [
        ("follow", "Follow", "for daily K-pop news"),
        ("comment", "Comment", "and tell us what you think"),
        ("save", "Save & share", "with a fellow fan"),
    ],
}

ICONS = {   # 24x24 stroke icons
    "follow": "<circle cx='9' cy='8' r='4'/><path d='M2 21v-1a7 7 0 0 1 14 0v1'/><path d='M19 8v6M16 11h6'/>",
    "comment": "<path d='M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-5A8 8 0 1 1 21 12z'/>",
    "save": "<path d='M6 3h12v18l-6-4.5L6 21z'/>",
}

OUTRO = """
.glow{position:absolute;left:50%;top:400px;width:900px;height:900px;transform:translate(-50%,-50%);
  background:radial-gradient(closest-side,rgba(255,46,136,.30),rgba(255,46,136,0));pointer-events:none}
.body{position:absolute;left:var(--pad-x);right:var(--pad-x);top:150px;bottom:var(--pad-bottom);
  display:flex;flex-direction:column;align-items:center;justify-content:center;padding-bottom:20px}
.avatar{width:320px;height:320px;border-radius:50%;
  box-shadow:0 0 0 8px var(--accent),0 24px 60px rgba(0,0,0,.45)}
.name{margin-top:48px;font-size:64px;font-weight:900;letter-spacing:-.03em}
.tag{margin-top:14px;font-size:34px;font-weight:500;color:var(--ink-2);letter-spacing:-.01em}
.acts{list-style:none;width:100%;margin-top:64px;border-top:2px solid var(--rule)}
.acts li{display:flex;align-items:center;gap:36px;padding:34px 8px;border-bottom:2px solid var(--rule)}
.ic{flex:none;width:88px;height:88px;border-radius:50%;background:var(--accent);
  display:flex;align-items:center;justify-content:center}
.ic svg{width:44px;height:44px;fill:none;stroke:#fff;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
.acts b{display:block;font-size:46px;font-weight:800;letter-spacing:-.02em;line-height:1.2}
.acts .t span{display:block;margin-top:6px;font-size:32px;font-weight:500;color:var(--ink-2);line-height:1.3}
"""

# Shrink the headline until it fits 3 lines (long titles), then the sub clamps to 2.
FIT_JS = """
<script>
const h=document.querySelector('h1,h2');
if(h){const lh=1.2,max=h.tagName==='H1'?3:2;let s=parseFloat(getComputedStyle(h).fontSize);
 const floor=h.tagName==='H1'?64:56;
 while(h.getBoundingClientRect().height>s*lh*max+2&&s>floor){s-=2;h.style.fontSize=s+'px';}}
</script>
"""

e = html.escape


def _bg(post, inner=False):
    if post.get("photo"):
        cls = "photo blur" if inner else "photo"
        return (f"<div class='{cls}' style=\"background-image:url('{e(post['photo'])}');"
                f"background-position:{e(post.get('focus', '50% 30%'))}\"></div>")
    return "<div class='brand-bg'></div>"


def _head(post, i, n):
    page = f"<span class='page'>{i} / {n}</span>" if n > 1 else ""
    return f"<header class='head'><span>{e(post['handle'])}</span>{page}</header>"


def _headline(post):
    text = e(post["headline"])
    hl = post.get("highlight")
    if hl and e(hl) in text:
        text = text.replace(e(hl), f"<em>{e(hl)}</em>", 1)
    return text


def _doc(css, body):
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><style>{TOKENS}{FONTS}{BASE}{css}</style>"
            f"</head><body>{body}{FIT_JS}</body></html>")


def build(post):
    cuts = ["cover"] + [k for k in ("info", "points") if post.get(k)]
    n = len(cuts) + 1                      # + common outro cut
    pages = []
    for i, kind in enumerate(cuts, 1):
        last = i == len(cuts)              # last content cut carries the source line
        if kind == "cover":
            sub = f"<p class='sub'>{e(post['sub'])}</p>" if post.get("sub") else ""
            credit = f"<span class='credit'>{e(post['credit'])}</span>" if post.get("credit") and post.get("photo") else ""
            src = f"<span class='credit'>{e(post['source'])}</span>" if last and post.get("source") and not credit else ""
            body = (f"{_bg(post)}<div class='scrim'></div>{_head(post, i, n)}"
                    f"<main class='body'><h1>{_headline(post)}</h1>{sub}"
                    f"<div class='meta'><span class='pill'>{e(post['category'])}</span>"
                    f"<span>{e(post['date'])}</span>{credit}{src}</div></main>")
            pages.append(_doc(COVER, body))
            continue
        if kind == "info":
            d = post["info"]
            content = "<dl class='rows'>" + "".join(
                f"<div class='row'><dt>{e(k)}</dt><dd>{e(v)}</dd></div>" for k, v in d["rows"]) + "</dl>"
        else:
            d = post["points"]
            content = "<ul class='items'>" + "".join(f"<li>{e(t)}</li>" for t in d["items"]) + "</ul>"
        foot_l = e(post["source"]) if last and post.get("source") else ""
        body = (f"{_bg(post, inner=True)}<div class='veil'></div>{_head(post, i, n)}"
                f"<main class='body'><h2>{e(d['title'])}</h2>{content}</main>"
                f"<footer class='foot'><span>{foot_l}</span></footer>")
        pages.append(_doc(INNER, body))
    pages.append(_doc(OUTRO, _outro(post, n)))
    return pages


def _outro(post, n):
    acts = "".join(
        f"<li><span class='ic'><svg viewBox='0 0 24 24'>{ICONS[k]}</svg></span>"
        f"<div class='t'><b>{e(title)}</b><span>{e(desc)}</span></div></li>"
        for k, title, desc in OUTRO_TEXT["actions"])
    return (f"<div class='brand-bg'></div><div class='glow'></div>{_head(post, n, n)}"
            f"<main class='body'><img class='avatar' src='{PROFILE.as_uri()}' alt=''>"
            f"<p class='name'>{e(post['handle'])}</p><p class='tag'>{e(OUTRO_TEXT['tagline'])}</p>"
            f"<ul class='acts'>{acts}</ul></main>")


def render(post, out_dir, name, page=None):
    """Render all cuts to JPEG (Instagram API accepts JPEG). Returns file paths."""
    from playwright.sync_api import sync_playwright
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    own = page is None
    if own:
        pw = sync_playwright().start(); br = pw.chromium.launch()
        page = br.new_page(viewport={"width": 1080, "height": 1350})
    for i, doc in enumerate(build(post), 1):
        h = out_dir / f"{name}_{i}.html"; h.write_text(doc, encoding="utf-8")
        page.goto(h.resolve().as_uri()); page.evaluate("document.fonts.ready")
        page.wait_for_timeout(150)
        f = out_dir / f"{name}_{i}.jpg"
        page.screenshot(path=str(f), type="jpeg", quality=92)
        files.append(f)
    if own:
        br.close(); pw.stop()
    return files
