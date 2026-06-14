# ✨ MagikBook API

> Бэкенд для сообщества AI-заклинаний: публикуй, модерируй, сражайся в битвах промптов и расшаривай магию в VK и Telegram.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI 0.133](https://img.shields.io/badge/FastAPI-0.133-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLModel](https://img.shields.io/badge/SQLModel-async-green.svg)](https://sqlmodel.tiangolo.com/)
[![Tests](https://img.shields.io/badge/tests-pytest-%230A9EDC.svg)](./tests/)
[![Code style](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://docs.astral.sh/ruff/)
[![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](./CHANGELOG.md)
[![Docker ready](https://img.shields.io/badge/Docker-ready-2496ED.svg)](./Dockerfile)

---

## 🪄 Что это

**MagikBook API** — сердце платформы для любителей генеративного ИИ. Здесь авторы загружают свои лучшие промпты, зрители голосуют в битвах с рейтингом ELO, а админы одним движением публикуют одобренный контент в соцсети.

Для кого:

- **Авторы промптов** — делитесь заклинаниями, собирайте лайки и копии.
- **Модераторы** — просматривайте очередь, одобряйте и отклоняйте загрузки.
- **Фронтенд MagikBook** — этот API заточен под Next.js-фронт с CORS/cookie.
- **Solo-разработчики и команды** — взяли, подняли, кастомизировали.

---

## 🔥 Возможности

| Фича | Ценность |
|------|----------|
| 📤 **Загрузка и модерация** | Файлы + метаданные, статусы `pending → approved/published → rejected`. |
| ⚔️ **Битва промптов** | Пара картинок, голосование, пересчёт ELO (K=32) в реальном времени. |
| 🤖 **Генерация через Gemini** | SSE-стрим с многоуровневым fallback по моделям. |
| 🔐 **Авторизация** | Email/OTP, Google OAuth, VK ID, Telegram Login Widget. |
| 📢 **Автопостинг** | VK и Telegram при одобрении, ручной fallback. |
| 🧙 **Кабинет и гримуар** | Статистика автора, сохранённые промпты, ежедневный бонус «маны». |
| 🐳 **Docker-ready** | Готовый Dockerfile; worker и Redis легко обернуть в Docker Compose. |

---

## 🚀 Быстрый старт

### Локально (Python 3.11+)

```bash
# 1. Клонировать репозиторий
git clone <repo-url>
cd magikbook-api

# 2. Создать виртуальное окружение и установить зависимости
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. Подготовить окружение
cp .env.example .env
# Отредактируй .env: SECRET_KEY, DATABASE_URL, GOOGLE_API_KEY и т.д.

# 4. Применить миграции
alembic upgrade head

# 5. Запустить dev-сервер
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

После запуска в режиме `development`:

- 📖 Документация API: http://localhost:8000/docs
- ❤️ Проверка здоровья: http://localhost:8000/health

### Docker

```bash
# Собрать образ
docker build -t magikbook-api .

# Запустить (пример; подставь свой .env)
docker run --rm -it \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/uploads:/app/uploads \
  magikbook-api
```

---

## 🏗️ Архитектура / стек

| Область | Технология | Назначение |
|---------|------------|------------|
| Язык | Python 3.11+ | Современный async Python. |
| Фреймворк | FastAPI 0.133 + Uvicorn | HTTP API, OpenAPI, SSE. |
| ORM / миграции | SQLModel + SQLAlchemy async + Alembic | Модели и версионирование схемы. |
| Конфигурация | Pydantic Settings | Чтение переменных окружения из `.env`. |
| Кэш / очереди | Redis + arq | Лимиты, сессии битв, фоновые воркеры. |
| Генерация | Google Gemini (`google-genai`) + `sse-starlette` | Стрим текста с fallback моделей. |
| Auth | JWT в httpOnly cookie, python-jose, passlib | Безопасная сессия пользователя. |
| БД (dev/prod) | aiosqlite / asyncpg | SQLite для разработки, PostgreSQL для продакшена. |
| Медиа | Pillow, aiofiles, python-multipart | Валидация и хранение файлов. |
| CI / качество | GitHub Actions, pytest, ruff | Линт, тесты, синхронизация категорий. |

### Системная схема

```text
[Browser / Next.js 3000]
         │
         ▼
   FastAPI 8000
         ├── SQLite / PostgreSQL
         ├── Redis (или in-memory fallback)
         ├── Google Gemini API
         ├── VK API (постинг)
         └── Telegram Bot API
```

Детали схемы, ELO и Gemini fallback — в [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 📁 Структура проекта

```text
magikbook-api/
├── src/
│   ├── main.py                 # FastAPI app, роутеры, lifespan
│   ├── config.py               # Pydantic Settings из env
│   ├── database.py             # async engine, сессии, init_db
│   ├── redis_client.py         # Redis или in-memory fallback
│   ├── dependencies.py         # JWT из cookie / Bearer
│   ├── models/                 # SQLModel ORM + Pydantic схемы
│   ├── routes/                 # HTTP API: auth, prompts, battle, ...
│   ├── services/               # Бизнес-логика, VK/Telegram/Gemini
│   ├── utils/                  # file_storage и прочее
│   └── workers/                # arq: daily_prompt, elo_flush
├── migrations/                 # Alembic
├── tests/                      # pytest
├── scripts/                    # seed, verify, check_category_sync
├── docs/                       # инциденты и заметки
├── Dockerfile
├── pyproject.toml
├── requirements.txt
├── .env.example
├── README.md                   # ← вы здесь
├── AGENTS.md                   # контракт для AI-агентов
├── CONTRIBUTING.md             # как участвовать
├── CHANGELOG.md                # история изменений
└── LICENSE                     # MIT
```

---

## 📖 Примеры

### Загрузить промпт

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -F "title=Киберпанк портрет" \
  -F "prompt_text=A cyberpunk portrait of a wizard..." \
  -F "category=art" \
  -F "media_type=image" \
  -F "ai_model=Midjourney" \
  -F "file=@preview.jpg" \
  http://localhost:8000/api/prompts/upload
```

### Получить пару для битвы

```bash
curl http://localhost:8000/api/battle/pair
```

### Проверить кабинет

```bash
curl -H "Cookie: access_token=<jwt>" \
  http://localhost:8000/api/cabinet/overview
```

### Одобрить промпт (только админ)

```bash
curl -X POST \
  -H "Cookie: access_token=<jwt>" \
  http://localhost:8000/api/moderation/<prompt_id>/approve
```

---

## 🔒 Безопасность и секреты

- **Не коммить** `.env`, `*.pem`, `id_*`, токены, пароли и базы данных.
- `magikbook.db` и `uploads/` уже в `.gitignore` — если `git status` их показывает как отслеживаемые, читай [`docs/INCIDENT_GIT_TRACKED_SQLITE_2026-04-11.md`](docs/INCIDENT_GIT_TRACKED_SQLITE_2026-04-11.md).
- Продакшен: используй `ENVIRONMENT=production`, PostgreSQL и настоящий Redis.

---

## 📚 Документация

| Файл | Описание |
|------|----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Системная схема, модели, ELO, Gemini |
| [SETUP_GUIDE.md](SETUP_GUIDE.md) | Настройка OAuth, VK/Telegram, БД, nginx |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Ветки, PR, CI, стиль коммитов |
| [CHANGELOG.md](CHANGELOG.md) | История изменений |
| [AGENTS.md](AGENTS.md) | Контракт для AI-агентов |
| [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md) | Чеклист перед боем |
| [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) | Пошаговый деплой |

---

## 🛤️ Дорожная карта

- [ ] Интеграция с S3 для хранения файлов.
- [ ] WebSocket-уведомления для модерации.
- [ ] Email-уведомления при отклонении промпта.
- [ ] Retry logic для failed publishing.
- [ ] Rate limiting на upload.
- [ ] Image optimization перед загрузкой.

История релизов — в [CHANGELOG.md](./CHANGELOG.md).

---

## 🧙 Участие

Хочешь добавить заклинание в книгу? См. [CONTRIBUTING.md](./CONTRIBUTING.md).

---

## 🧙 Лицензия

Распространяется под лицензией [MIT](./LICENSE) © 2026 Shugar86.

Создано с любовью к магии промптов ✨
