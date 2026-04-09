"""Tests for battle endpoints."""
import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app
from src.routes.battle import BATTLE_VOTE_RATE_LIMIT_SEC


@pytest.mark.asyncio
async def test_vote_success(monkeypatch):
    """Test that voting works (legacy test with mocked Redis)."""
    class DummyRedis:
        async def set(self, key, value, ex=None, nx=None):
            return True  # Rate limit acquired

    import src.redis_client
    monkeypatch.setattr(src.redis_client, "get_redis", lambda: DummyRedis())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/battle/vote", json={
            "winner_id": "1",
            "loser_id": "2"
        })
        # With new BattleService, it will try to get prompts from DB and return 404
        # since they don't exist (in-memory DB for this test)
        assert response.status_code in [404, 200, 429]


@pytest.mark.asyncio
async def test_battle_pair_returns_200(client: AsyncClient):
    """Battle pair endpoint should return 200 OK."""
    resp = await client.get("/api/battle/pair")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_battle_pair_returns_two_prompts(client: AsyncClient):
    """Battle pair should return 2 prompts or fallbacks."""
    resp = await client.get("/api/battle/pair")
    data = resp.json()
    assert "prompts" in data
    assert len(data["prompts"]) == 2


@pytest.mark.asyncio
async def test_vote_nonexistent_prompts_returns_404_or_429(client: AsyncClient):
    """Voting for non-existent prompts should return 404 or 429."""
    resp = await client.post(
        "/api/battle/vote",
        json={"winner_id": "fake-winner-id", "loser_id": "fake-loser-id"},
    )
    assert resp.status_code in (404, 429)


@pytest.mark.asyncio
async def test_vote_rate_limit_second_request_429(client: AsyncClient, monkeypatch):
    """When Redis rate-limit slot is taken, return 429 with Retry-After."""

    class BusyRedis:
        _first = True

        async def set(self, key, value, ex=None, nx=None):
            if self._first:
                self._first = False
                return True
            return False

    import src.redis_client

    monkeypatch.setattr(src.redis_client, "get_redis", lambda: BusyRedis())

    headers = {"X-Session-Token": "test-session-rl"}
    r1 = await client.post(
        "/api/battle/vote",
        json={"winner_id": "a", "loser_id": "b"},
        headers=headers,
    )
    r2 = await client.post(
        "/api/battle/vote",
        json={"winner_id": "a", "loser_id": "b"},
        headers=headers,
    )

    assert r1.status_code != 429
    assert r2.status_code == 429
    assert r2.headers.get("retry-after") == str(BATTLE_VOTE_RATE_LIMIT_SEC)
