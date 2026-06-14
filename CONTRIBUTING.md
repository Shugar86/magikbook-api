# 🧙 Участие в разработке MagikBook API

Спасибо, что заглянул в гримуар! Ниже — правила игры, чтобы магия не превратилась в хаос.

## 🌿 Ветки и pull request

1. **Не пушь напрямую в `main`** с продакшн-сервера без ревью (если договорились иначе — обсуди).
2. Создавай ветку от актуального `main`:

   ```bash
   git checkout -b feature/кратко-о-задаче
   # или
   git checkout -b fix/кратко-о-баге
   ```

3. Сделай изменения — **минимальный diff**, KISS.
4. Запушь ветку:

   ```bash
   git push -u origin имя-ветки
   ```

5. Открой **Pull Request в `main`** на GitHub.
6. Дождись зелёного CI (ruff + pytest) и при необходимости ревью.
7. Merge в `main` (squash или merge — по договорённости).

### CI обязателен

Workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) запускается на push в `main`/`develop` и на PR в `main`. Перед merge убедись, что проверки прошли.

### Branch protection (рекомендуется)

В настройках репозитория GitHub *Settings → Branches → Branch protection rules* для `main` включи:

- *Require a pull request before merging* (по желанию);
- *Require status checks to pass before merging* — job’ы **Lint (ruff)** и **Tests (pytest)**.

## 🪪 Git: автор коммитов

Коммиты вида `root@v2202603...` и приписки `Made-with: Cursor` ухудшают историю.

Задай автора один раз на машине, где коммитишь:

```bash
git config --global user.name "Твоё Имя"
git config --global user.email "you@example.com"
```

Или только для репозитория:

```bash
git config user.name "Твоё Имя"
git config user.email "you@example.com"
```

Проверка:

```bash
git config user.name
git log -1 --format='%an <%ae>'
```

## 🧹 Локальные проверки до push

```bash
pip install -e ".[dev]"
ruff check src/ tests/
ruff format --check src/ tests/
pytest tests/ -v --tb=short
python3 scripts/check_category_sync.py
```

Рядом с репозиторием должен лежать клон фронта `magikbook` (тот же родительский каталог), иначе скрипт синхронизации категорий выведет `SKIP`. Путь к `categories.ts` можно задать переменной `CATEGORIES_TS_PATH`.

Смоук фида по HTTP (когда API запущен):

```bash
BASE_URL=http://127.0.0.1:8000 ./scripts/verify_feed_curl.sh
# опционально: FRONTEND_URL=http://127.0.0.1:3000
```

Переменные для тестов см. в [`.github/workflows/ci.yml`](.github/workflows/ci.yml) (`env` в job `test`).

## 🛡️ Что нельзя коммитить

- `.env`, `*.pem`, `id_*`, токены, пароли.
- `magikbook.db` и другие `*.db` — даже при локальной разработке.
- `uploads/` — пользовательские файлы.
- `__pycache__/`, `.pytest_cache/`, `*.egg-info/` (если не отслеживаются).

Если `git status` показывает отслеживаемый `magikbook.db`, читай [`docs/INCIDENT_GIT_TRACKED_SQLITE_2026-04-11.md`](docs/INCIDENT_GIT_TRACKED_SQLITE_2026-04-11.md).

## 🏷️ Релизы

Версии и теги согласовывай с фронтендом. Кратко — в [`README.md`](README.md) и [`CHANGELOG.md`](CHANGELOG.md).

---

Если хочешь что-то обсудить до PR — открывай issue. Магия любит диалог ✨
