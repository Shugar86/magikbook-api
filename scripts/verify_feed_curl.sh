#!/usr/bin/env bash
# Ручной/CI смоук: проверка фида и фильтров категории.
# Использование:
#   export BASE_URL=http://127.0.0.1:8000   # или BACKEND_URL
#   ./scripts/verify_feed_curl.sh
# Опционально фронт Next:
#   export FRONTEND_URL=http://127.0.0.1:3000
set -euo pipefail

BASE_URL="${BASE_URL:-${BACKEND_URL:-http://127.0.0.1:8000}}"
FRONTEND_URL="${FRONTEND_URL:-}"

die() {
  echo "FAIL: $*" >&2
  exit 1
}

check_http() {
  local name="$1"
  local url="$2"
  local code
  code="$(curl -sS -o /tmp/mb_feed_body.json -w '%{http_code}' "$url")"
  if [[ "$code" != "200" ]]; then
    die "$name -> HTTP $code ($url)"
  fi
  echo "OK $name (HTTP $code)"
}

echo "BASE_URL=$BASE_URL"

check_http "feed basic" "${BASE_URL}/api/prompts/feed?page=1&page_size=5"
python3 - <<'PY' || die "feed JSON invalid"
import json, sys
with open("/tmp/mb_feed_body.json", encoding="utf-8") as f:
    d = json.load(f)
for k in ("prompts", "total_count", "page", "has_more"):
    assert k in d, k
sys.exit(0)
PY

check_http "feed category+image" "${BASE_URL}/api/prompts/feed?category=anime&media_type=image&page_size=5"

check_http "feed slug 3d" "${BASE_URL}/api/prompts/feed?category=3d&media_type=image&page_size=5"

if [[ -n "$FRONTEND_URL" ]]; then
  check_http "Next proxy feed" "${FRONTEND_URL}/api/feed?category=anime&media_type=image&page_size=5"
else
  echo "SKIP Next proxy (set FRONTEND_URL to test)"
fi

echo "All curl checks passed."
