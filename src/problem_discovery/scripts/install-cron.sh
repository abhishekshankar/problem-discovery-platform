#!/usr/bin/env bash
# Idempotent: replace block between markers in user crontab with scripts/crontab.txt body.
set -euo pipefail
MARK_BEGIN="# BEGIN gstack-signal-cron"
MARK_END="# END gstack-signal-cron"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE="$ROOT/scripts/crontab.txt"
if [[ ! -f "$TEMPLATE" ]]; then
  echo "Missing $TEMPLATE" >&2
  exit 1
fi
read -r -p "PYTHONPATH parent directory (directory containing problem_discovery package) [$ROOT/..]: " PARENT_IN
PARENT="${PARENT_IN:-"$ROOT/.."}"
PARENT="$(cd "$PARENT" && pwd)"
TMP="$(mktemp)"
(crontab -l 2>/dev/null | sed "/^${MARK_BEGIN//\//\\/}\$/,/^${MARK_END//\//\\/}\$/d" || true) >"$TMP"
{
  echo "$MARK_BEGIN"
  echo "# Installed $(date -Iseconds) from $TEMPLATE"
  sed "s|REPO_PARENT|$PARENT|g" "$TEMPLATE"
  echo "$MARK_END"
} >>"$TMP"
crontab "$TMP"
rm -f "$TMP"
echo "Crontab updated. Verify with: crontab -l"
