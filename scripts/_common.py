"""Общие функции скриптов и тестов: корень репозитория, конфиг, обход текстовых файлов."""

import os
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    raise SystemExit("Нужен Python 3.11 и новее")

import tomllib

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "defaults.toml"

TASK_DIRS = tuple(f"Task{number}" for number in range(1, 7))

# Служебные файлы систем, которые не считаются содержимым директории.
IGNORED_FILE_NAMES = frozenset({".DS_Store", "Thumbs.db"})

SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        "dist",
        ".idea",
        ".vscode",
    }
)

BINARY_SUFFIXES = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".pdf",
        ".zip",
        ".gz",
        ".tar",
        ".7z",
        ".woff",
        ".woff2",
        ".ttf",
        ".pyc",
    }
)


def load_config(path=CONFIG_PATH):
    """Читает config/defaults.toml и возвращает словарь разделов."""
    with open(path, "rb") as handle:
        return tomllib.load(handle)


def read_text(path):
    """Возвращает текст файла в UTF-8 или None, если файл бинарный или нечитаемый."""
    path = Path(path)
    if path.suffix.lower() in BINARY_SUFFIXES:
        return None
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def iter_text_files(root):
    """Обходит каталог, пропуская служебные каталоги и бинарные файлы. Отдает пары (путь, текст)."""
    root = Path(root)
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(name for name in dirs if name not in SKIP_DIRS)
        for name in sorted(files):
            path = Path(current) / name
            text = read_text(path)
            if text is not None:
                yield path, text


def get_value(config, dotted_key):
    """Возвращает значение по ключу вида раздел.параметр, например monitoring.namespace."""
    value = config
    for part in dotted_key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(dotted_key)
        value = value[part]
    return value


def main(argv=None):
    """Печатает значение параметра конфига. Используется в командах вида $(python scripts/_common.py ключ)."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("использование: python scripts/_common.py раздел.параметр", file=sys.stderr)
        return 2
    try:
        print(get_value(load_config(), args[0]))
    except KeyError:
        print(f"в config/defaults.toml нет ключа {args[0]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
