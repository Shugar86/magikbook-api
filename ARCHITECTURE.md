# Архитектура MagikBook

Единый обзор бэкенда и связки с фронтендом. Детали API: [README.md](README.md).

---

## Системная схема

```
[Browser]
    │
    ├── Next.js (порт 3000)
    │       ├── App Router (страницы, SSR)
    │       └── rewrites: /api/* и /uploads/* → BACKEND_URL
    │
    └── FastAPI (порт 8000)
            ├── SQLite / PostgreSQL (SQLModel / SQLAlchemy async)
            ├── Redis (опционально; иначе in-memory fallback в процессе)
            ├── Google Gemini API (генерация текста, SSE)
            ├── VK API (автопост при модерации, ручной fallback)
            └── Telegram Bot API (логин, посты в канал)
```

Публичный домен обычно проксирует на Next.js; браузер **не** обращается к FastAPI напрямую, кроме случаев прямой настройки reverse proxy на API.

---

## Модели данных (`src/models/db_models.py`)

ORM — SQLModel, таблицы задаются в классах `table=True`.

### `users`

| Поле | Смысл |
|------|--------|
| `id` | UUID строкой, PK |
| `email`, `telegram_id`, `google_id`, `vk_id` | Уникальные внешние идентификаторы (nullable) |
| `hashed_password` | Для email-логина |
| `username` | Отображаемое имя |
| `tokens` | Баланс «маны» для генераций |
| `referral_code`, `referred_by` | Реферальная логика |
| `auth_provider` | `email` / `google` / `vk` / `telegram` |
| `avatar_url` | URL аватара |
| `is_admin` | Доступ к модерации и админ-эндпойнтам |

### `prompts`

| Поле | Смысл |
|------|--------|
| Базовые поля `PromptBase` | `title`, `prompt_text`, `preview_url`, `media_type`, `category`, JSON-строки `variables`, `target_models`, `tone` |
| `elo_rating` | Рейтинг битвы (по умолчанию 1200) |
| `likes_count`, `copies`, `remixes` | Метрики |
| `is_trending`, `is_new` | Флаги ленты |
| `created_at`, `author_id` | Время и автор |
| `moderation_status` | `pending` \| `approved` \| `rejected` \| `published` (в коде approve сразу ведёт к `published`) |
| `moderated_by`, `moderated_at` | Кто и когда модерировал |
| `ai_model`, `file_path` | Модель ИИ и локальный путь к файлу |
| `vk_post_url`, `telegram_message_url` | Ссылки на посты |
| `result_example`, `result_image_url` | Примеры результата |
| `affiliate_links_str` | JSON партнёрских ссылок |

### `likes`

Связь пользователь–промпт, уникальная пара `(user_id, prompt_id)`.

### `saved_prompts` (гримуар)

Сохранённые пользователем промпты, уникальная пара `(user_id, prompt_id)`.

### `battle_votes`

| Поле | Смысл |
|------|--------|
| `user_id` | Авторизованный голосующий (nullable) |
| `session_token` | Анонимная сессия (nullable) |
| `winner_id`, `loser_id` | FK на `prompts` |

Уникальные ограничения: один голос на пару для пользователя и отдельно для сессии.

### `email_otps`

Одноразовые коды для входа по email: `email`, `code`, `created_at`, `used`.

---

## Модерация: состояния и переходы

Допустимые значения `moderation_status` в модели: **`pending`**, **`approved`**, **`rejected`**, **`published`**.

| Переход | Кто | Как в коде |
|---------|-----|------------|
| Появление записи | Пользователь | Загрузка `/api/prompts/upload` → обычно `pending` |
| Публикация в ленту после одобрения | Админ | `POST .../approve` → статус **`published`**, вызов VK/Telegram, обновление превью |
| Отклонение | Админ | `POST .../reject` → `rejected`, файл удаляется |
| Ручные обходы | Авторизованный пользователь | `publish.py`: ручной VK/TG или `manual-preview` может перевести `approved` → `published` |

Публичная лента и битва отбирают промпты с допустимыми статусами (см. `PromptService` / `BattleService`).

---

## ELO в битве

1. При **`POST /api/battle/vote`** `BattleService.record_vote`:
   - проверяет дубликат голоса по `user_id` или `session_token`;
   - создаёт запись `BattleVote`;
   - читает текущие `elo_rating` победителя и проигравшего;
   - вызывает **`EloService.calculate_new_ratings(R_w, R_l, k_factor=32)`** из [`elo_service.py`](src/services/elo_service.py).

2. Формула (K = 32):
   - \(E_w = 1 / (1 + 10^{(R_l - R_w)/400})\), \(E_l = 1 / (1 + 10^{(R_w - R_l)/400})\)
   - \(R_w' = \text{round}(R_w + K \cdot (1 - E_w))\)
   - \(R_l' = \text{round}(R_l + K \cdot (0 - E_l))\)
   - для проигравшего применяется пол **`ELO_MIN` = 800** (нижняя граница).

3. Дополнительно: если новый ELO > 1400, у промпта выставляется `is_trending = True`.

4. В репозитории есть **`workers/elo_flush.py`** — отдельный сценарий чтения ключей Redis `battle:*:wins`; основной путь обновления ELO в продакшене — **прямо в `record_vote`**. Воркер может дублировать или устаревать относительно текущей логики — ориентироваться на `battle_service.py`.

---

## Gemini: многоуровневый fallback

Список моделей в порядке попытки — константа **`GEMINI_MODELS`** в [`gemini_service.py`](src/services/gemini_service.py):

1. `gemini-2.5-flash-lite`
2. `gemini-2.5-flash`
3. `gemini-2.0-flash-lite`
4. `gemini-2.0-flash`
5. `gemini-1.5-flash`

Поведение:

- Для каждой модели вызывается стрим `generate_content_stream` с таймаутом `settings.gemini_stream_timeout_seconds`.
- Ошибки с текстом вроде **429**, **quota**, **too many requests** трактуются как `RateLimitError` → переход к следующей модели.
- Строки **not found**, **not supported**, **invalid model** — тоже переход к следующей модели.
- При **TimeoutError** стрим завершается сообщением об ошибке пользователю.
- Если все модели исчерпаны — в поток уходит сообщение о квоте/недоступности.

---

## Воркеры (`src/workers/`)

| Файл | Назначение |
|------|------------|
| `daily_prompt.py` | Генерация «заклинания дня» через Gemini и запись в БД (предполагается cron/arq) |
| `elo_flush.py` | Пакетная обработка голосов из Redis (альтернативный/legacy путь к ELO) |

Для запуска воркеров нужен рабочий **Redis** и отдельный процесс/контейнер — см. комментарии в файлах.

---

## Прочие слои

| Модуль | Роль |
|--------|------|
| [`dependencies.py`](src/dependencies.py) | Извлечение JWT из cookie `access_token` или Bearer |
| [`redis_client.py`](src/redis_client.py) | Redis async или `_InMemoryRedis` |
| [`utils/file_storage.py`](src/utils/file_storage.py) | Валидация MIME/размера, пути к `UPLOAD_DIR` |

---

## Версионирование API

В [`src/main.py`](src/main.py) у приложения FastAPI указано поле `version` (строка). Версия пакета в [`pyproject.toml`](pyproject.toml) может отличаться — для релизов ориентироваться на теги Git и `pyproject.toml`.
