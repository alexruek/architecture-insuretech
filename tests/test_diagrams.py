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


# Task4: диаграмма контейнеров C4 с продажей ОСАГО, доработанная из схемы Task3 (4.1-4.10).

TASK4 = ROOT / "Task4" / "InsureTech_C4_container-diagram-osago.drawio"
TASK4_SERVICES = TASK3_SERVICES | {"osago-aggregator"}
TASK4_KEYWORDS = [
    "osago-aggregator",
    "osago-aggregator-db",
    "SSE",
    "text/event-stream",
    "Last-Event-ID",
    "Redis",
    "TTL",
    "outbox",
    "идемпотентно",
    "нескольких экземплярах",
]


@pytest.fixture(scope="module")
def task4_items() -> list[dict]:
    assert TASK4.is_file(), f"нет файла {TASK4.relative_to(ROOT)}"
    return diagram_items(TASK4)


@pytest.fixture(scope="module")
def task4_text(task4_items) -> str:
    return " ".join(item["text"] for item in task4_items)


def block_names(items) -> dict:
    """Идентификатор блока -> имя из поля c4Name или c4Type."""
    return {item["id"]: item["attrs"].get("c4Name") or item["attrs"].get("c4Type") for item in items if not item["edge"]}


def edge_pairs(items) -> list[tuple]:
    names = block_names(items)
    return [(names.get(item["source"]), names.get(item["target"]), item) for item in items if item["edge"]]


def test_task4_uncompressed():
    pages = ET.parse(TASK4).getroot().findall("diagram")
    assert pages, "в файле нет страниц diagram"
    for page in pages:
        assert page.find("mxGraphModel") is not None, f"страница {page.get('name')} сохранена сжатой"


def test_task4_style():
    raw = TASK4.read_text(encoding="utf-8")
    for char, name in FORBIDDEN_CHARS.items():
        assert char not in raw, name
    assert "<b>" not in html.unescape(raw), "жирный шрифт в подписи"
    for style in re.findall(r'style="([^"]*)"', raw):
        match = re.search(r"fontStyle=(\d+)", style)
        assert not (match and int(match.group(1)) & 1), f"жирный шрифт в стиле: {style[:60]}"


@pytest.mark.parametrize("word", TASK4_KEYWORDS)
def test_task4_keywords(task4_text, word):
    assert word.lower() in task4_text.lower()


def test_task4_contains_task3_blocks(task3_items, task4_items):
    """4.1: все блоки схемы Task3 остались на схеме Task4."""
    task3 = {name for name in block_names(task3_items).values() if name}
    task4 = {name for name in block_names(task4_items).values() if name}
    assert task3 <= task4, f"пропали блоки: {sorted(task3 - task4)}"


def test_task4_kept_task3_edges(task3_items, task4_items):
    """4.1: связи схемы Task3 сохранены."""
    task3 = {(s, t) for s, t, _ in edge_pairs(task3_items)}
    task4 = {(s, t) for s, t, _ in edge_pairs(task4_items)}
    assert task3 <= task4, f"пропали связи: {sorted(task3 - task4)}"


def test_task4_decomposition(task4_items):
    """Добавлен только osago-aggregator, разрешенный заданием, брокер это инфраструктура."""
    services = {
        item["attrs"]["c4Name"]
        for item in task4_items
        if item["attrs"].get("c4Type") == "Container" and "Kotlin" in item["attrs"].get("c4Technology", "")
    }
    assert services == TASK4_SERVICES


def test_task4_osago_responsibility(task4_items):
    """4.2: контейнер подписан обязанностью из задания."""
    block = next(item for item in task4_items if item["attrs"].get("c4Name") == "osago-aggregator")
    text = block["text"].lower()
    for part in ("отправляет заявки в страховые", "опрашивает решения", "core-app"):
        assert part in text


def test_task4_osago_storage(config, task4_items):
    """4.3: у osago-aggregator свое хранилище с технологией из конфига."""
    db = [item for item in task4_items if item["attrs"].get("c4Type") == "osago-aggregator-db"]
    assert len(db) == 1
    assert db[0]["attrs"]["c4Technology"] == config["osago"]["storage"]
    assert ("osago-aggregator", "osago-aggregator-db") in {(s, t) for s, t, _ in edge_pairs(task4_items)}


def test_task4_broker_edges_name_topics(config, task4_items):
    """4.4, 4.5: стрелки брокера подписаны темой, у каждой темы есть издатель и потребитель с группой."""
    broker = config["broker"]
    topics = {broker[key] for key in ("topic_products", "topic_policies", "topic_osago_applications", "topic_osago_offers")}
    published, consumed = set(), set()
    for source, target, item in edge_pairs(task4_items):
        if broker["name"] not in (source, target):
            continue
        named = [topic for topic in topics if f"тема {topic}" in item["text"]]
        assert len(named) == 1, f"стрелка {item['id']}: не названа тема"
        if target == broker["name"]:
            published.add(named[0])
        else:
            consumed.add(named[0])
            assert f"группа {target}" in item["text"], f"стрелка {item['id']}: нет группы потребителей"
    assert published == topics
    assert consumed == topics


def test_task4_osago_api_through_broker(config, task4_items):
    """4.4, 4.5: core-app и osago-aggregator связаны только через брокер: заявки туда, решения обратно."""
    broker = config["broker"]
    pairs = {(s, t, item["text"]) for s, t, item in edge_pairs(task4_items)}
    for source, target, _ in pairs:
        assert {source, target} != {"core-app", "osago-aggregator"}, "прямая стрелка core-app и osago-aggregator"

    def has(source, target, topic):
        return any(s == source and t == target and f"тема {topic}" in text for s, t, text in pairs)

    assert has("core-app", broker["name"], broker["topic_osago_applications"])
    assert has(broker["name"], "osago-aggregator", broker["topic_osago_applications"])
    assert has("osago-aggregator", broker["name"], broker["topic_osago_offers"])
    assert has(broker["name"], "core-app", broker["topic_osago_offers"])


def test_task4_osago_calls_insurers(task4_items):
    """Две операции API страховых компаний из задания: создание заявки и получение предложения."""
    edges = [item for s, t, item in edge_pairs(task4_items) if (s, t) == ("osago-aggregator", "Системы страховых компаний")]
    assert len(edges) == 1
    text = edges[0]["text"]
    assert "REST" in text and "Создание заявки" in text and "Получение предложения" in text


def test_task4_web_integration(task4_items):
    """4.6, 4.7: REST для создания заявки и отдельная новая стрелка SSE для предложений."""
    pairs = edge_pairs(task4_items)
    rest = [item for s, t, item in pairs if (s, t) == ("InsureTech Web", "core-app") and "REST" in item["text"]]
    sse = [item for s, t, item in pairs if {s, t} == {"InsureTech Web", "core-app"} and "SSE" in item["text"]]
    assert len(rest) == 1 and "ОСАГО" in rest[0]["text"]
    assert len(sse) == 1 and sse[0]["id"] != rest[0]["id"]
    assert sse[0]["text"].count("REST") == 0


def test_task4_web_api_operations(task4_text):
    """4.6: операции API core-app для веб-приложения."""
    for operation in (
        "POST /api/v1/osago/applications",
        "GET /api/v1/osago/applications/{id}/offers",
        "GET /api/v1/osago/applications/{id}/offers/stream",
    ):
        assert operation in task4_text


def test_task4_values_match_config(config, task4_text):
    """Значения на схеме совпадают с конфигом."""
    osago = config["osago"]
    assert f"{config['requirements']['osago_max_wait_seconds']} с" in task4_text
    assert f"{osago['state_ttl_minutes']} минут (TTL)" in task4_text
    assert f"каждые {osago['sse_heartbeat_seconds']} с" in task4_text


def test_task4_edges_connected(task4_items):
    ids = {item["id"] for item in task4_items if not item["edge"]}
    for item in task4_items:
        if item["edge"]:
            assert item["source"] in ids and item["target"] in ids, f"стрелка {item['id']} не привязана"


# Task4: паттерны отказоустойчивости, несколько экземпляров, оценка нагрузки (4.8-4.10).

# Значки из библиотеки "Обозначения паттернов отказоустойчивости": значение prIcon в стиле.
PATTERN_ICONS = {"Timeout": "quota", "Retry": "deploy", "Rate Limiting": "job", "Circuit Breaker": "c_role"}
LIBRARY_SHAPE = "shape=mxgraph.kubernetes.icon2"
TASK4_PATTERN_KEYWORDS = ["Circuit Breaker", "Retry", "Timeout", "Rate Limiting", "2500", "60 с"]


def pattern_icons(items) -> list[dict]:
    model = ET.parse(TASK4).getroot().find("diagram/mxGraphModel/root")
    styles = {}
    for node in model:
        cell = node if node.tag == "mxCell" else node.find("mxCell")
        styles[node.get("id")] = cell.get("style") or ""
    return [item for item in items if item["attrs"].get("pattern")], styles


@pytest.mark.parametrize("word", TASK4_PATTERN_KEYWORDS)
def test_task4_pattern_keywords(task4_text, word):
    assert word in task4_text


def test_task4_pattern_icons_from_library(task4_items):
    """4.8: значки паттернов взяты из библиотеки и привязаны к существующим стрелкам."""
    icons, styles = pattern_icons(task4_items)
    edges = {item["id"]: item for item in task4_items if item["edge"]}
    assert icons
    for icon in icons:
        name = icon["attrs"]["pattern"]
        assert LIBRARY_SHAPE in styles[icon["id"]] and f"prIcon={PATTERN_ICONS[name]}" in styles[icon["id"]]
        assert icon["attrs"]["patternEdge"] in edges, f"значок {icon['id']}: нет стрелки"


def test_task4_patterns_on_required_edges(task4_items):
    """4.8: все четыре паттерна на вызовах страховых компаний, Rate Limiting на входе, Timeout и Retry на SSE."""
    icons, _ = pattern_icons(task4_items)
    names = block_names(task4_items)
    edges = {item["id"]: item for item in task4_items if item["edge"]}
    placed = {}
    for icon in icons:
        edge = edges[icon["attrs"]["patternEdge"]]
        key = (names[edge["source"]], names[edge["target"]], "SSE" in edge["text"])
        placed.setdefault(key, set()).add(icon["attrs"]["pattern"])
    assert placed[("osago-aggregator", "Системы страховых компаний", False)] == set(PATTERN_ICONS)
    assert "Rate Limiting" in placed[("Системы партнеров", "core-app", False)]
    assert "Rate Limiting" in placed[("InsureTech Web", "core-app", False)]
    assert {"Timeout", "Retry"} <= placed[("core-app", "InsureTech Web", True)]


def test_task4_patterns_legend(task4_items):
    """На схеме есть легенда со всеми четырьмя значками."""
    model = ET.parse(TASK4).getroot().find("diagram/mxGraphModel/root")
    legend = [node.get("style") or "" for node in model if (node.get("id") or "").startswith("legend-icon-")]
    assert sorted(re.search(r"prIcon=(\w+)", style).group(1) for style in legend) == sorted(PATTERN_ICONS.values())


def test_task4_patterns_match_config(config, task4_text):
    """Параметры паттернов на схеме совпадают с конфигом, отвергнутые паттерны обоснованы."""
    osago = config["osago"]
    assert f"ограничен {osago['insurer_call_timeout_seconds']} с" in task4_text
    assert f"до {osago['retry_max_attempts']} попыток" in task4_text
    assert f"от {osago['retry_base_delay_ms']} мс" in task4_text
    assert f"последние {osago['cb_window_calls']} вызовов" in task4_text
    assert f"не меньше {osago['cb_failure_rate_percent']}%" in task4_text
    assert f"на {osago['cb_open_seconds']} с" in task4_text
    assert f"не больше {osago['web_rate_limit_per_minute']} заявок" in task4_text
    assert f"{config['nginx']['rate'].replace('r/m', '')} запросов в минуту на партнера" in task4_text
    assert "Где паттерны не нужны" in task4_text


def test_task4_instances(task4_text):
    """4.9: работа при нескольких экземплярах описана для osago-aggregator и core-app."""
    for part in ("группу потребителей osago-aggregator", "аренду", "в собственной группе", "SKIP LOCKED"):
        assert part in task4_text


def test_task4_load_estimate(config, task4_text):
    """4.10: числа оценки нагрузки выводятся из конфига."""
    osago, req = config["osago"], config["requirements"]
    users, wait = req["osago_peak_concurrent_users"], req["osago_max_wait_seconds"]
    polls, t, interval = 0, osago["poll_first_seconds"], osago["poll_first_seconds"]
    while t <= wait:
        polls += 1
        interval = min(interval * 2, osago["poll_max_interval_seconds"])
        t += interval
    rate = -(-users // wait)
    insurers = osago["insurers_planned"]
    for phrase in (
        f"около {rate} новых заявок в секунду",
        f"не больше {polls} опросов",
        f"до {rate * polls} опросов в секунду",
        f"до {rate * (polls + 1) * insurers} исходящих",
        f"до {rate * (insurers + 1)} решений в секунду",
        f"{users * insurers} записей",
        f"до {-(-users // 3)} на экземпляр",
        "выдерживает пик",
    ):
        assert phrase in task4_text, phrase
