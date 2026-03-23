# Changelog

## [2025-03-23] - Gemini API Rate Limit Fix

### Исправлено (Backend)

#### Gemini Service
- **Мульти-модельный fallback** — автоматический переключение при rate limit:
  - Приоритет: `gemini-2.0-flash-lite` → `gemini-2.0-flash` → `gemini-1.5-flash`
  - `flash-lite` — самая быстрая и дешевая модель для базовых задач
  - Автоматический retry при 429 Too Many Requests
  - Graceful degradation с информативным сообщением пользователю

- **Улучшенная обработка ошибок**:
  - Детекция rate limit ошибок по коду 429 и тексту "Quota exceeded"
  - Логирование каждой попытки модели
  - Чёткое сообщение при исчерпании всех квот

### Deployment
```bash
# Пересобрать и перезапустить бэкенд
cd /opt/projects/magikbook-api
git pull
docker compose up -d --build magikbook-api
```

---

## [2025-03-23] - Frontend Auth UI Fixes

### Исправлено (Frontend)

#### Telegram Login Widget
- **Новый компонент** `TelegramLoginWidget` — стабильная реализация без конфликта с React DOM:
  - Использует `useRef` вместо `getElementById` и `innerHTML`
  - Корректно управляет скриптом через императивный DOM вне React reconciler
  - Уникальный ID для каждого инстанса виджета
  - Предотвращает исчезновение кнопки после клика или ререндера

#### Auth Flow Stabilization
- **Header state management** — сброс состояния при открытии/закрытии модалки:
  - `handleOpenAuthModal` — единая функция открытия с reset `showTelegramButton`, `loading`, `error`
  - `handleCloseAuthModal` — единая функция закрытия с полным сбросом состояния
  - Telegram-вход больше не прячет кнопку навсегда после первого успеха

- **Submit page** — устранён re-auth loop:
  - Убран client-side redirect на login при `!res.ok` от `/api/auth/me`
  - Middleware остаётся единственным gatekeeper для `/submit`
  - Исправлен путь upload: `/api/prompts/upload` → `/api/upload`

- **Cookie propagation** — корректная передача всех Set-Cookie:
  - Используется `response.headers.getSetCookie()` вместо `get('set-cookie')`
  - Применено во всех auth route'ах: `login`, `register`, `telegram`
  - OAuth callbacks (Google/VK) теперь передают все cookie корректно

#### Client-Server Auth Consistency
- **API Route** `/api/prompts/my-uploads` — проксирование с передачей cookie:
  - Фиксит "Не удалось загрузить промпты" в кабинете
  - Единый auth flow с SSR (`/cabinet` page)

- **Исправлены типы** `MyUpload.status` → `MyUpload.moderation_status`:
  - Соответствие фактическому ответу бэкенда `/api/prompts/my-uploads`
  - Фильтрация и отображение статусов работает корректно

#### Protected Routes
- **`/submit` page** — добавлен `credentials: 'include'` для auth check
- **SplashCursor** — `pointer-events: none` для canvas, предотвращает перехват кликов

### Deployment
```bash
# Пересобрать и перезапустить фронтенд
cd /opt/projects/magikbook
git pull
docker compose up -d --build magikbook-frontend
```

---

## [2025-03-23] - Production Fixes & SSR/Docker Compatibility

### Исправлено

#### Database Schema
- **Добавлены колонки в `prompts`** - миграция для полей, отсутствующих в существующей БД:
  ```sql
  ALTER TABLE prompts ADD COLUMN result_example VARCHAR;
  ALTER TABLE prompts ADD COLUMN result_image_url VARCHAR;
  ALTER TABLE prompts ADD COLUMN affiliate_links_str VARCHAR;
  ```
  Эти поля были в модели SQLModel, но отсутствовали в SQLite, что вызывало `OperationalError`.

- **Добавлена колонка `is_admin` в `users`** - критичная для авторизации:
  ```sql
  ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0;
  ```
  Без этой колонки login/register возвращали 500 ошибку.

#### Configuration
- **FRONTEND_URL** - критически важная переменная для production:
  - OAuth редиректы (Google/VK) теперь корректно возвращают на `https://magikbook.ru`
  - Необходимо задать в `.env`: `FRONTEND_URL=https://magikbook.ru`

#### Models Update
- **SavedPrompt & Like** - миграция с `session_token` на `user_id` (FK):
  - Теперь сохранённые промпты и лайки привязаны к аккаунту пользователя
  - Уникальный constraint `(user_id, prompt_id)` предотвращает дублирование

### Production Deployment Notes

```bash
# 1. Миграция БД (внутри Docker контейнера)
docker exec magikbook-api sqlite3 /app/magikbook.db "
ALTER TABLE prompts ADD COLUMN result_example VARCHAR;
ALTER TABLE prompts ADD COLUMN result_image_url VARCHAR;
ALTER TABLE prompts ADD COLUMN affiliate_links_str VARCHAR;
ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0;
"

# 2. Обновить .env
echo "FRONTEND_URL=https://magikbook.ru" >> .env

# 3. Пересобрать и перезапустить
docker compose up -d --build magikbook-api magikbook-frontend
```

---

## [Unreleased] - Cabinet, OAuth, Upload, Moderation, Publishing

### Добавлено

#### User Cabinet
- **Endpoint** `GET /api/cabinet/overview` — полная сводка данных пользователя:
  - Профиль пользователя с флагом `can_claim_bonus` (доступность ежедневного бонуса)
  - Статистика: saved_count, submitted_count, approved_count, pending_count, rejected_count
  - Агрегированные метрики: total_likes, total_copies
  - Лучший промпт пользователя (по количеству лайков)
- **Новые схемы:** `CabinetOverview`, `CabinetStats`, `CabinetTopPrompt`, `CabinetUserOut`
- **Роутер** `src/routes/cabinet.py` с зависимостью `get_current_user`

#### Enhanced Existing Endpoints
- **`GET /api/prompts/my-uploads`** — добавлены поля `likes_count`, `copies`, `preview_url`
- **`GET /api/grimoire`** — добавлена пагинация (`skip`, `limit`), поля `preview_url`, `likes_count`, `copies`

#### OAuth Integration
- **Google OAuth** - endpoints `/api/auth/google` и `/api/auth/google/callback`
- **VK ID OAuth** - endpoints `/api/auth/vk` и `/api/auth/vk/callback`
- **Логика связывания аккаунтов** - при OAuth авторизации ищет существующего пользователя по email и связывает аккаунты
- **Новые поля в User модели:** `google_id`, `vk_id`, `auth_provider`, `avatar_url`

#### File Upload
- **Endpoint** `POST /api/prompts/upload` - загрузка промптов с файлами
- **Валидация файлов:** размер (max 50MB), MIME-type (image/video)
- **Хранение файлов:** временная директория `./uploads/temp/pending/`
- **Утилиты:** `src/utils/file_storage.py` для работы с файлами
- **Endpoint** `GET /api/prompts/my-uploads` - просмотр своих загруженных промптов

#### Moderation System
- **Новые поля в Prompt модели:**
  - `moderation_status` (pending/approved/rejected/published)
  - `moderated_by`, `moderated_at`
  - `ai_model` - нейросеть (Midjourney, DALL-E)
  - `file_path` - локальный путь к файлу
  - `vk_post_url`, `telegram_message_url`
- **Endpoints:**
  - `GET /api/moderation` - очередь на модерацию
  - `POST /api/moderation/{id}/approve` - одобрить и запустить автопостинг
  - `POST /api/moderation/{id}/reject` - отклонить и удалить файл
  - `GET /api/moderation/stats` - статистика модерации

#### Publishing (VK + Telegram)
- **VK Publisher** (`src/services/vk_publisher.py`)
  - Загрузка фото на сервер VK
  - Создание поста на стене группы
  - Получение `photo_url` для превью
- **Telegram Publisher** (`src/services/telegram_publisher.py`)
  - Отправка фото/видео в канал
  - HTML форматирование текста
- **Fallback endpoints:**
  - `POST /api/publish/vk` - ручная публикация в VK
  - `POST /api/publish/telegram` - ручная публикация в Telegram
  - `POST /api/publish/{id}/manual-preview` - установка preview_url вручную

#### Configuration
- **Новые env переменные:**
  ```
  # OAuth
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
  VK_CLIENT_ID, VK_CLIENT_SECRET, VK_REDIRECT_URI
  
  # Upload
  UPLOAD_DIR, MAX_FILE_SIZE, FILE_CLEANUP_DAYS
  
  # Publishing
  VK_ACCESS_TOKEN, VK_GROUP_ID
  TELEGRAM_CHANNEL_ID
  ```

### Зависимости
- Добавлены: `python-multipart>=0.0.9`, `aiofiles>=24.1.0`, `Pillow>=11.0.0`

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/auth/google` | Начало Google OAuth |
| GET | `/api/auth/google/callback` | Callback Google |
| GET | `/api/auth/vk` | Начало VK OAuth |
| GET | `/api/auth/vk/callback` | Callback VK |
| POST | `/api/prompts/upload` | Загрузка промпта с файлом |
| GET | `/api/prompts/my-uploads` | Мои загрузки |
| GET | `/api/moderation` | Очередь модерации |
| POST | `/api/moderation/{id}/approve` | Одобрить + автопостинг |
| POST | `/api/moderation/{id}/reject` | Отклонить |
| GET | `/api/moderation/stats` | Статистика |
| POST | `/api/publish/vk` | Ручная публикация VK |
| POST | `/api/publish/telegram` | Ручная публикация Telegram |
| POST | `/api/publish/{id}/manual-preview` | Установить preview_url |

### Файлы

#### Новые:
- `src/utils/file_storage.py` - работа с файлами
- `src/routes/uploads.py` - upload endpoints
- `src/routes/moderation.py` - moderation endpoints
- `src/routes/publish.py` - fallback publishing endpoints
- `src/services/vk_publisher.py` - VK API интеграция
- `src/services/telegram_publisher.py` - Telegram Bot API интеграция

#### Измененные:
- `src/config.py` - добавлены настройки OAuth и publishing
- `src/models/db_models.py` - новые поля для moderation и OAuth
- `src/routes/auth.py` - Google и VK OAuth endpoints
- `src/main.py` - подключены новые роутеры
- `pyproject.toml` - новые зависимости

### Документация
- `API_DOCUMENTATION.md` - полная документация API
- `SETUP_GUIDE.md` - руководство по настройке
- `CHANGELOG.md` - этот файл

---

## Миграция базы данных

При обновлении существующей БД необходимо добавить новые поля:

### Для SQLite

```sql
-- User table
ALTER TABLE users ADD COLUMN google_id VARCHAR;
ALTER TABLE users ADD COLUMN vk_id VARCHAR;
ALTER TABLE users ADD COLUMN auth_provider VARCHAR DEFAULT 'email';
ALTER TABLE users ADD COLUMN avatar_url VARCHAR;

CREATE UNIQUE INDEX ix_users_google_id ON users(google_id);
CREATE UNIQUE INDEX ix_users_vk_id ON users(vk_id);

-- Prompt table
ALTER TABLE prompts ADD COLUMN moderation_status VARCHAR DEFAULT 'published';
ALTER TABLE prompts ADD COLUMN moderated_by VARCHAR;
ALTER TABLE prompts ADD COLUMN moderated_at TIMESTAMP;
ALTER TABLE prompts ADD COLUMN ai_model VARCHAR;
ALTER TABLE prompts ADD COLUMN file_path VARCHAR;
ALTER TABLE prompts ADD COLUMN vk_post_url VARCHAR;
ALTER TABLE prompts ADD COLUMN telegram_message_url VARCHAR;

CREATE INDEX ix_prompts_moderation_status ON prompts(moderation_status);
```

### Для PostgreSQL (с SQLAlchemy Alembic)

```bash
# Создать миграцию
alembic revision -m "add_oauth_and_moderation_fields"

# Применить
alembic upgrade head
```

### Автоматическая миграция

При использовании SQLite с SQLModel, таблицы будут автоматически обновлены при пересоздании. Для production PostgreSQL рекомендуется использовать Alembic.

---

## Тестирование

### Проверка OAuth

```bash
# Google
curl -v http://localhost:8000/api/auth/google

# VK
curl -v http://localhost:8000/api/auth/vk
```

### Проверка Upload

```bash
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  -F "title=Test" \
  -F "prompt_text=This is a long test prompt..." \
  -F "category=art" \
  -F "media_type=image" \
  -F "ai_model=Midjourney" \
  -F "file=@test.jpg" \
  http://localhost:8000/api/prompts/upload
```

### Проверка Moderation

```bash
# Получить очередь
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/moderation?status=pending

# Одобрить
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/moderation/PROMPT_ID/approve
```

---

## Известные ограничения

1. **Moderation Access** - все авторизованные пользователи могут модерировать (для упрощения). Добавьте проверку `is_admin` для production.

2. **File Storage** - файлы хранятся локально. Для production с большим объемом рекомендуется S3.

3. **VK Publishing** - только для изображений (video не поддерживается VK wall.post с загрузкой файла).

4. **Telegram Email** - при OAuth через Telegram без email генерируется фейковый email `tg_{id}@telegram.local`.

---

## Roadmap

- [ ] Добавить `is_admin` поле в User модель
- [ ] Интеграция с S3 для хранения файлов
- [ ] WebSocket notifications для модерации
- [ ] Email notifications при отклонении промпта
- [ ] Retry logic для failed publishing
- [ ] Rate limiting на upload (5 файлов/час на пользователя)
- [ ] Celery + Redis для async publishing
- [ ] Image optimization перед загрузкой (resize, compress)
