import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app

@pytest.mark.asyncio
async def test_generate_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Mocking the generation so we don't hit real Google API
        # We assume the endpoint responds with text/event-stream
        response = await client.post("/api/generate", json={
            "category": "work",
            "model": "chatgpt",
            "style": "formal",
            "input": "test prompt"
        })
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

@pytest.mark.asyncio
async def test_generate_invalid_request():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Missing required fields
        response = await client.post("/api/generate", json={
            "category": "work"
        })
        assert response.status_code == 422
