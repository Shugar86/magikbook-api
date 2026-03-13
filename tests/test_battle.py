import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app

@pytest.mark.asyncio
async def test_vote_success(monkeypatch):
    class DummyRedis:
        async def incr(self, key):
            pass

    import src.redis_client
    monkeypatch.setattr(src.redis_client, "get_redis", lambda: DummyRedis())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/battle/vote", json={
            "winner_id": "1",
            "loser_id": "2"
        })
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "message": "Vote recorded successfully."}

@pytest.mark.asyncio
async def test_vote_redis_failure(monkeypatch):
    import src.redis_client
    monkeypatch.setattr(src.redis_client, "get_redis", lambda: None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/battle/vote", json={
            "winner_id": "1",
            "loser_id": "2"
        })
        assert response.status_code == 500
        assert response.json()["detail"] == "Redis connection failed"
