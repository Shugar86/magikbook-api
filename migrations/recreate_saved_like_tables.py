"""Migration: Recreate saved_prompts and likes tables with user_id FK.

Since tables are empty (0 rows), we can safely drop and recreate them
with the new schema using user_id foreign key instead of session_token.

Run with: python migrations/recreate_saved_like_tables.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlmodel import SQLModel

from src.database import engine
from src.models.db_models import SavedPrompt, Like  # noqa: F401 - needed for table creation


async def migrate():
    """Drop old tables and recreate with new schema."""
    print("Starting migration: Recreate saved_prompts and likes tables...")

    async with engine.begin() as conn:
        # Drop old tables if they exist
        print("Dropping old tables...")
        await conn.execute(text("DROP TABLE IF EXISTS saved_prompts"))
        await conn.execute(text("DROP TABLE IF EXISTS likes"))
        print("Old tables dropped.")

        # Create new tables with updated schema
        print("Creating new tables with user_id foreign keys...")
        await conn.run_sync(SQLModel.metadata.create_all)
        print("New tables created.")

    print("Migration completed successfully!")
    print("New schema:")
    print("  - saved_prompts: id, user_id (FK to users.id), prompt_id (FK to prompts.id)")
    print("  - likes: id, user_id (FK to users.id), prompt_id (FK to prompts.id)")


if __name__ == "__main__":
    asyncio.run(migrate())
