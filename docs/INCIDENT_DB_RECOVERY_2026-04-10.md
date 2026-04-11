# Зафиксированный эпизод: восстановление БД MagikBook (SQLite)

**Дата фиксации:** 2026-04-10 (UTC, сервер `/opt/projects`).  
**Цель записи:** сохранить контекст инцидента (пропажа админов и «не те» промпты), выполненные действия и артефакты, чтобы не потерять при смене чата или среды.

---

## Симптомы

- В UI не отображалась модерация (нет пользователей с `is_admin = 1` в БД).
- Ожидались опубликованные промпты с VK («Девушка-Галактика», «Оживающая скульптура Кинцуги»), фактически в БД были другие данные (старый кинцуги с локальным файлом, без эталонных VK-полей).
- Отдельный поиск `magikbook*.db` в `/opt/projects` не выявил готового бэкапа MagikBook (кроме bind-mount файла на хосте).

**Вероятная причина класса:** подмена/откат файла `magikbook.db` или работа не с тем инстансом; восстановление — с хоста/бэкапов/ручной правкой. (Отдельно: если `magikbook.db` случайно был в git, см. [INCIDENT_GIT_TRACKED_SQLITE_2026-04-11.md](INCIDENT_GIT_TRACKED_SQLITE_2026-04-11.md).)

---

## Что сделано (выполнено на сервере)

1. **Снимок до изменений:**  
   ` /opt/projects/magikbook-api/magikbook.db.bak.20260410_100053 `  
   (создан перед SQL; при необходимости отката скопировать обратно на `magikbook.db` при остановленном API).

2. **Пользователи:**  
   `UPDATE users SET is_admin = 1` для:
   - `minerg000@gmail.com`
   - `nsn@infodon.ru`
   - `nsnplus@ya.ru`

3. **Промпты:**
   - **UPDATE** существующей записи id `83bd2e8a-28ea-42d8-9054-1f449d049ee6`: заголовок «Оживающая скульптура Кинцуги», `moderation_status = published`, очистка `file_path`, заполнение `vk_post_url` (`https://vk.com/wall-123919685_5787`), повышение `elo_rating`, превью — URL шаблона `sun9-55.userapi.com/...`.
   - **INSERT** новой записи id `93f39208-e7e3-4843-bb03-311469a3f572`: «Девушка-Галактика», `published`, `vk_post_url` `https://vk.com/wall-123919685_5788`, превью — шаблон `sun9-74.userapi.com/...`, `created_at` по эталону (2026-04-09 13:32:17 UTC в данных).

4. **Профилактика:**
   - Скрипт: [`scripts/backup_magikbook_db.sh`](../scripts/backup_magikbook_db.sh)
   - Каталог снимков: `data/backups/magikbook/`
   - Cron: `/etc/cron.d/magikbook-db-backup` (ежедневно 03:00 UTC, лог `/var/log/magikbook-db-backup.log`)
   - Документация: раздел в [`PRODUCTION_CHECKLIST.md`](../PRODUCTION_CHECKLIST.md)

---

## Важные оговорки

- URL превью VK (`sun9-*.userapi.com`) при восстановлении заданы **шаблоном**; если превью в UI битые — заменить в таблице `prompts.preview_url` на фактические из постов VK.
- После смены `is_admin` в БД пользователям нужна **актуальная сессия** (перелогин), чтобы в шапке появилась «Модерация».
- Путь к БД в Docker: `./magikbook-api/magikbook.db` на хосте → `/app/magikbook.db` в контейнере ([`docker-compose.yml`](../../docker-compose.yml) в корне `/opt/projects`).

---

## Связанные документы

- Краткое обновление в [`DIAGNOSTIC_CONTENT_MODERATION.md`](DIAGNOSTIC_CONTENT_MODERATION.md)
- Чеклист продакшена: [`PRODUCTION_CHECKLIST.md`](../PRODUCTION_CHECKLIST.md)
