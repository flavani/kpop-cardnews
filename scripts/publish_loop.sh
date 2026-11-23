#!/usr/bin/env bash
# Publish this batch: up to 4 posts, one per hour (publish.py enforces the gap, pause, block
# cooldown and duplicate checks). Unlike the old inline loop it
#   - waits up to 12 min for the render workflow when nothing is ready yet (edit push starts
#     render and this pipeline at the same moment),
#   - keeps going after an ordinary failure (e.g. Instagram media-download timeout): the next
#     hour tries again; publish.py moves a card to failed/ after its max attempts,
#   - stops only on pause / action block / quota / dry-run / an empty queue after posting,
#   - stops starting new attempts after ~3h20m so the job (230 min) and the reel step fit,
#   - logs every attempt to data/publish_runs.jsonl so a short run can be explained later.
set -u
START=$(date +%s)
DEADLINE=$((START + 200 * 60))
posted=0
render_wait=0
attempt=0

log() {  # log <outcome> <last line>
  python3 - "$1" "$2" "$attempt" "$posted" <<'PY'
import json, sys, os, datetime
outcome, line, attempt, posted = sys.argv[1:5]
row = {"at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
       "run": os.environ.get("GITHUB_RUN_ID"), "attempt": int(attempt), "posted": int(posted),
       "outcome": outcome, "msg": line[:300]}
os.makedirs("data", exist_ok=True)
with open("data/publish_runs.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps(row, ensure_ascii=False) + "\n")
PY
}

while :; do
  attempt=$((attempt + 1))
  git pull -q --rebase origin main
  out=$(python scripts/publish.py 2>&1); rc=$?
  echo "$out"
  last=$(echo "$out" | grep -v '^\s*$' | tail -1)

  if echo "$out" | grep -qE "^published |already on Instagram|actually posted"; then
    outcome=posted; posted=$((posted + 1))
  elif echo "$out" | grep -q "no approved post waiting"; then
    outcome=empty
  elif echo "$out" | grep -qE "publishing paused|publishing blocked|limit reached|dry-run|action block"; then
    outcome=stop
  elif echo "$out" | grep -q "interval limit"; then
    outcome=gap
  elif [ $rc -ne 0 ]; then
    outcome=error
  else
    outcome=other
  fi
  log "$outcome" "$last"
  bash scripts/commit_push.sh "발행: 인스타그램 게시"
  echo "[loop] attempt $attempt: $outcome (posted $posted)"

  case $outcome in
    stop) break ;;
    empty)
      if [ $posted -eq 0 ] && [ $render_wait -lt 12 ]; then   # cards may still be rendering
        render_wait=$((render_wait + 1)); sleep 60; continue
      fi
      break ;;
    gap) pause=300 ;;                                           # re-check every 5 min
    *) pause=3600 ;;                                            # posted / error / other
  esac
  [ $posted -ge 4 ] && break
  [ $(( $(date +%s) + pause )) -gt $DEADLINE ] && { echo "[loop] out of time"; break; }
  sleep $pause
done
echo "[loop] done: $posted posted"
exit 0
