"""Security-related tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_test_setup_endpoint_not_available(client: AsyncClient):
    """test_setup endpoint should not be available in non-dev environment."""
    # Note: In test environment, ENVIRONMENT may be set to "development"
    # This test verifies the endpoint either returns 403 (wrong token) or 404 (not mounted)
    resp = await client.post(
        "/api/test_setup/reset",
        headers={"X-Test-Token": "some-token"},
    )
    # If environment=development: 403 (wrong token)
    # If environment=production: 404 (not mounted)
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_moderation_queue_requires_auth(client: AsyncClient):
    """Moderation queue should require authentication."""
    resp = await client.get("/api/moderation")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_approve_requires_auth(client: AsyncClient):
    """Approve endpoint should require authentication."""
    resp = await client.post("/api/moderation/some-id/approve")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reject_requires_auth(client: AsyncClient):
    """Reject endpoint should require authentication."""
    resp = await client.post("/api/moderation/some-id/reject")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_grant_requires_auth(client: AsyncClient):
    """Admin grant endpoint should require authentication."""
    resp = await client.post("/api/admin/grant/some-user-id")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Health check should be public and return 200."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
