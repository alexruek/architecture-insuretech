"""A8: единый стиль документации. Запрещенные символы и слова собраны из кодов и частей."""

import check_style
import pytest

YO = chr(0x0451)
DASH = chr(0x2014)
BOLD = "*" * 2
AI = chr(0x0418) * 2

NOTE_PHRASES = ["подстав" + "ьте", "приложи" + "те", "сверь" + "те"]
FORBIDDEN_WORDS = [
    "нейро" + "сеть",
    "сгене" + "рировано",
    "Cla" + "ude",
    "TO" + "DO",
    "T" + "BD",
    "X" * 3,
]


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_repo_has_no_style_issues(repo_root):
    assert check_style.find_issues(repo_root) == []


@pytest.mark.parametrize("name", ["a.md", "b.py", "c.drawio", "d.yaml"])
def test_detects_letter_yo(tmp_path, name):
    write(tmp_path, name, "ел" + YO + "\n")
    assert len(check_style.find_issues(tmp_path)) == 1


def test_detects_uppercase_yo(tmp_path):
    write(tmp_path, "a.md", chr(0x0401) + "лка\n")
    assert len(check_style.find_issues(tmp_path)) == 1


@pytest.mark.parametrize("name", ["a.md", "b.py", "c.drawio"])
def test_detects_long_dash(tmp_path, name):
    write(tmp_path, name, "а " + DASH + " б\n")
    assert len(check_style.find_issues(tmp_path)) == 1


def test_bold_only_in_markdown(tmp_path):
    write(tmp_path, "a.md", "текст " + BOLD + "важно" + BOLD + "\n")
    write(tmp_path, "b.txt", "текст " + BOLD + "важно" + BOLD + "\n")
    issues = check_style.find_issues(tmp_path)
    assert len(issues) == 1
    assert issues[0].startswith("a.md:1:")


@pytest.mark.parametrize("phrase", NOTE_PHRASES)
@pytest.mark.parametrize("name", ["a.md", "c.drawio"])
def test_detects_note_phrases(tmp_path, phrase, name):
    write(tmp_path, name, phrase.capitalize() + " значение\n")
    assert len(check_style.find_issues(tmp_path)) == 1


@pytest.mark.parametrize("word", FORBIDDEN_WORDS)
@pytest.mark.parametrize("name", ["a.md", "c.drawio"])
def test_detects_forbidden_words(tmp_path, word, name):
    write(tmp_path, name, "строка " + word + " конец\n")
    assert len(check_style.find_issues(tmp_path)) == 1


@pytest.mark.parametrize("text", [AI, "Это " + AI + ".", "(" + AI + ")"])
def test_detects_standalone_ai_word(tmp_path, text):
    write(tmp_path, "a.md", text + "\n")
    assert len(check_style.find_issues(tmp_path)) == 1


@pytest.mark.parametrize("text", [AI + chr(0x0421), chr(0x0422) + AI, "ии", chr(0x0418)])
def test_ignores_ai_inside_other_words(tmp_path, text):
    write(tmp_path, "a.md", text + "\n")
    assert check_style.find_issues(tmp_path) == []


def test_binary_files_are_skipped(tmp_path):
    payload = b"\x89PNG\r\n\x1a\n\x00" + ("ел" + YO).encode("utf-8")
    (tmp_path / "pic.png").write_bytes(payload)
    (tmp_path / "blob.dat").write_bytes(payload)
    assert check_style.find_issues(tmp_path) == []


def test_service_dirs_are_skipped(tmp_path):
    write(tmp_path, ".git/config", "ел" + YO + "\n")
    write(tmp_path, ".venv/lib/a.py", "ел" + YO + "\n")
    assert check_style.find_issues(tmp_path) == []


def test_issue_has_path_and_line(tmp_path):
    write(tmp_path, "docs/a.md", "чисто\nел" + YO + "\n")
    assert check_style.find_issues(tmp_path) == ["docs/a.md:2: буква е с двумя точками"]


def test_placeholder_in_markdown_text(tmp_path):
    write(tmp_path, "a.md", "Откройте <файл> в редакторе\n")
    assert len(check_style.find_issues(tmp_path)) == 1


@pytest.mark.parametrize(
    "text",
    [
        "```\nкоманда <файл>\n```\n",
        "Команда `cat <файл>` читает файл\n",
        "[схема](<Task1/a b.drawio>)\n",
        "Сайт <https://example.com>\n",
        "Стрелка A <- B -> C\n",
    ],
)
def test_placeholder_exceptions(tmp_path, text):
    write(tmp_path, "a.md", text)
    assert check_style.find_issues(tmp_path) == []


def test_placeholder_only_checked_in_markdown(tmp_path):
    write(tmp_path, "a.py", "x = '<файл>'\n")
    assert check_style.find_issues(tmp_path) == []


def test_main_output_and_exit_code(tmp_path, capsys):
    write(tmp_path, "a.md", "чисто\n")
    assert check_style.main([str(tmp_path)]) == 0
    assert capsys.readouterr().out == ""
    write(tmp_path, "b.md", "а " + DASH + " б\n")
    assert check_style.main([str(tmp_path)]) == 1
    assert capsys.readouterr().out == "b.md:1: длинное тире\n"
