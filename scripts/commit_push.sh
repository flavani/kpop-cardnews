#!/usr/bin/env bash
# Commit any changes and push to main, rebasing on top of concurrent pushes.
set -euo pipefail
msg="$1"
git config user.name "cardnews-bot"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -A
if git diff --cached --quiet; then
  echo "no changes"; exit 0
fi
git commit -q -m "$msg"
for i in 1 2 3 4 5; do
  if git pull -q --rebase origin main && git push -q origin HEAD:main; then
    echo "pushed"; exit 0
  fi
  sleep $((i * 5))
done
echo "push failed" >&2; exit 1
