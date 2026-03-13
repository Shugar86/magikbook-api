import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.routes import auth, battle, generate, grimoire, prompts, paywall, test_setup, uploads, moderation, publish
from src.database import init_db
from src.redis_client import init_redis, close_redis
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to db, redis, etc.
    logger.info("Starting MagikBook API")
    await init_db()
    await init_redis()
    yield
    # Shutdown: close connections
    logger.info("Shutting down MagikBook API")
    await close_redis()


app = FastAPI(
    title="MagikBook API",
    description="Backend for MagikBook, AI prompt generation and rating system.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate.router)
app.include_router(battle.router)
app.include_router(grimoire.router)
app.include_router(auth.router)
app.include_router(prompts.router)
app.include_router(paywall.router)
app.include_router(uploads.router)
app.include_router(moderation.router)
app.include_router(publish.router)
app.include_router(test_setup.router)

import os
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/health")
async def health_check():
    return {"status": "ok"}
