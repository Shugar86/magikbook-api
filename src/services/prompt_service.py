"""PromptService — вся бизнес-логика работы с промптами.

Роуты в routes/prompts.py только вызывают методы этого класса.
"""
import json
import logging
import re
from typing import Optional, Sequence

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db_models import Like, Prompt, User
from src.models.schemas import (
    FeedResponse,
    HomepageResponse,
    LikeResponse,
    OgMeta,
    PortfolioResponse,
    PortfolioUserPublic,
    PromptCreate,
    PromptOut,
    SiteStats,
)
from src.redis_client import get_redis
from src.category_labels import merged_category_values_for_filters

logger = logging.getLogger(__name__)


class PromptService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _authors_by_ids(self, author_ids: Sequence[Optional[str]]) -> dict[str, tuple[str, Optional[str]]]:
        """Load username and avatar_url for distinct author IDs."""
        unique = {aid for aid in author_ids if aid}
        if not unique:
            return {}
        result = await self.db.execute(select(User).where(User.id.in_(unique)))
        users = result.scalars().all()
        return {u.id: (u.username, u.avatar_url) for u in users}

    def _prompt_out_with_authors(
        self, prompt: Prompt, authors: dict[str, tuple[str, Optional[str]]]
    ) -> PromptOut:
        """Build PromptOut and attach author display fields when available."""
        base = PromptOut.model_validate(prompt)
        if not prompt.author_id:
            return base
        info = authors.get(prompt.author_id)
        if not info:
            return base
        username, avatar_url = info
        return base.model_copy(
            update={"author_username": username, "author_avatar_url": avatar_url}
        )

    async def _serialize_prompts_with_authors(self, prompts: Sequence[Prompt]) -> list[PromptOut]:
        """Batch-resolve authors for a list of prompts."""
        authors = await self._authors_by_ids([p.author_id for p in prompts])
        return [self._prompt_out_with_authors(p, authors) for p in prompts]

    # ─── Статистика ────────────────────────────────────────────

    async def get_stats(self) -> SiteStats:
        """Get site-wide prompt statistics."""
        text_count = await self.db.scalar(
            select(func.count())
            .select_from(Prompt)
            .where(Prompt.media_type == "text")
            .where(Prompt.moderation_status.in_(["approved", "published"]))
        ) or 0
        image_count = await self.db.scalar(
            select(func.count())
            .select_from(Prompt)
            .where(Prompt.media_type.in_(["image", "video"]))
            .where(Prompt.moderation_status.in_(["approved", "published"]))
        ) or 0
        return SiteStats(
            text_count=text_count,
            image_count=image_count,
            total_count=text_count + image_count,
        )

    # ─── Главная страница ───────────────────────────────────────

    async def get_homepage_data(self) -> HomepageResponse:
        """Get data for homepage: trending text, trending media, daily prompt."""
        text_result = await self.db.execute(
            select(Prompt)
            .where(Prompt.media_type == "text")
            .where(Prompt.moderation_status.in_(["approved", "published"]))
            .order_by(Prompt.likes_count.desc())
            .limit(6)
        )
        trending_text = text_result.scalars().all()

        media_result = await self.db.execute(
            select(Prompt)
            .where(Prompt.media_type.in_(["image", "video"]))
            .where(Prompt.moderation_status.in_(["approved", "published"]))
            .order_by(Prompt.elo_rating.desc())
            .limit(8)
        )
        trending_media = media_result.scalars().all()

        daily_prompt = trending_text[0] if trending_text else None
        stats = await self.get_stats()

        text_out = await self._serialize_prompts_with_authors(trending_text)
        media_out = await self._serialize_prompts_with_authors(trending_media)
        daily_out = (
            (await self._serialize_prompts_with_authors([daily_prompt]))[0]
            if daily_prompt
            else None
        )
        return HomepageResponse(
            trending_text=text_out,
            trending_media=media_out,
            daily_prompt=daily_out,
            stats=stats,
        )

    # ─── Лента ─────────────────────────────────────────────────

    async def get_feed(
        self,
        media_type: Optional[str] = None,
        category: Optional[Sequence[str]] = None,
        filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> FeedResponse:
        """Get paginated feed of prompts with filters."""
        query = select(Prompt).where(
            Prompt.moderation_status.in_(["approved", "published"])
        )
        if media_type:
            query = query.where(Prompt.media_type == media_type)
        cat_vals: list[str] = []
        if category:
            cat_vals = merged_category_values_for_filters(list(category))
        if cat_vals:
            query = query.where(Prompt.category.in_(cat_vals))

        if filter == "trending":
            query = query.order_by(Prompt.elo_rating.desc())
        elif filter == "new":
            query = query.order_by(Prompt.created_at.desc())
        elif filter == "best":
            query = query.order_by(Prompt.likes_count.desc())
        else:
            query = query.order_by(Prompt.created_at.desc())

        offset = (page - 1) * page_size
        result = await self.db.execute(query.offset(offset).limit(page_size))
        prompts = result.scalars().all()

        count_q = (
            select(func.count())
            .select_from(Prompt)
            .where(Prompt.moderation_status.in_(["approved", "published"]))
        )
        if media_type:
            count_q = count_q.where(Prompt.media_type == media_type)
        if cat_vals:
            count_q = count_q.where(Prompt.category.in_(cat_vals))
        total = await self.db.scalar(count_q) or 0

        prompts_out = await self._serialize_prompts_with_authors(prompts)
        return FeedResponse(
            prompts=prompts_out,
            total_count=total,
            page=page,
            page_size=page_size,
            has_more=total > (offset + len(prompts)),
        )

    # ─── Отдельный промпт ──────────────────────────────────────

    async def get_by_id(self, prompt_id: str) -> PromptOut:
        """Get single prompt by ID."""
        prompt = await self.db.get(Prompt, prompt_id)
        if not prompt or prompt.moderation_status not in ("approved", "published"):
            raise HTTPException(status_code=404, detail="Prompt not found")
        authors = await self._authors_by_ids([prompt.author_id])
        return self._prompt_out_with_authors(prompt, authors)

    async def get_public_portfolio(self, username: str) -> PortfolioResponse:
        """Public media prompts for a user by username (approved/published only)."""
        user_row = await self.db.execute(select(User).where(User.username == username))
        user = user_row.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        media_result = await self.db.execute(
            select(Prompt)
            .where(Prompt.author_id == user.id)
            .where(Prompt.media_type.in_(["image", "video"]))
            .where(Prompt.moderation_status.in_(["approved", "published"]))
            .order_by(Prompt.elo_rating.desc())
        )
        prompts = media_result.scalars().all()
        authors_map: dict[str, tuple[str, Optional[str]]] = {
            user.id: (user.username, user.avatar_url)
        }
        prompts_out = [self._prompt_out_with_authors(p, authors_map) for p in prompts]
        return PortfolioResponse(
            user=PortfolioUserPublic(username=user.username, avatar_url=user.avatar_url),
            prompts=prompts_out,
        )

    async def get_og_meta(self, prompt_id: str) -> OgMeta:
        """Get OpenGraph metadata for a prompt."""
        prompt = await self.db.get(Prompt, prompt_id)
        if not prompt or prompt.moderation_status not in ("approved", "published"):
            raise HTTPException(status_code=404, detail="Prompt not found")
        return OgMeta(
            title=f"{prompt.title} — MagikBook",
            description=prompt.prompt_text[:160],
            image=prompt.result_image_url or prompt.preview_url,
            category=prompt.category,
            media_type=prompt.media_type,
            prompt_id=prompt.id,
        )

    # ─── Создание промпта ──────────────────────────────────────

    async def publish(self, payload: PromptCreate, author_id: str) -> PromptOut:
        """Create a new prompt."""
        prompt_text = payload.prompt_text.strip()
        variables = list(set(re.findall(r"\{([^}]+)\}", prompt_text)))
        variables_str = json.dumps(variables, ensure_ascii=False) if variables else None

        # Use user-provided target_models if available, otherwise use defaults
        if payload.target_models is not None:
            target_models = payload.target_models
        elif payload.media_type == "text":
            target_models = ["ChatGPT", "Claude"]
        else:
            target_models = []
        target_models_str = json.dumps(target_models) if target_models else None

        # Handle affiliate_links if provided
        affiliate_links_str = None
        if payload.affiliate_links:
            affiliate_links_str = json.dumps(payload.affiliate_links, ensure_ascii=False)

        prompt = Prompt(
            title=payload.title.strip() or "Без названия",
            prompt_text=prompt_text,
            category=payload.category,
            media_type=payload.media_type,
            preview_url=payload.preview_url,
            author_id=author_id,
            variables_str=variables_str,
            target_models_str=target_models_str,
            result_example=payload.result_example,
            result_image_url=payload.result_image_url,
            affiliate_links_str=affiliate_links_str,
        )
        self.db.add(prompt)
        await self.db.commit()
        await self.db.refresh(prompt)
        authors = await self._authors_by_ids([prompt.author_id])
        return self._prompt_out_with_authors(prompt, authors)

    # ─── Лайки ─────────────────────────────────────────────────

    async def like(self, prompt_id: str, actor: str, client_ip: str) -> LikeResponse:
        """Like a prompt with rate limiting."""
        redis = get_redis()
        if redis:
            rl_key = f"like:rate_limit:{actor}:{client_ip}"
            acquired = await redis.set(rl_key, "1", ex=2, nx=True)
            if not acquired:
                raise HTTPException(status_code=429, detail="Too Many Requests")

        prompt = await self.db.get(Prompt, prompt_id)
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")

        existing = await self.db.execute(
            select(Like).where(
                Like.user_session == actor,
                Like.prompt_id == prompt_id,
            )
        )
        if existing.scalar_one_or_none():
            return LikeResponse(
                status="ok",
                message="Already liked",
                likes_count=prompt.likes_count,
            )

        self.db.add(Like(user_session=actor, prompt_id=prompt_id))
        prompt.likes_count += 1
        try:
            await self.db.commit()
            await self.db.refresh(prompt)
        except IntegrityError:
            await self.db.rollback()
            return LikeResponse(
                status="ok",
                message="Already liked",
                likes_count=prompt.likes_count - 1,
            )
        return LikeResponse(status="ok", likes_count=prompt.likes_count)

    # ─── Копирование ───────────────────────────────────────────

    async def increment_copy_count(
        self,
        prompt_id: str,
        client_ip: str = "unknown",
        session_token: Optional[str] = None,
    ) -> dict:
        """Increment copy count for a prompt with rate limiting."""
        redis = get_redis()
        actor = session_token or client_ip
        if redis:
            acquired = await redis.set(f"copy:rate_limit:{actor}", "1", ex=10, nx=True)
            if not acquired:
                raise HTTPException(status_code=429, detail="Too Many Requests")

        prompt = await self.db.get(Prompt, prompt_id)
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        prompt.copies += 1
        await self.db.commit()
        return {"status": "ok", "copies": prompt.copies}
