import asyncio
import os
import glob
import logging
import uuid
import random

from sqlalchemy import select
from src.database import async_session_maker, init_db
from src.models.db_models import Prompt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# NOTE: This path should be configured via environment variable or config
# for different deployment environments. Default is for development.
TEMP_DIR = os.getenv("MAGICKBOOK_TEMP_DIR", "/home/tutoradmin/magikbook/temp")

async def import_temp_data():
    await init_db()
    async with async_session_maker() as session:
        txt_files = glob.glob(os.path.join(TEMP_DIR, "*.txt"))
        
        imported_count = 0
        for txt_path in txt_files:
            base_name = os.path.basename(txt_path)
            file_id = os.path.splitext(base_name)[0]
            
            # Read text
            with open(txt_path, "r", encoding="utf-8") as f:
                prompt_text = f.read().strip()
                
            if not prompt_text:
                continue
                
            # Determine media file
            media_type = "text"
            preview_url = None
            category = "art"
            title = prompt_text[:40] + "..." if len(prompt_text) > 40 else prompt_text
            
            # Check for corresponding media files
            if os.path.exists(os.path.join(TEMP_DIR, f"{file_id}.png")):
                media_type = "image"
                preview_url = f"/content/{file_id}.png"
            elif os.path.exists(os.path.join(TEMP_DIR, f"{file_id}.jpg")):
                media_type = "image"
                preview_url = f"/content/{file_id}.jpg"
            elif os.path.exists(os.path.join(TEMP_DIR, f"{file_id}.mp4")):
                media_type = "video"
                preview_url = f"/content/{file_id}.mp4"
                category = "video"
            else:
                category = "excuses"
                
            # Create Prompt
            new_prompt = Prompt(
                id=str(uuid.uuid4()),
                title=title,
                prompt_text=prompt_text,
                preview_url=preview_url,
                media_type=media_type,
                category=category,
                likes_count=random.randint(50, 500),
                elo_rating=random.randint(1200, 1800)
            )
            session.add(new_prompt)
            imported_count += 1
            
        await session.commit()
        logger.info(f"Successfully imported {imported_count} real prompts from @temp.")

if __name__ == "__main__":
    asyncio.run(import_temp_data())
