# MagikBook Setup Guide

Полное руководство по настройке бэкенда MagikBook.

## Быстрый старт

```bash
# 1. Клонирование и установка
cd magikbook-api
pip install -e ".[dev]"

# 2. Создание .env файла
cp .env.example .env
# Отредактируйте .env

# 3. Инициализация БД
python -c "from src.database import init_db; import asyncio; asyncio.run(init_db())"

# 4. Запуск
python -m uvicorn src.main:app --reload --port 8000
```

---

## Настройка OAuth

### 1. Google OAuth

#### Шаг 1: Создание проекта в Google Cloud Console

1. Перейдите на [Google Cloud Console](https://console.cloud.google.com/projectselector2/auth/)
2. Создайте новый проект (например, "MagikBook")
3. Включите **Google+ API** в Library

#### Шаг 2: Создание OAuth Client ID

1. Перейдите в **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
2. Выберите тип **Web application**
3. Добавьте Authorized redirect URIs:
   - `https://magikbook.ru/api/auth/google/callback` (production)
   - `http://localhost:8000/api/auth/google/callback` (development)
4. Сохраните **Client ID** и **Client Secret**

#### Шаг 3: Настройка .env

```bash
GOOGLE_CLIENT_ID=123456789-abcdef.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxx
GOOGLE_REDIRECT_URI=https://magikbook.ru/api/auth/google/callback
```

---

### 2. VK ID OAuth

#### Шаг 1: Создание приложения

1. Перейдите на [VK ID for Developers](https://id.vk.com/about)
2. Нажмите **"Создать приложение"**
3. Выберите платформу **Web**

#### Шаг 2: Настройка redirect URI

1. В настройках приложения добавьте:
   - `https://magikbook.ru/api/auth/vk/callback` (production)
   - `http://localhost:8000/api/auth/vk/callback` (development)

#### Шаг 3: Получение credentials

1. Скопируйте **App ID** → `VK_CLIENT_ID`
2. Перейдите в **Настройки** → **Защищенный ключ** → `VK_CLIENT_SECRET`

#### Шаг 4: Настройка .env

```bash
VK_CLIENT_ID=12345678
VK_CLIENT_SECRET=xxxxxxxxxxxxxxxx
VK_REDIRECT_URI=https://magikbook.ru/api/auth/vk/callback
```

---

### 3. Telegram OAuth (уже настроен)

Telegram Login Widget уже работает через бота @magikbook_bot.

Для работы в `.env` должно быть:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

---

## Настройка публикации

### 1. VK Постинг

#### Шаг 1: Создание токена

1. Перейдите на [VK Dev](https://dev.vk.com/)
2. Создайте **Standalone-приложение** (или используйте существующее)
3. Получите токен с правами:
   - `wall` (постинг на стену)
   - `photos` (загрузка фото)
   - `video` (загрузка видео для постов с роликами)
   - `groups` (управление группой)

**Или через Implicit Flow:**
```
https://oauth.vk.com/authorize?client_id=YOUR_APP_ID&display=page&redirect_uri=https://oauth.vk.com/blank.html&scope=wall,photos,video,groups&response_type=token&v=5.199
```

#### Шаг 2: Настройка группы

1. Создайте группу VK или используйте существующую
2. Получите ID группы (в настройках группы → Адрес → ID)
   - ID будет с минусом: `-123456789`
3. Добавьте приложение в управление группой:
   - Управление → Приложения → Добавить приложение

#### Шаг 3: Настройка .env

```bash
VK_ACCESS_TOKEN=vk1.a.xxxxxxxxxxxxxxxx
VK_GROUP_ID=-123456789
```

---

### 2. Telegram Постинг

#### Шаг 1: Создание бота

1. Напишите [@BotFather](https://t.me/botfather)
2. Создайте нового бота: `/newbot`
3. Сохраните **token**

#### Шаг 2: Создание канала

1. Создайте канал в Telegram
2. Добавьте бота администратором:
   - Управление каналом → Администраторы → Добавить администратора
   - Выберите бота, дайте права на публикацию сообщений

#### Шаг 3: Получение ID канала

**Вариант A:** Используйте username канала
```bash
TELEGRAM_CHANNEL_ID=@your_channel_username
```

**Вариант B:** Числовой ID
1. Отправьте любое сообщение в канал
2. Откройте `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Найдите `"chat":{"id":-100xxxxxxxxxx` - это ID канала

#### Шаг 4: Настройка .env

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxyz
TELEGRAM_CHANNEL_ID=@magikbook_channel
```

---

## Настройка базы данных

### SQLite (по умолчанию, для разработки)

```bash
DATABASE_URL=sqlite+aiosqlite:///./magikbook.db
```

### PostgreSQL (для production)

```bash
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/magikbook
```

**Инициализация:**
```bash
# Автоматически создаст таблицы при первом запуске
python -m uvicorn src.main:app
```

---

## Пример .env файла

```bash
# =============================================================================
# Основные настройки
# =============================================================================

# Database
DATABASE_URL=sqlite+aiosqlite:///./magikbook.db
# DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/magikbook

# Redis (опционально)
REDIS_URL=redis://localhost:6379/0
# REDIS_URL=  # Пусто = in-memory fallback

# Security
SECRET_KEY=your-secret-key-here-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=10080  # 7 days

# Frontend URL (для CORS)
FRONTEND_URL=https://magikbook.ru
# FRONTEND_URL=http://localhost:3000  # Development

# =============================================================================
# Google OAuth
# =============================================================================
GOOGLE_CLIENT_ID=123456789-abcdef.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxx
GOOGLE_REDIRECT_URI=https://magikbook.ru/api/auth/google/callback

# =============================================================================
# VK ID OAuth
# =============================================================================
VK_CLIENT_ID=12345678
VK_CLIENT_SECRET=xxxxxxxxxxxxxxxx
VK_REDIRECT_URI=https://magikbook.ru/api/auth/vk/callback

# =============================================================================
# VK Publishing
# =============================================================================
VK_ACCESS_TOKEN=vk1.a.xxxxxxxxxxxxxxxx
VK_GROUP_ID=-123456789

# =============================================================================
# Telegram Bot (для авторизации и постинга)
# =============================================================================
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxyz
TELEGRAM_CHANNEL_ID=@magikbook_channel

# =============================================================================
# File Upload
# =============================================================================
UPLOAD_DIR=./uploads/temp
MAX_FILE_SIZE=52428800  # 50 MB
FILE_CLEANUP_DAYS=7

# =============================================================================
# AI Generation (Gemini)
# =============================================================================
GOOGLE_API_KEY=your_gemini_api_key_here
GEMINI_STREAM_TIMEOUT_SECONDS=45
```

---

## Проверка настройки

### 1. Проверка OAuth

```bash
# Проверка Google
curl http://localhost:8000/api/auth/google
# Должен вернуть редирект на accounts.google.com

# Проверка VK
curl http://localhost:8000/api/auth/vk
# Должен вернуть редирект на id.vk.com
```

### 2. Проверка публикации

```bash
# Проверка конфигурации
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/moderation/stats

# Должен вернуть:
# {
#   "publishing_configured": {
#     "vk": true,
#     "telegram": true
#   }
# }
```

### 3. Проверка загрузки файлов

```bash
# Создайте тестовый файл и загрузите
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "title=Test" \
  -F "prompt_text=This is a test prompt with enough length..." \
  -F "category=art" \
  -F "media_type=image" \
  -F "ai_model=Midjourney" \
  -F "file=@test.jpg" \
  http://localhost:8000/api/prompts/upload
```

---

## Troubleshooting

### OAuth не работает

**Проблема:** `OAuth not configured` (503 ошибка)

**Решение:**
```bash
# Проверьте что переменные заданы
echo $GOOGLE_CLIENT_ID
echo $VK_CLIENT_ID

# Или в Python:
python -c "from src.config import settings; print(settings.google_client_id)"
```

---

### VK публикация не работает

**Проблема:** Ошибка при публикации

**Проверки:**
1. Токен валидный?
   ```bash
   curl "https://api.vk.com/method/users.get?access_token=YOUR_TOKEN&v=5.199"
   ```
2. Бот/приложение добавлено в админы группы?
3. ID группы указан с минусом? (`-123456789`)

---

### Telegram публикация не работает

**Проблема:** Бот не может отправить сообщение

**Проверки:**
1. Бот является администратором канала?
2. Права на публикацию сообщений включены?
3. Channel ID указан правильно?
   - С @ для username: `@channelname`
   - Или числовой: `-100xxxxxxxxxx`

---

### Файлы не загружаются

**Проблема:** 413 Payload Too Large

**Решение:** Проверьте `MAX_FILE_SIZE` и nginx limit (если используется):
```nginx
client_max_body_size 50M;
```

---

## Развертывание на production

### 1. Nginx конфигурация

```nginx
server {
    listen 80;
    server_name magikbook.ru;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name magikbook.ru;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    client_max_body_size 50M;

    # Frontend (Next.js на порту 3002)
    location / {
        proxy_pass http://localhost:3002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2. Systemd service

```ini
# /etc/systemd/system/magikbook-api.service
[Unit]
Description=MagikBook API
After=network.target

[Service]
Type=simple
User=magikbook
WorkingDirectory=/opt/magikbook-api
Environment=PATH=/opt/magikbook-api/venv/bin
EnvironmentFile=/opt/magikbook-api/.env
ExecStart=/opt/magikbook-api/venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

### 3. Автоочистка файлов (cron)

```bash
# Добавьте в crontab
0 2 * * * cd /opt/magikbook-api && /opt/magikbook-api/venv/bin/python -c "from src.utils.file_storage import cleanup_old_files; cleanup_old_files()" >> /var/log/magikbook/cleanup.log 2>&1
```

---

## Полезные ссылки

- [Google OAuth 2.0 Docs](https://developers.google.com/identity/protocols/oauth2)
- [VK ID Docs](https://id.vk.com/about)
- [VK API Docs](https://dev.vk.com/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
