:sparkles: MagikBook API Changelog

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).

## [Unreleased]

### Добавлено

- Расширенная документация: README с hero, badges и примерами; AGENTS.md с контрактом агента; CONTRIBUTING.md с DoD; CHANGELOG в формате Keep a Changelog.
- Дорожная карта проекта в README.

### Изменено

- Визуальная консистентность документов: единые заголовки, shields, перекрёстные ссылки.

## [0.2.0] — 2026-04-09 — Релиз «наполнение и постинг»

### Добавлено

- **Кабинет автора** — `GET /api/cabinet/overview`: профиль, статистика, лучший промпт, бонус «маны».
- **Расширенная лента** — пагинация, фильтры по категориям (OR), виртуальный slug праздников.
- **OAuth** — Google, VK ID, Telegram Login Widget; связывание аккаунтов по email.
- **Загрузка файлов** — `POST /api/prompts/upload` с валидацией MIME/размера.
- **Модерация** — очередь, одобрение, отклонение, статистика.
- **Автопостинг** — VK (стена группы) и Telegram (канал) при одобрении; ручные fallback-эндпойнты.
- **Gemini service** — многоуровневый fallback между моделями и retry при 429.
- **ELO рейтинг** — пересчёт после каждого голоса с K=32 и нижней границей 800.
- **Реферальная система** — `referral_code`, `referred_by` в `users`.

### Изменено

- Фронтенд синхронизирован до v2.1.0 (submit, upload, модерация, битва).

## [0.2.1] — 2026-04-11

### Исправлено

- **VK публикация** — `wall.post` и `photos.saveWallPhoto` теперь передают параметры в теле POST (form-urlencoded), исправлен HTTP 414 на длинных промптах.
- **Маршрутизация** — `uploads.router` подключён до `prompts.router`, чтобы `GET /api/prompts/my-uploads` не обрабатывался как `/{prompt_id}`.
- **Кабинет** — счётчик «одобрено» теперь включает промпты со статусами `approved` и `published`.
- **Авторизация** — поле `is_admin` в ответе `GET /api/auth/me`.

## [0.1.1] — 2025-03-23 — Real Battle Voting System

### Изменено

- **Битва по-настоящему** — голоса сохраняются в `battle_votes`, уникальные ограничения против накрутки, реальные проценты на основе всех голосов.
- **ELO** — обновляется при каждом голосовании.
- **API битвы** — `POST /api/battle/vote` возвращает `{left_pct, right_pct, total_votes}`; `GET /api/battle/stats/{prompt_id}` для статистики промпта.

### Исправлено

- Анонимные пользователи могут голосовать через `session_token`.

## [0.1.0] — 2025-03-23 — Like System, Gemini Fix & Auth Stabilization

### Добавлено

- **Like System** — `GET/POST /api/prompts/{id}/like` с привязкой к пользователю.
- **Gemini fallback** — автопереключение моделей при rate limit и `model not found`.

### Исправлено

- **Telegram Login Widget** — стабильная реализация без конфликта с React DOM.
- **Auth flow** — сброс состояния модалки, устранён re-auth loop на `/submit`, корректная передача `Set-Cookie`.
- **Client-Server Consistency** — проксирование `/api/prompts/my-uploads` с cookie, правильные типы `moderation_status`.
- **Upload path** — фронтенд использует `/api/upload`.

## [0.0.2] — 2025-03-23 — Production Fixes & SSR/Docker Compatibility

### Добавлено

- **Миграции БД** — Alembic для добавления недостающих колонок (`result_example`, `result_image_url`, `affiliate_links_str`, `is_admin`).
- **Модели SavedPrompt & Like** — миграция с `session_token` на `user_id` с уникальным constraint.

### Исправлено

- **Production конфигурация** — `FRONTEND_URL` используется для OAuth редиректов.
- **Docker** — совместимость образа и SSR.

## [0.0.1] — 2025-03-23 — Cabinet, OAuth, Upload, Moderation, Publishing

### Добавлено

- Базовый API на FastAPI + SQLModel.
- Роутеры: `auth`, `prompts`, `battle`, `cabinet`, `grimoire`, `uploads`, `moderation`, `publish`, `users`.
- Сервисы: VK publisher, Telegram publisher, Gemini service, ELO service.
- Workers: `daily_prompt`, `elo_flush` на arq + Redis.
- Первичная документация: `API_DOCUMENTATION.md`, `SETUP_GUIDE.md`.
