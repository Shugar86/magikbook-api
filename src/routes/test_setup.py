import os
import logging
from fastapi import APIRouter, Header, HTTPException
from sqlmodel import SQLModel

from src.database import engine

router = APIRouter(prefix="/api/test_setup", tags=["Testing"])
logger = logging.getLogger(__name__)


@router.post("/reset")
async def reset_database(x_test_token: str = Header(None)):
    expected_token = os.getenv("E2E_TEST_TOKEN")
    if not expected_token or x_test_token != expected_token:
        logger.warning(
            f"Unauthorized E2E reset attempt. Expected: {expected_token}, Got: {x_test_token}"
        )
        raise HTTPException(status_code=403, detail="Invalid or missing X-Test-Token")

    logger.info("Dropping and recreating all tables for E2E testing...")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    logger.info(
        "Database reset complete. Seeding removed — add seed data manually if needed."
    )

    return {"status": "ok", "message": "Database reset complete (seeding removed)."}
