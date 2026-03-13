"""Сервис для публикации промптов в Telegram канал."""

from typing import Optional
import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


async def publish_to_telegram(
    title: str,
    prompt_text: str,
    ai_model: Optional[str],
    file_path: str,
    media_type: str,  # "image" | "video"
    prompt_id: str
) -> dict:
    """
    Публикация промпта в Telegram канал.

    Args:
        title: Название промпта
        prompt_text: Текст промпта
        ai_model: Название нейросети
        file_path: Путь к файлу
        media_type: Тип медиа ("image" или "video")
        prompt_id: ID промпта для ссылки

    Returns:
        dict: {message_id, message_url}

    Raises:
        Exception: При ошибке публикации
    """
    if not settings.telegram_bot_token or not settings.telegram_channel_id:
        raise ValueError("Telegram credentials not configured")

    # Формируем подпись
    caption = _format_telegram_caption(title, prompt_text, ai_model, prompt_id)

    # Определяем метод отправки в зависимости от типа медиа
    if media_type == "image":
        method = "sendPhoto"
        file_param = "photo"
    elif media_type == "video":
        method = "sendVideo"
        file_param = "video"
    else:
        raise ValueError(f"Unsupported media_type: {media_type}")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"

    # Отправляем файл с подписью
    async with httpx.AsyncClient() as client:
        with open(file_path, "rb") as f:
            files = {file_param: (file_path.split("/")[-1], f, _get_mime_type(media_type))}
            data = {
                "chat_id": settings.telegram_channel_id,
                "caption": caption,
                "parse_mode": "HTML",
            }

            response = await client.post(url, data=data, files=files, timeout=60.0)

    if response.status_code != 200:
        raise Exception(f"Telegram API error: {response.text}")

    result = response.json()

    if not result.get("ok"):
        error_desc = result.get("description", "Unknown error")
        raise Exception(f"Telegram API error: {error_desc}")

    message_id = result["result"]["message_id"]
    chat_id = result["result"]["chat"]["id"]

    # Формируем URL сообщения
    if settings.telegram_channel_id.startswith("@"):
        channel_name = settings.telegram_channel_id.lstrip("@")
        message_url = f"https://t.me/{channel_name}/{message_id}"
    else:
        # Для числового ID канала используем прямую ссылку
        message_url = f"https://t.me/c/{str(chat_id).replace('-100', '')}/{message_id}"

    logger.info(f"Published to Telegram: {message_url}")

    return {
        "message_id": message_id,
        "message_url": message_url,
    }


def _format_telegram_caption(
    title: str,
    prompt_text: str,
    ai_model: Optional[str],
    prompt_id: str
) -> str:
    """Форматирует подпись для Telegram."""
    # Экранируем HTML-символы в тексте
    def escape_html(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    lines = [
        f"<b>{escape_html(title)}</b>",
        "",
        "Промпт:",
        f"<code>{escape_html(prompt_text[:3000])}</code>",  # Ограничение Telegram
    ]

    if ai_model:
        lines.extend(["", f"Нейросеть: {escape_html(ai_model)}"])

    lines.extend(["", f"👉 <a href='https://magikbook.ru/prompt/{prompt_id}'>magikbook.ru</a>"])

    caption = "\n".join(lines)

    # Telegram ограничение на длину подписи (1024 символа для фото/видео)
    if len(caption) > 1024:
        truncated_text = escape_html(prompt_text[:500])
        caption = (
            f"<b>{escape_html(title)}</b>\n\n"
            f"Промпт:\n<code>{truncated_text}...</code>\n\n"
            f"👉 <a href='https://magikbook.ru/prompt/{prompt_id}'>magikbook.ru</a>"
        )

    return caption


def _get_mime_type(media_type: str) -> str:
    """Возвращает MIME-тип по media_type."""
    mapping = {
        "image": "image/jpeg",
        "video": "video/mp4",
    }
    return mapping.get(media_type, "application/octet-stream")


async def check_telegram_config() -> bool:
    """Проверяет настроена ли интеграция с Telegram."""
    return bool(settings.telegram_bot_token and settings.telegram_channel_id)


async def send_text_message(text: str) -> dict:
    """
    Отправляет текстовое сообщение в канал (для уведомлений).

    Args:
        text: Текст сообщения

    Returns:
        dict: Результат отправки
    """
    if not settings.telegram_bot_token or not settings.telegram_channel_id:
        raise ValueError("Telegram credentials not configured")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={
            "chat_id": settings.telegram_channel_id,
            "text": text,
            "parse_mode": "HTML",
        })

    if response.status_code != 200:
        raise Exception(f"Telegram API error: {response.text}")

    result = response.json()
    if not result.get("ok"):
        raise Exception(f"Telegram API error: {result.get('description', 'Unknown error')}")

    return result["result"]
