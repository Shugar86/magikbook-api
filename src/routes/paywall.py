"""
Paywall routes: Telegram Stars and Social Paywall (subscription checking).
"""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_db_session
from src.dependencies import get_current_user
from src.models.db_models import User

router = APIRouter(prefix="/api/paywall")
logger = logging.getLogger(__name__)


class StarsPaymentRequest(BaseModel):
    stars_amount: int = 50


class SubscriptionCheckRequest(BaseModel):
    channel_username: str  # e.g. "@MagikBook_Sponsor"


@router.post("/stars")
async def buy_mana_with_stars(
    payload: StarsPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Buy mana with Telegram Stars.
    Requires proper Telegram Payments v2 / Stars webhook integration.
    Stars payments must be initiated from the Telegram Bot side, not from a web request.
    See: https://core.telegram.org/bots/payments
    """
    raise HTTPException(
        status_code=501,
        detail=(
            "Telegram Stars payments require a bot-side integration. "
            "Initiate the payment through the Telegram bot, which sends a webhook to /api/payments/stars/webhook."
        ),
    )


async def _check_telegram_subscription(
    telegram_user_id: int, channel_username: str
) -> bool:
    """
    Calls Telegram Bot API getChatMember to check if user is subscribed to a channel.
    Returns True if the user is a member/admin/creator, False otherwise.
    """
    bot_token = settings.telegram_bot_token
    if not bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — cannot verify subscription.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/getChatMember"
    params = {
        "chat_id": channel_username,
        "user_id": telegram_user_id,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
        data = resp.json()
        if not data.get("ok"):
            logger.warning("getChatMember error: %s", data.get("description"))
            return False
        status = data["result"]["status"]
        return status in ("member", "administrator", "creator")
    except Exception as e:
        logger.error("Error calling Telegram getChatMember: %s", e)
        return False


@router.post("/check-subscription")
async def check_telegram_subscription(
    payload: SubscriptionCheckRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Check if user is subscribed to a Telegram channel and grant mana reward.
    Uses current_user.telegram_id which is verified during Telegram login.
    """
    if not current_user.telegram_id:
        raise HTTPException(
            status_code=400,
            detail="Необходима авторизация через Telegram для проверки подписки.",
        )

    is_subscribed = await _check_telegram_subscription(
        int(current_user.telegram_id), payload.channel_username
    )

    if not is_subscribed:
        raise HTTPException(
            status_code=403,
            detail=f"Подписка на {payload.channel_username} не найдена. Сначала подпишись на канал.",
        )

    bonus_mana = 10
    current_user.tokens += bonus_mana
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    logger.info(
        "User %s received %d mana for subscribing to %s",
        current_user.id,
        bonus_mana,
        payload.channel_username,
    )
    return {
        "status": "ok",
        "message": f"Бонус +{bonus_mana} маны за подписку на {payload.channel_username}!",
        "tokens": current_user.tokens,
        "channel": payload.channel_username,
    }


@router.get("/sponsor-channel")
async def get_sponsor_channel():
    """Returns the current sponsor channel for social paywall."""
    return {
        "channel_username": "@MagikBook_Sponsor",
        "channel_url": "https://t.me/MagikBook_Sponsor",
        "invite_url": "https://t.me/+m1YFPmoim_plYzUy",
        "reward_mana": 10,
        "description": "Подпишись на канал спонсора и получи +10 генераций бесплатно!",
    }
