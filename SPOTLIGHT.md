# SPOTLIGHT — magikbook-api

## Architecture pearls (2-3 files/decisions that make this project tick)

**1. `src/main.py` — композиция приложения и «хрупкий» порядок роутеров**

Точка входа FastAPI с паттерном `lifespan` (`asynccontextmanager`): на старте `init_db()` + `init_redis()`, на shutdown `close_redis()`. Роутеры подключаются явным списком; критичный комментарий и решение: **`uploads.router` регистрируется до `prompts.router`**, иначе `/api/prompts/my-uploads` перехватывается как `/api/prompts/{prompt_id}` (зафиксировано в коммите `7ba5cdd`). В dev подключается `test_setup.router`; OpenAPI (`/docs`, `/redoc`) отключены вне `settings.environment == "development"`. Статика `uploads/` монтируется через `StaticFiles`. Это классический **composition root** для FastAPI с environment-gating.

**2. `src/config.py` + `src/redis_client.py` — конфиг и деградация без Redis**

`Settings` на `pydantic_settings.BaseSettings` с `.env`, десятками интеграций (Google Gemini, VK, Telegram, SMTP/Resend, OAuth). Метод `cookie_secure_effective()` — явная логика Secure-cookie для production. `redis_client.py` реализует **graceful fallback**: при пустом `REDIS_URL` — in-memory stub `_InMemoryRedis` с TTL; при наличии URL — реальный `redis.asyncio`. Rate-limit батлов (`routes/battle.py`, `BATTLE_VOTE_RATE_LIMIT_SEC = 30`) опирается на `SET ... NX` — работает и в stub, и в Redis.

**3. Слой сервисов: `BattleService` / `EloService` / `PromptService`**

Бизнес-логика вынесена из роутов в `src/services/`. `BattleService` (`battle_service.py`) — ELO (K=32, min=800), выбор пары через `func.random()`, учёт `BattleVote`, агрегаты win%. `PromptService` обслуживает фид, портфолио (`users.py` → `get_public_portfolio`), my-uploads с battle-статистикой. Роуты тонкие: DI через `Depends(get_db_session)` и фабрики `_service()`. Паттерн: **async SQLAlchemy session + Pydantic `PromptOut`**.

## Hidden risks (1-2 places that could bite)

**1. Два источника правды для зависимостей и схемы БД**

- **Dockerfile** ставит пакеты из `requirements.txt` (+ ручной `pip install`), а **pyproject.toml** объявляет `version = "0.2.0"` и другой набор версий — риск расхождения prod/dev. В `main.py` версия API `"0.1.0"` — ещё один drift.
- `init_db()` в `database.py` делает `SQLModel.metadata.create_all` при старте, хотя в зависимостях есть **Alembic** — [uncertain], насколько миграции обязательны в production vs «создать таблицы на лету».
- Дефолт `secret_key: str = "secret"` в `Settings` — опасно, если `.env` не задан на VPS.

**2. Тесты и продакшен-инциденты**

- `test_battle.py::test_vote_success` допускает `404 | 200 | 429` — наследие после введения `BattleService`; слабая спецификация, маскирует регрессии.
- В git-истории: коммит с **`.venv` в репозитории** (`5477fe5`), инцидент **`magikbook.db` в git** (`b6d1a86`, `80b3e98`) — культура осознания риска есть, но один неверный `git add` снова убьёт прод.
- Порядок роутеров в `main.py` — единственная «защита» от коллизии path params; новый роутер в `prompts` легко сломает `/my-uploads` без теста на порядок.

## Reuse gold (what could be copied to another project)

| Паттерн | Где | Зачем |
|--------|-----|-------|
| Redis stub с TTL | `src/redis_client.py` | Локальная разработка без Docker Redis |
| Override `get_db_session` + in-memory SQLite | `tests/conftest.py` | Изолированные async contract-тесты FastAPI |
| Rate limit `SET key NX` + заголовок `Retry-After` | `routes/battle.py`, `test_vote_rate_limit_second_request_429` | Готовый шаблон anti-spam для POST |
| `pydantic-settings` + `cookie_secure_effective()` | `src/config.py` | Env-based security без размазанных `if prod` |
| Contract-тесты домена | `tests/test_artist_glory_portfolio.py` | Явные инварианты API (portfolio, feed author, battle aggregates) |
| Fallback-контент для пустой БД | `FALLBACK_PROMPTS` в `battle.py` | UX при отсутствии данных (с оговоркой: не путать с реальными id) |

## Key commits vibe (if git history visible)

Ритм последних ~20 коммитов: **продуктовые фичи (VK, feed, Artist Glory) → точечные fix (routing, cookies, 414 URI, cabinet stats) → документация и инциденты**.

- Префиксы: `feat`, `fix`, `docs`, `chore` — осмысленные, не «wip».
- Сильный акцент на **VK-интеграцию** и публикацию (`vk_publisher`, wall.post, BBCode).
- Повторяющиеся **fix(routing)** и **fix(auth)** — признак зрелости через боль продакшена, а не только TDD.
- Недавно: `docs: PROJECT.md, STATE.md, COCKPIT.md` — переход к формализованному состоянию проекта.
- `chore(release): v0.2.0` — релизный ритм есть; ветка `main` опережает `vds/main` на 1 коммит [по git_status на момент анализа].

Стиль: **прагматичный maintainer** — чинит прод, документирует инциденты, не боится отключать воркеры (`fix(worker): disable daily prompt generation`).

## Questions for the author

1. **Production DB**: целевой runtime — PostgreSQL (`asyncpg` в deps) или до сих пор SQLite (`database_url` по умолчанию `sqlite+aiosqlite:///./magikbook.db`)? Какой путь деплоя считается canonical — Docker + `requirements.txt` или `pip install -e .` из `pyproject.toml`?

2. **Alembic vs `create_all`**: миграции обязательны при деплое, или `init_db()` в `lifespan` достаточно? Есть ли риск рассинхрона схемы между VPS и локальной `magikbook.db`?

3. **Граница `PromptService`**: портфолио, фид, my-uploads и модерация — всё в одном сервисе [по импортам в `users.py` и тестам]. Планируется ли разделение (например, `PortfolioService`) или сознательный «god service» для скорости итераций Artist Glory?
