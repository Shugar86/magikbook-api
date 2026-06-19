"""Tests for prompt endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db_models import Prompt


@pytest.mark.asyncio
async def test_homepage_returns_200(client: AsyncClient):
    """Homepage endpoint should return 200 OK."""
    resp = await client.get("/api/prompts/homepage")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_homepage_has_required_keys(client: AsyncClient):
    """Homepage response should contain all required fields."""
    resp = await client.get("/api/prompts/homepage")
    data = resp.json()
    assert "trending_text" in data
    assert "trending_media" in data
    assert "daily_prompt" in data
    assert "stats" in data
    assert "text_count" in data["stats"]
    assert "image_count" in data["stats"]
    assert "total_count" in data["stats"]


@pytest.mark.asyncio
async def test_feed_returns_200(client: AsyncClient):
    """Feed endpoint should return 200 OK."""
    resp = await client.get("/api/prompts/feed")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_feed_pagination_keys(client: AsyncClient):
    """Feed response should contain pagination fields."""
    resp = await client.get("/api/prompts/feed?page=1&page_size=5")
    data = resp.json()
    assert "prompts" in data
    assert "total_count" in data
    assert "page" in data
    assert "page_size" in data
    assert "has_more" in data
    assert isinstance(data["prompts"], list)


@pytest.mark.asyncio
async def test_feed_with_category_and_media_type_returns_200(client: AsyncClient):
    """Feed with category slug and media_type should return 200 (empty DB is ok)."""
    resp = await client.get(
        "/api/prompts/feed?category=anime&media_type=image&page_size=5"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "prompts" in data
    assert "total_count" in data


@pytest.mark.asyncio
async def test_feed_category_slug_matches_legacy_label_in_db(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Slug in query must match rows stored with legacy «emoji + title» category."""
    legacy = "🌸 Аниме"
    p = Prompt(
        id="test-legacy-anime-1",
        title="Anime test",
        prompt_text="x" * 40,
        media_type="image",
        category=legacy,
        moderation_status="published",
    )
    db_session.add(p)
    await db_session.commit()

    resp = await client.get(
        "/api/prompts/feed?category=anime&media_type=image&page_size=20"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] >= 1
    ids = [x["id"] for x in data["prompts"]]
    assert "test-legacy-anime-1" in ids


@pytest.mark.asyncio
async def test_get_nonexistent_prompt_returns_404(client: AsyncClient):
    """Getting a non-existent prompt should return 404."""
    resp = await client.get("/api/prompts/nonexistent-id-12345")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_og_meta_nonexistent_returns_404(client: AsyncClient):
    """OG meta for non-existent prompt should return 404."""
    resp = await client.get("/api/prompts/nonexistent-id-12345/og-meta")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_like_without_auth_returns_401(client: AsyncClient):
    """Liking without authentication should return 401."""
    resp = await client.post("/api/prompts/fake-id/like")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_publish_requires_auth(client: AsyncClient):
    """Publishing without authentication should return 401."""
    resp = await client.post(
        "/api/prompts/publish",
        json={
            "title": "Test",
            "prompt_text": "Test prompt text that is long enough",
            "category": "test",
        },
    )
    assert resp.status_code == 401
