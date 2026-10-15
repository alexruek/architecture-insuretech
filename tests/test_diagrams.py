"""Проверки схем draw.io: файл несжатый, стиль соблюден, ключевые решения подписаны."""

import html
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TASK1 = ROOT / "Task1" / "InureTech_технологическая архитектура_to-be.drawio"

FORBIDDEN_CHARS = {"\u0451": "буква е с двумя точками", "\u0401": "буква Е с двумя точками", "\u2014": "длинное тире"}
TASK1_KEYWORDS = [
    "RTO",
    "RPO",
    "99,9",
    "Patroni",
    "etcd",
    "WAL",
    "archive_timeout",
    "health check",
    "шардирован",
    "горизонтальн",
    "вертикальн",
    "CDN",
    "Application Load Balancer",
    "HAProxy",
    "ru-central1-a",
    "ru-central1-b",
    "ru-central1-d",
]
TASK1_COMPONENTS = [
    "core-app",
    "client-info",
    "ins-product-aggregator",
    "ins-comp-settlement",
    "веб-приложение",
    "PostgreSQL",
    "Kubernetes",
]
# ALB -> ingress трех кластеров, CDN -> источник, HAProxy -> Patroni,
# readiness и liveness подов, мониторинг площадок
TASK1_MIN_HEALTH_CHECKS = 7


def labels(path: Path) -> list[str]:
    """Возвращает подписи всех элементов схемы без HTML-разметки."""
    root = ET.parse(path).getroot()
    result = []
    for elem in root.iter():
        for attr in ("value", "label"):
            raw = elem.get(attr)
            if raw:
                text = re.sub(r"<[^>]+>", " ", raw)
                text = html.unescape(text)
                result.append(re.sub(r"\s+", " ", text).strip())
    return result


@pytest.fixture(scope="module")
def task1_text() -> str:
    assert TASK1.is_file(), f"нет файла {TASK1.relative_to(ROOT)}"
    return " ".join(labels(TASK1))


def test_task1_uncompressed():
    root = ET.parse(TASK1).getroot()
    pages = root.findall("diagram")
    assert pages, "в файле нет страниц diagram"
    for page in pages:
        assert page.find("mxGraphModel") is not None, f"страница {page.get('name')} сохранена сжатой"


def test_task1_style():
    raw = TASK1.read_text(encoding="utf-8")
    for char, name in FORBIDDEN_CHARS.items():
        assert char not in raw, name
    assert "<b>" not in html.unescape(raw), "жирный шрифт в подписи"
    for style in re.findall(r'style="([^"]*)"', raw):
        match = re.search(r"fontStyle=(\d+)", style)
        assert not (match and int(match.group(1)) & 1), f"жирный шрифт в стиле: {style[:60]}"


@pytest.mark.parametrize("word", TASK1_KEYWORDS)
def test_task1_keywords(task1_text, word):
    assert word.lower() in task1_text.lower()


@pytest.mark.parametrize("name", TASK1_COMPONENTS)
def test_task1_components(task1_text, name):
    assert name.lower() in task1_text.lower()


def test_task1_health_checks():
    count = sum("health check" in text.lower() for text in labels(TASK1))
    assert count >= TASK1_MIN_HEALTH_CHECKS, f"подписанных health check: {count}"
