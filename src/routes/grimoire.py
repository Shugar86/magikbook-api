import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_optional_user
from src.database import get_db_session
from src.models.db_models import Prompt, SavedPrompt, User

router = APIRouter(prefix="/api/grimoire")
logger = logging.getLogger(__name__)

class SavePromptRequest(BaseModel):
    prompt_id: str

@router.post("")
async def save_prompt(
    request: SavePromptRequest,
    x_session_token: Optional[str] = Header(default=None, description="Unique user session token"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    actor = current_user.id if current_user else x_session_token
    if not actor:
        raise HTTPException(status_code=401, detail="Auth or X-Session-Token required")

    # Check if prompt exists
    prompt = await db.get(Prompt, request.prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    # Check if already saved
    result = await db.execute(
        select(SavedPrompt).where(
            SavedPrompt.session_token == actor,
            SavedPrompt.prompt_id == request.prompt_id
        )
    )
    existing_save = result.scalar_one_or_none()
    if existing_save:
        return {"status": "ok", "message": "Already saved"}

    # Save
    new_save = SavedPrompt(session_token=actor, prompt_id=request.prompt_id)
    db.add(new_save)
    await db.commit()
    return {"status": "ok", "message": "Prompt saved"}

@router.get("")
async def get_grimoire(
    x_session_token: Optional[str] = Header(default=None, description="Unique user session token"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    actor = current_user.id if current_user else x_session_token
    if not actor:
        raise HTTPException(status_code=401, detail="Auth or X-Session-Token required")

    result = await db.execute(
        select(Prompt).join(SavedPrompt).where(SavedPrompt.session_token == actor)
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
            } for p in prompts
        ]
    }

@router.delete("/{prompt_id}")
async def remove_from_grimoire(
    prompt_id: str,
    x_session_token: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    actor = current_user.id if current_user else x_session_token
    if not actor:
        raise HTTPException(status_code=401, detail="Auth or X-Session-Token required")

    result = await db.execute(
        select(SavedPrompt).where(
            SavedPrompt.session_token == actor,
            SavedPrompt.prompt_id == prompt_id,
        )
    )
    saved = result.scalar_one_or_none()
    if not saved:
        raise HTTPException(status_code=404, detail="Not in grimoire")

    await db.delete(saved)
    await db.commit()
    return {"status": "ok", "message": "Removed from grimoire"}

