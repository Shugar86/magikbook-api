# Deployment Checklist

Чеклист для проверки после развертывания новой версии.

## Предварительная настройка

- [ ] Создан `.env` файл из `.env.example`
- [ ] Установлены все переменные окружения
- [ ] Установлены зависимости: `pip install -e ".[dev]"`
- [ ] Инициализирована БД

## OAuth Настройка

### Google OAuth
- [ ] Создан проект в Google Cloud Console
- [ ] Включен Google+ API
- [ ] Создан OAuth 2.0 Client ID (тип: Web application)
- [ ] Добавлены redirect URIs:
  - [ ] `https://magikbook.ru/api/auth/google/callback`
- [ ] Сохранены `GOOGLE_CLIENT_ID` и `GOOGLE_CLIENT_SECRET` в `.env`
- [ ] Проверка: `curl -v https://magikbook.ru/api/auth/google` → редирект на Google

### VK OAuth
- [ ] Создано приложение на https://id.vk.com/about
- [ ] Добавлен redirect URI: `https://magikbook.ru/api/auth/vk/callback`
- [ ] Получен `VK_CLIENT_ID` (App ID)
- [ ] Получен `VK_CLIENT_SECRET` (Защищенный ключ)
- [ ] Сохранены в `.env`
- [ ] Проверка: `curl -v https://magikbook.ru/api/auth/vk` → редирект на VK

### Telegram OAuth
- [ ] Бот @magikbook_bot создан через @BotFather
- [ ] Домен magikbook.ru настроен в BotFather (`/setdomain`)
- [ ] `TELEGRAM_BOT_TOKEN` сохранен в `.env`

## Publishing Настройка

### VK Publishing
- [ ] Получен access token с правами `wall`, `photos`, `groups`
- [ ] Группа VK создана/настроена
- [ ] ID группы получен (с минусом: `-123456789`)
- [ ] Приложение добавлено в управление группой
- [ ] `VK_ACCESS_TOKEN` и `VK_GROUP_ID` сохранены в `.env`
- [ ] Проверка конфигурации:
  ```bash
  curl -H "Authorization: Bearer TOKEN" \
    https://magikbook.ru/api/moderation/stats
  ```
  → `"vk": true` в `publishing_configured`

### Telegram Publishing
- [ ] Бот добавлен администратором в канал
- [ ] Права на публикацию сообщений выданы
- [ ] Получен ID канала (`@channel_name` или `-100xxx`)
- [ ] `TELEGRAM_CHANNEL_ID` сохранен в `.env`
- [ ] Проверка: `"telegram": true` в `/api/moderation/stats`

## File Upload

- [ ] Директория `UPLOAD_DIR` создана и доступна для записи
- [ ] Nginx настроен: `client_max_body_size 50M;`
- [ ] Проверка загрузки:
  ```bash
  curl -X POST \
    -H "Authorization: Bearer TOKEN" \
    -F "title=Test" \
    -F "prompt_text=Test prompt with enough length..." \
    -F "category=art" \
    -F "media_type=image" \
    -F "ai_model=Midjourney" \
    -F "file=@test.jpg" \
    https://magikbook.ru/api/prompts/upload
  ```

## Модерация

- [ ] Проверка доступа к `/api/moderation`
- [ ] Тест approve с автопостингом:
  1. [ ] Загрузить тестовый промпт
  2. [ ] Вызвать `/api/moderation/{id}/approve`
  3. [ ] Проверить пост в VK группе
  4. [ ] Проверить сообщение в Telegram канале
  5. [ ] Проверить что файл удален с сервера
- [ ] Тест reject:
  1. [ ] Загрузить тестовый промпт
  2. [ ] Вызвать `/api/moderation/{id}/reject`
  3. [ ] Проверить что файл удален

## База данных

- [ ] Миграции применены (новые поля в User и Prompt)
- [ ] Проверка структуры таблиц:
  ```sql
  -- User должен иметь:
  -- google_id, vk_id, auth_provider, avatar_url
  
  -- Prompt должен иметь:
  -- moderation_status, moderated_by, moderated_at, ai_model, file_path, vk_post_url, telegram_message_url
  ```

## Безопасность

- [ ] `SECRET_KEY` изменен с дефолтного
- [ ] HTTPS включен
- [ ] HttpOnly cookies работают
- [ ] `DEBUG=false` (production)

## Мониторинг

- [ ] Логирование настроено
- [ ] Cron job для очистки старых файлов:
  ```bash
  0 2 * * * cd /opt/magikbook-api && /opt/magikbook-api/venv/bin/python -c "from src.utils.file_storage import cleanup_old_files; cleanup_old_files()"
  ```

## Финальная проверка

- [ ] Health check проходит:
  ```bash
  curl https://magikbook.ru/health
  # → {"status": "ok"}
  ```
- [ ] Все OAuth работают:
  - [ ] Google → callback → cookie установлен
  - [ ] VK → callback → cookie установлен
  - [ ] Telegram → widget работает
- [ ] Upload → Moderation → Publish flow работает end-to-end

## Откат (Rollback)

При необходимости отката:

1. Остановить сервис: `systemctl stop magikbook-api`
2. Восстановить БД из бэкапа (если миграции ломают существующие данные)
3. Переключить на предыдущий git commit
4. Перезапустить: `systemctl start magikbook-api`

## Post-Deployment

- [ ] Уведомление команды о новых endpoint'ах
- [ ] Обновление фронтенда (если нужно)
- [ ] Мониторинг ошибок в логах первые 24 часа
