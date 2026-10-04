"""Проверка A2 и A5: шесть директорий Task1 - Task6, в каждой хотя бы один файл.

Ключ --final: файл .gitkeep не считается содержимым директории.
"""

import argparse
import sys
from pathlib import Path

from _common import IGNORED_FILE_NAMES, ROOT, TASK_DIRS


def find_problems(root, final=False):
    """Возвращает список строк с проблемами, пустой список означает, что все в порядке."""
    root = Path(root)
    problems = []
    for name in TASK_DIRS:
        directory = root / name
        if not directory.is_dir():
            problems.append(f"{name}: директория не найдена")
            continue
        files = [
            path
            for path in directory.rglob("*")
            if path.is_file() and path.name not in IGNORED_FILE_NAMES
        ]
        if final:
            files = [path for path in files if path.name != ".gitkeep"]
        if not files:
            suffix = " (файл .gitkeep не считается)" if final else ""
            problems.append(f"{name}: нет файлов{suffix}")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description="Проверка структуры директорий заданий")
    parser.add_argument("--final", action="store_true", help="не учитывать файл .gitkeep")
    parser.add_argument("--root", default=str(ROOT), help="корень репозитория")
    args = parser.parse_args(argv)

    problems = find_problems(args.root, final=args.final)
    for item in problems:
        print(item)
    if problems:
        return 1
    print("структура в порядке: " + ", ".join(TASK_DIRS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
