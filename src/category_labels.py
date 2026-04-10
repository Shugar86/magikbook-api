"""Соответствие slug категории (форма submit / URL) и значений в БД.

Старые/сидированные записи хранят ``category`` как «emoji + пробел + название»,
новые — как латинский slug. Фильтры ленты должны учитывать оба варианта.
"""

from __future__ import annotations

# (slug, emoji, title) — как во фронте src/lib/categories.ts
_RAW: list[tuple[str, str, str]] = [
    # text
    ("excuses", "🙈", "Отмазки"),
    ("pickup", "💘", "Пикап"),
    ("resume", "📄", "Резюме"),
    ("contracts", "📋", "Договоры"),
    ("letters", "✉️", "Письма"),
    ("compliments", "🌹", "Комплименты"),
    ("jokes", "😂", "Шутки"),
    ("toasts", "🥂", "Тосты"),
    ("wishes", "🎁", "Поздравления"),
    ("apologies", "🙏", "Извинения"),
    ("motivation", "💪", "Мотивация"),
    ("stories", "📖", "Истории"),
    ("poetry", "🎭", "Стихи"),
    ("scripts", "🎬", "Сценарии"),
    ("sms", "💬", "СМС"),
    ("reviews", "⭐", "Отзывы"),
    ("speeches", "🎤", "Речи"),
    ("breakup", "💔", "Расставания"),
    ("flirt", "😏", "Флирт"),
    ("negotiation", "🤝", "Переговоры"),
    # image
    ("photo", "📷", "Фото"),
    ("video", "🎬", "Видео"),
    ("portrait", "🧑‍🎨", "Портрет"),
    ("avatar", "👤", "Аватарки"),
    ("logo", "🔷", "Логотипы"),
    ("anime", "🌸", "Аниме"),
    ("landscape", "🌄", "Пейзаж"),
    ("3d", "🧊", "3D"),
    ("stickers", "🎴", "Стикеры"),
    ("interior", "🛋️", "Интерьер"),
    ("art", "🎨", "Арты"),
    ("pixelart", "👾", "Пиксельарт"),
    ("cyberpunk", "🤖", "Киберпанк"),
    ("cartoon", "🐭", "Мультяшные"),
    ("fantasy", "🐉", "Фэнтези"),
    ("postcards", "💌", "Открытки"),
    # holidays
    ("feb14", "💘", "14 февраля"),
    ("feb23", "🎖️", "23 февраля"),
    ("mar8", "💐", "8 марта"),
    ("newyear", "🎄", "Новый год"),
    ("birthday", "🎂", "День рождения"),
]


def _build_legacy_map() -> dict[str, str]:
    return {slug: f"{emoji} {title}" for slug, emoji, title in _RAW}


LEGACY_LABEL_BY_SLUG: dict[str, str] = _build_legacy_map()


def category_values_for_slug_filter(slug: str) -> list[str]:
    """
    Все значения ``Prompt.category``, которые считаются этой категорией.

    Args:
        slug: Латинский slug из UI (например ``anime``).

    Returns:
        Список для ``WHERE category IN (...)``: slug и легаси-подпись, без дублей.
    """
    if not slug:
        return []
    legacy = LEGACY_LABEL_BY_SLUG.get(slug)
    if legacy and legacy != slug:
        return [slug, legacy]
    return [slug]
