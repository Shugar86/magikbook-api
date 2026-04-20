import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.routes import auth, battle, cabinet, generate, grimoire, prompts, paywall, test_setup, uploads, moderation, publish, users
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
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
    openapi_url="/openapi.json" if settings.environment == "development" else None,
)

allowed_origins = [settings.frontend_url]
if settings.environment == "development":
    allowed_origins += [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate.router)
app.include_router(battle.router)
app.include_router(grimoire.router)
app.include_router(auth.router)
app.include_router(users.router)
# uploads before prompts: /api/prompts/my-uploads must not match /api/prompts/{prompt_id}
app.include_router(uploads.router)
app.include_router(prompts.router)
app.include_router(paywall.router)
app.include_router(moderation.router)
app.include_router(publish.router)
app.include_router(cabinet.router)

if settings.environment == "development":
    app.include_router(test_setup.router)
    logger.warning("⚠️  test_setup router ENABLED (dev mode only!)")

import os
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/health")
async def health_check():
    return {"status": "ok"}
