# STATE — magikbook-api

*Updated: 2026-05-30*

## Status (active/paused/experimental/archived + why)

**Active** — проект в эксплуатации и активной доработке. Фокус последних недель: стабилизация VK-автопостинга, auth/cookie, маршрутизация API; в рабочей копии — фича **Artist Glory** (публичное портфолио пользователя). Worker «заклинание дня» временно отключён (`663ef5a`).

## What is happening now (branch, commits focus, uncommitted)

- **Ветка:** `main` @ `b0f72f6`, синхронизирована с `vds/main`.
- **Недавние коммиты (фокус):**
  - VK: form body для `wall.post` / `photos.saveWallPhoto` (fix 414), save-publish-token, BBCode/CTA, embed video.
  - Auth: `path=/` для access_token cookie.
  - Routing: `uploads` перед `prompts`; cabinet stats для published.
  - Workers: arq из `REDIS_URL`; daily prompt generation **disabled**.
  - Docs/incident: untrack `magikbook.db`, отчёт VK, changelog 2026-04-11.
- **Незакоммичено (modified):**
  - `.env.example` — новые переменные [уточнить по diff].
  - `src/routes/uploads.py` — расширение логики загрузок (+58 строк).
  - `src/services/prompt_service.py` — портфолио, поля автора в ленте (+79 строк).
  - `tests/test_battle.py`, `tests/test_generate.py` — обновления тестов.
  - `src/magikbook_api.egg-info/*` — артефакты сборки (не для коммита).
- **Незакоммичено (untracked):**
  - `src/routes/users.py` — `GET /api/users/{username}/portfolio` (уже подключён в `main.py`).
  - `tests/test_artist_glory_portfolio.py` — контрактные тests Artist Glory.
  - `magikbook.db.before-restore.20260411_194719` — бэкап БД (не коммитить).
  - `token.md` — вероятно секреты (не коммитить).

## Blockers (what blocks progress)

1. **VK API** — права токена, привязка IP, standalone bypass; требует ручного сопровождения токена (`vk_integration_report.md`).
2. **Daily prompt worker отключён** — «заклинание дня» на главной не генерируется автоматически, пока не включат обратно.
3. **Незавершённый Artist Glory** — `users.py` и тесты не в git; нужен коммит и синхронизация с фронтом MagikBook.
4. **Расхождение версий** — `pyproject.toml` `0.2.0` vs `main.py` OpenAPI `0.1.0`.
5. **Локальные артефакты** — бэкапы `.db`, `token.md` в рабочей директории (риск случайного коммита).

## Last release / milestone

- **CHANGELOG [2026-04-09]:** релиз «наполнение и постинг», API **v0.2.0** — модерация, `is_admin`, битва с `session_token`, синхронизация с фронтом v2.1.0.
- **Milestone [2026-04-11]:** hotfix-пакет VK 414, router order, cabinet stats, документирование инцидента SQLite в git.
- **Последний коммит [2026-04-20 area]:** обновление VK integration report (auth + 404 fixes) — дата в отчёте «20 Апреля 2026».

## Planned (next 3-5 concrete steps)

1. Закоммитить Artist Glory: `users.py`, `prompt_service.py`, `uploads.py`, тесты — без секретов и `.db`.
2. Прогнать CI локально: `ruff check`, `pytest tests/ -v`.
3. Решить судьбу `daily_prompt` worker — включить с мониторингом или формализовать отключение в docs.
4. Синхронизировать версию API в `main.py` с `pyproject.toml` (0.2.0).
5. Актуализировать `.env.example` и README при новых env для portfolio/Artist Glory.
