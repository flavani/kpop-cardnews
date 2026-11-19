"""Semi-auto review via GitHub Issues.

  python review.py open     -> open one issue per pending_review post (with previews)
  python review.py handle   -> act on an issue comment ("발행" / "보류")
"""
import json
import os
import shutil
import sys

import requests

from common import QUEUE, REJECTED, load_json, queue_posts, raw_url, repo_slug, save_json

API = "https://api.github.com"
APPROVE = ("발행", "승인", "ok", "ㅇㅋ", "go")
REJECT = ("보류", "거절", "삭제", "no", "skip")


def gh(method, path, **kw):
    r = requests.request(method, f"{API}/repos/{repo_slug()}{path}", timeout=30, headers={
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json"}, **kw)
    r.raise_for_status()
    return r.json() if r.content else {}


def issue_body(d, post):
    imgs = "\n".join(f"<img src=\"{raw_url(f'queue/{d.name}/{i}.jpg')}\" width=\"360\">"
                     for i in range(1, post["rendered"] + 1))
    srcs = "\n".join(f"- {u}" for u in post.get("sources", []))
    note = "" if post.get("photo_used") or not post.get("photo") else "\n> ⚠️ 사진을 불러오지 못해 기본 배경으로 만들었어요.\n"
    sens = "\n> ⚠️ 민감한 소식이라 공식 입장 중심으로 작성했어요. 표현을 한 번 더 확인해 주세요.\n" \
        if post.get("sensitivity") == "official_statement" else ""
    return f"""{imgs}
{note}{sens}
**캡션**
```
{post.get('caption', '')}
```
**사진:** {post.get('photo') or '없음 (기본 배경)'}

**확인한 출처**
{srcs}

---
이 댓글창에 **`발행`** 이라고 쓰면 발행 대기열에 올라가고, **`보류`** 라고 쓰면 버려요.
"""


def open_issues():
    opened = 0
    for d, post in queue_posts():
        if post.get("status") != "pending_review" or post.get("issue"):
            continue
        title = f"[검수] {post.get('category', '')} · {post.get('headline', d.name)}"
        issue = gh("POST", "/issues", json={"title": title[:250], "body": issue_body(d, post),
                                            "labels": ["검수대기"]})
        post["issue"] = issue["number"]
        save_json(d / "post.json", post)
        opened += 1
    print(f"opened {opened} review issues")


def handle_comment():
    event = load_json(os.environ["GITHUB_EVENT_PATH"])
    if event["comment"].get("author_association") not in ("OWNER", "MEMBER", "COLLABORATOR"):
        print("comment not from a maintainer; ignored")
        return
    words = event["comment"]["body"].strip().lower()
    number = event["issue"]["number"]
    target = next(((d, p) for d, p in queue_posts() if p.get("issue") == number), None)
    if not target:
        print(f"no queued post for issue #{number}")
        return
    d, post = target
    if words.startswith(APPROVE):
        post.update(status="approved", approved=True)
        save_json(d / "post.json", post)
        msg, reason = "발행 대기열에 올렸어요. 20분 안팎으로 순서대로 발행돼요.", "completed"
    elif words.startswith(REJECT):
        post["status"] = "rejected"
        save_json(d / "post.json", post)
        REJECTED.mkdir(exist_ok=True)
        shutil.move(str(d), str(REJECTED / d.name))
        msg, reason = "보류했어요. 이 게시물은 발행되지 않아요.", "not_planned"
    else:
        print("comment is neither approve nor reject; ignored")
        return
    gh("POST", f"/issues/{number}/comments", json={"body": msg})
    gh("PATCH", f"/issues/{number}", json={"state": "closed", "state_reason": reason, "labels": []})
    print(msg)


if __name__ == "__main__":
    {"open": open_issues, "handle": handle_comment}[sys.argv[1]]()
