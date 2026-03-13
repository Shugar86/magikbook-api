import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings

logger = logging.getLogger(__name__)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_async_engine(settings.database_url, echo=False, connect_args=connect_args)

async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session

async def init_db():
    from src.models.db_models import Like, Prompt, SavedPrompt, User
    from sqlmodel import SQLModel
    
    async with engine.begin() as conn:
        logger.info("Initializing database tables...")
        # To run simple sync metadata create_all
        await conn.run_sync(SQLModel.metadata.create_all)
        logger.info("Database tables initialized.")
