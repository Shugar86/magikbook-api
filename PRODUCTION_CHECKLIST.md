# Чеклист продакшена MagikBook

Расширяет и консолидирует шаги из чеклиста фронтенда (`magikbook/docs/PRODUCTION.md` в репозитории `magikbook`). Переменные окружения см. [`.env.example`](.env.example) и [README.md](README.md).

---

## Перед первым деплоем

- [ ] Скопировать `.env.example` → `.env` в **magikbook-api** и **magikbook**, заполнить обязательные значения.
- [ ] Установить **`ENVIRONMENT=production`** в API для Secure-cookie (и HTTPS на сайте).
- [ ] Задать **`DATABASE_URL`** на PostgreSQL (async), не использовать SQLite на общем хосте без бэкапов.
- [ ] Задать **`SECRET_KEY`** (длина ≥ 32 символов, случайная строка).
- [ ] Задать **`FRONTEND_URL`** — публичный URL фронта (CORS).
- [ ] Выполнить миграции: `scripts/upgrade_db.sh` или `alembic upgrade head` в окружении API.
- [ ] Убедиться, что каталог **`UPLOAD_DIR`** существует и доступен процессу API.
- [ ] Установить **`is_admin = true`** первому пользователю вручную в БД (таблица `users`), либо после первого входа через **`POST /api/admin/grant/{user_id}`** с другого админа.
- [ ] Проверить **VK**: `VK_ACCESS_TOKEN`, `VK_GROUP_ID` — вызов API VK вручную или тестовый пост (см. комментарии в `.env.example` про права токена).
- [ ] Проверить **Telegram**: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID` — тестовое сообщение в канал (если используется автопост).
- [ ] Для email-OTP: `SMTP_*` или Resend, см. [README.md](README.md); проверка `curl` на `send-otp` как в документе фронта `docs/PRODUCTION.md`.
- [ ] На фронте: **`BACKEND_URL`** = внутренний URL API (например `http://magikbook-api:8000` в Docker Compose).
- [ ] Сайт отдаётся по **HTTPS** (иначе Secure cookie в проде не сохранятся в браузере).

---

## Бэкап `magikbook.db` (SQLite на VDS)

Файл `./magikbook.db` монтируется с хоста в контейнер (`docker-compose.yml`); **в git не входит** (`.gitignore`). Любая подмена файла на хосте сразу меняет прод-данные (пользователи, админы, промпты).

Журнал одного восстановления (админы, VK-промпты, cron-бэкап): [`docs/INCIDENT_DB_RECOVERY_2026-04-10.md`](docs/INCIDENT_DB_RECOVERY_2026-04-10.md).

- [ ] Настроить **регулярное копирование** на хост, например cron раз в сутки:  
  `scripts/backup_magikbook_db.sh` — кладёт снимки в `data/backups/magikbook/` (каталог в `.gitignore`), по умолчанию хранит 14 дней (`MAGIKBOOK_DB_BACKUP_RETAIN_DAYS`).
- [ ] Перед ручной правкой БД: `cp magikbook.db magikbook.db.bak.$(date +%Y%m%d_%H%M%S)`.
- [ ] Не класть пустой `magikbook.db` из образа поверх хостового файла при деплое.

Пример cron:

```cron
0 3 * * * root /opt/projects/magikbook-api/scripts/backup_magikbook_db.sh >> /var/log/magikbook-db-backup.log 2>&1
```

---

## После каждого деплоя

- [ ] Выполнить **миграции БД** до перезапуска контейнеров с новой версией кода.
- [ ] Проверить **`GET /health`** на стороне FastAPI (прямой запрос к порту 8000 или через внутренний URL) — ответ `200`, тело `{"status":"ok"}`.
- [ ] Открыть **`/admin`** на фронте: неавторизованный пользователь перенаправляется на логин; пользователь без `is_admin` — на главную (см. [`magikbook/src/app/admin/layout.tsx`](../magikbook/src/app/admin/layout.tsx)).
- [ ] Дымовой прогон: главная, лента, карточка промпта, вход (если OTP — SMTP), битва, генерация (если задан `GOOGLE_API_KEY`).

---

## Опционально

- [ ] **Redis** (`REDIS_URL`) для согласованных лимитов между несколькими инстансами API и для ежедневного бонуса без 503.
- [ ] Мониторинг логов и дискового пространства под `uploads/`.

---

## Быстрые ссылки

| Документ | Где |
|----------|-----|
| Env и смоук фронта | Репозиторий `magikbook`, файл `docs/PRODUCTION.md` |
| Полный список API | [README.md](README.md) |
| Архитектура | [ARCHITECTURE.md](ARCHITECTURE.md) |
