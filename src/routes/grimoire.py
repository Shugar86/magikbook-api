import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_current_user
from src.database import get_db_session
from src.models.db_models import Prompt, SavedPrompt, User

router = APIRouter(prefix="/api/grimoire")
logger = logging.getLogger(__name__)


class SavePromptRequest(BaseModel):
    prompt_id: str


@router.post("")
async def save_prompt(
    request: SavePromptRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Save a prompt to user's grimoire.
    Requires authentication.
    """
    # Check if prompt exists
    prompt = await db.get(Prompt, request.prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    # Check if already saved
    result = await db.execute(
        select(SavedPrompt).where(
            SavedPrompt.user_id == current_user.id,
            SavedPrompt.prompt_id == request.prompt_id,
        )
    )
    existing_save = result.scalar_one_or_none()
    if existing_save:
        return {"status": "ok", "message": "Already saved"}

    # Save using user_id
    new_save = SavedPrompt(user_id=current_user.id, prompt_id=request.prompt_id)
    db.add(new_save)
    await db.commit()
    return {"status": "ok", "message": "Prompt saved"}


@router.get("")
async def get_grimoire(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get saved prompts from user's grimoire.
    Requires authentication.

    Args:
        skip: Number of prompts to skip (for pagination)
        limit: Maximum number of prompts to return (default 100)

    Returns:
        dict: List of saved prompts with total count
    """
    # Get total count by user_id
    count_query = select(func.count()).select_from(SavedPrompt).where(
        SavedPrompt.user_id == current_user.id
    )
    total_count = (await db.scalar(count_query)) or 0

    # Get paginated results by user_id
    result = await db.execute(
        select(Prompt)
        .join(SavedPrompt)
        .where(SavedPrompt.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    prompts = result.scalars().all()

    return {
        "prompts": [
            {
                "id": p.id,
                "title": p.title,
                "prompt_text": p.prompt_text,
                "preview_url": p.preview_url,
                "media_type": p.media_type,
                "category": p.category,
                "likes_count": p.likes_count,
                "copies": p.copies,
            } for p in prompts
        ],
        "total": total_count,
        "skip": skip,
        "limit": limit,
    }


@router.delete("/{prompt_id}")
async def remove_from_grimoire(
    prompt_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Remove a prompt from user's grimoire.
    Requires authentication.
    """
    result = await db.execute(
        select(SavedPrompt).where(
            SavedPrompt.user_id == current_user.id,
            SavedPrompt.prompt_id == prompt_id,
        )
    )
    saved = result.scalar_one_or_none()
    if not saved:
        raise HTTPException(status_code=404, detail="Not in grimoire")

    await db.delete(saved)
    await db.commit()
    return {"status": "ok", "message": "Removed from grimoire"}
