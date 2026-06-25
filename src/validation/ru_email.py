"""Validation helpers for Russian email providers (registration only)."""

RU_EMAIL_ERROR = (
    "Регистрация доступна только с российскими почтовиками "
    "(mail.ru, yandex.ru, rambler.ru и др.)"
)

RU_EMAIL_DOMAINS: frozenset[str] = frozenset(
    {
        # Mail.ru Group
        "mail.ru",
        "inbox.ru",
        "bk.ru",
        "list.ru",
        "internet.ru",
        # Yandex
        "yandex.ru",
        "ya.ru",
        # Rambler
        "rambler.ru",
        "lenta.ru",
        "ro.ru",
        "myrambler.ru",
        "autorambler.ru",
    }
)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def email_domain(email: str) -> str:
    normalized = normalize_email(email)
    if "@" not in normalized:
        return ""
    return normalized.rsplit("@", 1)[-1]


def is_ru_provider_email(email: str) -> bool:
    domain = email_domain(email)
    return bool(domain) and domain in RU_EMAIL_DOMAINS
