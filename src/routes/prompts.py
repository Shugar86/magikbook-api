import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db_session
from src.dependencies import get_current_user, get_optional_user
from src.models.db_models import Like, Prompt, User

router = APIRouter(prefix="/api/prompts")
logger = logging.getLogger(__name__)


class PublishPromptRequest(BaseModel):
    title: str
    prompt_text: str = Field(min_length=20)
    category: str
    media_type: str = "text"
    preview_url: Optional[str] = None


@router.get("/homepage")
async def get_homepage_data(db: AsyncSession = Depends(get_db_session)):
    # 1. Топ текстовых (только approved/published)
    text_result = await db.execute(
        select(Prompt)
        .where(Prompt.media_type == "text")
        .where(Prompt.moderation_status.in_(["approved", "published"]))
        .order_by(Prompt.likes_count.desc())
        .limit(6)
    )
    trending_text = text_result.scalars().all()

    # 2. Топ медиа (картинки/видео) - только approved/published
    media_result = await db.execute(
        select(Prompt)
        .where(Prompt.media_type.in_(["image", "video"]))
        .where(Prompt.moderation_status.in_(["approved", "published"]))
        .order_by(Prompt.elo_rating.desc())
        .limit(8)
    )
    trending_media = media_result.scalars().all()

    # 3. Заклинание дня (берем самый залайканный текст, если есть)
    daily_prompt = trending_text[0] if trending_text else None

    def serialize(p: Prompt):
        return {
            "id": p.id,
            "title": p.title,
            "prompt_text": p.prompt_text,
            "preview_url": p.preview_url,
            "media_type": p.media_type,
            "category": p.category,
            "variables": p.variables,
            "targetModels": p.target_models,
            "tone": p.tone,
            "copies": p.copies,
            "remixes": p.remixes,
            "isTrending": p.is_trending,
            "isNew": p.is_new,
            "createdAt": p.created_at.isoformat() if p.created_at else None,
            "likes_count": p.likes_count,
            "elo_rating": p.elo_rating,
            "author_id": p.author_id,
        }

    return {
        "trending_text": [serialize(p) for p in trending_text],
        "trending_media": [serialize(p) for p in trending_media],
        "daily_prompt": serialize(daily_prompt) if daily_prompt else None,
    }

@router.get("/feed")
async def get_prompts_feed(
    media_type: Optional[str] = None,
    category: Optional[str] = None,
    filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db_session)
):
    # Только approved/published промпты в публичном фиде
    query = select(Prompt).where(Prompt.moderation_status.in_(["approved", "published"]))

    if media_type:
        query = query.where(Prompt.media_type == media_type)
    if category:
        query = query.where(Prompt.category == category)
        
    if filter == "trending":
        query = query.order_by(Prompt.elo_rating.desc())
    elif filter == "new":
        query = query.order_by(Prompt.created_at.desc())
    elif filter == "best":
        query = query.order_by(Prompt.likes_count.desc())
    else:
        query = query.order_by(Prompt.created_at.desc())
        
    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    prompts = result.scalars().all()
    
    # Total count (optional but helpful) - только approved/published
    from sqlalchemy import func
    count_query = select(func.count()).select_from(Prompt).where(
        Prompt.moderation_status.in_(["approved", "published"])
    )
    if media_type:
        count_query = count_query.where(Prompt.media_type == media_type)
    if category:
        count_query = count_query.where(Prompt.category == category)
    
    total_result = await db.execute(count_query)
    total_count = total_result.scalar_one()

    return {
        "prompts": [
            {
                "id": p.id,
                "title": p.title,
                "prompt_text": p.prompt_text,
                "preview_url": p.preview_url,
                "media_type": p.media_type,
                "category": p.category,
                "variables": p.variables,
                "targetModels": p.target_models,
                "tone": p.tone,
                "copies": p.copies,
                "remixes": p.remixes,
                "isTrending": p.is_trending,
                "isNew": p.is_new,
                "createdAt": p.created_at.isoformat() if p.created_at else None,
                "likes_count": p.likes_count,
                "elo_rating": p.elo_rating,
                "author_id": p.author_id,
            }
            for p in prompts
        ],
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "has_more": total_count > (offset + len(prompts))
    }

@router.post("/publish")
async def publish_prompt(
    payload: PublishPromptRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    import re
    import json
    
    prompt_text = payload.prompt_text.strip()
    variables = list(set(re.findall(r'\{([^}]+)\}', prompt_text)))
    
    variables_str = json.dumps(variables) if variables else None
    target_models_str = json.dumps(["ChatGPT", "Claude"]) if payload.media_type == "text" else None

    prompt = Prompt(
        title=payload.title.strip() or "Без названия",
        prompt_text=prompt_text,
        category=payload.category,
        media_type=payload.media_type,
        preview_url=payload.preview_url,
        author_id=current_user.id,
        variables_str=variables_str,
        target_models_str=target_models_str
    )
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    return {
        "status": "ok",
        "prompt": {
            "id": prompt.id,
            "title": prompt.title,
            "prompt_text": prompt.prompt_text,
            "category": prompt.category,
            "media_type": prompt.media_type,
            "author_id": prompt.author_id,
        },
    }

@router.get("/{prompt_id}")
async def get_prompt(
    prompt_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    prompt = await db.get(Prompt, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    # Проверка moderation_status для публичного доступа
    if prompt.moderation_status not in ("approved", "published"):
        raise HTTPException(status_code=404, detail="Prompt not found")
        
    return {
        "id": prompt.id,
        "title": prompt.title,
        "prompt_text": prompt.prompt_text,
        "preview_url": prompt.preview_url,
        "media_type": prompt.media_type,
        "category": prompt.category,
        "variables": prompt.variables,
        "targetModels": prompt.target_models,
        "tone": prompt.tone,
        "copies": prompt.copies,
        "remixes": prompt.remixes,
        "isTrending": prompt.is_trending,
        "isNew": prompt.is_new,
        "createdAt": prompt.created_at.isoformat() if prompt.created_at else None,
        "likes_count": prompt.likes_count,
        "elo_rating": prompt.elo_rating,
        "author_id": prompt.author_id,
    }

@router.post("/{prompt_id}/like")
async def like_prompt(
    prompt_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    x_session_token: Optional[str] = Header(default=None),
    current_user: Optional[User] = Depends(get_optional_user),
):
    from sqlalchemy.exc import IntegrityError
    from src.redis_client import get_redis
    
    actor = current_user.id if current_user else x_session_token
    if not actor:
        raise HTTPException(status_code=401, detail="Auth or X-Session-Token required")
        
    redis = get_redis()
    client_ip = request.client.host if request.client else "unknown"
    rl_key = f"like:rate_limit:{actor}:{client_ip}"
    
    if redis:
        acquired = await redis.set(rl_key, "1", ex=2, nx=True)
        if not acquired:
            raise HTTPException(status_code=429, detail="Too Many Requests")

    prompt = await db.get(Prompt, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    already_liked = await db.execute(
        select(Like).where(Like.user_session == actor, Like.prompt_id == prompt_id)
    )
    if already_liked.scalar_one_or_none():
        return {"status": "ok", "message": "Already liked", "likes_count": prompt.likes_count}

    db.add(Like(user_session=actor, prompt_id=prompt_id))
    prompt.likes_count += 1
    try:
        await db.commit()
        await db.refresh(prompt)
    except IntegrityError:
        await db.rollback()
        return {"status": "ok", "message": "Already liked", "likes_count": prompt.likes_count - 1}
        
    return {"status": "ok", "likes_count": prompt.likes_count}


@router.post("/{prompt_id}/copy-count")
async def increment_copy_count(
    prompt_id: str,
    db: AsyncSession = Depends(get_db_session),
    x_session_token: Optional[str] = Header(default=None),
):
    """Increment the copies counter when a user copies a prompt text."""
    prompt = await db.get(Prompt, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    prompt.copies += 1
    await db.commit()
    return {"status": "ok", "copies": prompt.copies}

