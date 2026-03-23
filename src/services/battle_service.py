"""BattleService — ELO система сравнения промптов.

Формула ELO:
  E_a = 1 / (1 + 10^((R_b - R_a) / 400))
  R_a_new = R_a + K * (1 - E_a)   для победителя
  R_b_new = R_b + K * (0 - E_b)   для проигравшего
  K = 32 (стандартный коэффициент)
  Минимальный рейтинг: 800
"""
import logging
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db_models import Prompt
from src.models.schemas import PromptOut
from src.services.elo_service import EloService

logger = logging.getLogger(__name__)

ELO_K = 32
ELO_MIN = 800


class BattleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_pair(self) -> list[PromptOut]:
        """Get a random pair of image prompts for battle."""
        result = await self.db.execute(
            select(Prompt)
            .where(Prompt.media_type == "image")
            .where(Prompt.moderation_status.in_(["approved", "published"]))
            .order_by(func.random())
            .limit(2)
        )
        return [PromptOut.model_validate(p) for p in result.scalars().all()]

    async def record_vote(self, winner_id: str, loser_id: str) -> dict:
        """Record a battle vote and update ELO ratings."""
        from fastapi import HTTPException

        winner = await self.db.get(Prompt, winner_id)
        loser = await self.db.get(Prompt, loser_id)

        if not winner or not loser:
            raise HTTPException(status_code=404, detail="One or both prompts not found")

        # Calculate new ELO ratings using EloService
        new_winner_elo, new_loser_elo = EloService.calculate_new_ratings(
            winner.elo_rating, loser.elo_rating, k_factor=ELO_K
        )

        # Apply minimum rating floor
        new_loser_elo = max(new_loser_elo, ELO_MIN)

        winner.elo_rating = new_winner_elo
        loser.elo_rating = new_loser_elo

        # Automatically mark trending if rating > 1400
        winner.is_trending = new_winner_elo > 1400
        loser.is_trending = new_loser_elo > 1400

        await self.db.commit()

        logger.info(
            "ELO updated: winner %s %d→%d, loser %s %d→%d",
            winner_id,
            winner.elo_rating,
            new_winner_elo,
            loser_id,
            loser.elo_rating,
            new_loser_elo,
        )

        return {
            "status": "ok",
            "winner": {"id": winner_id, "new_elo": new_winner_elo},
            "loser": {"id": loser_id, "new_elo": new_loser_elo},
        }
