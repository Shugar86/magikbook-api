import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
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
    category: Optional[str] = None,
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
    x_session_token: Optional[str] = Header(default=None),
    current_user: Optional[User] = Depends(get_optional_user),
    svc: PromptService = Depends(_service),
):
    """Like a prompt."""
    actor = current_user.id if current_user else x_session_token
    if not actor:
        raise HTTPException(status_code=401, detail="Auth or X-Session-Token required")
    client_ip = request.client.host if request.client else "unknown"
    return await svc.like(prompt_id, actor, client_ip)


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
