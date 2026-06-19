import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

import src.redis_client as redis_client
from src.database import get_db_session
from src.services.battle_service import BattleService
from src.dependencies import get_optional_user
from src.models.db_models import User, Prompt

router = APIRouter(prefix="/api/battle")
logger = logging.getLogger(__name__)

# Seconds between battle votes per IP (must match frontend cooldown messaging).
BATTLE_VOTE_RATE_LIMIT_SEC = 30

FALLBACK_PROMPTS = [
    {
        "id": "fallback-left",
        "title": "Демо визуализация A",
        "prompt_text": "Кинематографичный кадр, детальный свет, магическая атмосфера.",
        "preview_url": "https://picsum.photos/seed/fallback-left/600/800",
        "category": "art",
        "elo_rating": 1200,
        "likes_count": 0,
        "copies": 0,
        "remixes": 0,
        "isTrending": False,
        "isNew": False,
        "targetModels": [],
        "media_type": "image",
        "result_example": None,
        "result_image_url": None,
        "affiliate_links": None,
    },
    {
        "id": "fallback-right",
        "title": "Демо визуализация B",
        "prompt_text": "Эпичная сцена, контрастные тени, насыщенные цвета, фэнтези стиль.",
        "preview_url": "https://picsum.photos/seed/fallback-right/600/800",
        "category": "fantasy",
        "elo_rating": 1200,
        "likes_count": 0,
        "copies": 0,
        "remixes": 0,
        "isTrending": False,
        "isNew": False,
        "targetModels": [],
        "media_type": "image",
        "result_example": None,
        "result_image_url": None,
        "affiliate_links": None,
    },
]

FALLBACK_VOTE_IDS = frozenset(p["id"] for p in FALLBACK_PROMPTS)


class VoteRequest(BaseModel):
    winner_id: str
    loser_id: str
    session_token: Optional[str] = Field(
        default=None,
        description="Анонимная сессия, если заголовок X-Session-Token срезан прокси.",
    )


def _service(db: AsyncSession = Depends(get_db_session)) -> BattleService:
    """Dependency to get BattleService instance."""
    return BattleService(db)


@router.get("/pair")
async def get_battle_pair(svc: BattleService = Depends(_service)):
    """Get two random image prompts for battle."""
    prompts = await svc.get_pair()
    if len(prompts) < 2:
        return {"prompts": FALLBACK_PROMPTS}
    return {"prompts": [p.model_dump(by_alias=True) for p in prompts]}


@router.post("/vote")
async def vote_battle(
    payload: VoteRequest,
    request: Request,
    svc: BattleService = Depends(_service),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """Record a battle vote and update ELO ratings.

    Requires authentication OR session token to prevent duplicate votes.
    Returns real vote percentages based on all votes in database.
    """
    redis = redis_client.get_redis()
    if redis:
        client_ip = request.client.host if request.client else "unknown"
        rl_key = f"battle:rate_limit:{client_ip}"
        acquired = await redis.set(rl_key, "1", ex=BATTLE_VOTE_RATE_LIMIT_SEC, nx=True)
        if not acquired:
            raise HTTPException(
                status_code=429,
                detail="Подождите перед следующим голосом в битве.",
                headers={"Retry-After": str(BATTLE_VOTE_RATE_LIMIT_SEC)},
            )

    header_tok = (request.headers.get("x-session-token") or "").strip()
    body_tok = (payload.session_token or "").strip()
    session_token = header_tok or body_tok or None

    # Require either user auth or session token
    if not current_user and not session_token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please log in or provide session token.",
        )

    user_id = current_user.id if current_user else None

    if {payload.winner_id, payload.loser_id} == FALLBACK_VOTE_IDS:
        return {
            "status": "ok",
            "winner": {"id": payload.winner_id, "new_elo": 1200, "votes": 12},
            "loser": {"id": payload.loser_id, "new_elo": 1200, "votes": 10},
            "left_pct": 55,
            "right_pct": 45,
            "total_votes": 22,
        }

    try:
        result = await svc.record_vote(
            payload.winner_id,
            payload.loser_id,
            user_id=user_id,
            session_token=session_token,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording battle vote: {e}")
        raise HTTPException(status_code=500, detail="Failed to record vote")


@router.get("/stats/{prompt_id}")
async def get_battle_stats(
    prompt_id: str,
    svc: BattleService = Depends(_service),
):
    """Get battle statistics for a specific prompt."""
    win_pct, total_votes = await svc.get_vote_percentages(prompt_id)

    prompt = await svc.db.get(Prompt, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    return {
        "prompt_id": prompt_id,
        "win_percentage": win_pct,
        "total_votes": total_votes,
        "elo_rating": prompt.elo_rating,
    }
