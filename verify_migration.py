#!/usr/bin/env python3
"""
Скрипт полной проверки миграции MagikBook.
Проверяет БД, файлы, эндпоинты, Docker-контейнеры.
Запускать изнутри контейнера magikbook-api или с хоста с установленными зависимостями.
"""

import asyncio
import json
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

from sqlalchemy import text, func, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Конфигурация
DB_PATH = Path("/app/magikbook.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"
UPLOADS_DIR = Path("/app/uploads")
BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"


def print_section(title: str):
    print(f"\n{'=' * 60}")
    print(f"{title}")
    print(f"{'=' * 60}")


def print_ok(msg: str):
    print(f"{Colors.GREEN}✅ {msg}{Colors.RESET}")


def print_error(msg: str):
    print(f"{Colors.RED}❌ {msg}{Colors.RESET}")


def print_warn(msg: str):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.RESET}")


async def check_database():
    """Проверка состояния БД."""
    print_section("1. ПРОВЕРКА БАЗЫ ДАННЫХ")

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    issues = []
    warnings = []

    async with async_session() as session:
        # 1.1 Таблицы
        result = await session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        )
        tables = {row[0] for row in result.all()}
        expected = {"users", "prompts", "likes", "saved_prompts", "alembic_version"}
        missing = expected - tables

        if missing:
            print_error(f"Отсутствуют таблицы: {missing}")
            issues.append(f"Missing tables: {missing}")
        else:
            print_ok(f"Все таблицы на месте ({len(expected)})")

        # 1.2 Alembic версия
        try:
            result = await session.execute(text("SELECT version_num FROM alembic_version"))
            version = result.scalar_one()
            if version == "c75ac982ce2a":
                print_ok(f"Alembic версия актуальна: {version}")
            else:
                print_warn(f"Alembic версия: {version} (ожидается c75ac982ce2a)")
                warnings.append(f"Alembic version: {version}")
        except Exception as e:
            print_error(f"Не удалось получить версию Alembic: {e}")
            issues.append("Alembic version check failed")

        # 1.3 Колонки модерации
        result = await session.execute(text("PRAGMA table_info(prompts)"))
        columns = {row[1] for row in result.all()}
        moderation_cols = {
            "moderation_status", "moderated_by", "moderated_at", "ai_model",
            "file_path", "vk_post_url", "telegram_message_url"
        }
        missing_cols = moderation_cols - columns
        if missing_cols:
            print_error(f"Отсутствуют колонки модерации: {missing_cols}")
            issues.append(f"Missing moderation columns: {missing_cols}")
        else:
            print_ok("Все колонки модерации на месте")

        # 1.4 Количество записей
        counts = {}
        for table in ["users", "prompts", "likes", "saved_prompts"]:
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            counts[table] = result.scalar_one()

        print(f"   Записей: prompts={counts['prompts']}, users={counts['users']}, likes={counts['likes']}")

        if counts['prompts'] == 0:
            warnings.append("No prompts in database")

        # 1.5 Moderation status
        result = await session.execute(
            text("SELECT moderation_status, COUNT(*) FROM prompts GROUP BY moderation_status")
        )
        status_counts = {row[0] or "NULL": row[1] for row in result.all()}
        print(f"   Moderation status: {status_counts}")

        if "NULL" in status_counts:
            print_error(f"{status_counts['NULL']} промптов без moderation_status!")
            issues.append(f"{status_counts['NULL']} prompts with NULL moderation_status")

        # 1.6 Orphan likes
        result = await session.execute(
            text("SELECT COUNT(*) FROM likes WHERE prompt_id NOT IN (SELECT id FROM prompts)")
        )
        orphan_likes = result.scalar_one()
        if orphan_likes > 0:
            print_warn(f"{orphan_likes} orphaned likes")
            warnings.append(f"{orphan_likes} orphaned likes")
        else:
            print_ok("Нет orphaned likes")

    await engine.dispose()
    return issues, warnings


async def check_files():
    """Проверка файлов."""
    print_section("2. ПРОВЕРКА ФАЙЛОВ ИЗОБРАЖЕНИЙ")

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    issues = []
    warnings = []

    async with async_session() as session:
        # 2.1 Промпты с file_path
        result = await session.execute(
            text("SELECT file_path FROM prompts WHERE file_path IS NOT NULL AND file_path != ''")
        )
        db_files = {row[0].split("/")[-1] for row in result.all() if row[0]}

        # 2.2 Файлы на диске
        if UPLOADS_DIR.exists():
            disk_files = {f.name for f in UPLOADS_DIR.iterdir() if f.is_file()}
        else:
            print_error(f"Директория {UPLOADS_DIR} не существует!")
            issues.append("Uploads directory missing")
            await engine.dispose()
            return issues, warnings

        print(f"   Файлов в БД: {len(db_files)}")
        print(f"   Файлов на диске: {len(disk_files)}")

        # 2.3 Проверка существования
        missing_on_disk = db_files - disk_files
        orphan_on_disk = disk_files - db_files

        if missing_on_disk:
            print_error(f"{len(missing_on_disk)} файлов из БД отсутствуют на диске")
            issues.append(f"{len(missing_on_disk)} DB files missing on disk")
        else:
            print_ok("Все файлы из БД существуют на диске")

        if orphan_on_disk:
            print_warn(f"{len(orphan_on_disk)} файлов на диске не связаны с БД")
            warnings.append(f"{len(orphan_on_disk)} orphan files on disk")

        # 2.4 Проверка preview_url
        result = await session.execute(
            text("""
                SELECT COUNT(*) FROM prompts
                WHERE media_type IN ('image', 'video')
                  AND (preview_url IS NULL OR preview_url = '')
            """)
        )
        no_preview = result.scalar_one()

        if no_preview > 0:
            print_error(f"{no_preview} медиа-промптов без preview_url!")
            issues.append(f"{no_preview} media prompts without preview_url")
        else:
            print_ok("Все медиа-промпты имеют preview_url")

    await engine.dispose()
    return issues, warnings


def test_endpoint(method: str, path: str, expected_status: int = 200):
    """Тестирование эндпоинта."""
    url = path if path.startswith("http") else f"{BASE_URL}{path}"
    try:
        if method == "GET":
            response = urlopen(url, timeout=10)
            status = response.getcode()
        else:
            req = Request(url, method=method)
            response = urlopen(req, timeout=10)
            status = response.getcode()
        return status == expected_status, status
    except HTTPError as e:
        return e.code == expected_status, e.code
    except URLError as e:
        return False, f"Connection error: {e.reason}"
    except Exception as e:
        return False, str(e)


def check_endpoints():
    """Проверка эндпоинтов."""
    print_section("3. ПРОВЕРКА ЭНДПОИНТОВ")

    tests = [
        ("GET", "/health", 200, "Health check"),
        ("GET", "/api/prompts/homepage", 200, "Homepage API"),
        ("GET", "/api/prompts/feed?page=1&page_size=5", 200, "Feed API"),
        ("GET", "/api/battle/pair", 200, "Battle pair"),
        ("GET", "/api/auth/me", 401, "Auth me (unauthorized)"),
        ("GET", f"{FRONTEND_URL}/api/prompts/homepage", 200, "Frontend proxy (homepage)"),
        ("GET", f"{FRONTEND_URL}/api/feed?page=1", 200, "Frontend proxy (feed)"),
    ]

    issues = []
    passed = 0

    for method, path, expected, name in tests:
        success, status = test_endpoint(method, path, expected)
        if success:
            print_ok(f"{name}: {method} -> {status}")
            passed += 1
        else:
            print_error(f"{name}: {method} -> {status} (expected {expected})")
            issues.append(f"{name} failed")

    print(f"\n   Пройдено: {passed}/{len(tests)}")
    return issues


def main():
    """Главная функция."""
    print("=" * 60)
    print("ПОЛНАЯ ПРОВЕРКА МИГРАЦИИ MAGIKBOOK")
    print("=" * 60)

    all_issues = []
    all_warnings = []

    # 1. Database check
    db_issues, db_warnings = asyncio.run(check_database())
    all_issues.extend(db_issues)
    all_warnings.extend(db_warnings)

    # 2. Files check
    file_issues, file_warnings = asyncio.run(check_files())
    all_issues.extend(file_issues)
    all_warnings.extend(file_warnings)

    # 3. Endpoints check
    endpoint_issues = check_endpoints()
    all_issues.extend(endpoint_issues)

    # Summary
    print_section("ИТОГИ ПРОВЕРКИ")

    if all_issues:
        print_error(f"Найдено проблем: {len(all_issues)}")
        for issue in all_issues:
            print(f"   - {issue}")
    else:
        print_ok("Критических проблем не найдено")

    if all_warnings:
        print_warn(f"Предупреждений: {len(all_warnings)}")
        for warning in all_warnings:
            print(f"   - {warning}")

    print()
    if all_issues:
        print_error("❌ ПРОВЕРКА НЕ ПРОЙДЕНА")
        return 1
    elif all_warnings:
        print_warn("⚠️  ПРОВЕРКА ПРОЙДЕНА С ПРЕДУПРЕЖДЕНИЯМИ")
        return 0
    else:
        print_ok("✅ ПРОВЕРКА ПОЛНОСТЬЮ ПРОЙДЕНА")
        return 0


if __name__ == "__main__":
    sys.exit(main())
