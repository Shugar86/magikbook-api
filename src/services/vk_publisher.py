"""Сервис для публикации промптов в VK группу."""

from __future__ import annotations

import json
import logging
import mimetypes
from pathlib import Path
from typing import Any, Optional

import httpx

from src.config import settings
from src.utils.file_storage import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS

logger = logging.getLogger(__name__)

VK_API_VERSION = "5.199"
# Таймаут загрузки крупного видео на сервер VK (сек).
VK_VIDEO_UPLOAD_TIMEOUT = 300.0
VK_PUBLISH_TOKEN_PATH = Path("uploads/vk_publish_access_token.txt")


def _get_vk_access_token() -> str:
    """Prefer server-issued user token for wall posting, fallback to .env token."""
    try:
        if VK_PUBLISH_TOKEN_PATH.is_file():
            token = VK_PUBLISH_TOKEN_PATH.read_text(encoding="utf-8").strip()
            if token:
                return token
    except Exception as e:
        logger.warning("Failed to read VK publish token file: %s", e)
    return (settings.vk_access_token or "").strip()


def _resolve_wall_media_kind(file_path: str, media_type: Optional[str]) -> str:
    """Определяет image/video по полю промпта или расширению файла."""
    if media_type in ("image", "video"):
        return media_type
    ext = Path(file_path).suffix.lower()
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    return "image"


async def _vk_video_get_metadata(owner_id: int, video_id: int) -> tuple[Optional[str], Optional[str]]:
    """
    Запрашивает video.get: access_key для video_ext.php (параметр hash) и URL превью.

    Returns:
        (access_key или None, url превью или None)
    """
    ep = "https://api.vk.com/method/video.get"
    params = {
        "access_token": _get_vk_access_token(),
        "v": VK_API_VERSION,
        "videos": f"{owner_id}_{video_id}",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(ep, params=params)
        if r.status_code != 200:
            logger.warning("video.get HTTP %s: %s", r.status_code, r.text[:200])
            return None, None
        data = r.json()
        if "error" in data:
            logger.warning("video.get error: %s", data["error"])
            return None, None
        items = data.get("response", {}).get("items") or []
        if not items:
            return None, None
        item = items[0]
        access_key = item.get("access_key")
        if isinstance(access_key, str) and access_key:
            pass
        else:
            access_key = None
        thumb: Optional[str] = None
        images = item.get("image")
        if isinstance(images, list) and images:
            last = images[-1]
            if isinstance(last, dict):
                thumb = last.get("url") or last.get("src")
            elif isinstance(last, str) and last.startswith("http"):
                thumb = last
        return access_key, thumb
    except Exception as e:
        logger.warning("video.get failed: %s", e)
        return None, None


def _vk_thumb_from_video_upload(data: dict[str, Any]) -> Optional[str]:
    """Достаёт URL превью из ответа после загрузки видео."""
    img = data.get("image")
    if isinstance(img, str) and img.startswith("http"):
        return img
    if isinstance(img, list) and img:
        first = img[0]
        if isinstance(first, dict):
            url = first.get("url") or first.get("src")
            if isinstance(url, str) and url.startswith("http"):
                return url
    return None


async def publish_to_vk(
    title: str,
    prompt_text: str,
    ai_model: Optional[str],
    file_path: str,
    prompt_id: str,
    media_type: Optional[str] = None,
) -> dict:
    """
    Публикация промпта в VK группу (фото или видео на стене).

    Args:
        title: Название промпта
        prompt_text: Текст промпта
        ai_model: Название нейросети
        file_path: Путь к файлу изображения/видео
        prompt_id: ID промпта для ссылки
        media_type: Тип из БД («image» / «video»); иначе по расширению файла

    Returns:
        dict: post_id, post_url, photo_url; для видео ещё video_owner_id, video_id, video_hash (access_key)

    Raises:
        Exception: При ошибке публикации
    """
    if not _get_vk_access_token() or not settings.vk_group_id:
        raise ValueError("VK credentials not configured")

    vk_group_id = settings.vk_group_id
    kind = _resolve_wall_media_kind(file_path, media_type)
    message = _format_vk_message(title, prompt_text, ai_model, prompt_id)

    video_owner_id: Optional[int] = None
    video_id_vk: Optional[int] = None
    video_hash: Optional[str] = None

    if kind == "video":
        video_data = await _upload_video_to_vk(
            file_path=file_path,
            vk_group_id=vk_group_id,
            title=title[:250],
        )
        owner_id = int(video_data["owner_id"])
        vid = int(video_data["video_id"])
        attachments = f"video{owner_id}_{vid}"
        thumb = video_data.get("thumb_url")
        upload_access = video_data.get("access_key")
        meta_key, meta_thumb = await _vk_video_get_metadata(owner_id, vid)
        if meta_thumb:
            thumb = meta_thumb or thumb
        video_hash = (meta_key or upload_access) or None
        video_owner_id = owner_id
        video_id_vk = vid
    else:
        try:
            photo_data = await _upload_photo_to_vk(file_path, vk_group_id)
        except Exception as e:
            logger.error("Failed to upload photo to VK: %s", e)
            raise
        attachments = f"photo{photo_data['owner_id']}_{photo_data['id']}"
        thumb = photo_data.get("sizes", [{}])[-1].get("url", "") if photo_data.get("sizes") else None

    post_url = "https://api.vk.com/method/wall.post"
    post_params: dict[str, Any] = {
        "access_token": _get_vk_access_token(),
        "v": VK_API_VERSION,
        "owner_id": vk_group_id,
        "from_group": 1,
        "message": message,
        "attachments": attachments,
    }

    # Тело запроса, не query: длинный текст промпта иначе даёт HTTP 414 Request-URI Too Large
    last_exc: Exception | None = None
    for _attempt in range(2):  # одна повторная попытка при сетевых ошибках
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(post_url, data=post_params)
            break
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            last_exc = exc
            logger.warning("wall.post attempt %d failed: %s", _attempt + 1, exc)
    else:
        raise Exception(f"VK wall.post network error after retries: {last_exc}")

    if response.status_code != 200:
        raise Exception(f"VK wall.post failed: {response.text}")

    result = response.json()

    if "error" in result:
        error_msg = result["error"].get("error_msg", "Unknown error")
        raise Exception(f"VK API error: {error_msg}")

    post_id = result["response"].get("post_id")
    wall_url = f"https://vk.com/wall{vk_group_id}_{post_id}"

    logger.info("Published to VK: %s", wall_url)

    return {
        "post_id": post_id,
        "post_url": wall_url,
        "photo_url": thumb or "",
        "video_owner_id": video_owner_id,
        "video_id": video_id_vk,
        "video_hash": video_hash,
    }


def _vk_upload_photo_param(photo_val: Any) -> str:
    """VK ожидает строку; иногда в JSON приходит массив — сериализуем как в ответе VK."""
    if photo_val is None:
        return ""
    if isinstance(photo_val, str):
        return photo_val
    return json.dumps(photo_val, ensure_ascii=False)


async def _upload_photo_to_vk(file_path: str, group_id: str) -> dict:
    """
    Загружает фото на сервер VK.

    Returns:
        dict: Информация о загруженном фото
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"VK upload: file not found: {file_path}")

    raw = path.read_bytes()
    if not raw:
        raise ValueError(f"VK upload: empty file: {file_path}")

    upload_url_endpoint = "https://api.vk.com/method/photos.getWallUploadServer"
    upload_params = {
        "access_token": _get_vk_access_token(),
        "v": VK_API_VERSION,
        "group_id": group_id.lstrip("-"),
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        upload_response = await client.get(upload_url_endpoint, params=upload_params)

    if upload_response.status_code != 200:
        raise Exception(f"Failed to get upload server: {upload_response.text}")

    upload_data = upload_response.json()
    if "error" in upload_data:
        raise Exception(f"VK API error: {upload_data['error']}")

    upload_url = upload_data["response"]["upload_url"]

    mime, _ = mimetypes.guess_type(file_path)
    mime = mime or "image/jpeg"
    fname = path.name

    async def _post_to_upload(field: str) -> httpx.Response:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Байты целиком — без «обрыва» файлового дескриптора до отправки multipart
            files = {field: (fname, raw, mime)}
            return await client.post(upload_url, files=files)

    file_response = await _post_to_upload("photo")

    if file_response.status_code != 200:
        raise Exception(f"Failed to upload file: {file_response.text}")

    try:
        file_data = file_response.json()
    except ValueError as e:
        raise Exception(f"VK upload: non-JSON response: {file_response.text[:500]}") from e

    photo_val = file_data.get("photo")
    if not photo_val and photo_val != 0:
        logger.warning(
            "VK wall upload returned empty photo with field 'photo', retrying with 'file' (%s)",
            fname,
        )
        file_response = await _post_to_upload("file")
        if file_response.status_code != 200:
            raise Exception(f"Failed to upload file (retry): {file_response.text}")
        try:
            file_data = file_response.json()
        except ValueError as e:
            raise Exception(
                f"VK upload (retry): non-JSON: {file_response.text[:500]}",
            ) from e
        photo_val = file_data.get("photo")

    photo_str = _vk_upload_photo_param(photo_val)
    if not photo_str:
        logger.error("VK wall upload response (no photo): %s", file_data)
        raise Exception(
            "VK upload returned empty photo after upload; check image format/size and multipart field",
        )

    save_url = "https://api.vk.com/method/photos.saveWallPhoto"
    save_params = {
        "access_token": _get_vk_access_token(),
        "v": VK_API_VERSION,
        "group_id": group_id.lstrip("-"),
        "photo": photo_str,
        "server": file_data.get("server"),
        "hash": file_data.get("hash"),
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        save_response = await client.post(save_url, data=save_params)

    if save_response.status_code != 200:
        raise Exception(f"Failed to save photo: {save_response.text}")

    save_data = save_response.json()
    if "error" in save_data:
        raise Exception(f"VK API error: {save_data['error']}")

    return save_data["response"][0]


async def _upload_video_to_vk(file_path: str, vk_group_id: str, title: str) -> dict[str, Any]:
    """
    Загружает видео через video.save + POST на upload_url.

    Returns:
        dict с ключами owner_id, video_id, thumb_url (опционально)
    """
    gid = vk_group_id.lstrip("-")
    save_ep = "https://api.vk.com/method/video.save"
    save_params = {
        "access_token": _get_vk_access_token(),
        "v": VK_API_VERSION,
        "group_id": gid,
        "name": title or "Magikbook",
        "wallpost": 0,
    }

    async with httpx.AsyncClient() as client:
        save_response = await client.get(save_ep, params=save_params)

    if save_response.status_code != 200:
        raise Exception(f"video.save HTTP error: {save_response.text}")

    save_json = save_response.json()
    if "error" in save_json:
        raise Exception(f"VK video.save error: {save_json['error']}")

    resp = save_json["response"]
    upload_url = resp["upload_url"]

    mime, _ = mimetypes.guess_type(file_path)
    async with httpx.AsyncClient(timeout=VK_VIDEO_UPLOAD_TIMEOUT) as client:
        with open(file_path, "rb") as f:
            files = {"video_file": (Path(file_path).name, f, mime or "video/mp4")}
            up = await client.post(upload_url, files=files)

    if up.status_code != 200:
        raise Exception(f"VK video upload HTTP {up.status_code}: {up.text[:500]}")

    try:
        up_data = up.json()
    except ValueError as e:
        raise Exception(f"VK video upload: non-JSON response: {up.text[:300]}") from e

    if isinstance(up_data, dict) and "response" in up_data and isinstance(up_data["response"], dict):
        up_data = up_data["response"]

    if isinstance(up_data, dict) and up_data.get("error"):
        raise Exception(f"VK video upload error: {up_data['error']}")

    ud: dict[str, Any] = up_data if isinstance(up_data, dict) else {}

    owner_id = ud.get("owner_id") or resp.get("owner_id")
    video_id = ud.get("video_id") or resp.get("video_id")
    if owner_id is None or video_id is None:
        logger.error("Unexpected VK video upload JSON: %s", up_data)
        raise Exception("VK video upload: missing owner_id or video_id in response")

    thumb = _vk_thumb_from_video_upload(ud)
    access_key = ud.get("access_key")
    if isinstance(access_key, str) and access_key:
        pass
    else:
        access_key = None

    return {
        "owner_id": owner_id,
        "video_id": video_id,
        "thumb_url": thumb,
        "access_key": access_key,
    }


def _format_vk_message(
    title: str,
    prompt_text: str,
    ai_model: Optional[str],
    prompt_id: str,
) -> str:
    """Форматирует сообщение для публикации в VK (BBCode-ссылка — см. post-format в доке VK)."""
    # Публичная ссылка на промпт: в проде обычно https://magikbook.ru (см. frontend_url в .env)
    base = (settings.frontend_url or "https://magikbook.ru").rstrip("/")
    if not base.startswith("http"):
        base = f"https://{base}"
    prompt_url = f"{base}/prompt/{prompt_id}"
    lines = [
        f"📌 {title}",
        "",
        "Промпт:",
        prompt_text[:2000],
    ]

    if ai_model:
        lines.extend(["", f"🤖 Нейросеть: {ai_model}"])

    # VK wall.post не всегда рендерит BBCode-якорь для внешних ссылок через API.
    # Делаем предсказуемый формат: CTA-текст + обычный URL, который VK автоссылит.
    lines.extend(
        [
            "",
            "───────────────",
            "",
            "✨ Открыть промпт в MagikBook:",
            prompt_url,
        ]
    )

    return "\n".join(lines)


async def check_vk_config() -> bool:
    """Проверяет настроена ли интеграция с VK."""
    return bool(_get_vk_access_token() and settings.vk_group_id)
