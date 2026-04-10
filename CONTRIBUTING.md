# Участие в разработке (magikbook-api)

## Ветки и pull request

1. **Не пушьте напрямую в `main` с продакшн-сервера без ревью**, если команда договорилась о PR. Рабочий минимум:
   - ветка от актуального `main`: `feature/кратко-о-задаче` или `fix/кратко`;
   - изменения, `git push -u origin имя-ветки`;
   - **Pull Request в `main`** на GitHub;
   - дождаться **зелёного CI** (ruff + pytest) и при необходимости ревью;
   - merge в `main` (squash или merge — по договорённости).

2. **CI обязателен для качества:** workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) запускается на push в `main`/`develop` и на PR в `main`. Перед merge убедитесь, что проверки прошли.

3. **Branch protection (рекомендуется на GitHub):** в настройках репозитория *Settings → Branches → Branch protection rules* для `main` включите:
   - *Require a pull request before merging* (по желанию);
   - *Require status checks to pass before merging* — отметьте job’ы **Lint (ruff)** и **Tests (pytest)**.

Так пайплайн перестаёт быть «декоративным»: без зелёных проверок merge блокируется.

---

## Git: автор коммитов (не root и не автогенератор)

Коммиты вида `root@v2202603...` и приписки **Made-with: Cursor** ухудшают историю и аудит.

### Идентификатор разработчика

На машине, где вы коммитите (в т.ч. VPS), один раз задайте:

```bash
git config --global user.name "Ваше Имя"
git config --global user.email "your@email.com"
```

Для **одного репозитория** без глобальной смены:

```bash
cd /path/to/magikbook-api
git config user.name "Ваше Имя"
git config user.email "your@email.com"
```

Проверка: `git config user.name` и `git log -1 --format='%an <%ae>'`.

### Приписка Made-with: Cursor

Она добавляется средой Cursor к сообщению коммита. Рекомендации:

- Перед финальным коммитом **отредактируйте сообщение** и удалите строку `Made-with: Cursor`, либо отключите соответствующую опцию в **Cursor Settings** (раздел про Git / коммиты — название может меняться между версиями).
- Либо коммитьте из терминала: `git commit` после ручного ввода сообщения без лишних строк.

Итог: в истории должен быть осмысленный заголовок (и при необходимости тело) **без** служебных хвостов, автор — **реальный человек или бот с осмысленным именем**, не `root`.

---

## Локальные проверки до push

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

---

## Релизы

Версии и теги согласуйте с фронтендом; кратко см. [README.md](README.md) и [CHANGELOG.md](CHANGELOG.md).
