# K-pop 카드뉴스 자동 발행

K-pop 소식을 모아 1~3컷 카드뉴스로 만들고 인스타그램에 올리는 자동화예요.
Claude 구독 외에 다른 유료 서비스는 쓰지 않아요(GitHub 공개 저장소와 Instagram API는 무료).

## 어떻게 돌아가나요

| 순서 | 누가 | 언제 | 하는 일 |
|---|---|---|---|
| 1. 수집 | GitHub Actions | 15분마다 | 매체 RSS·소속사 공식 YouTube에서 새 소식 후보를 `data/candidates.json`에 쌓아요 |
| 2. 편집 | Claude 예약 작업 | 1시간마다 | 후보를 골라 사실을 확인하고, 문구를 직접 써서 `queue/`에 게시물을 만들어요 |
| 3. 렌더링 | GitHub Actions | 게시물이 생기면 바로 | 카드 이미지(1080×1350 JPEG)를 만들어요 |
| 4. 검수 | **나** | 원할 때 | 검수 모드에서는 게시물마다 이슈가 열려요. 미리보기를 보고 댓글로 결정해요 |
| 5. 발행 | GitHub Actions | 20분마다 1건 | 승인된 게시물을 순서대로 인스타그램에 올려요 |

## 검수하는 방법 (반자동 모드)

1. GitHub 앱이나 웹에서 저장소의 **Issues** 탭을 열어요. `[검수]`로 시작하는 이슈가 게시물 하나예요.
2. 카드 미리보기, 캡션, 확인한 출처를 보고 댓글을 달아요.
   - **`발행`** → 발행 대기열에 올라가요 (20분 안팎으로 순서대로 발행)
   - **`보류`** → 버려요
3. 이슈는 자동으로 닫혀요.

> 💡 GitHub 모바일 앱에서 알림을 켜 두면 새 검수 이슈가 올 때마다 알림이 와요.

## 완전 자동으로 바꾸기

`config/settings.json`에서 `"mode": "review"`를 `"mode": "auto"`로 바꾸면 검수 없이 바로 발행 대기열에 올라가요.

## 설정 파일

- `config/settings.json`
  - `handle`: 카드 왼쪽 위에 들어가는 계정명
  - `max_posts_per_run`: Claude가 한 번에 만드는 최대 게시물 수
  - `ai_label`: 인스타그램 'AI 정보' 라벨 표시 여부
- `config/sources.json`: 수집 소스 목록. 소스별 상태는 `data/source_status.json`에서 볼 수 있어요.
- `.claude/skills/kpop-cardnews/SKILL.md`: Claude 편집 기준(무엇을 다루고, 어떻게 쓰는지).

## 필요한 Secrets (Settings → Secrets and variables → Actions)

| 이름 | 필수 | 설명 |
|---|---|---|
| `IG_ACCESS_TOKEN` | ✅ | 인스타그램 장기 액세스 토큰 (60일 유효) |
| `IG_USER_ID` | 선택 | 인스타그램 계정 ID. 없으면 자동으로 찾아요 |
| `GH_PAT` | 선택 | 토큰 자동 갱신용. 없으면 갱신 시점에 알림 이슈가 열려요 |

토큰이 없으면 발행 단계는 아무것도 올리지 않고 "dry-run" 기록만 남겨요.

## 문제가 생기면

- **Actions** 탭에서 빨간 ❌ 표시가 있는 실행을 눌러 보면 이유가 나와요.
- 발행이 3번 실패한 게시물은 `failed/` 폴더로 옮겨져요. `post.json`의 `last_error`에 이유가 있어요.
