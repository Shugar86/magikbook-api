"""Tests for prompt endpoints."""
import pytest
from httpx import AsyncClient


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
