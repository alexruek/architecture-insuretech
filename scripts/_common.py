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
