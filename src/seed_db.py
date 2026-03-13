import asyncio
import logging
from sqlalchemy import select
from src.database import async_session_maker, init_db
from src.models.db_models import Prompt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

POPULAR_TEXT_CATEGORIES = [
    "excuses",
    "pickup",
    "resume",
    "contracts",
    "compliments",
    "toasts",
    "apologies",
    "flirt",
]

POPULAR_IMAGE_CATEGORIES = [
    "anime",
    "cyberpunk",
    "avatar",
    "art",
    "fantasy",
    "3d",
    "stickers",
    "portrait",
]


def build_text_seed_items() -> list[dict]:
    items: list[dict] = []
    for category in POPULAR_TEXT_CATEGORIES:
        for idx in range(1, 6):
            items.append(
                {
                    "id": f"text-{category}-{idx}",
                    "title": f"{category.capitalize()} шаблон {idx}",
                    "media_type": "text",
                    "preview_url": None,
                    "category": category,
                    "prompt_text": (
                        f"Создай качественный текстовый промпт по теме {category}. "
                        f"Версия {idx}. Укажи структуру, тон и 3 варианта формулировки."
                    ),
                    "likes": 200 + idx * 37,
                }
            )
    return items


def build_image_seed_items() -> list[dict]:
    items: list[dict] = []
    for category in POPULAR_IMAGE_CATEGORIES:
        for idx in range(1, 6):
            items.append(
                {
                    "id": f"image-{category}-{idx}",
                    "title": f"{category.capitalize()} визуал {idx}",
                    "media_type": "image",
                    "preview_url": f"https://picsum.photos/seed/{category}-{idx}/600/800",
                    "category": category,
                    "prompt_text": (
                        f"Сгенерируй изображение в стиле {category}, вариант {idx}, "
                        "с кинематографичным светом, детализированной сценой и чистой композицией."
                    ),
                    "likes": 300 + idx * 41,
                }
            )
    return items

async def seed():
    await init_db()
    async with async_session_maker() as session:
        # Check if already seeded
        result = await session.execute(select(Prompt).limit(1))
        existing = result.scalar_one_or_none()
        if existing:
            logger.info("Database already has prompts. Skipping seed.")
            return

        logger.info("Seeding prompts...")
        for item in [*build_image_seed_items(), *build_text_seed_items()]:
            prompt = Prompt(
                id=item["id"],
                title=item["title"],
                prompt_text=item["prompt_text"],
                preview_url=item["preview_url"],
                media_type=item["media_type"],
                category=item["category"],
                likes_count=item["likes"]
            )
            session.add(prompt)
        
        await session.commit()
        logger.info("Seeding complete.")

if __name__ == "__main__":
    asyncio.run(seed())
