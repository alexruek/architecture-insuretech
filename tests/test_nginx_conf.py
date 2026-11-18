"""6.1-6.4: Task6/nginx.conf доработан из шаблона задания, лимит и код ответа совпадают с конфигом.

Значения в nginx.conf записаны буквально и сверяются с разделом nginx файла config/defaults.toml.
Синтаксис проверяется самим nginx через scripts/check_nginx.py, если nginx установлен.
"""

import re
import subprocess

import pytest

import check_nginx

CONF = ("Task6", "nginx.conf")


def strip_comments(text):
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def parse(text):
    """Разбирает конфиг nginx в список узлов (имя, аргументы, дочерние узлы или None)."""
    tokens = re.findall(r'"[^"]*"|[{};]|[^\s{};]+', strip_comments(text))
    position = 0

    def block():
        nonlocal position
        nodes = []
        while position < len(tokens):
            token = tokens[position]
            if token == "}":
                position += 1
                return nodes
            words = []
            while tokens[position] not in ("{", ";", "}"):
                words.append(tokens[position])
                position += 1
            end = tokens[position]
            position += 1
            if end == "{":
                nodes.append((words[0], words[1:], block()))
            elif end == ";":
                nodes.append((words[0], words[1:], None))
            else:
                raise ValueError("лишняя закрывающая скобка")
        return nodes

    nodes = block()
    if position != len(tokens):
        raise ValueError("разбор не дошел до конца файла")
    return nodes


def find(nodes, name, args=None):
    return [node for node in nodes if node[0] == name and (args is None or node[1] == args)]


def one(nodes, name, args=None):
    found = find(nodes, name, args)
    assert len(found) == 1, f"ожидалась одна директива {name} {args or ''}, найдено {len(found)}"
    return found[0]


@pytest.fixture(scope="module")
def text(repo_root):
    path = repo_root.joinpath(*CONF)
    if not path.exists():
        pytest.skip("Task6/nginx.conf еще не добавлен")
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def tree(text):
    return parse(text)


@pytest.fixture(scope="module")
def http(tree):
    return one(tree, "http")[2]


@pytest.fixture(scope="module")
def location(http, config):
    server = one(http, "server")[2]
    return one(server, "location", [config["nginx"]["location"]])[2]


def test_braces_balanced(text):
    clean = strip_comments(text)
    assert clean.count("{") == clean.count("}")


def test_only_http_on_top_level(tree):
    assert [node[0] for node in tree] == ["http"]


def test_template_kept(http, config):
    nginx = config["nginx"]
    upstream = one(http, "upstream", [nginx["upstream"]])[2]
    assert [node[1] for node in upstream] == [[host] for host in nginx["servers"]]
    assert all(node[0] == "server" for node in upstream)
    server = one(http, "server")[2]
    assert one(server, "listen")[1] == [str(nginx["listen"])]


def test_proxy_pass(location, config):
    assert one(location, "proxy_pass")[1] == [f"http://{config['nginx']['upstream']}"]


def test_limit_req_zone(http, config):
    nginx = config["nginx"]
    args = one(http, "limit_req_zone")[1]
    assert args == [nginx["key"], f"zone={nginx['zone']}:{nginx['zone_size']}", f"rate={nginx['rate']}"]


def test_rate_is_ten_per_minute(config):
    assert config["nginx"]["rate"] == "10r/m"
    assert check_nginx.rate_interval_seconds(config["nginx"]["rate"]) == 6


def test_limit_req_applied_to_location(location, config):
    assert one(location, "limit_req")[1] == [f"zone={config['nginx']['zone']}"]


def test_limit_req_status(http, config):
    assert config["nginx"]["status"] == 429
    assert one(http, "limit_req_status")[1] == [str(config["nginx"]["status"])]


def test_no_burst(text, config):
    assert config["nginx"]["burst"] == 0
    assert "burst" not in text


def test_no_events_block(tree):
    assert not find(tree, "events")


def test_check_config_replaces_hosts_and_port(text, config, tmp_path):
    nginx = config["nginx"]
    built = check_nginx.build_check_config(text, nginx, tmp_path, 18080, 18081)
    tree = parse(built)
    assert [node[0] for node in tree] == ["pid", "error_log", "events", "http"]
    http = one(tree, "http")[2]
    upstream = one(http, "upstream", [nginx["upstream"]])[2]
    assert [node[1] for node in upstream] == [["127.0.0.1:18081"]] * len(nginx["servers"])
    servers = find(http, "server")
    assert sorted(one(node[2], "listen")[1][0] for node in servers) == ["127.0.0.1:18080", "127.0.0.1:18081"]
    assert one(http, "limit_req_zone")[1] == one(parse(text)[0][2], "limit_req_zone")[1]
    for host in nginx["servers"]:
        assert host not in built


def test_check_config_requires_template_lines(config, tmp_path):
    with pytest.raises(ValueError):
        check_nginx.build_check_config("http {\n}\n", config["nginx"], tmp_path, 1, 2)


@pytest.mark.skipif(not check_nginx.find_nginx(None), reason="nginx не установлен")
def test_nginx_syntax(text, config, tmp_path):
    nginx = check_nginx.find_nginx(None)
    conf = tmp_path / "nginx.conf"
    conf.write_text(check_nginx.build_check_config(text, config["nginx"], tmp_path, 18080, 18081), encoding="utf-8")
    result = subprocess.run(
        [nginx, "-t", "-p", str(tmp_path), "-e", str(tmp_path / "error.log"), "-c", str(conf)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "syntax is ok" in result.stderr
