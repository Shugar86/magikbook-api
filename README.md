# MagikBook API

Бэкенд **MagikBook** — платформа для публикации и обмена AI-промптами: загрузка контента, модерация, лента, битва промптов с ELO, генерация текста через Google Gemini, автопостинг в VK и Telegram, авторизация (email/OTP, Google, VK, Telegram).

**Стек:** Python 3.11+, FastAPI, SQLModel/SQLAlchemy (async), Alembic, Pydantic Settings, Redis (опционально, с in-memory fallback), SSE для стриминга генерации.

**Разработка и CI:** ветки, pull request, обязательные проверки GitHub Actions, настройка автора коммита (не `root`), работа без лишних приписок в сообщениях — см. [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Архитектура модулей `src/`

### `src/routes/`

| Файл | Назначение |
|------|------------|
| `auth.py` | Регистрация, логин, email OTP, logout, сессия `/me`, ежедневный бонус, OAuth Google/VK, Telegram Login Widget |
| `prompts.py` | Главная/лента, карточка промпта, OG-meta, публикация промпта, лайки, счётчик копирований |
| `uploads.py` | Загрузка файлов и создание промпта на модерации, список «мои загрузки» |
| `moderation.py` | Очередь модерации, превью файлов, approve/reject, статистика, выдача админки, партнёрские ссылки |
| `publish.py` | Ручная публикация в VK/Telegram и ручной `preview_url` (fallback) |
| `battle.py` | Пара для битвы, голосование, статистика голосов/ELO по промпту |
| `cabinet.py` | Обзор личного кабинета (статистика, бонусы) |
| `grimoire.py` | Сохранённые промпты пользователя (добавить/список/удалить) |
| `generate.py` | SSE-стрим генерации промпта через Gemini (лимиты маны) |
| `paywall.py` | Telegram Stars, проверка подписки на канал, конфиг спонсора |
| `test_setup.py` | **Только `ENVIRONMENT=development`:** сброс БД для E2E (`POST /api/test_setup/reset`, заголовок `X-Test-Token`) |

### `src/services/`

| Файл | Назначение |
|------|------------|
| `gemini_service.py` | Стриминг генерации, многофазный fallback по моделям Gemini |
| `vk_publisher.py` | Публикация поста и фото в VK |
| `telegram_publisher.py` | Публикация в Telegram-канал |
| `prompt_service.py` | Бизнес-логика промптов, ленты, главной |
| `battle_service.py` | Пара для битвы, голоса, пересчёт ELO после голоса |
| `elo_service.py` | `calculate_new_ratings` — формула ELO (K=32) |

### Прочее

| Файл / каталог | Назначение |
|----------------|------------|
| `models/db_models.py` | ORM-модели: `User`, `Prompt`, `Like`, `SavedPrompt`, `BattleVote`, `EmailOTP` |
| `models/schemas.py` | Pydantic-схемы ответов/запросов API |
| `database.py` | Async engine, сессии, `init_db` |
| `config.py` | Настройки из переменных окружения (`Settings`) |
| `dependencies.py` | `get_current_user`, `get_optional_user` (JWT из cookie или Bearer) |
| `redis_client.py` | Redis или in-memory fallback |
| `utils/file_storage.py` | Сохранение и валидация загружаемых файлов |
| `workers/` | `arq_redis.py`, `daily_prompt.py`, `elo_flush.py` — фоновые задачи (arq/cron; `REDIS_URL` и контейнер `magikbook-worker` в compose) |

---

## Переменные окружения

Значения по умолчанию — из [`src/config.py`](src/config.py); имена переменных в `.env` — в UPPER_SNAKE_CASE (как в [`.env.example`](.env.example)).

| Переменная | Обязательно | По умолчанию (логика) | Описание |
|------------|-------------|------------------------|----------|
| `DATABASE_URL` | Да в проде | `sqlite+aiosqlite:///./magikbook.db` | URL БД (async SQLAlchemy) |
| `REDIS_URL` | Нет | пусто → in-memory | Redis для лимитов и бонусов; без него используется заглушка в памяти |
| `SECRET_KEY` | Да в проде | `secret` | JWT и подписи |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Нет | `10080` | Срок жизни access-токена |
| `ALGORITHM` | Нет | `HS256` | Алгоритм JWT (не продублирован в `.env.example`) |
| `FRONTEND_URL` | Да в проде | `http://localhost:3000` | CORS и редиректы OAuth |
| `ENVIRONMENT` | Рекомендуется | `development` | `production` → Secure cookie (если не переопределено `COOKIE_SECURE`) |
| `COOKIE_SECURE` | Нет | авто от `ENVIRONMENT` | Принудительно Secure для cookie |
| `GOOGLE_API_KEY` | Для генерации | пусто | Gemini; без ключа `POST /api/generate` → 503 |
| `GEMINI_STREAM_TIMEOUT_SECONDS` | Нет | `45` | Таймаут стрима Gemini |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` | Для Google OAuth | см. `config.py` | OAuth 2.0 |
| `VK_CLIENT_ID` / `VK_CLIENT_SECRET` / `VK_REDIRECT_URI` | Для VK OAuth | см. `config.py` | OAuth VK ID |
| `VK_ACCESS_TOKEN` / `VK_GROUP_ID` | Для автопоста VK | пусто | Публикация в группу |
| `TELEGRAM_BOT_TOKEN` | Для Telegram login и API | пусто | Верификация виджета и боты |
| `TELEGRAM_CHANNEL_ID` | Для автопоста | пусто | Канал для постов |
| `UPLOAD_DIR` | Нет | `./uploads/temp` | Каталог загрузок |
| `MAX_FILE_SIZE` | Нет | `52428800` | Макс. размер файла (байты) |
| `FILE_CLEANUP_DAYS` | Нет | `7` | Устаревшие файлы (логика очистки — по коду) |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | Для email OTP | см. `config.py` | Отправка кодов |
| `RESEND_API_KEY` | Нет | пусто | Альтернатива Resend API |
| `DEBUG` | Нет | — | Есть в `.env.example`, **не** объявлено в `Settings` — игнорируется приложением, если не добавить в код |
| `LOG_LEVEL` | Нет | — | То же |

Полный комментированный шаблон: [`.env.example`](.env.example).

### Docker Compose (`/opt/projects/docker-compose.yml`)

Поднимаются **`magikbook-redis`**, **`magikbook-api`**, **`magikbook-worker`**, **`magikbook-frontend`**. Для API и воркера в Compose задано `REDIS_URL=redis://magikbook-redis:6379/0`, так что бонус и лимиты не зависят от in-memory заглушки.

- **Ежедневный бонус** (`POST /api/auth/daily-bonus`) и анонимные лимиты используют ключи с датой **`YYYY-MM-DD` по UTC**. Новый «день» для бонуса наступает в полночь UTC, а не по локальному времени пользователя.
- **Заклинание дня** на главной обновляет **`magikbook-worker`** (arq: ELO каждые ~5 минут, генерация «дня» в **00:00 UTC**). Нужны рабочий Redis, `GOOGLE_API_KEY` и общий том `magikbook.db` с API.
- **Диагностика:** `docker logs magikbook-api 2>&1 | grep -i redis` — ожидается `Connected to Redis at redis://...`; строка `Using in-memory Redis stub` значит, что контейнер не видит внешний Redis (часто пустой `REDIS_URL` без Compose). `docker exec magikbook-redis redis-cli ping` → `PONG`. Пример ключа бонуса в Redis: `daily_bonus:<uuid_пользователя>:2026-04-11`.

---

## Локальная разработка

1. Клонировать репозиторий, создать venv и установить зависимости:
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```
2. Скопировать `cp .env.example .env` и заполнить обязательные переменные (минимум `SECRET_KEY`, при необходимости БД и OAuth).
3. Применить миграции:
   ```bash
   alembic upgrade head
   ```
   Либо скрипт из корня API: [`scripts/upgrade_db.sh`](scripts/upgrade_db.sh) (выполняет `alembic upgrade head`).
4. Запуск dev-сервера:
   ```bash
   uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
   ```
5. В режиме `development` доступны интерактивная документация: `/docs`, `/redoc`, OpenAPI `/openapi.json`. В `production` они отключены в [`main.py`](src/main.py).

---

## Продакшен (Docker)

- Поднять сервис с переменными из `.env` (в т.ч. `ENVIRONMENT=production`, `DATABASE_URL` на PostgreSQL, `FRONTEND_URL` с публичным URL фронта).
- Перед перезапуском контейнера с новой версией кода выполнить миграции: `scripts/upgrade_db.sh` или `alembic upgrade head` в контексте образа/тома с кодом.
- Проверка живости: **`GET /health`** (не под префиксом `/api`).

Подробный чеклист: [`PRODUCTION_CHECKLIST.md`](PRODUCTION_CHECKLIST.md). Системная архитектура: [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Справочник API

Все пути — как в коде FastAPI. Авторизация: cookie `access_token` (HttpOnly) или заголовок `Authorization: Bearer <token>`.

### Система

| Метод | Путь | Auth | Описание |
|-------|------|------|----------|
| GET | `/health` | Нет | Статус `{"status":"ok"}` |

### Auth (`/api/auth`)

| Метод | Путь | Auth | Описание |
|-------|------|------|----------|
| POST | `/api/auth/register` | Нет | Регистрация email/пароль, выдача cookie |
| POST | `/api/auth/login` | Нет | Вход email/пароль |
| POST | `/api/auth/send-otp` | Нет | Отправка кода OTP на email |
| POST | `/api/auth/verify-otp` | Нет | Проверка OTP, выдача cookie |
| POST | `/api/auth/logout` | Нет | Очистка cookie сессии |
| GET | `/api/auth/me` | Да | Текущий пользователь, в т.ч. `is_admin` |
| POST | `/api/auth/daily-bonus` | Да | Ежедневный бонус маны (нужен Redis) |
| POST | `/api/auth/telegram` | Нет | Вход через Telegram Login Widget |
| GET | `/api/auth/google` | Нет | Старт OAuth Google |
| GET | `/api/auth/google/callback` | Нет | Callback Google |
| GET | `/api/auth/vk` | Нет | Старт OAuth VK |
| GET | `/api/auth/vk/callback` | Нет | Callback VK |

### Промпты (`/api/prompts`)

| Метод | Путь | Auth | Описание |
|-------|------|------|----------|
| GET | `/api/prompts/homepage` | Нет | Данные главной |
| GET | `/api/prompts/feed` | Нет | Лента с фильтрами |
| GET | `/api/prompts/{prompt_id}/og-meta` | Нет | Open Graph для шаринга |
| GET | `/api/prompts/{prompt_id}` | Нет | Карточка промпта |
| POST | `/api/prompts/publish` | Да | Создание промпта (текстовый сценарий) |
| POST | `/api/prompts/{prompt_id}/like` | Да | Лайк / снять лайк |
| GET | `/api/prompts/{prompt_id}/like` | Да | Статус лайка и счётчик |
| POST | `/api/prompts/{prompt_id}/copy-count` | Нет | Инкремент копирований (лимиты по IP/сессии) |

### Загрузки

| Метод | Путь | Auth | Описание |
|-------|------|------|----------|
| POST | `/api/prompts/upload` | Да | Форма: загрузка файла + метаданные промпта |
| GET | `/api/prompts/my-uploads` | Да | Список загрузок пользователя |

### Модерация и админ

| Метод | Путь | Auth | Описание |
|-------|------|------|----------|
| GET | `/api/moderation` | Да, админ | Очередь промптов по статусу |
| GET | `/api/moderation/files/{filename}` | Да, админ | Отдача файла превью |
| POST | `/api/moderation/{prompt_id}/approve` | Да, админ | Одобрение, публикация в VK/TG, статус `published` |
| POST | `/api/moderation/{prompt_id}/reject` | Да, админ | Отклонение |
| GET | `/api/moderation/stats` | Да, админ | Счётчики по статусам |
| POST | `/api/admin/grant/{user_id}` | Да, админ | Выдать пользователю `is_admin` |
| PATCH | `/api/admin/prompts/{prompt_id}/affiliate-links` | Да, админ | Партнёрские ссылки |

### Публикация (ручной fallback)

| Метод | Путь | Auth | Описание |
|-------|------|------|----------|
| POST | `/api/publish/vk` | Да | Ручной пост в VK |
| POST | `/api/publish/telegram` | Да | Ручной пост в Telegram |
| POST | `/api/publish/{prompt_id}/manual-preview` | Да | Установка `preview_url` вручную |

### Битва (`/api/battle`)

| Метод | Путь | Auth | Описание |
|-------|------|------|----------|
| GET | `/api/battle/pair` | Нет | Две картинки или демо-fallback |
| POST | `/api/battle/vote` | Опционально | Голос; для анонимов `session_token` в теле |
| GET | `/api/battle/stats/{prompt_id}` | Нет | Процент побед, голосов, ELO |

### Кабинет и гримуар

| Метод | Путь | Auth | Описание |
|-------|------|------|----------|
| GET | `/api/cabinet/overview` | Да | Обзор кабинета |
| POST | `/api/grimoire` | Да | Сохранить промпт |
| GET | `/api/grimoire` | Да | Список сохранённых |
| DELETE | `/api/grimoire/{prompt_id}` | Да | Удалить из сохранённых |

### Генерация и paywall

| Метод | Путь | Auth | Описание |
|-------|------|------|----------|
| POST | `/api/generate` | Опционально | SSE-стрим генерации (лимиты маны / анонимные лимиты) |
| POST | `/api/paywall/stars` | Да | Telegram Stars: сейчас **501** — нужна интеграция на стороне бота (см. [`paywall.py`](src/routes/paywall.py)) |
| POST | `/api/paywall/check-subscription` | Да | Проверка подписки Telegram, начисление маны |
| GET | `/api/paywall/sponsor-channel` | Нет | Данные канала-спонсора |

### Только development

| Метод | Путь | Auth | Описание |
|-------|------|------|----------|
| POST | `/api/test_setup/reset` | Заголовок `X-Test-Token` = `E2E_TEST_TOKEN` | Сброс схемы БД |

---

## Модерация (схема)

```
Загрузка / публикация
        │
        ▼
   pending ──────────────────────────────┐
        │                                 │
        │              approve (админ)     │
        ▼                                 ▼
   rejected                          published
   (файл удалён)              (VK / Telegram, preview_url)
```

Код `approve` в [`routes/moderation.py`](src/routes/moderation.py) выставляет статус **`published`** сразу после одобрения (и при необходимости обновляет ссылки на посты).

---

## Известные ограничения

- **Redis** не обязателен: в памяти процесса есть fallback; для продакшена с несколькими инстансами нужен настоящий Redis.
- **`/docs`**, **`/redoc`**, **`/openapi.json`** отключены при `ENVIRONMENT != development` в [`main.py`](src/main.py).
- **SQLite** удобен для разработки; под высокую нагрузку и конкурентные записи рекомендуется PostgreSQL.
- Версия в `FastAPI(..., version=...)` в [`main.py`](src/main.py) может не совпадать с `pyproject.toml` — ориентироваться на теги релиза и `pyproject.toml`.

---

## Прочая документация в репозитории

| Файл | Содержание |
|------|------------|
| [CONTRIBUTING.md](CONTRIBUTING.md) | Ветки, PR, CI, git config, сообщения коммитов |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Системная схема, модели, ELO, Gemini, модерация |
| [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md) | Чеклист деплоя |
| [CHANGELOG.md](CHANGELOG.md) | История изменений |
| [SETUP_GUIDE.md](SETUP_GUIDE.md) | Детальная настройка OAuth и публикации |
