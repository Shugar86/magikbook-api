"""Fallback endpoints для ручной публикации (если автопостинг не сработал)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db_session
from src.dependencies import get_current_user
from src.models.db_models import Prompt, User
from src.services.vk_publisher import publish_to_vk, check_vk_config
from src.services.telegram_publisher import publish_to_telegram, check_telegram_config
from src.utils.file_storage import delete_file, file_exists

router = APIRouter()


class VKPublishRequest(BaseModel):
    """Запрос на публикацию в VK."""
    prompt_id: str


class TelegramPublishRequest(BaseModel):
    """Запрос на публикацию в Telegram."""
    prompt_id: str


class ManualPreviewUrlRequest(BaseModel):
    """Запрос на установку preview_url вручную."""
    preview_url: str


@router.post("/api/publish/vk")
async def manual_publish_vk(
    request: VKPublishRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Ручная публикация в VK (фолбэк для модерации).

    Используется когда автопостинг не сработал.
    """
    # Проверяем что VK настроен
    if not await check_vk_config():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VK publishing not configured"
        )

    # Получаем промпт
    prompt = await db.get(Prompt, request.prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )

    if prompt.media_type not in ("image", "video"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VK publishing only supports image or video prompts",
        )

    if not prompt.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file to publish"
        )

    if not file_exists(prompt.file_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File not found: {prompt.file_path}"
        )

    try:
        result = await publish_to_vk(
            title=prompt.title,
            prompt_text=prompt.prompt_text,
            ai_model=prompt.ai_model,
            file_path=prompt.file_path,
            prompt_id=prompt.id,
            media_type=prompt.media_type,
        )

        # Обновляем промпт
        prompt.vk_post_url = result.get("post_url")
        vk_preview = result.get("photo_url")
        if vk_preview and not prompt.preview_url:
            prompt.preview_url = vk_preview
        v_own = result.get("video_owner_id")
        v_id = result.get("video_id")
        v_hash = result.get("video_hash")
        if v_own is not None:
            prompt.vk_video_owner_id = int(v_own)
        if v_id is not None:
            prompt.vk_video_id = int(v_id)
        if v_hash:
            prompt.vk_video_hash = str(v_hash)

        # Если статус был "approved", меняем на "published"
        if prompt.moderation_status == "approved":
            prompt.moderation_status = "published"

        # Удаляем файл
        await delete_file(prompt.file_path)
        prompt.file_path = None

        await db.commit()
        await db.refresh(prompt)

        return {
            "status": "ok",
            "message": "Published to VK successfully",
            "result": result,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"VK publishing failed: {str(e)}"
        )


@router.post("/api/publish/telegram")
async def manual_publish_telegram(
    request: TelegramPublishRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Ручная публикация в Telegram (фолбэк для модерации).

    Используется когда автопостинг не сработал.
    """
    # Проверяем что Telegram настроен
    if not await check_telegram_config():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram publishing not configured"
        )

    # Получаем промпт
    prompt = await db.get(Prompt, request.prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )

    if prompt.media_type not in ("image", "video"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram publishing only supports image/video prompts"
        )

    if not prompt.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file to publish"
        )

    if not file_exists(prompt.file_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File not found: {prompt.file_path}"
        )

    try:
        result = await publish_to_telegram(
            title=prompt.title,
            prompt_text=prompt.prompt_text,
            ai_model=prompt.ai_model,
            file_path=prompt.file_path,
            media_type=prompt.media_type,
            prompt_id=prompt.id
        )

        # Обновляем промпт
        prompt.telegram_message_url = result.get("message_url")

        # Если статус был "approved", меняем на "published"
        if prompt.moderation_status == "approved":
            prompt.moderation_status = "published"

        # Удаляем файл
        await delete_file(prompt.file_path)
        prompt.file_path = None

        await db.commit()
        await db.refresh(prompt)

        return {
            "status": "ok",
            "message": "Published to Telegram successfully",
            "result": result,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Telegram publishing failed: {str(e)}"
        )


@router.post("/api/publish/{prompt_id}/manual-preview")
async def set_manual_preview_url(
    prompt_id: str,
    request: ManualPreviewUrlRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Установить preview_url вручную (например, после ручной загрузки в VK).

    Используется когда модератор сам загружает файл в VK
    и получает прямую ссылку на изображение.
    """
    prompt = await db.get(Prompt, prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )

    if prompt.moderation_status not in ("approved", "published"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prompt must be approved first"
        )

    # Устанавливаем preview_url
    prompt.preview_url = request.preview_url

    # Если статус "approved", меняем на "published"
    if prompt.moderation_status == "approved":
        prompt.moderation_status = "published"

    # Удаляем локальный файл (если есть)
    if prompt.file_path:
        await delete_file(prompt.file_path)
        prompt.file_path = None

    await db.commit()
    await db.refresh(prompt)

    return {
        "status": "ok",
        "message": "Preview URL set manually",
        "prompt": {
            "id": prompt.id,
            "preview_url": prompt.preview_url,
            "moderation_status": prompt.moderation_status,
        }
    }
