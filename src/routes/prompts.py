import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db_session
from src.dependencies import get_current_user, get_optional_user
from src.models.db_models import User
from src.models.schemas import (
    FeedResponse,
    HomepageResponse,
    LikeResponse,
    OgMeta,
    PromptCreate,
    PromptOut,
)
from src.services.prompt_service import PromptService

router = APIRouter(prefix="/api/prompts")
logger = logging.getLogger(__name__)


def _service(db: AsyncSession = Depends(get_db_session)) -> PromptService:
    """Dependency to get PromptService instance."""
    return PromptService(db)


@router.get("/homepage")
async def get_homepage_data(svc: PromptService = Depends(_service)):
    """Get homepage data: trending text, trending media, daily prompt."""
    result = await svc.get_homepage_data()
    return result.model_dump(by_alias=True)


@router.get("/feed")
async def get_prompts_feed(
    media_type: Optional[str] = None,
    category: Optional[List[str]] = Query(None, description="Рубрики (OR): повторяющийся query-параметр category"),
    filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    svc: PromptService = Depends(_service),
):
    """Get paginated feed of prompts with filters."""
    result = await svc.get_feed(media_type, category, filter, page, page_size)
    return result.model_dump(by_alias=True)


@router.get("/{prompt_id}/og-meta", response_model=OgMeta)
async def get_prompt_og_meta(
    prompt_id: str,
    svc: PromptService = Depends(_service),
):
    """Get OpenGraph metadata for a prompt."""
    return await svc.get_og_meta(prompt_id)


@router.get("/{prompt_id}")
async def get_prompt(
    prompt_id: str,
    svc: PromptService = Depends(_service),
):
    """Get single prompt by ID."""
    result = await svc.get_by_id(prompt_id)
    return result.model_dump(by_alias=True)


@router.post("/publish")
async def publish_prompt(
    payload: PromptCreate,
    current_user: User = Depends(get_current_user),
    svc: PromptService = Depends(_service),
):
    """Publish a new prompt."""
    result = await svc.publish(payload, current_user.id)
    return {"status": "ok", "prompt": result.model_dump(by_alias=True)}


@router.post("/{prompt_id}/like", response_model=LikeResponse)
async def like_prompt(
    prompt_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Toggle like on a prompt. Requires authentication.
    If already liked - removes like (unlike). If not liked - adds like.
    """
    from sqlalchemy import select
    from src.models.db_models import Like, Prompt
    from src.redis_client import get_redis

    # Rate limiting
    redis = get_redis()
    if redis:
        client_ip = request.client.host if request.client else "unknown"
        rl_key = f"like:rate_limit:{current_user.id}:{client_ip}"
        acquired = await redis.set(rl_key, "1", ex=2, nx=True)
        if not acquired:
            raise HTTPException(status_code=429, detail="Too Many Requests")

    # Get prompt
    prompt = await db.get(Prompt, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    # Check if already liked
    existing = await db.execute(
        select(Like).where(
            Like.user_id == current_user.id,
            Like.prompt_id == prompt_id,
        )
    )
    liked = existing.scalar_one_or_none()

    if liked:
        # Unlike: remove like and decrement count
        await db.delete(liked)
        prompt.likes_count = max(0, prompt.likes_count - 1)
        is_liked = False
    else:
        # Like: add like and increment count
        db.add(Like(user_id=current_user.id, prompt_id=prompt_id))
        prompt.likes_count += 1
        is_liked = True

    await db.commit()
    await db.refresh(prompt)

    return LikeResponse(
        status="ok",
        likes_count=prompt.likes_count,
        message="Liked" if is_liked else "Unliked",
    )


@router.get("/{prompt_id}/like", response_model=dict)
async def get_like_status(
    prompt_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Check if current user has liked this prompt.
    Returns {liked: true/false, likes_count: number}
    """
    from sqlalchemy import select, func
    from src.models.db_models import Like, Prompt

    # Get prompt with likes count
    prompt = await db.get(Prompt, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    # Check if user liked this prompt
    existing = await db.execute(
        select(Like).where(
            Like.user_id == current_user.id,
            Like.prompt_id == prompt_id,
        )
    )
    liked = existing.scalar_one_or_none()

    return {
        "liked": bool(liked),
        "likes_count": prompt.likes_count,
    }


@router.post("/{prompt_id}/copy-count")
async def increment_copy_count(
    prompt_id: str,
    request: Request,
    x_session_token: Optional[str] = Header(default=None),
    svc: PromptService = Depends(_service),
):
    """Increment copy count for a prompt."""
    client_ip = request.client.host if request.client else "unknown"
    return await svc.increment_copy_count(prompt_id, client_ip, x_session_token)
