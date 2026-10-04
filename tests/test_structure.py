"""A2, A5: директории заданий и их содержимое."""

import check_structure
import pytest
from _common import IGNORED_FILE_NAMES, TASK_DIRS


def real_files(directory):
    return [
        path
        for path in directory.rglob("*")
        if path.is_file() and path.name not in IGNORED_FILE_NAMES
    ]


@pytest.mark.parametrize("name", TASK_DIRS)
def test_task_dir_exists(repo_root, name):
    assert (repo_root / name).is_dir()


@pytest.mark.parametrize("name", TASK_DIRS)
def test_task_dir_has_a_file(repo_root, name):
    assert real_files(repo_root / name), f"{name}: нет файлов"


@pytest.mark.parametrize("name", TASK_DIRS)
def test_gitkeep_removed_when_real_file_present(repo_root, name):
    directory = repo_root / name
    others = [path for path in real_files(directory) if path.name != ".gitkeep"]
    gitkeep = directory / ".gitkeep"
    assert not (others and gitkeep.exists()), f"{name}: .gitkeep рядом с настоящим файлом"


@pytest.mark.parametrize("path", ["logs", "docs/diagrams", "docs/screenshots"])
def test_service_dir_exists(repo_root, path):
    assert (repo_root / path).is_dir()


def test_config_sections(config):
    required = [
        "repo",
        "app",
        "memory_hpa",
        "rps_hpa",
        "monitoring",
        "locust",
        "capture",
        "nginx",
        "requirements",
    ]
    for section in required:
        assert config.get(section), f"в config/defaults.toml нет раздела {section}"


def make_task_dirs(root):
    for name in TASK_DIRS:
        (root / name).mkdir()
        (root / name / ".gitkeep").touch()


def test_checker_counts_gitkeep_by_default(tmp_path):
    make_task_dirs(tmp_path)
    assert check_structure.find_problems(tmp_path) == []


def test_checker_final_ignores_gitkeep(tmp_path):
    make_task_dirs(tmp_path)
    assert len(check_structure.find_problems(tmp_path, final=True)) == len(TASK_DIRS)
    (tmp_path / "Task1" / "file.txt").write_text("x", encoding="utf-8")
    assert len(check_structure.find_problems(tmp_path, final=True)) == len(TASK_DIRS) - 1


def test_checker_reports_missing_dir(tmp_path):
    make_task_dirs(tmp_path)
    (tmp_path / "Task3" / ".gitkeep").unlink()
    (tmp_path / "Task3").rmdir()
    problems = check_structure.find_problems(tmp_path)
    assert problems == ["Task3: директория не найдена"]


def test_checker_ignores_system_files(tmp_path):
    make_task_dirs(tmp_path)
    (tmp_path / "Task2" / ".gitkeep").unlink()
    (tmp_path / "Task2" / ".DS_Store").touch()
    assert check_structure.find_problems(tmp_path) == ["Task2: нет файлов"]
