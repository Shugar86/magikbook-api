# PROJECT — magikbook-api

Anchor (immutable core). Changing meaning = new project.

## Mission (1-2 sentences, north star)

Бэкенд **MagikBook** — платформа для публикации, модерации и обмена AI-промптами: лента, битва с ELO, генерация через Gemini, автопостинг в VK и Telegram, мульти-провайдерная авторизация. North star: дать сообществу живую экосистему промптов с честным рейтингом, модерацией и дистрибуцией в соцсети.

## Immutable core (3-6 principles that cannot break)

1. **Контент проходит модерацию** — публичная лента и API отдают только `approved` / `published` промпты; черновики и отклонённые не утекают наружу.
2. **Авторизация через JWT** — сессия в cookie (`path=/`) или Bearer; защищённые эндпойнты требуют валидного пользователя.
3. **Async-first data layer** — SQLModel/SQLAlchemy async, Alembic для схемы; прод — PostgreSQL, локально — SQLite.
4. **Redis или in-memory fallback** — лимиты, бонусы и анти-накрутка битвы; в Docker Compose Redis обязателен для согласованности между API и worker.
5. **Публикация в VK — form body, не query** — длинные промпты не должны ломать постинг (414 URI Too Long).
6. **Prod DB не в git** — `magikbook.db` в `.gitignore`; коммит production SQLite запрещён (см. инцидент 2026-04-11).

## Key technical decisions (table: Decision | Why)

| Decision | Why |
|----------|-----|
| FastAPI + SQLModel async | Единый стек типов, OpenAPI, SSE для генерации, async I/O под внешние API |
| JWT в httpOnly cookie + OAuth (Google/VK/Telegram) | Браузерный фронт на Next.js с CORS/credentials; несколько провайдеров входа |
| arq + Redis для workers | Cron: flush ELO (~5 мин), «заклинание дня» (00:00 UTC); отделение фона от API |
| SSE через `sse-starlette` + Gemini fallback по моделям | Стриминг UX генерации; устойчивость при недоступности одной модели |
| SQLite dev / PostgreSQL prod | Быстрый локальный цикл; asyncpg в prod |
| Порядок роутеров: `uploads` до `prompts` | `/api/prompts/my-uploads` не перехватывается как `{prompt_id}` |
| VK Standalone token bypass [документировано] | Обход ограничений VK ID для wall/photos на сервере (`vk_integration_report.md`) |
| `ENVIRONMENT=development` → `/docs`, test_setup | OpenAPI и сброс БД только в dev |

## Stack (languages, frameworks, key libs)

- **Язык:** Python 3.11+
- **Фреймворк:** FastAPI, Uvicorn
- **ORM / миграции:** SQLModel, SQLAlchemy async, Alembic
- **Конфиг:** pydantic-settings
- **Auth:** python-jose, passlib
- **Кэш / очереди:** redis, arq
- **AI:** google-genai (Gemini), sse-starlette
- **БД:** aiosqlite (dev), asyncpg (prod)
- **Почта:** aiosmtplib, email-validator
- **Медиа:** Pillow, aiofiles, python-multipart
- **CI / качество:** pytest, pytest-asyncio, httpx, ruff
- **Контейнеризация:** Docker (`Dockerfile`), Docker Compose [вне репо: `/opt/projects/docker-compose.yml`]
- **Версия пакета:** `0.2.0` (`pyproject.toml`); OpenAPI app version `0.1.0` [расхождение]

## Key files / entry points

| Путь | Назначение |
|------|------------|
| `src/main.py` | FastAPI app, CORS, lifespan, регистрация роутеров, `/health`, mount `/uploads` |
| `src/config.py` | `Settings` из env |
| `src/database.py` | Async engine, сессии, `init_db` |
| `src/models/db_models.py` | ORM: User, Prompt, Like, SavedPrompt, BattleVote, EmailOTP |
| `src/routes/*.py` | HTTP API (auth, prompts, uploads, moderation, battle, generate, …) |
| `src/services/*.py` | Бизнес-логика, VK/Telegram/Gemini |
| `src/workers/` | arq: `elo_flush`, `daily_prompt`, `arq_redis` |
| `migrations/` + `alembic.ini` | Схема БД |
| `Dockerfile` | Prod-образ API |
| `pyproject.toml` / `requirements.txt` | Зависимости |
| `smoke_tests.py` | Ручные smoke-тесты против `localhost:8000` |
| `verify_db.py`, `verify_files.py`, `verify_migration.py` | Скрипты верификации |

## Documentation (existing docs links)

| Документ | Содержание |
|----------|------------|
| [README.md](README.md) | Обзор API, env, dev/prod, модули |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Системная схема, модели, потоки |
| [SETUP_GUIDE.md](SETUP_GUIDE.md) | Пошаговая настройка |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Ветки, PR, CI, стиль коммитов |
| [CHANGELOG.md](CHANGELOG.md) | История изменений |
| [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) | Чеклист деплоя |
| [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md) | Prod-готовность |
| [vk_integration_report.md](vk_integration_report.md) | VK OAuth, токены, обходы, багфиксы |
| [docs/INCIDENT_GIT_TRACKED_SQLITE_2026-04-11.md](docs/INCIDENT_GIT_TRACKED_SQLITE_2026-04-11.md) | Инцидент: SQLite в git |
| [docs/INCIDENT_DB_RECOVERY_2026-04-10.md](docs/INCIDENT_DB_RECOVERY_2026-04-10.md) | Восстановление БД |
| [docs/DIAGNOSTIC_CONTENT_MODERATION.md](docs/DIAGNOSTIC_CONTENT_MODERATION.md) | Диагностика модерации |

## Health (how to check it works)

1. **Liveness:** `GET /health` → `{"status":"ok"}` (порт 8000).
2. **Dev docs:** при `ENVIRONMENT=development` — `/docs`, `/redoc`, `/openapi.json`.
3. **Миграции:** `alembic upgrade head` или `scripts/upgrade_db.sh`.
4. **Тесты:** `pytest tests/ -v` (CI: ruff + pytest с Redis service).
5. **Smoke:** `python smoke_tests.py` при поднятом API на `localhost:8000`.
6. **Redis (Docker):** `docker exec magikbook-redis redis-cli ping` → `PONG`; в логах API — `Connected to Redis`, не `Using in-memory Redis stub`.
7. **Verify-скрипты:** `python verify_db.py`, `verify_migration.py`, `verify_files.py`.
