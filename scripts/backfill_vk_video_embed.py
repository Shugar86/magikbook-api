#!/usr/bin/env python3
"""
Догоняет vk_video_owner_id / vk_video_id / vk_video_hash для старых видео-промптов,
у которых есть vk_post_url (пост на стене), но нет полей для iframe.

Использует VK API wall.getById → вложение video → owner_id, id, access_key.

Запуск из корня API (или из /app в Docker):

    cd /opt/projects/magikbook-api
    PYTHONPATH=. python scripts/backfill_vk_video_embed.py

    # только показать, что сделает:
    PYTHONPATH=. python scripts/backfill_vk_video_embed.py --dry-run

    # ограничить число записей:
    PYTHONPATH=. python scripts/backfill_vk_video_embed.py --limit 5

Требуется VK_ACCESS_TOKEN с правами wall, video (как для публикации).
"""

from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Optional

import httpx

# Загрузка .env при запуске из CLI
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from src.config import settings

logger = logging.getLogger(__name__)

VK_API = "https://api.vk.com/method"
VK_V = "5.199"


def _sqlite_path() -> Path:
    url = settings.database_url
    if "sqlite+aiosqlite:///" in url:
        raw = url.split("sqlite+aiosqlite:///")[-1]
    elif "sqlite:///" in url:
        raw = url.split("sqlite:///")[-1]
    else:
        raise SystemExit(f"Ожидался SQLite в database_url, получено: {url!r}")
    p = Path(raw)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent / p
    return p


def parse_wall_post_id(vk_post_url: str) -> Optional[str]:
    """
    Из URL поста вида https://vk.com/wall-123919685_5790 возвращает строку для posts: -123919685_5790.
    """
    if not vk_post_url or not vk_post_url.strip():
        return None
    m = re.search(r"wall(-?\d+)_(\d+)", vk_post_url)
    if not m:
        logger.warning("Не удалось разобрать vk_post_url: %s", vk_post_url[:80])
        return None
    return f"{m.group(1)}_{m.group(2)}"


def fetch_video_from_wall_post(posts_key: str) -> Optional[dict[str, Any]]:
    """Возвращает dict с owner_id, id, access_key или None."""
    if not settings.vk_access_token:
        raise SystemExit("VK_ACCESS_TOKEN не задан в окружении / .env")

    params = {
        "access_token": settings.vk_access_token,
        "v": VK_V,
        "posts": posts_key,
    }
    url = f"{VK_API}/wall.getById"
    with httpx.Client(timeout=30.0) as client:
        r = client.get(url, params=params)
    if r.status_code != 200:
        logger.error("wall.getById HTTP %s: %s", r.status_code, r.text[:300])
        return None
    data = r.json()
    if "error" in data:
        logger.error("wall.getById error: %s", data["error"])
        return None
    raw = data.get("response")
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = raw.get("items") or []
    else:
        items = []
    if not items:
        logger.warning("Пост не найден: %s", posts_key)
        return None
    post = items[0]
    attachments = post.get("attachments") or []
    for att in attachments:
        if att.get("type") == "video":
            v = att.get("video") or {}
            oid = v.get("owner_id")
            vid = v.get("id")
            if oid is None or vid is None:
                continue
            return {
                "owner_id": int(oid),
                "id": int(vid),
                "access_key": v.get("access_key"),
            }
    logger.warning("В посте %s нет вложения video", posts_key)
    return None


def run_backfill(*, dry_run: bool, limit: Optional[int]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    db_path = _sqlite_path()
    if not db_path.is_file():
        raise SystemExit(f"База не найдена: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, vk_post_url
        FROM prompts
        WHERE media_type = 'video'
          AND vk_post_url IS NOT NULL
          AND TRIM(vk_post_url) != ''
          AND (vk_video_owner_id IS NULL OR vk_video_id IS NULL)
        ORDER BY created_at DESC
        """
    )
    rows = cur.fetchall()
    if limit is not None:
        rows = rows[:limit]

    if not rows:
        logger.info("Нечего обновлять: подходящих строк нет.")
        return 0

    updated = 0
    for row in rows:
        pid = row["id"]
        url = row["vk_post_url"]
        posts_key = parse_wall_post_id(url)
        if not posts_key:
            continue

        video = fetch_video_from_wall_post(posts_key)
        if not video:
            continue

        access_key = video.get("access_key")
        hash_val = str(access_key) if access_key else None

        logger.info(
            "prompt %s → video %s_%s hash=%s",
            pid,
            video["owner_id"],
            video["id"],
            "да" if hash_val else "нет",
        )

        if dry_run:
            updated += 1
            continue

        cur.execute(
            """
            UPDATE prompts
            SET vk_video_owner_id = ?, vk_video_id = ?, vk_video_hash = ?
            WHERE id = ?
            """,
            (video["owner_id"], video["id"], hash_val, pid),
        )
        if cur.rowcount:
            updated += 1

    if not dry_run:
        conn.commit()
    conn.close()

    logger.info("Готово: %s записей %s.", updated, "(dry-run)" if dry_run else "обновлено")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Backfill VK video embed fields from vk_post_url")
    p.add_argument("--dry-run", action="store_true", help="Не писать в БД, только лог")
    p.add_argument("--limit", type=int, default=None, help="Максимум строк")
    args = p.parse_args()
    try:
        return run_backfill(dry_run=args.dry_run, limit=args.limit)
    except SystemExit as e:
        if isinstance(e.code, int):
            return e.code
        raise


if __name__ == "__main__":
    sys.exit(main())
