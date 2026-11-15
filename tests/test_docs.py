"""Проверки документов: относительные ссылки ведут на файлы, у каждой проблемы Task3 есть решение."""

import re
from pathlib import Path

import pytest
from _common import SKIP_DIRS

ROOT = Path(__file__).resolve().parents[1]
PROBLEMS = ROOT / "Task3" / "problems.md"

# Ссылка вида [текст](путь) или [текст](<путь с пробелами>).
LINK_RE = re.compile(r"\[[^\]]*\]\((<[^>]+>|[^)\s]+)\)")
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "#")
REQUIRED_COLUMNS = ("Проблема или риск", "Решение", "Элемент схемы")
# Темы, которые по критерию 3.1 должны быть раскрыты в списке проблем.
REQUIRED_TOPICS = (
    "синхронн",
    "десять",
    "задерж",
    "реплик",
    "пакетн",
    "точкой отказа",
)


def markdown_files():
    result = []
    for path in sorted(ROOT.rglob("*.md")):
        if not SKIP_DIRS.intersection(path.relative_to(ROOT).parts):
            result.append(path)
    return result


def relative_links(path):
    links = []
    in_fence = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for target in LINK_RE.findall(line):
            target = target.strip("<>")
            if not target.startswith(EXTERNAL_PREFIXES):
                links.append(target.split("#")[0])
    return links


def read_table(path, first_column):
    """Возвращает строки md-таблицы, заголовок которой начинается с first_column и содержит нужные колонки."""
    header = None
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            if rows:
                break
            header = None
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if set(cells[0]) <= set("-: "):
            continue
        if header[0] == first_column and all(name in header for name in REQUIRED_COLUMNS):
            rows.append(dict(zip(header, cells)))
    return rows


@pytest.mark.parametrize("path", markdown_files(), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_relative_links_exist(path):
    for target in relative_links(path):
        if not (path.parent / target).exists():
            pytest.fail(f"{path.relative_to(ROOT).as_posix()}: нет файла по ссылке {target}")


def problem_rows():
    if not PROBLEMS.is_file():
        pytest.skip("Task3/problems.md еще не добавлен")
    rows = read_table(PROBLEMS, "N")
    assert rows, "в Task3/problems.md нет таблицы проблем"
    return rows


def test_problems_have_solutions():
    for row in problem_rows():
        for column in REQUIRED_COLUMNS:
            assert row.get(column), f"проблема {row['N']}: пустая колонка {column}"
        assert re.search(r"`[^`]+`", row["Элемент схемы"]), f"проблема {row['N']}: не назван элемент схемы"


def test_problems_numbered_in_order():
    numbers = [row["N"] for row in problem_rows()]
    assert numbers == [str(index) for index in range(1, len(numbers) + 1)]


@pytest.mark.parametrize("topic", REQUIRED_TOPICS)
def test_problems_cover_required_topics(topic):
    text = " ".join(row["Проблема или риск"] + " " + row["Как проявится при росте"] for row in problem_rows())
    assert topic in text.lower()
