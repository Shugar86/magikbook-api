#!/usr/bin/env python3
"""Проверка соответствия file_path в БД и реальных файлов на диске."""

import asyncio
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DB_PATH = Path("/app/magikbook.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"
UPLOADS_DIR = Path("/app/uploads")


async def check_files():
    """Проверка файлов."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        print("=" * 60)
        print("ПРОВЕРКА ФАЙЛОВ ИЗОБРАЖЕНИЙ")
        print("=" * 60)

        # 1. Получить все промпты с file_path
        print("\n[1] ПРОВЕРКА file_path В БД:")
        result = await session.execute(
            text("""
                SELECT id, title, file_path, preview_url, media_type, moderation_status
                FROM prompts
                WHERE file_path IS NOT NULL AND file_path != ''
            """)
        )
        prompts_with_files = result.all()
        print(f"   Промптов с file_path: {len(prompts_with_files)}")

        # 2. Проверить существование файлов
        print("\n[2] ПРОВЕРКА СУЩЕСТВОВАНИЯ ФАЙЛОВ:")
        missing_files = []
        existing_files = []

        for row in prompts_with_files:
            prompt_id, title, file_path, preview_url, media_type, status = row
            # file_path может быть относительным (uploads/xxx.png)
            file_full_path = UPLOADS_DIR.parent / file_path if not file_path.startswith('/') else Path(file_path)
            # Если путь начинается с uploads/, ищем относительно /app
            if file_path.startswith("uploads/"):
                file_full_path = UPLOADS_DIR.parent / file_path

            exists = file_full_path.exists()
            if exists:
                existing_files.append((prompt_id, file_path, file_full_path))
            else:
                missing_files.append((prompt_id, title, file_path, file_full_path))

        print(f"   Существуют: {len(existing_files)}")
        print(f"   Отсутствуют: {len(missing_files)}")

        if missing_files:
            print("\n   ⚠️  ОТСУТСТВУЮЩИЕ ФАЙЛЫ:")
            for prompt_id, title, file_path, full_path in missing_files[:10]:
                print(f"      - {prompt_id[:8]} | {title[:25]:25} | {file_path}")
            if len(missing_files) > 10:
                print(f"      ... и еще {len(missing_files) - 10}")

        # 3. Проверить файлы в uploads/ без записей в БД
        print("\n[3] ОРФАННЫЕ ФАЙЛЫ (нет в БД):")
        if UPLOADS_DIR.exists():
            db_files = {row[2].split("/")[-1] for row in prompts_with_files}  # имена файлов из БД
            disk_files = {f.name for f in UPLOADS_DIR.iterdir() if f.is_file()}
            orphan_files = disk_files - db_files

            print(f"   Файлов на диске: {len(disk_files)}")
            print(f"   Файлов в БД: {len(db_files)}")
            print(f"   Орфанных файлов: {len(orphan_files)}")

            if orphan_files:
                print("\n   Файлы без записей в БД (первые 10):")
                for f in list(orphan_files)[:10]:
                    print(f"      - {f}")
        else:
            print(f"   ⚠️  Директория {UPLOADS_DIR} не существует!")

        # 4. Проверка preview_url
        print("\n[4] ПРОВЕРКА preview_url:")
        result = await session.execute(
            text("""
                SELECT id, title, preview_url, media_type
                FROM prompts
                WHERE media_type IN ('image', 'video')
            """)
        )
        media_prompts = result.all()

        no_preview = [r for r in media_prompts if not r[2]]
        with_preview = [r for r in media_prompts if r[2]]

        print(f"   Медиа-промптов: {len(media_prompts)}")
        print(f"   С preview_url: {len(with_preview)}")
        print(f"   Без preview_url: {len(no_preview)}")

        if with_preview:
            # Анализ типов URL
            urls = [r[2] for r in with_preview]
            http_urls = [u for u in urls if u.startswith("http")]
            local_urls = [u for u in urls if u.startswith("/uploads") or u.startswith("uploads")]
            other_urls = [u for u in urls if u not in http_urls and u not in local_urls]

            print(f"\n   Типы preview_url:")
            print(f"      HTTP (VK/Telegram/внешние): {len(http_urls)}")
            print(f"      Локальные (/uploads): {len(local_urls)}")
            print(f"      Другие: {len(other_urls)}")

            if other_urls[:5]:
                print(f"\n   Примеры 'других' URL:")
                for u in other_urls[:5]:
                    print(f"      - {u[:60]}")

        # 5. Сводка
        print("\n" + "=" * 60)
        print("ИТОГО ПО ФАЙЛАМ")
        print("=" * 60)

        issues = []
        if missing_files:
            issues.append(f"{len(missing_files)} файлов из БД отсутствуют на диске")
        if orphan_files:
            issues.append(f"{len(orphan_files)} файлов на диске без записей в БД")
        if no_preview:
            issues.append(f"{len(no_preview)} медиа без preview_url")

        if issues:
            print("\n⚠️  НАЙДЕНЫ ПРОБЛЕМЫ:")
            for issue in issues:
                print(f"   - {issue}")
        else:
            print("\n✅ ПРОБЛЕМ С ФАЙЛАМИ НЕ НАЙДЕНО")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_files())
