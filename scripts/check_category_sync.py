#!/usr/bin/env python3
"""Сверка slug и легаси-подписей между фронтом и API.

Сравнивает ``src/lib/categories.ts`` (MagikBook) с ``src/category_labels.py``.
При расхождении наборов slug или пары emoji/title для легаси-строки — код выхода 1.

Запуск из корня репозитория magikbook-api::

    python3 scripts/check_category_sync.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _parse_categories_ts(path: Path) -> dict[str, tuple[str, str]]:
    """Возвращает slug -> (emoji, title) из categories.ts."""
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"slug:\s*'([^']+)'\s*,\s*emoji:\s*'([^']*)'\s*,\s*title:\s*'([^']*)'",
        re.MULTILINE,
    )
    out: dict[str, tuple[str, str]] = {}
    for m in pattern.finditer(text):
        slug, emoji, title = m.group(1), m.group(2), m.group(3)
        out[slug] = (emoji, title)
    return out


def _parse_category_labels_raw(path: Path) -> dict[str, tuple[str, str]]:
    """Парсит кортежи _RAW в category_labels.py: slug -> (emoji, title)."""
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'^\s+\("([^"]+)",\s*"([^"]*)",\s*"([^"]*)"\)',
        re.MULTILINE,
    )
    out: dict[str, tuple[str, str]] = {}
    for m in pattern.finditer(text):
        slug, emoji, title = m.group(1), m.group(2), m.group(3)
        out[slug] = (emoji, title)
    return out


def main() -> int:
    root = _repo_root()
    env_ts = os.environ.get("CATEGORIES_TS_PATH")
    if env_ts:
        ts_path = Path(env_ts).resolve()
    else:
        ts_path = root.parent / "magikbook" / "src" / "lib" / "categories.ts"
    py_path = root / "src" / "category_labels.py"

    if not ts_path.is_file():
        print(
            "SKIP: categories.ts not found "
            f"({ts_path}). Clone magikbook next to magikbook-api or set CATEGORIES_TS_PATH.",
            file=sys.stderr,
        )
        return 0
    if not py_path.is_file():
        print(f"ERROR: category_labels.py not found: {py_path}", file=sys.stderr)
        return 1

    ts_map = _parse_categories_ts(ts_path)
    py_map = _parse_category_labels_raw(py_path)

    ts_slugs = set(ts_map.keys())
    py_slugs = set(py_map.keys())

    errors: list[str] = []
    if ts_slugs != py_slugs:
        only_ts = sorted(ts_slugs - py_slugs)
        only_py = sorted(py_slugs - ts_slugs)
        if only_ts:
            errors.append(f"Only in categories.ts (add to category_labels._RAW): {only_ts}")
        if only_py:
            errors.append(f"Only in category_labels.py (add to categories.ts): {only_py}")

    common = ts_slugs & py_slugs
    for slug in sorted(common):
        te, tt = ts_map[slug]
        pe, pt = py_map[slug]
        if (te, tt) != (pe, pt):
            errors.append(
                f"Mismatch for slug {slug!r}: "
                f"TS ({te!r}, {tt!r}) vs PY ({pe!r}, {pt!r})"
            )

    if errors:
        print("category sync FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"OK: {len(common)} categories match between categories.ts and category_labels.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
