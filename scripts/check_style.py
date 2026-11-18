"""Проверка стиля A8 без grep -P. Пустой вывод и код возврата 0 означают, что замечаний нет.

Проверяется каждый текстовый файл репозитория, включая схемы .drawio.
Бинарные файлы пропускаются. Шаблоны собраны из кодов символов и частей слов,
чтобы этот файл не срабатывал сам на себя.
"""

import argparse
import re
import sys
from pathlib import Path

from _common import ROOT, iter_text_files

# Буква е с двумя точками (строчная и заглавная), длинное тире, двойная звездочка.
YO_CHARS = (chr(0x0451), chr(0x0401))
LONG_DASH = chr(0x2014)
BOLD_MARK = "*" * 2

# Фразы-пометки автору и слова, которым нет места в сдаваемых файлах.
NOTE_PHRASES = ("подстав" + "ьте", "приложи" + "те", "сверь" + "те")
FORBIDDEN_WORDS = (
    "нейро" + "сет",
    "сгене" + "рир",
    "cla" + "ude",
    "to" + "do",
    "t" + "bd",
    "x" * 3,
)

PHRASE_RE = re.compile("|".join(NOTE_PHRASES), re.IGNORECASE)
WORD_RE = re.compile("|".join(FORBIDDEN_WORDS), re.IGNORECASE)
# Два заглавных символа только как отдельное слово, с учетом регистра.
AI_RE = re.compile(r"(?<!\w)" + chr(0x0418) * 2 + r"(?!\w)")

# Заглушка в угловых скобках: открывающая скобка, буква, любой текст, закрывающая скобка.
PLACEHOLDER_RE = re.compile(r"<(?!https?://)[^\W\d_][^<>]*>")
LINK_TARGET_RE = re.compile(r"\]\(<[^>]*>\)")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def check_text(rel_path, suffix, text):
    """Возвращает список замечаний вида путь:строка: причина для одного файла."""
    issues = []
    is_markdown = suffix.lower() == ".md"
    in_fence = False

    for number, line in enumerate(text.splitlines(), start=1):
        reasons = []

        if any(char in line for char in YO_CHARS):
            reasons.append("буква е с двумя точками")
        if LONG_DASH in line:
            reasons.append("длинное тире")
        if PHRASE_RE.search(line):
            reasons.append("пометка автору")
        if WORD_RE.search(line):
            reasons.append("запрещенное слово")
        if AI_RE.search(line):
            reasons.append("упоминание искусственного интеллекта")

        if is_markdown:
            if BOLD_MARK in line:
                reasons.append("двойные звездочки в md")
            if FENCE_RE.match(line):
                in_fence = not in_fence
            elif not in_fence:
                cleaned = LINK_TARGET_RE.sub("](x)", line)
                cleaned = INLINE_CODE_RE.sub("", cleaned)
                if PLACEHOLDER_RE.search(cleaned):
                    reasons.append("заглушка в угловых скобках в md")

        issues.extend(f"{rel_path}:{number}: {reason}" for reason in reasons)
    return issues


def find_issues(root):
    """Проверяет все текстовые файлы под root и возвращает список замечаний."""
    root = Path(root)
    issues = []
    for path, text in iter_text_files(root):
        rel_path = path.relative_to(root).as_posix()
        issues.extend(check_text(rel_path, path.suffix, text))
    return issues


def main(argv=None):
    parser = argparse.ArgumentParser(description="Проверка стиля документации и схем")
    parser.add_argument("root", nargs="?", default=str(ROOT), help="корень проверки")
    args = parser.parse_args(argv)

    issues = find_issues(args.root)
    for item in issues:
        print(item)
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
