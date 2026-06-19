import logging
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.schemas import GenerateRequest
from src.services.gemini_service import GeminiService
from src.redis_client import get_redis
from src.dependencies import get_optional_user, get_db_session
from src.models.db_models import User

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/generate")
async def generate_prompt(
    request: GenerateRequest,
    req: Request,
    db: AsyncSession = Depends(get_db_session),
    x_session_token: str = Header(default=None),
    current_user: User | None = Depends(get_optional_user),
):
    if not (settings.google_api_key or "").strip():
        raise HTTPException(
            status_code=503,
            detail="Генерация промптов отключена: не задан GOOGLE_API_KEY.",
        )

    # Daily Mana tracking
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    redis = get_redis()

    if current_user:
        if current_user.tokens <= 0:
            raise HTTPException(status_code=402, detail="Магия иссякла")
        current_user.tokens -= 1
        db.add(current_user)
        await db.commit()
    else:
        identifier = x_session_token or req.client.host
        key = f"anon_uses:{identifier}:{today}"
        uses = await redis.get(key)
        uses_int = int(uses) if uses is not None else 0
        if uses_int >= 3:
            raise HTTPException(status_code=402, detail="Магия иссякла")
        # Increment with 24h TTL so the counter resets daily
        new_val = await redis.incr(key)
        if new_val == 1:
            # First use today: set 24h expiry (86400 seconds)
            await redis.expire(key, 86400)

    async def event_generator():
        try:
            async for chunk in GeminiService.generate_prompt_stream(request):
                # Send SSE data event
                yield {"event": "message", "data": json.dumps({"text": chunk})}
            # End of stream event
            yield {"event": "done", "data": json.dumps({"text": ""})}
        except Exception as e:
            logger.error(f"Error streaming response: {e}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())
