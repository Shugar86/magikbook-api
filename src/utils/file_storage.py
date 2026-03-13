"""Утилиты для работы с файлами: сохранение, валидация, очистка."""

import os
import time
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import UploadFile, HTTPException
from PIL import Image

from src.config import settings

# Допустимые MIME-типы
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm"}
ALLOWED_MEDIA_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_VIDEO_TYPES

# Расширения файлов
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".webm"}


def get_upload_dir() -> Path:
    """Возвращает путь к директории для загрузки файлов."""
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def get_pending_dir() -> Path:
    """Возвращает путь к директории для файлов на модерации."""
    pending_dir = get_upload_dir() / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    return pending_dir


def get_approved_dir() -> Path:
    """Возвращает путь к директории для одобренных файлов."""
    approved_dir = get_upload_dir() / "approved"
    approved_dir.mkdir(parents=True, exist_ok=True)
    return approved_dir


async def validate_file(file: UploadFile, media_type: str) -> bool:
    """
    Проверяет файл на соответствие требованиям.

    Args:
        file: Загружаемый файл
        media_type: Тип медиа ("image" или "video")

    Returns:
        bool: True если файл прошел валидацию

    Raises:
        HTTPException: Если файл не прошел валидацию
    """
    # Проверка размера файла (читаем первый chunk)
    content = await file.read(settings.max_file_size + 1)
    await file.seek(0)  # Сбрасываем позицию для последующего чтения

    if len(content) > settings.max_file_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.max_file_size / (1024 * 1024):.0f} MB"
        )

    # Проверка MIME-type
    if file.content_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type}. "
                   f"Allowed: {', '.join(ALLOWED_MEDIA_TYPES)}"
        )

    # Проверка соответствия media_type и content_type
    if media_type == "image" and file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Expected image file, got: {file.content_type}"
        )

    if media_type == "video" and file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Expected video file, got: {file.content_type}"
        )

    # Для изображений - дополнительная валидация через Pillow
    if media_type == "image":
        try:
            img = Image.open(io.BytesIO(content))
            img.verify()  # Проверяем что это валидное изображение
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid image file: {str(e)}"
            )

    return True


async def save_upload_file(
    file: UploadFile,
    user_id: str,
    prompt_id: str
) -> str:
    """
    Сохраняет загруженный файл во временную директорию.

    Args:
        file: Загружаемый файл
        user_id: ID пользователя
        prompt_id: ID промпта

    Returns:
        str: Путь к сохраненному файлу
    """
    pending_dir = get_pending_dir()

    # Определяем расширение из content-type или filename
    ext = _get_extension_from_content_type(file.content_type)
    if not ext and file.filename:
        ext = Path(file.filename).suffix.lower()

    # Генерируем имя файла: user_{user_id}_{prompt_id}_{timestamp}{ext}
    timestamp = int(time.time())
    filename = f"user_{user_id}_{timestamp}_{prompt_id}{ext}"
    file_path = pending_dir / filename

    # Сохраняем файл
    content = await file.read()
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    return str(file_path)


def _get_extension_from_content_type(content_type: Optional[str]) -> str:
    """Возвращает расширение файла по MIME-type."""
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
    }
    return mapping.get(content_type, "")


async def delete_file(file_path: str) -> bool:
    """
    Удаляет файл по пути.

    Args:
        file_path: Путь к файлу

    Returns:
        bool: True если файл удален успешно
    """
    try:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            return True
    except Exception:
        pass
    return False


def cleanup_old_files(days: Optional[int] = None) -> int:
    """
    Очищает файлы старше указанного количества дней.

    Args:
        days: Количество дней (по умолчанию из settings.file_cleanup_days)

    Returns:
        int: Количество удаленных файлов
    """
    if days is None:
        days = settings.file_cleanup_days

    cutoff_time = time.time() - (days * 24 * 60 * 60)
    upload_dir = get_upload_dir()
    deleted_count = 0

    for subdir in ["pending", "approved"]:
        subdir_path = upload_dir / subdir
        if not subdir_path.exists():
            continue

        for file_path in subdir_path.iterdir():
            if file_path.is_file():
                try:
                    file_mtime = file_path.stat().st_mtime
                    if file_mtime < cutoff_time:
                        file_path.unlink()
                        deleted_count += 1
                except Exception:
                    pass

    return deleted_count


def get_file_size(file_path: str) -> int:
    """Возвращает размер файла в байтах."""
    try:
        return Path(file_path).stat().st_size
    except Exception:
        return 0


def file_exists(file_path: str) -> bool:
    """Проверяет существование файла."""
    return Path(file_path).exists() if file_path else False


# Import io здесь чтобы избежать circular import при использовании в validate_file
import io  # noqa: E402
