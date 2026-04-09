#!/usr/bin/env sh
# Run from repo root after: pip install -e .  (or venv with alembic)
set -e
cd "$(dirname "$0")/.."
exec alembic upgrade head
