import pytest
from httpx import AsyncClient, ASGITransport

from src.main import app


class _MemoryRedis:
    """Минимальный in-memory Redis для анонимного счётчика в /api/generate."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def incr(self, key: str) -> int:
        cur = int(self._data.get(key, "0"))
        nxt = cur + 1
        self._data[key] = str(nxt)
        return nxt

    async def expire(self, key: str, seconds: int) -> bool:
        return True


class _MockGemini:
    @staticmethod
    async def generate_prompt_stream(request):  # noqa: ANN001
        yield "test-chunk"


@pytest.mark.asyncio
async def test_generate_success(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.routes.generate as generate_route
    from src.config import settings

    monkeypatch.setattr(settings, "google_api_key", "test-key-for-ci")
    # В модуле generate уже импортирован get_redis — патчим ссылку в этом модуле.
    monkeypatch.setattr(generate_route, "get_redis", lambda: _MemoryRedis())
    monkeypatch.setattr(generate_route, "GeminiService", _MockGemini)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/generate",
            json={
                "category": "work",
                "model": "chatgpt",
                "style": "formal",
                "input": "test prompt",
            },
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_generate_invalid_request() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/generate",
            json={"category": "work"},
        )
        assert response.status_code == 422
