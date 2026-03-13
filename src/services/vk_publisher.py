"""Сервис для публикации промптов в VK группу."""

from typing import Optional
import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


async def publish_to_vk(
    title: str,
    prompt_text: str,
    ai_model: Optional[str],
    file_path: str,
    prompt_id: str
) -> dict:
    """
    Публикация промпта в VK группу.

    Args:
        title: Название промпта
        prompt_text: Текст промпта
        ai_model: Название нейросети
        file_path: Путь к файлу изображения/видео
        prompt_id: ID промпта для ссылки

    Returns:
        dict: {post_id, post_url, photo_url}

    Raises:
        Exception: При ошибке публикации
    """
    if not settings.vk_access_token or not settings.vk_group_id:
        raise ValueError("VK credentials not configured")

    vk_group_id = settings.vk_group_id

    # Формируем сообщение
    message = _format_vk_message(title, prompt_text, ai_model, prompt_id)

    # 1. Загружаем фото на сервер VK
    try:
        photo_data = await _upload_photo_to_vk(file_path, vk_group_id)
    except Exception as e:
        logger.error(f"Failed to upload photo to VK: {e}")
        raise

    # 2. Создаем пост на стене группы
    attachments = f"photo{photo_data['owner_id']}_{photo_data['id']}"

    post_url = "https://api.vk.com/method/wall.post"
    post_params = {
        "access_token": settings.vk_access_token,
        "v": "5.199",  # Версия API
        "owner_id": vk_group_id,
        "from_group": 1,  # От имени группы
        "message": message,
        "attachments": attachments,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(post_url, params=post_params)

    if response.status_code != 200:
        raise Exception(f"VK wall.post failed: {response.text}")

    result = response.json()

    if "error" in result:
        error_msg = result["error"].get("error_msg", "Unknown error")
        raise Exception(f"VK API error: {error_msg}")

    post_id = result["response"].get("post_id")
    post_url = f"https://vk.com/wall{vk_group_id}_{post_id}"

    # URL фото для превью (берем максимальный размер)
    photo_url = photo_data.get("sizes", [{}])[-1].get("url", "")

    logger.info(f"Published to VK: {post_url}")

    return {
        "post_id": post_id,
        "post_url": post_url,
        "photo_url": photo_url,
    }


async def _upload_photo_to_vk(file_path: str, group_id: str) -> dict:
    """
    Загружает фото на сервер VK.

    Returns:
        dict: Информация о загруженном фото
    """
    # 1. Получаем URL сервера для загрузки
    upload_url_endpoint = "https://api.vk.com/method/photos.getWallUploadServer"
    upload_params = {
        "access_token": settings.vk_access_token,
        "v": "5.199",
        "group_id": group_id.lstrip("-"),  # Убираем минус если есть
    }

    async with httpx.AsyncClient() as client:
        upload_response = await client.get(upload_url_endpoint, params=upload_params)

    if upload_response.status_code != 200:
        raise Exception(f"Failed to get upload server: {upload_response.text}")

    upload_data = upload_response.json()
    if "error" in upload_data:
        raise Exception(f"VK API error: {upload_data['error']}")

    upload_url = upload_data["response"]["upload_url"]

    # 2. Загружаем файл на сервер
    async with httpx.AsyncClient() as client:
        with open(file_path, "rb") as f:
            files = {"photo": (file_path.split("/")[-1], f, "image/jpeg")}
            file_response = await client.post(upload_url, files=files)

    if file_response.status_code != 200:
        raise Exception(f"Failed to upload file: {file_response.text}")

    file_data = file_response.json()

    # 3. Сохраняем фото
    save_url = "https://api.vk.com/method/photos.saveWallPhoto"
    save_params = {
        "access_token": settings.vk_access_token,
        "v": "5.199",
        "group_id": group_id.lstrip("-"),
        "photo": file_data.get("photo"),
        "server": file_data.get("server"),
        "hash": file_data.get("hash"),
    }

    async with httpx.AsyncClient() as client:
        save_response = await client.post(save_url, params=save_params)

    if save_response.status_code != 200:
        raise Exception(f"Failed to save photo: {save_response.text}")

    save_data = save_response.json()
    if "error" in save_data:
        raise Exception(f"VK API error: {save_data['error']}")

    return save_data["response"][0]


def _format_vk_message(
    title: str,
    prompt_text: str,
    ai_model: Optional[str],
    prompt_id: str
) -> str:
    """Форматирует сообщение для публикации в VK."""
    lines = [
        f"Название: {title}",
        "",
        "Промпт:",
        prompt_text[:2000],  # Ограничение VK
    ]

    if ai_model:
        lines.extend(["", f"Нейросеть: {ai_model}"])

    lines.extend(["", f"Источник: https://magikbook.ru/prompt/{prompt_id}"])

    return "\n".join(lines)


async def check_vk_config() -> bool:
    """Проверяет настроена ли интеграция с VK."""
    return bool(settings.vk_access_token and settings.vk_group_id)
