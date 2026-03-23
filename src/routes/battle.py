import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

import src.redis_client as redis_client
from src.database import get_db_session
from src.services.battle_service import BattleService

router = APIRouter(prefix="/api/battle")
logger = logging.getLogger(__name__)

FALLBACK_PROMPTS = [
    {
        "id": "fallback-left",
        "title": "Демо визуализация A",
        "prompt_text": "Кинематографичный кадр, детальный свет, магическая атмосфера.",
        "preview_url": "https://picsum.photos/seed/fallback-left/600/800",
        "category": "art",
        "elo_rating": 1200,
    },
    {
        "id": "fallback-right",
        "title": "Демо визуализация B",
        "prompt_text": "Эпичная сцена, контрастные тени, насыщенные цвета, фэнтези стиль.",
        "preview_url": "https://picsum.photos/seed/fallback-right/600/800",
        "category": "fantasy",
        "elo_rating": 1200,
    },
]


class VoteRequest(BaseModel):
    winner_id: str
    loser_id: str


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
):
    """Record a battle vote and update ELO ratings."""
    redis = redis_client.get_redis()
    if redis:
        client_ip = request.client.host if request.client else "unknown"
        rl_key = f"battle:rate_limit:{client_ip}"
        acquired = await redis.set(rl_key, "1", ex=2, nx=True)
        if not acquired:
            raise HTTPException(status_code=429, detail="Too Many Requests")
    return await svc.record_vote(payload.winner_id, payload.loser_id)
