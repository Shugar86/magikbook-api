"""API endpoints for file uploads and prompt submission."""

from typing import Optional
import json
import re

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_db_session
from src.dependencies import get_current_user
from src.models.db_models import Prompt, User
from src.utils.file_storage import validate_file, save_upload_file

router = APIRouter()


@router.post("/api/prompts/upload")
async def upload_prompt(
    title: str = Form(..., min_length=1, max_length=200),
    prompt_text: str = Form(..., min_length=20),
    category: str = Form(...),
    media_type: str = Form(..., pattern="^(text|image|video)$"),
    ai_model: Optional[str] = Form(None),
    result_example: Optional[str] = Form(None),
    result_image_url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Загрузка нового промпта с файлом (для image/video).

    Для text-промптов файл не требуется.
    Для image/video промптов файл обязателен.
    Файл сохраняется во временную директорию и ожидает модерации.

    Args:
        title: Название промпта
        prompt_text: Текст промпта (минимум 20 символов)
        category: Категория промпта
        media_type: Тип медиа ("text", "image", "video")
        ai_model: Название нейросети (для image/video)
        file: Файл изображения или видео (опционально для text)

    Returns:
        dict: Информация о созданном промпте со статусом "pending"
    """
    # Валидация: для image/video файл обязателен
    if media_type in ("image", "video"):
        if not file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File is required for {media_type} prompts"
            )
        if not ai_model:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ai_model is required for image/video prompts (e.g., 'Midjourney', 'DALL-E')"
            )

    # Валидация файла (если есть)
    file_path = None
    if file:
        await validate_file(file, media_type)

    # Извлекаем переменные из prompt_text
    variables = list(set(re.findall(r'\{([^}]+)\}', prompt_text)))
    variables_str = json.dumps(variables) if variables else None

    # Определяем target_models на основе media_type
    if media_type == "text":
        target_models_str = json.dumps(["ChatGPT", "Claude"])
    else:
        target_models_str = json.dumps([ai_model]) if ai_model else None

    # Создаем запись в БД
    prompt = Prompt(
        title=title.strip() or "Без названия",
        prompt_text=prompt_text.strip(),
        category=category,
        media_type=media_type,
        author_id=current_user.id,
        variables_str=variables_str,
        target_models_str=target_models_str,
        moderation_status="pending",
        ai_model=ai_model,
        file_path=None,  # Пока None, обновим после сохранения файла
        result_example=result_example,
        result_image_url=result_image_url,
    )

    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)

    # Сохраняем файл (если есть)
    if file:
        try:
            file_path = await save_upload_file(
                file=file,
                user_id=current_user.id,
                prompt_id=prompt.id
            )
            # Обновляем запись с путем к файлу
            prompt.file_path = file_path
            await db.commit()
        except Exception as e:
            # При ошибке сохранения файла - удаляем запись из БД
            await db.delete(prompt)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save file: {str(e)}"
            )

    return {
        "status": "ok",
        "prompt": {
            "id": prompt.id,
            "title": prompt.title,
            "category": prompt.category,
            "media_type": prompt.media_type,
            "moderation_status": prompt.moderation_status,
            "ai_model": prompt.ai_model,
            "file_path": prompt.file_path,
            "author_id": prompt.author_id,
        },
        "message": "Промпт отправлен на модерацию. Он появится в ленте после проверки."
    }


@router.get("/api/prompts/my-uploads")
async def get_my_uploads(
    moderation_status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Получить список загруженных пользователем промптов.

    Args:
        moderation_status: Фильтр по статусу модерации ("pending", "approved", "rejected", "published")

    Returns:
        list: Список промптов пользователя
    """
    from sqlalchemy import select

    query = select(Prompt).where(Prompt.author_id == current_user.id)

    if moderation_status and moderation_status != "all":
        query = query.where(Prompt.moderation_status == moderation_status)

    # Сортируем по дате создания (новые сначала)
    query = query.order_by(Prompt.created_at.desc())

    result = await db.execute(query)
    prompts = result.scalars().all()

    return {
        "prompts": [
            {
                "id": p.id,
                "title": p.title,
                "category": p.category,
                "media_type": p.media_type,
                "moderation_status": p.moderation_status,
                "ai_model": p.ai_model,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "moderated_at": p.moderated_at.isoformat() if p.moderated_at else None,
                "likes_count": p.likes_count,
                "copies": p.copies,
                "preview_url": p.preview_url,
            }
            for p in prompts
        ],
        "total": len(prompts)
    }
