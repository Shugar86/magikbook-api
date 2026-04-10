#!/usr/bin/env bash
# Ежедневный снимок SQLite (bind-mount в Docker). Хранить вне git.
set -euo pipefail
SRC="${MAGIKBOOK_DB:-/opt/projects/magikbook-api/magikbook.db}"
DST="${MAGIKBOOK_DB_BACKUP_DIR:-/opt/projects/magikbook-api/data/backups/magikbook}"
RETAIN_DAYS="${MAGIKBOOK_DB_BACKUP_RETAIN_DAYS:-14}"

mkdir -p "$DST"
if [[ ! -f "$SRC" ]]; then
  echo "ERROR: database file not found: $SRC" >&2
  exit 1
fi
cp -a "$SRC" "$DST/magikbook_$(date -u +%Y%m%d_%H%M%S).db"
find "$DST" -maxdepth 1 -name 'magikbook_*.db' -mtime "+${RETAIN_DAYS}" -delete 2>/dev/null || true
echo "OK: backup -> $DST"
