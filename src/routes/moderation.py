"""API endpoints for content moderation."""

from datetime import datetime
from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_db_session
from src.dependencies import get_current_user
from src.models.db_models import Prompt, User
from src.models.schemas import AffiliateLinksUpdate
from src.services.vk_publisher import publish_to_vk, check_vk_config
from src.services.telegram_publisher import publish_to_telegram, check_telegram_config
from src.utils.file_storage import delete_file
import json

router = APIRouter()
logger = logging.getLogger(__name__)


def _is_admin(user: User) -> bool:
    """Проверяет является ли пользователь администратором."""
    return user.is_admin


@router.get("/api/moderation")
async def get_moderation_queue(
    moderation_status: str = "pending",  # pending | approved | rejected | published | all
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Получить список промптов на модерацию.

    Args:
        moderation_status: Фильтр по статусу модерации
        page: Номер страницы
        page_size: Количество элементов на странице

    Returns:
        list: Список промптов со статусом модерации
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    query = select(Prompt)

    if moderation_status != "all":
        query = query.where(Prompt.moderation_status == moderation_status)

    # Сортируем: сначала новые (pending), потом по дате
    query = query.order_by(Prompt.created_at.desc())

    # Пагинация
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    prompts = result.scalars().all()

    # Получаем общее количество
    from sqlalchemy import func
    count_query = select(func.count()).select_from(Prompt)
    if moderation_status != "all":
        count_query = count_query.where(Prompt.moderation_status == moderation_status)

    total_result = await db.execute(count_query)
    total_count = total_result.scalar_one()

    return {
        "prompts": [
            {
                "id": p.id,
                "title": p.title,
                "prompt_text": p.prompt_text,
                "category": p.category,
                "media_type": p.media_type,
                "ai_model": p.ai_model,
                "moderation_status": p.moderation_status,
                "file_path": p.file_path,
                "preview_url": p.preview_url,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "author_id": p.author_id,
                "likes_count": p.likes_count,
            }
            for p in prompts
        ],
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "has_more": total_count > (offset + len(prompts))
    }


@router.post("/api/moderation/{prompt_id}/approve")
async def approve_prompt(
    prompt_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Одобрить промпт и запустить автопостинг в VK и Telegram.

    Args:
        prompt_id: ID промпта для одобрения

    Returns:
        dict: Результат одобрения и публикации
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Получаем промпт
    prompt = await db.get(Prompt, prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )

    if prompt.moderation_status not in ("pending", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve prompt with status: {prompt.moderation_status}"
        )

    # Обновляем статус на "approved"
    prompt.moderation_status = "approved"
    prompt.moderated_by = current_user.id
    prompt.moderated_at = datetime.utcnow()

    await db.commit()

    # Результаты публикации
    vk_result = None
    telegram_result = None
    errors = []

    # Автопостинг в VK (только для image с файлом)
    if prompt.media_type == "image" and prompt.file_path:
        try:
            if await check_vk_config():
                vk_result = await publish_to_vk(
                    title=prompt.title,
                    prompt_text=prompt.prompt_text,
                    ai_model=prompt.ai_model,
                    file_path=prompt.file_path,
                    prompt_id=prompt.id
                )
                prompt.vk_post_url = vk_result.get("post_url")
                prompt.preview_url = vk_result.get("photo_url")  # URL из VK для превью
                logger.info(f"Published to VK: {vk_result.get('post_url')}")
            else:
                errors.append("VK not configured")
                logger.warning("VK publishing skipped - not configured")
        except Exception as e:
            error_msg = f"VK publishing failed: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)

    # Автопостинг в Telegram
    if prompt.file_path and prompt.media_type in ("image", "video"):
        try:
            if await check_telegram_config():
                telegram_result = await publish_to_telegram(
                    title=prompt.title,
                    prompt_text=prompt.prompt_text,
                    ai_model=prompt.ai_model,
                    file_path=prompt.file_path,
                    media_type=prompt.media_type,
                    prompt_id=prompt.id
                )
                prompt.telegram_message_url = telegram_result.get("message_url")
                logger.info(f"Published to Telegram: {telegram_result.get('message_url')}")
            else:
                errors.append("Telegram not configured")
                logger.warning("Telegram publishing skipped - not configured")
        except Exception as e:
            error_msg = f"Telegram publishing failed: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)

    # Если хотя бы одна публикация успешна (или это text-промпт) - обновляем статус на published
    if prompt.media_type == "text" or vk_result or telegram_result:
        prompt.moderation_status = "published"

        # Удаляем локальный файл после успешной публикации
        if prompt.file_path:
            try:
                await delete_file(prompt.file_path)
                prompt.file_path = None
                logger.info(f"Deleted local file for prompt {prompt.id}")
            except Exception as e:
                logger.warning(f"Failed to delete file {prompt.file_path}: {e}")

    await db.commit()
    await db.refresh(prompt)

    return {
        "status": "ok",
        "message": "Prompt approved and published" if prompt.moderation_status == "published" else "Prompt approved but publishing had issues",
        "prompt": {
            "id": prompt.id,
            "title": prompt.title,
            "moderation_status": prompt.moderation_status,
            "preview_url": prompt.preview_url,
            "vk_post_url": prompt.vk_post_url,
            "telegram_message_url": prompt.telegram_message_url,
        },
        "publishing_results": {
            "vk": vk_result,
            "telegram": telegram_result,
        },
        "errors": errors if errors else None,
    }


@router.post("/api/moderation/{prompt_id}/reject")
async def reject_prompt(
    prompt_id: str,
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Отклонить промпт и удалить связанный файл.

    Args:
        prompt_id: ID промпта для отклонения
        reason: Причина отклонения (опционально)

    Returns:
        dict: Результат отклонения
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Получаем промпт
    prompt = await db.get(Prompt, prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )

    if prompt.moderation_status == "published":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reject already published prompt"
        )

    # Удаляем файл если есть
    if prompt.file_path:
        try:
            await delete_file(prompt.file_path)
            logger.info(f"Deleted file for rejected prompt {prompt.id}")
        except Exception as e:
            logger.warning(f"Failed to delete file {prompt.file_path}: {e}")

    # Обновляем статус
    prompt.moderation_status = "rejected"
    prompt.moderated_by = current_user.id
    prompt.moderated_at = datetime.utcnow()
    prompt.file_path = None  # Очищаем путь к файлу

    await db.commit()
    await db.refresh(prompt)

    # TODO: Отправить уведомление пользователю (опционально)

    return {
        "status": "ok",
        "message": "Prompt rejected",
        "reason": reason,
        "prompt": {
            "id": prompt.id,
            "title": prompt.title,
            "moderation_status": prompt.moderation_status,
            "moderated_at": prompt.moderated_at.isoformat() if prompt.moderated_at else None,
        }
    }


@router.get("/api/moderation/stats")
async def get_moderation_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Получить статистику модерации.

    Returns:
        dict: Статистика по статусам модерации
    """
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    from sqlalchemy import func

    query = select(
        Prompt.moderation_status,
        func.count(Prompt.id).label("count")
    ).group_by(Prompt.moderation_status)

    result = await db.execute(query)
    stats = {row.moderation_status: row.count for row in result.all()}

    return {
        "stats": {
            "pending": stats.get("pending", 0),
            "approved": stats.get("approved", 0),
            "rejected": stats.get("rejected", 0),
            "published": stats.get("published", 0),
            "total": sum(stats.values()),
        },
        "publishing_configured": {
            "vk": await check_vk_config(),
            "telegram": await check_telegram_config(),
        }
    }


@router.post("/api/admin/grant/{user_id}")
async def grant_admin_rights(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Выдать права администратора пользователю (только для существующих админов)."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    target_user = await db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    target_user.is_admin = True
    await db.commit()
    return {"status": "ok", "user_id": user_id, "is_admin": True}


@router.patch("/api/admin/prompts/{prompt_id}/affiliate-links")
async def update_affiliate_links(
    prompt_id: str,
    payload: AffiliateLinksUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Update affiliate links for a prompt (admin only)."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    prompt = await db.get(Prompt, prompt_id)
    if not prompt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")

    # Convert dict to JSON string for storage
    prompt.affiliate_links_str = json.dumps(payload.affiliate_links, ensure_ascii=False)
    await db.commit()
    await db.refresh(prompt)

    return {
        "status": "ok",
        "prompt_id": prompt_id,
        "affiliate_links": payload.affiliate_links,
    }
