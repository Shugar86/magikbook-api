"""API endpoints for user cabinet/dashboard."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db_session
from src.dependencies import get_current_user
from src.models.db_models import Prompt, SavedPrompt, User
from src.models.schemas import CabinetOverview, CabinetStats, CabinetTopPrompt, UserOut
from src.redis_client import get_redis

router = APIRouter(prefix="/api/cabinet")


@router.get("/overview", response_model=CabinetOverview)
async def get_cabinet_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get comprehensive cabinet overview for the current user.

    Returns user profile, statistics about their prompts and saves,
    their top performing prompt, and daily bonus availability.

    Returns:
        CabinetOverview: Complete dashboard data for the user
    """
    # Check daily bonus availability
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    bonus_key = f"daily_bonus:{current_user.id}:{today}"
    can_claim_bonus = True

    try:
        redis = get_redis()
        if redis:
            already_claimed = await redis.get(bonus_key)
            can_claim_bonus = not bool(already_claimed)
    except Exception:
        # If Redis is unavailable, assume bonus can be claimed
        can_claim_bonus = True

    # Get saved prompts count
    saved_count_query = select(func.count()).select_from(SavedPrompt).where(
        SavedPrompt.session_token == current_user.id
    )
    saved_count = (await db.scalar(saved_count_query)) or 0

    # Get user's prompts with aggregated stats
    prompts_query = select(Prompt).where(Prompt.author_id == current_user.id)
    result = await db.execute(prompts_query)
    user_prompts = result.scalars().all()

    # Calculate stats
    submitted_count = len(user_prompts)
    approved_count = sum(1 for p in user_prompts if p.moderation_status == "approved")
    pending_count = sum(1 for p in user_prompts if p.moderation_status == "pending")
    rejected_count = sum(1 for p in user_prompts if p.moderation_status == "rejected")
    total_likes = sum(p.likes_count for p in user_prompts)
    total_copies = sum(p.copies for p in user_prompts)

    # Find top prompt (by likes_count + copies, only approved/published)
    top_prompt: Optional[CabinetTopPrompt] = None
    approved_prompts = [
        p for p in user_prompts
        if p.moderation_status in ("approved", "published")
    ]
    if approved_prompts:
        best_prompt = max(approved_prompts, key=lambda p: p.likes_count + p.copies)
        if best_prompt.likes_count + best_prompt.copies > 0:
            top_prompt = CabinetTopPrompt(
                id=best_prompt.id,
                title=best_prompt.title,
                likes_count=best_prompt.likes_count,
                copies=best_prompt.copies,
            )

    # Build user data with bonus availability flag
    user_data = UserOut.model_validate(current_user)

    return CabinetOverview(
        user={
            "id": user_data.id,
            "username": user_data.username,
            "avatar_url": user_data.avatar_url,
            "tokens": user_data.tokens,
            "referral_code": user_data.referral_code,
            "auth_provider": user_data.auth_provider,
            "is_admin": user_data.is_admin,
            "can_claim_bonus": can_claim_bonus,
        },
        stats=CabinetStats(
            saved_count=saved_count,
            submitted_count=submitted_count,
            approved_count=approved_count,
            pending_count=pending_count,
            rejected_count=rejected_count,
            total_likes=total_likes,
            total_copies=total_copies,
        ),
        top_prompt=top_prompt,
    )
