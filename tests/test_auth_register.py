"""Tests for password registration and login."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db_models import User

REGISTER_PAYLOAD = {
    "email": "user@mail.ru",
    "password": "password123",
    "username": "testuser",
}


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, db_session: AsyncSession):
    resp = await client.post("/api/auth/register", json=REGISTER_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "user@mail.ru"
    assert data["username"] == "testuser"
    assert "access_token" in data

    result = await db_session.execute(select(User).where(User.email == "user@mail.ru"))
    user = result.scalar_one()
    assert user.hashed_password.startswith("$2")
    assert user.auth_provider == "email"


@pytest.mark.asyncio
async def test_register_rejects_gmail(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register",
        json={**REGISTER_PAYLOAD, "email": "user@gmail.com"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_rejects_short_password(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register",
        json={**REGISTER_PAYLOAD, "password": "short"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_rejects_short_username(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register",
        json={**REGISTER_PAYLOAD, "username": "a"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(client: AsyncClient):
    first = await client.post("/api/auth/register", json=REGISTER_PAYLOAD)
    assert first.status_code == 200

    second = await client.post(
        "/api/auth/register",
        json={**REGISTER_PAYLOAD, "username": "other"},
    )
    assert second.status_code == 400
    assert second.json()["detail"] == "Email уже зарегистрирован"


@pytest.mark.asyncio
async def test_login_after_register(client: AsyncClient):
    reg = await client.post("/api/auth/register", json=REGISTER_PAYLOAD)
    assert reg.status_code == 200

    login = await client.post(
        "/api/auth/login",
        json={"email": "user@mail.ru", "password": "password123"},
    )
    assert login.status_code == 200
    assert login.json()["email"] == "user@mail.ru"
