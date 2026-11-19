# kpop-cardnews

K-pop 소식을 인스타그램 카드뉴스로 자동 발행하는 저장소.

- 매시간 예약 작업에서 Claude가 할 일은 `.claude/skills/kpop-cardnews/SKILL.md`에 있다. "카드뉴스 작업 실행"이라는 요청을 받으면 그 스킬을 그대로 따른다.
- Claude가 쓰는 파일: 새 `queue/<id>/post.json`, `data/ledger.json` 뿐. 나머지(scripts, workflows, config, templates, 기존 queue/posted)는 사람이 요청할 때만 수정한다.
- 수집(collect)·렌더링(render)·검수(review)·발행(publish)은 GitHub Actions가 한다.
