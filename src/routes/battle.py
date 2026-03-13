import logging
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.database import get_db_session
from src.models.db_models import Prompt
import src.redis_client as redis_client

router = APIRouter(prefix="/api/battle")
logger = logging.getLogger(__name__)

class VoteRequest(BaseModel):
    winner_id: str
    loser_id: str

@router.post("/vote")
async def vote_battle(payload: VoteRequest, request: Request):
    redis = redis_client.get_redis()
    if not redis:
        raise HTTPException(status_code=500, detail="Redis connection failed")
        
    client_ip = request.client.host if request.client else "unknown"
    rl_key = f"battle:rate_limit:{client_ip}"
    
    # Atomically check and set rate limit (2 seconds)
    acquired = await redis.set(rl_key, "1", ex=2, nx=True)
    if not acquired:
        raise HTTPException(status_code=429, detail="Too Many Requests")
    
    # Store wins and losses in Redis for batch processing
    await redis.incr(f"battle:{payload.winner_id}:wins")
    await redis.incr(f"battle:{payload.loser_id}:losses")
    
    return {"status": "ok", "message": "Vote recorded successfully."}

@router.get("/pair")
async def get_battle_pair(db: AsyncSession = Depends(get_db_session)):
    # Simple approach: fetch two random prompts.
    # A more advanced approach could group by Elo. 
    result = await db.execute(select(Prompt).where(Prompt.media_type == "image").order_by(func.random()).limit(2))
    prompts = result.scalars().all()
    
    if len(prompts) < 2:
        return {
            "prompts": [
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
        }
        
    return {
        "prompts": [
            {
                "id": p.id,
                "title": p.title,
                "prompt_text": p.prompt_text,
                "preview_url": p.preview_url,
                "category": p.category,
                "elo_rating": p.elo_rating
            } for p in prompts
        ]
    }
