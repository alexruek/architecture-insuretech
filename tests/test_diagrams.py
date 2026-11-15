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


# Task3: диаграмма контейнеров C4 после перехода на Event-Driven архитектуру (3.2-3.6)

TASK3 = ROOT / "Task3" / "InsureTech_C4_container-diagram.drawio"
TASK3_PROBLEMS = ROOT / "Task3" / "problems.md"
TASK3_KEYWORDS = [
    "брокер",
    "outbox",
    "Transactional Outbox",
    "тема",
    "Event-Streaming",
    "группа",
    "REST",
    "PostgreSQL",
    "инфраструктура",
    "идемпотент",
]
# Декомпозиция не меняется: сервисы те же, что в исходной схеме.
TASK3_SERVICES = {"core-app", "client-info", "ins-product-aggregator", "ins-comp-settlement"}
TASK3_OTHER = ["Веб-приложение", "Клиент", "Партнер", "Страховые компании"]


def cells(path: Path):
    return [cell for cell in ET.parse(path).getroot().iter("mxCell")]


def clean(raw: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))
    return re.sub(r"\s+", " ", text).strip()


@pytest.fixture(scope="module")
def task3_text() -> str:
    assert TASK3.is_file(), f"нет файла {TASK3.relative_to(ROOT)}"
    return " ".join(labels(TASK3))


def test_task3_uncompressed():
    pages = ET.parse(TASK3).getroot().findall("diagram")
    assert pages, "в файле нет страниц diagram"
    for page in pages:
        assert page.find("mxGraphModel") is not None, f"страница {page.get('name')} сохранена сжатой"


def test_task3_style():
    raw = TASK3.read_text(encoding="utf-8")
    for char, name in FORBIDDEN_CHARS.items():
        assert char not in raw, name
    assert "<b>" not in html.unescape(raw), "жирный шрифт в подписи"
    for style in re.findall(r'style="([^"]*)"', raw):
        match = re.search(r"fontStyle=(\d+)", style)
        assert not (match and int(match.group(1)) & 1), f"жирный шрифт в стиле: {style[:60]}"


@pytest.mark.parametrize("word", TASK3_KEYWORDS)
def test_task3_keywords(task3_text, word):
    assert word.lower() in task3_text.lower()


@pytest.mark.parametrize("name", sorted(TASK3_SERVICES) + TASK3_OTHER)
def test_task3_components(task3_text, name):
    assert name.lower() in task3_text.lower()


def test_task3_decomposition_unchanged():
    """Контейнеры с типом сервис или бэкенд-приложение совпадают с исходным набором."""
    services = set()
    for cell in cells(TASK3):
        text = clean(cell.get("value"))
        match = re.match(r"(\S+) \[Container: (сервис|бэкенд-приложение)\]", text)
        if match:
            services.add(match.group(1))
    assert services == TASK3_SERVICES


def test_task3_broker_matches_config(config, task3_text):
    broker = config["broker"]
    assert broker["name"] in task3_text
    assert f"{broker['brokers']} брокера в {broker['brokers']} зонах" in task3_text
    assert f"фактор репликации {broker['replication_factor']}" in task3_text
    assert f"min.insync.replicas {broker['min_insync_replicas']}" in task3_text


def test_task3_edges_connected():
    all_cells = cells(TASK3)
    ids = {cell.get("id") for cell in all_cells}
    edges = [cell for cell in all_cells if cell.get("edge") == "1"]
    assert edges
    for edge in edges:
        assert edge.get("source") in ids and edge.get("target") in ids, f"стрелка {edge.get('id')} не привязана"
        assert clean(edge.get("value")), f"стрелка {edge.get('id')} без подписи"


def test_task3_broker_edges_name_topics(config):
    """Каждая стрелка брокера подписана темой, обе темы имеют издателя и потребителя."""
    broker = config["broker"]
    topics = (broker["topic_products"], broker["topic_policies"])
    all_cells = cells(TASK3)
    broker_ids = {cell.get("id") for cell in all_cells if broker["name"] in clean(cell.get("value")) and cell.get("vertex") == "1" and "[Container" in clean(cell.get("value"))}
    assert len(broker_ids) == 1, "на схеме должен быть один контейнер брокера"
    broker_id = broker_ids.pop()
    published, consumed = set(), set()
    for cell in all_cells:
        if cell.get("edge") != "1" or broker_id not in (cell.get("source"), cell.get("target")):
            continue
        text = clean(cell.get("value"))
        named = [topic for topic in topics if f"тема {topic}" in text]
        assert len(named) == 1, f"стрелка {cell.get('id')}: не названа тема"
        (published if cell.get("target") == broker_id else consumed).add(named[0])
    assert published == set(topics)
    assert consumed == set(topics)


def test_task3_no_direct_calls_between_decoupled_services():
    """core-app, ins-comp-settlement и ins-product-aggregator связаны только через брокер."""
    all_cells = cells(TASK3)
    names = {}
    for cell in all_cells:
        text = clean(cell.get("value"))
        for service in TASK3_SERVICES:
            if text.startswith(service + " [Container"):
                names[cell.get("id")] = service
    decoupled = {"core-app", "ins-comp-settlement", "ins-product-aggregator"}
    for cell in all_cells:
        if cell.get("edge") == "1":
            pair = {names.get(cell.get("source")), names.get(cell.get("target"))}
            assert not (len(pair) == 2 and pair <= decoupled), f"прямая стрелка {cell.get('id')}"


def test_task3_problem_elements_on_diagram(task3_text):
    """3.6: элементы схемы, названные в таблице проблем, есть на схеме."""
    lines = [line for line in TASK3_PROBLEMS.read_text(encoding="utf-8").splitlines() if re.match(r"\| \d+ \|", line)]
    elements = set()
    for line in lines:
        elements.update(re.findall(r"`([^`]+)`", line))
    assert elements, "в таблице проблем не названы элементы схемы"
    for element in sorted(elements):
        assert element in task3_text, f"на схеме нет элемента {element}"
