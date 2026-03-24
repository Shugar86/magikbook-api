"""BattleService — ELO система сравнения промптов с подсчетом голосов.

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

from src.models.db_models import Prompt, BattleVote
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

    async def check_already_voted(
        self, winner_id: str, loser_id: str, user_id: str = None, session_token: str = None
    ) -> bool:
        """Check if user already voted on this specific pair."""
        if user_id:
            result = await self.db.execute(
                select(BattleVote).where(
                    BattleVote.user_id == user_id,
                    BattleVote.winner_id == winner_id,
                    BattleVote.loser_id == loser_id,
                )
            )
            return result.scalar_one_or_none() is not None
        elif session_token:
            result = await self.db.execute(
                select(BattleVote).where(
                    BattleVote.session_token == session_token,
                    BattleVote.winner_id == winner_id,
                    BattleVote.loser_id == loser_id,
                )
            )
            return result.scalar_one_or_none() is not None
        return False

    async def get_vote_percentages(self, prompt_id: str) -> tuple[int, int]:
        """Get vote percentages for a prompt in all its battles.
        
        Returns: (win_percentage, total_votes)
        """
        # Count wins
        wins_result = await self.db.execute(
            select(func.count()).where(BattleVote.winner_id == prompt_id)
        )
        wins = wins_result.scalar() or 0

        # Count losses
        losses_result = await self.db.execute(
            select(func.count()).where(BattleVote.loser_id == prompt_id)
        )
        losses = losses_result.scalar() or 0

        total = wins + losses
        if total == 0:
            return 0, 0

        win_pct = round((wins / total) * 100)
        return win_pct, total

    async def record_vote(
        self, winner_id: str, loser_id: str, user_id: str = None, session_token: str = None
    ) -> dict:
        """Record a battle vote and update ELO ratings."""
        from fastapi import HTTPException

        winner = await self.db.get(Prompt, winner_id)
        loser = await self.db.get(Prompt, loser_id)

        if not winner or not loser:
            raise HTTPException(status_code=404, detail="One or both prompts not found")

        # Check if already voted
        already_voted = await self.check_already_voted(winner_id, loser_id, user_id, session_token)
        if already_voted:
            raise HTTPException(status_code=409, detail="You already voted on this battle")

        # Record the vote
        vote = BattleVote(
            user_id=user_id,
            session_token=session_token,
            winner_id=winner_id,
            loser_id=loser_id,
        )
        self.db.add(vote)

        # Save old ELO values before updating
        old_winner_elo = winner.elo_rating
        old_loser_elo = loser.elo_rating

        # Calculate new ELO ratings using EloService
        new_winner_elo, new_loser_elo = EloService.calculate_new_ratings(
            old_winner_elo, old_loser_elo, k_factor=ELO_K
        )

        # Apply minimum rating floor
        new_loser_elo = max(new_loser_elo, ELO_MIN)

        winner.elo_rating = new_winner_elo
        loser.elo_rating = new_loser_elo

        # Automatically mark trending if rating > 1400
        winner.is_trending = new_winner_elo > 1400
        loser.is_trending = new_loser_elo > 1400

        await self.db.commit()

        # Calculate real vote percentages
        left_pct, left_votes = await self.get_vote_percentages(winner_id)
        right_pct, right_votes = await self.get_vote_percentages(loser_id)

        # Normalize percentages to sum to 100
        total_votes = left_votes + right_votes
        if total_votes > 0:
            left_pct = round((left_votes / total_votes) * 100)
            right_pct = 100 - left_pct

        logger.info(
            "Battle vote recorded: user=%s, winner=%s %d→%d (votes: %d), loser=%s %d→%d (votes: %d)",
            user_id or session_token[:8] if session_token else "anon",
            winner_id,
            old_winner_elo,
            new_winner_elo,
            left_votes,
            loser_id,
            old_loser_elo,
            new_loser_elo,
            right_votes,
        )

        return {
            "status": "ok",
            "winner": {"id": winner_id, "new_elo": new_winner_elo, "votes": left_votes},
            "loser": {"id": loser_id, "new_elo": new_loser_elo, "votes": right_votes},
            "left_pct": left_pct,
            "right_pct": right_pct,
            "total_votes": total_votes,
        }
