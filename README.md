# MagikBook API

Backend API для MagikBook - платформы для генерации и обмена AI промптами.

Чеклист продакшена (env, миграции, SMTP): в репозитории фронтенда файл `docs/PRODUCTION.md`, либо см. `.env.example` здесь.

## Возможности

- **OAuth Аутентификация** - Google, VK ID, Telegram
- **AI Генерация** - Stream-based генерация промптов через Google Gemini
- **File Upload** - Загрузка изображений и видео с валидацией
- **Модерация** - Система модерации контента
- **Автопостинг** - Публикация в VK и Telegram
- **ELO Рейтинг** - Система ранжирования промптов

## Быстрый старт

```bash
# 1. Установка
pip install -e ".[dev]"

# 2. Конфигурация
cp .env.example .env
# Отредактируйте .env файл

# 3. Инициализация БД
python -c "from src.database import init_db; import asyncio; asyncio.run(init_db())"

# 4. Запуск
python -m uvicorn src.main:app --reload --port 8000
```

## Документация

| Документ | Описание |
|----------|----------|
| [API_DOCUMENTATION.md](API_DOCUMENTATION.md) | Полная документация API endpoints |
| [SETUP_GUIDE.md](SETUP_GUIDE.md) | Пошаговая настройка OAuth и publishing |
| [CHANGELOG.md](CHANGELOG.md) | История изменений и миграции |

## Структура проекта

```
magikbook-api/
├── src/
│   ├── config.py              # Конфигурация (pydantic-settings)
│   ├── database.py            # SQLModel/SQLAlchemy setup
│   ├── dependencies.py        # FastAPI dependencies
│   ├── main.py                # FastAPI app entry point
│   ├── models/
│   │   ├── db_models.py       # SQLModel таблицы
│   │   └── schemas.py         # Pydantic request/response models
│   ├── routes/
│   │   ├── auth.py            # OAuth (Google, VK, Telegram)
│   │   ├── battle.py          # ELO battle system
│   │   ├── generate.py        # AI generation (Gemini)
│   │   ├── grimoire.py        # Saved prompts
│   │   ├── moderation.py      # Content moderation
│   │   ├── paywall.py         # Telegram Stars, subscriptions
│   │   ├── prompts.py         # Prompt CRUD, feed, likes
│   │   ├── publish.py         # Fallback publishing endpoints
│   │   ├── uploads.py         # File upload
│   │   └── test_setup.py      # Test utilities
│   ├── services/
│   │   ├── gemini_service.py  # Google Gemini integration
│   │   ├── telegram_publisher.py  # Telegram Bot API
│   │   └── vk_publisher.py    # VK API
│   └── utils/
│       └── file_storage.py    # File validation & storage
├── pyproject.toml
├── .env.example
├── API_DOCUMENTATION.md
├── SETUP_GUIDE.md
└── CHANGELOG.md
```

## API Overview

### Аутентификация

```
GET  /api/auth/google              # Начало Google OAuth
GET  /api/auth/google/callback     # Callback от Google
GET  /api/auth/vk                  # Начало VK OAuth
GET  /api/auth/vk/callback         # Callback от VK
POST /api/auth/telegram            # Telegram Login Widget
POST /api/auth/register            # Email регистрация
POST /api/auth/login               # Email вход
POST /api/auth/logout              # Выход
GET  /api/auth/me                  # Инфо о пользователе
```

### Промпты

```
GET  /api/prompts/homepage         # Главная страница
GET  /api/prompts/feed             # Лента с фильтрами
GET  /api/prompts/{id}             # Детали промпта
POST /api/prompts/publish          # Публикация (legacy)
POST /api/prompts/upload           # Загрузка с файлом
POST /api/prompts/{id}/like        # Лайк
POST /api/prompts/{id}/copy-count  # Увеличить счетчик копий
```

### Модерация

```
GET  /api/moderation               # Очередь модерации
GET  /api/moderation/stats         # Статистика
POST /api/moderation/{id}/approve   # Одобрить + автопостинг
POST /api/moderation/{id}/reject    # Отклонить
```

### AI Генерация

```
POST /api/generate                 # Stream-based генерация (SSE)
```

## Environment Variables

См. [.env.example](.env.example) для полного списка.

**Обязательные для OAuth:**
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `VK_CLIENT_ID`, `VK_CLIENT_SECRET`

**Обязательные для публикации:**
- `VK_ACCESS_TOKEN`, `VK_GROUP_ID`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`

**Обязательные для AI:**
- `GOOGLE_API_KEY`

## Разработка

### Запуск с hot reload

```bash
python -m uvicorn src.main:app --reload --port 8000
```

### Тесты

```bash
pytest
```

### Линтинг

```bash
ruff check .
```

## Production Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install -e "."

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Systemd

См. [SETUP_GUIDE.md](SETUP_GUIDE.md) для примера systemd service файла.

### Nginx

```nginx
location /api/ {
    proxy_pass http://localhost:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    client_max_body_size 50M;
}
```

## Архитектура

```
┌─────────────┐
│   Frontend  │  Next.js (порт 3002)
│  (Nginx)    │
└──────┬──────┘
       │ HTTPS
       │
┌──────▼──────┐
│    Nginx    │  (порт 443)
│   Proxy     │
└──────┬──────┘
       │
       ├──────────────┐
       │              │
┌──────▼──────┐ ┌─────▼──────┐
│   Next.js   │ │  FastAPI   │
│   (3002)    │ │   (8000)   │
└─────────────┘ └─────┬──────┘
                      │
           ┌──────────┼──────────┐
           │          │          │
      ┌────▼────┐ ┌──▼───┐ ┌───▼────┐
      │PostgreSQL│ │Redis │ │Uploads │
      │  (5432)  │ │(6379)│ │ /temp  │
      └──────────┘ └──────┘ └────────┘
```

## Contributing

1. Fork репозиторий
2. Создайте feature branch (`git checkout -b feature/amazing`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing`)
5. Создайте Pull Request

## License

MIT

## Support

По вопросам и предложениям:
- Telegram: @magikbook_support
- Email: support@magikbook.ru
