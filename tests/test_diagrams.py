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


# Task3: диаграмма контейнеров C4 на основе исходной схемы (3.2-3.6).
# Схема сохранена в формате draw.io с элементами object: подпись задана шаблоном с полями c4Name, c4Type, c4Technology, c4Description.

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
# Блоки исходной схемы, которые должны остаться (имя клиентской БД и веб-приложения хранится в поле c4Type).
TASK3_SOURCE_BLOCKS = [
    "Клиент",
    "InsureTech Web",
    "Системы партнеров",
    "Системы страховых компаний",
    "Платежный сервис",
    "core-db",
    "ins-comp-settlement-db",
    "client-info-db",
]


def diagram_items(path: Path) -> list[dict]:
    """Возвращает блоки и стрелки схемы: id, поля c4, подпись с подставленными полями, источник и цель."""
    items = []
    model = ET.parse(path).getroot().find("diagram/mxGraphModel/root")
    for node in model:
        if node.tag == "object":
            attrs = dict(node.attrib)
            cell = node.find("mxCell")
            raw = attrs.get("label", "")
            raw = re.sub(r"%(\w+)%", lambda m: attrs.get(m.group(1), ""), raw)
        elif node.tag == "mxCell" and node.get("id") not in ("0", "1"):
            attrs, cell, raw = dict(node.attrib), node, node.get("value", "")
        else:
            continue
        items.append(
            {
                "id": attrs["id"],
                "attrs": attrs,
                "edge": cell.get("edge") == "1",
                "source": cell.get("source"),
                "target": cell.get("target"),
                "text": clean(raw),
            }
        )
    return items


def clean(raw: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", html.unescape(raw or "")))
    return re.sub(r"\s+", " ", text).strip()


@pytest.fixture(scope="module")
def task3_items() -> list[dict]:
    assert TASK3.is_file(), f"нет файла {TASK3.relative_to(ROOT)}"
    return diagram_items(TASK3)


@pytest.fixture(scope="module")
def task3_text(task3_items) -> str:
    return " ".join(item["text"] for item in task3_items)


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


@pytest.mark.parametrize("name", sorted(TASK3_SERVICES) + TASK3_SOURCE_BLOCKS)
def test_task3_components(task3_text, name):
    assert name.lower() in task3_text.lower()


def test_task3_no_duplicate_blocks(task3_items):
    """В исходной схеме блоки партнеров и страховых компаний лежали тремя копиями, на схеме остается по одному."""
    ids = [item["id"] for item in task3_items]
    assert len(ids) == len(set(ids)), "повторяющиеся идентификаторы"
    names = [
        (item["attrs"].get("c4Name") or item["attrs"].get("c4Type"))
        for item in task3_items
        if not item["edge"] and item["attrs"].get("c4Type") != "SystemScopeBoundary" and "c4Type" in item["attrs"]
    ]
    assert len(names) == len(set(names)), f"повторяющиеся блоки: {sorted(n for n in set(names) if names.count(n) > 1)}"


def test_task3_decomposition_unchanged(task3_items):
    """Сервисы (контейнеры на Kotlin, SpringBoot) совпадают с исходным набором, брокер это инфраструктура."""
    services = {
        item["attrs"]["c4Name"]
        for item in task3_items
        if item["attrs"].get("c4Type") == "Container" and "Kotlin" in item["attrs"].get("c4Technology", "")
    }
    assert services == TASK3_SERVICES


def test_task3_broker_is_infrastructure(config, task3_items):
    brokers = [item for item in task3_items if item["attrs"].get("c4Name") == config["broker"]["name"]]
    assert len(brokers) == 1
    assert "инфраструктура" in brokers[0]["text"].lower()
    assert "не функциональный сервис" in brokers[0]["text"]


def test_task3_broker_matches_config(config, task3_text):
    broker = config["broker"]
    assert broker["name"] in task3_text
    assert f"{broker['brokers']} брокера в {broker['brokers']} зонах" in task3_text
    assert f"фактор репликации {broker['replication_factor']}" in task3_text
    assert f"min.insync.replicas {broker['min_insync_replicas']}" in task3_text


def test_task3_edges_connected(task3_items):
    ids = {item["id"] for item in task3_items if not item["edge"]}
    edges = [item for item in task3_items if item["edge"]]
    assert edges
    for edge in edges:
        assert edge["source"] in ids and edge["target"] in ids, f"стрелка {edge['id']} не привязана"


def test_task3_broker_edges_name_topics(config, task3_items):
    """Каждая стрелка брокера подписана темой, обе темы имеют издателя и потребителя."""
    broker = config["broker"]
    topics = (broker["topic_products"], broker["topic_policies"])
    broker_id = next(item["id"] for item in task3_items if item["attrs"].get("c4Name") == broker["name"])
    published, consumed = set(), set()
    for item in task3_items:
        if not item["edge"] or broker_id not in (item["source"], item["target"]):
            continue
        named = [topic for topic in topics if f"тема {topic}" in item["text"]]
        assert len(named) == 1, f"стрелка {item['id']}: не названа тема"
        (published if item["target"] == broker_id else consumed).add(named[0])
    assert published == set(topics)
    assert consumed == set(topics)


def test_task3_consumer_groups(task3_items):
    """Читающие стрелки брокера называют группу потребителей, равную имени читающего сервиса."""
    names = {item["id"]: item["attrs"].get("c4Name") for item in task3_items if not item["edge"]}
    broker_ids = {i for i, name in names.items() if name == "Apache Kafka"}
    for item in task3_items:
        if item["edge"] and item["source"] in broker_ids:
            assert f"группа {names[item['target']]}" in item["text"], f"стрелка {item['id']}: нет группы потребителей"


def test_task3_no_direct_calls_between_decoupled_services(task3_items):
    """core-app, ins-comp-settlement и ins-product-aggregator связаны только через брокер."""
    names = {item["id"]: item["attrs"].get("c4Name") for item in task3_items if not item["edge"]}
    decoupled = {"core-app", "ins-comp-settlement", "ins-product-aggregator"}
    for item in task3_items:
        if item["edge"]:
            pair = {names.get(item["source"]), names.get(item["target"])}
            assert not (len(pair) == 2 and pair <= decoupled), f"прямая стрелка {item['id']}"


def test_task3_kept_synchronous_edges(task3_items):
    """Синхронные связи из исходной схемы, которые не относятся к переводу на события, сохранены."""
    names = {item["id"]: item["attrs"].get("c4Name") or item["attrs"].get("c4Type") for item in task3_items if not item["edge"]}
    pairs = {(names.get(item["source"]), names.get(item["target"])) for item in task3_items if item["edge"]}
    expected = {
        ("InsureTech Web", "core-app"),
        ("InsureTech Web", "client-info"),
        ("core-app", "client-info"),
        ("core-app", "core-db"),
        ("Системы партнеров", "core-app"),
        ("ins-product-aggregator", "Системы страховых компаний"),
        ("ins-comp-settlement", "Системы страховых компаний"),
        ("core-app", "Платежный сервис"),
        ("InsureTech Web", "Платежный сервис"),
    }
    assert expected <= pairs


def test_task3_problem_elements_on_diagram(task3_text):
    """3.6: элементы схемы, названные в таблице проблем, есть на схеме."""
    lines = [line for line in TASK3_PROBLEMS.read_text(encoding="utf-8").splitlines() if re.match(r"\| \d+ \|", line)]
    elements = set()
    for line in lines:
        elements.update(re.findall(r"`([^`]+)`", line))
    assert elements, "в таблице проблем не названы элементы схемы"
    for element in sorted(elements):
        assert element in task3_text, f"на схеме нет элемента {element}"
