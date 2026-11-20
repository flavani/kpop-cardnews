"""Night Gradient roundup reel (1080x1920, 9:16).

One video that strings several posts together, the most eye-catching one first:
  story 1..N  photo slow push-in, "K-POP ROUNDUP 01/04" tag, pill + date,
              headline lines rise in, sub, credit           (STORY s each)
  outro       avatar, handle, follow / comment / save        (OUTRO s)
Frames are captured deterministically: every CSS animation is paused and
seeked (document.getAnimations()), then ffmpeg encodes H.264 + silent AAC.
Music is attached by Instagram itself at publish time (Audio API), not baked in.

Text stays inside Instagram's Reels safe area (top ~220 px, bottom ~380 px and
the right-hand button column are covered by the app UI).
"""
import html
import subprocess
import tempfile
from pathlib import Path

import night_gradient as ng

e = html.escape
W, H, FPS = 1080, 1920, 30
STORY, OUTRO, FADE = 4.6, 3.2, 0.4

CSS = """
:root{--pad-x:80px;--accent:#ff2e88;--accent-text:#ff7ab3;--ink:#fff;
  --ink-2:rgba(255,236,245,.88);--ink-3:rgba(255,228,240,.70);--rule:rgba(255,220,236,.18);--night:#0d0a1a}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1920px}
body{position:relative;overflow:hidden;background:var(--night);color:var(--ink);
  font-family:'Pretendard',sans-serif;word-break:keep-all;-webkit-font-smoothing:antialiased}
.scene{position:absolute;inset:0;overflow:hidden;background:var(--night)}
.fadein{opacity:0;animation:fadein %(fade)ss ease-out both}
@keyframes fadein{from{opacity:0}to{opacity:1}}
@keyframes rise{from{opacity:0;transform:translateY(46px)}to{opacity:1;transform:none}}
@keyframes pop{0%%{opacity:0;transform:scale(.6)}70%%{opacity:1;transform:scale(1.06)}100%%{opacity:1;transform:scale(1)}}
@keyframes push{from{transform:scale(1.0)}to{transform:scale(1.12)}}
@keyframes bar{from{transform:scaleX(0)}to{transform:scaleX(1)}}
.a{opacity:0;animation:rise .65s cubic-bezier(.2,.8,.2,1) both}

.top{position:absolute;top:230px;left:var(--pad-x);right:var(--pad-x);
  display:flex;justify-content:space-between;align-items:center;font-size:30px;font-weight:700;letter-spacing:.04em}
.top .num{color:var(--ink-2);font-weight:600;letter-spacing:.02em}
.top .num b{color:var(--accent-text)}
.prog{position:absolute;top:286px;left:var(--pad-x);right:var(--pad-x);display:flex;gap:10px}
.prog i{flex:1;height:6px;border-radius:3px;background:rgba(255,255,255,.22);overflow:hidden}
.prog i.done{background:#fff}
.prog i.now::after{content:'';display:block;height:100%%;background:#fff;transform-origin:left;
  animation:bar linear both;animation-duration:inherit;animation-delay:inherit}

.bgblur{position:absolute;inset:-100px;background-size:cover;background-position:center;
  filter:blur(60px) saturate(1.2) brightness(.7)}
.hero{position:absolute;left:0;right:0;top:0;height:1080px;background-size:cover;
  transform-origin:50%% 40%%;animation:push linear both;
  -webkit-mask-image:linear-gradient(180deg,#000 62%%,transparent 100%%)}
.scrim{position:absolute;inset:0;background:
  linear-gradient(180deg,rgba(8,6,16,.62) 0,rgba(8,6,16,0) 420px),
  linear-gradient(180deg,rgba(8,6,16,0) 30%%,rgba(8,6,16,.55) 42%%,rgba(8,6,16,.88) 54%%,rgba(8,6,16,.96) 70%%,rgba(8,6,16,.98) 100%%)}
.brand-bg{position:absolute;inset:0;background:
  radial-gradient(70%% 45%% at 25%% 22%%,#5b2a6e 0%%,transparent 70%%),
  radial-gradient(60%% 40%% at 85%% 55%%,#24306e 0%%,transparent 70%%),
  linear-gradient(170deg,#1c1336,#0d0a1a)}
.cover{position:absolute;left:var(--pad-x);right:140px;bottom:400px}
.tags{display:flex;align-items:center;gap:24px;font-size:30px;font-weight:500;color:var(--ink-3);margin-bottom:36px}
.pill{display:inline-flex;align-items:center;height:56px;padding:0 24px;border-radius:28px;
  background:var(--accent);color:#fff;font-size:28px;font-weight:800;letter-spacing:.06em}
h1{font-size:86px;font-weight:900;line-height:1.16;letter-spacing:-.03em}
h1 .ln{display:block}
h1 em{font-style:normal;color:var(--accent-text)}
.sub{margin-top:32px;font-size:40px;font-weight:500;line-height:1.42;color:var(--ink-2)}
.credit{margin-top:40px;font-size:26px;font-weight:500;color:var(--ink-3)}

.glow{position:absolute;left:50%%;top:640px;width:1000px;height:1000px;transform:translate(-50%%,-50%%);
  background:radial-gradient(closest-side,rgba(255,46,136,.32),rgba(255,46,136,0))}
.outro{position:absolute;left:var(--pad-x);right:var(--pad-x);top:330px;bottom:400px;
  display:flex;flex-direction:column;align-items:center;justify-content:center}
.avatar{width:360px;height:360px;border-radius:50%%;opacity:0;
  box-shadow:0 0 0 9px var(--accent),0 24px 60px rgba(0,0,0,.45);animation:pop .7s ease-out both}
.name{margin-top:52px;font-size:72px;font-weight:900;letter-spacing:-.03em}
.tag{margin-top:14px;font-size:36px;font-weight:500;color:var(--ink-2)}
.acts{list-style:none;width:100%%;margin-top:60px;border-top:2px solid var(--rule)}
.acts li{display:flex;align-items:center;gap:36px;padding:34px 8px;border-bottom:2px solid var(--rule)}
.ic{flex:none;width:92px;height:92px;border-radius:50%%;background:var(--accent);
  display:flex;align-items:center;justify-content:center}
.ic svg{width:46px;height:46px;fill:none;stroke:#fff;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
.acts b{display:block;font-size:48px;font-weight:800;letter-spacing:-.02em;line-height:1.2}
.acts .t span{display:block;margin-top:6px;font-size:33px;font-weight:500;color:var(--ink-2)}
""" % {"fade": FADE}


def _d(t):
    return f"style='animation-delay:{t:.2f}s'"


def _lines(post, width=18):
    """Greedy word wrap for the 86px headline (~18 chars per line); highlight wrapped in <em>."""
    lines, cur = [], ""
    for w in post["headline"].split():
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur); cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    hl, out = post.get("highlight"), []
    for ln in lines:
        t = e(ln)
        if hl and e(hl) in t:
            t = t.replace(e(hl), f"<em>{e(hl)}</em>", 1); hl = None
        out.append(t)
    return out


def _story(post, i, n, t0):
    photo = post.get("photo")
    bg = f"background-image:url('{e(photo)}')" if photo else ""
    focus = e(post.get("focus", "50% 40%"))
    cls = "scene" + (" fadein" if i else "")
    prog = "".join(
        "<i class='done'></i>" if k < i else
        (f"<i class='now' style='animation-duration:{STORY:.2f}s;animation-delay:{t0:.2f}s'></i>" if k == i else "<i></i>")
        for k in range(n))
    lead = 0.1 if i == 0 else 0.35          # the first second decides whether people keep watching
    t = t0 + lead
    h1 = ""
    for ln in _lines(post):
        h1 += f"<span class='ln a' {_d(t)}>{ln}</span>"; t += 0.15
    sub = f"<p class='sub a' {_d(t + 0.1)}>{e(post['sub'])}</p>" if post.get("sub") else ""
    credit = f"<p class='credit a' {_d(t + 0.35)}>{e(post['credit'])}</p>" if post.get("credit") and photo else ""
    visual = (f"<div class='bgblur' style=\"{bg}\"></div><div class='hero' style=\"{bg};background-position:{focus};"
              f"animation-duration:{STORY + FADE:.2f}s;animation-delay:{t0:.2f}s\"></div>") if photo \
        else "<div class='brand-bg'></div>"
    return (f"<section class='{cls}' {_d(t0)}>{visual}<div class='scrim'></div>"
            f"<header class='top'><span>K-POP ROUNDUP</span><span class='num'><b>{i + 1:02d}</b> / {n:02d}</span></header>"
            f"<div class='prog'>{prog}</div>"
            f"<main class='cover'><div class='tags a' {_d(t0 + lead - 0.1)}><span class='pill'>{e(post['category'])}</span>"
            f"<span>{e(post.get('date', ''))}</span></div><h1>{h1}</h1>{sub}{credit}</main></section>")


def _outro(handle, t0):
    acts = ""
    for i, (k, ttl, desc) in enumerate(ng.OUTRO_TEXT["actions"]):
        acts += (f"<li class='a' {_d(t0 + 1.1 + i * 0.22)}><span class='ic'><svg viewBox='0 0 24 24'>{ng.ICONS[k]}</svg></span>"
                 f"<div class='t'><b>{e(ttl)}</b><span>{e(desc)}</span></div></li>")
    return (f"<section class='scene fadein' {_d(t0)}><div class='brand-bg'></div><div class='glow'></div>"
            f"<main class='outro'><img class='avatar' {_d(t0 + 0.25)} src='{ng.PROFILE.as_uri()}' alt=''>"
            f"<p class='name a' {_d(t0 + 0.6)}>{e(handle)}</p>"
            f"<p class='tag a' {_d(t0 + 0.75)}>{e(ng.OUTRO_TEXT['tagline'])}</p>"
            f"<ul class='acts'>{acts}</ul></main></section>")


def build(posts, handle):
    """posts: already ordered (lead story first); each needs headline, category, date, optional photo (URL)."""
    n = len(posts)
    scenes = "".join(_story(p, i, n, i * STORY) for i, p in enumerate(posts))
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><style>{ng.FONTS}{CSS}</style>"
            f"</head><body>{scenes}{_outro(handle, n * STORY)}</body></html>")


def duration(n):
    return n * STORY + OUTRO


def render(posts, handle, out_path, fps=FPS):
    """Render to H.264 MP4 with a silent AAC track. Returns the path."""
    from playwright.sync_api import sync_playwright
    out_path = Path(out_path)
    dur = duration(len(posts))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        page_file = tmp / "reel.html"
        page_file.write_text(build(posts, handle), encoding="utf-8")
        with sync_playwright() as pw:
            br = pw.chromium.launch()
            page = br.new_page(viewport={"width": W, "height": H})
            page.goto(page_file.resolve().as_uri())
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(400)
            page.evaluate("document.getAnimations().forEach(a=>a.pause())")
            for i in range(int(dur * fps)):
                page.evaluate(f"document.getAnimations().forEach(a=>a.currentTime={i * 1000 / fps})")
                page.screenshot(path=str(tmp / f"f{i:04d}.jpg"), type="jpeg", quality=95)
            br.close()
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(tmp / "f%04d.jpg"),
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-vf", f"fade=t=out:st={dur - 0.4:.2f}:d=0.4",
            "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out_path)],
            check=True)
    return out_path
