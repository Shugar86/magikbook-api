#!/usr/bin/env python3
"""Скрипт проверки состояния БД после миграции."""

import asyncio
import json
from pathlib import Path
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Путь к БД
DB_PATH = Path(__file__).parent / "magikbook.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"


async def check_database():
    """Проверка состояния БД."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        print("=" * 60)
        print("ПРОВЕРКА СОСТОЯНИЯ БД MAGIKBOOK")
        print("=" * 60)

        # 1. Проверка существования таблиц
        print("\n[1] ТАБЛИЦЫ В БД:")
        result = await session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        )
        tables = [row[0] for row in result.all()]
        print(f"   Найдено таблиц: {len(tables)}")
        for t in tables:
            print(f"   - {t}")

        expected_tables = {"users", "prompts", "likes", "saved_prompts", "alembic_version"}
        missing = expected_tables - set(tables)
        if missing:
            print(f"   ⚠️  ОТСУТСТВУЮТ: {missing}")
        else:
            print(f"   ✅ Все ожидаемые таблицы на месте")

        # 2. Проверка колонок в prompts
        print("\n[2] КОЛОНКИ ТАБЛИЦЫ prompts:")
        result = await session.execute(text("PRAGMA table_info(prompts)"))
        columns = {row[1]: row[2] for row in result.all()}
        moderation_cols = [
            "moderation_status",
            "moderated_by",
            "moderated_at",
            "ai_model",
            "file_path",
            "vk_post_url",
            "telegram_message_url",
        ]
        for col in moderation_cols:
            if col in columns:
                print(f"   ✅ {col}: {columns[col]}")
            else:
                print(f"   ⚠️  {col}: ОТСУТСТВУЕТ")

        # 3. Проверка колонок в users
        print("\n[3] КОЛОНКИ ТАБЛИЦЫ users:")
        result = await session.execute(text("PRAGMA table_info(users)"))
        columns = {row[1]: row[2] for row in result.all()}
        oauth_cols = ["google_id", "vk_id", "auth_provider", "avatar_url"]
        for col in oauth_cols:
            if col in columns:
                print(f"   ✅ {col}: {columns[col]}")
            else:
                print(f"   ⚠️  {col}: ОТСУТСТВУЕТ")

        # 4. Подсчет записей
        print("\n[4] КОЛИЧЕСТВО ЗАПИСЕЙ:")
        counts = {}
        for table in ["users", "prompts", "likes", "saved_prompts"]:
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar_one()
            counts[table] = count
            print(f"   {table}: {count}")

        # 5. Статистика moderation_status
        print("\n[5] СТАТИСТИКА ПО moderation_status:")
        result = await session.execute(
            text("SELECT moderation_status, COUNT(*) FROM prompts GROUP BY moderation_status")
        )
        status_counts = {row[0]: row[1] for row in result.all()}
        if status_counts:
            for status, count in status_counts.items():
                status_str = status if status else "NULL"
                print(f"   {status_str}: {count}")
        else:
            print("   (нет данных)")

        # 6. Промпты с NULL moderation_status
        print("\n[6] ПРОМПТЫ С NULL moderation_status:")
        result = await session.execute(
            text("SELECT COUNT(*) FROM prompts WHERE moderation_status IS NULL")
        )
        null_count = result.scalar_one()
        if null_count > 0:
            print(f"   ⚠️  {null_count} промптов без moderation_status!")
        else:
            print(f"   ✅ Все промпты имеют moderation_status")

        # 7. Промпты с media_type=image/video без preview_url
        print("\n[7] МЕДИА-ПРОМПТЫ БЕЗ preview_url:")
        result = await session.execute(
            text("""
                SELECT COUNT(*)
                FROM prompts
                WHERE media_type IN ('image', 'video')
                  AND (preview_url IS NULL OR preview_url = '')
            """)
        )
        no_preview_count = result.scalar_one()
        if no_preview_count > 0:
            print(f"   ⚠️  {no_preview_count} медиа-промптов без preview_url!")
            # Показать примеры
            result = await session.execute(
                text("""
                    SELECT id, title, media_type, file_path, moderation_status
                    FROM prompts
                    WHERE media_type IN ('image', 'video')
                      AND (preview_url IS NULL OR preview_url = '')
                    LIMIT 5
                """)
            )
            print("   Примеры (первые 5):")
            for row in result.all():
                print(f"     - {row[0][:8]}... | {row[1][:30]:30} | {row[2]} | {row[4]}")
        else:
            print(f"   ✅ Все медиа-промпты имеют preview_url")

        # 8. Промпты с file_path
        print("\n[8] ПРОМПТЫ С file_path:")
        result = await session.execute(
            text("SELECT COUNT(*) FROM prompts WHERE file_path IS NOT NULL AND file_path != ''")
        )
        with_file_path = result.scalar_one()
        print(f"   Всего: {with_file_path}")

        # Показать пути
        result = await session.execute(
            text("""
                SELECT id, file_path, moderation_status
                FROM prompts
                WHERE file_path IS NOT NULL AND file_path != ''
                LIMIT 5
            """)
        )
        print("   Примеры путей:")
        for row in result.all():
            print(f"     - {row[0][:8]}... | {row[1][:50]:50} | {row[2]}")

        # 9. Проверка orphan likes
        print("\n[9] ORPHAN LIKES:")
        result = await session.execute(
            text("""
                SELECT COUNT(*) FROM likes
                WHERE prompt_id NOT IN (SELECT id FROM prompts)
            """)
        )
        orphan_likes = result.scalar_one()
        if orphan_likes > 0:
            print(f"   ⚠️  {orphan_likes} orphaned likes (битые ссылки)")
        else:
            print(f"   ✅ Нет orphaned likes")

        # 10. Проверка alembic версии
        print("\n[10] ALEMBIC VERSION:")
        try:
            result = await session.execute(text("SELECT version_num FROM alembic_version"))
            version = result.scalar_one()
            print(f"   Текущая версия: {version}")
            # Последняя миграция: c75ac982ce2a
            if version == "c75ac982ce2a":
                print(f"   ✅ Это последняя версия (moderation fields)")
            else:
                print(f"   ⚠️  Не последняя версия. Ожидается: c75ac982ce2a")
        except Exception as e:
            print(f"   ⚠️  Ошибка получения версии: {e}")

        print("\n" + "=" * 60)
        print("ПРОВЕРКА ЗАВЕРШЕНА")
        print("=" * 60)

        # Итоговая сводка
        issues = []
        if missing:
            issues.append(f"Отсутствуют таблицы: {missing}")
        if null_count > 0:
            issues.append(f"{null_count} промптов без moderation_status")
        if no_preview_count > 0:
            issues.append(f"{no_preview_count} медиа без preview_url")
        if orphan_likes > 0:
            issues.append(f"{orphan_likes} orphaned likes")

        if issues:
            print("\n⚠️  НАЙДЕНЫ ПРОБЛЕМЫ:")
            for issue in issues:
                print(f"   - {issue}")
        else:
            print("\n✅ КРИТИЧЕСКИХ ПРОБЛЕМ НЕ НАЙДЕНО")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_database())
