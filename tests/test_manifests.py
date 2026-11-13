"""2.3-2.7, 2.9-2.14: манифесты Task2, значения чартов мониторинга и скрипты нагрузки.

Значения в манифестах записаны буквально и сверяются с config/defaults.toml.
Проверки файла пропускаются, пока сам файл не добавлен в репозиторий.
"""

import re

import pytest
import yaml

TASK2 = "Task2"


def load(repo_root, relative):
    path = repo_root / TASK2 / relative
    if not path.exists():
        pytest.skip(f"{TASK2}/{relative} еще не добавлен")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture
def deployment(repo_root):
    return load(repo_root, "deployment.yaml")


@pytest.fixture
def service(repo_root):
    return load(repo_root, "service.yaml")


@pytest.fixture
def hpa_memory(repo_root):
    return load(repo_root, "hpa-memory.yaml")


@pytest.fixture
def hpa_rps(repo_root):
    return load(repo_root, "hpa-rps.yaml")


def container(deployment):
    containers = deployment["spec"]["template"]["spec"]["containers"]
    assert len(containers) == 1
    return containers[0]


# 2.3 Deployment


def test_deployment_identity(deployment, config):
    app = config["app"]
    assert deployment["apiVersion"] == "apps/v1"
    assert deployment["kind"] == "Deployment"
    assert deployment["metadata"]["name"] == app["name"]
    assert deployment["metadata"]["namespace"] == app["namespace"]


def test_deployment_one_replica(deployment):
    assert deployment["spec"]["replicas"] == 1


def test_deployment_selector_matches_template(deployment, config):
    selector = deployment["spec"]["selector"]["matchLabels"]
    labels = deployment["spec"]["template"]["metadata"]["labels"]
    assert selector == {"app": config["app"]["name"]}
    assert selector.items() <= labels.items()


def test_deployment_image_and_port(deployment, config):
    app = config["app"]
    item = container(deployment)
    assert item["image"] == f"{app['image']}:{app['tag']}"
    ports = [port["containerPort"] for port in item["ports"]]
    assert ports == [app["port"]]


def test_deployment_memory(deployment, config):
    resources = container(deployment)["resources"]
    assert resources["limits"]["memory"] == config["memory_hpa"]["limit"]
    assert resources["requests"]["memory"] == config["memory_hpa"]["request"]


def test_probe_does_not_touch_counted_endpoint(deployment):
    probe = container(deployment)["readinessProbe"]["httpGet"]
    assert probe["path"] == "/metrics"


# 2.4 Service


def test_service_identity(service, config):
    app = config["app"]
    assert service["kind"] == "Service"
    assert service["metadata"]["name"] == app["name"]
    assert service["metadata"]["namespace"] == app["namespace"]
    assert service["spec"]["type"] == "NodePort"


def test_service_selects_deployment_pods(service, deployment):
    labels = deployment["spec"]["template"]["metadata"]["labels"]
    assert service["spec"]["selector"].items() <= labels.items()


def test_service_port(service, deployment, config):
    ports = service["spec"]["ports"]
    assert len(ports) == 1
    assert ports[0]["port"] == config["app"]["port"]
    container_port_names = {port["name"] for port in container(deployment)["ports"]}
    assert ports[0]["targetPort"] in container_port_names


# 2.5, 2.13 HPA


def check_hpa_common(hpa, section, config):
    app = config["app"]
    assert hpa["apiVersion"] == "autoscaling/v2"
    assert hpa["kind"] == "HorizontalPodAutoscaler"
    assert hpa["metadata"]["name"] == app["name"]
    assert hpa["metadata"]["namespace"] == app["namespace"]
    target = hpa["spec"]["scaleTargetRef"]
    assert target == {"apiVersion": "apps/v1", "kind": "Deployment", "name": app["name"]}
    assert hpa["spec"]["minReplicas"] == config[section]["min_replicas"]
    assert hpa["spec"]["maxReplicas"] == config[section]["max_replicas"]
    assert len(hpa["spec"]["metrics"]) == 1
    return hpa["spec"]["metrics"][0]


def test_hpa_memory(hpa_memory, config):
    metric = check_hpa_common(hpa_memory, "memory_hpa", config)
    assert metric["type"] == "Resource"
    assert metric["resource"]["name"] == "memory"
    target = metric["resource"]["target"]
    assert target == {
        "type": "Utilization",
        "averageUtilization": config["memory_hpa"]["target_utilization"],
    }


def test_hpa_rps(hpa_rps, config):
    rps = config["rps_hpa"]
    metric = check_hpa_common(hpa_rps, "rps_hpa", config)
    assert metric["type"] == "Pods"
    assert metric["pods"]["metric"]["name"] == rps["metric_name"]
    target = metric["pods"]["target"]
    assert target == {"type": "AverageValue", "averageValue": str(rps["target_rps_per_pod"])}


def test_both_hpa_share_name(hpa_memory, hpa_rps):
    assert hpa_memory["metadata"]["name"] == hpa_rps["metadata"]["name"]


# 2.6 locustfile из задания


def test_locustfile_matches_task(repo_root):
    path = repo_root / TASK2 / "locustfile.py"
    if not path.exists():
        pytest.skip("locustfile.py еще не добавлен")
    text = path.read_text(encoding="utf-8")
    assert "class WebsiteUser(HttpUser):" in text
    assert "wait_time = between(1, 5)" in text
    assert 'self.client.get("/")' in text
    compile(text, str(path), "exec")


# 2.9-2.12 мониторинг


def test_prometheus_values(repo_root, config):
    values = load(repo_root, "monitoring/prometheus-values.yaml")
    spec = values["prometheus"]["prometheusSpec"]
    assert spec["scrapeInterval"] == config["monitoring"]["scrape_interval"]
    assert spec["serviceMonitorSelectorNilUsesHelmValues"] is False
    for component in ("alertmanager", "grafana"):
        assert values[component]["enabled"] is False


def test_servicemonitor_matches_service(repo_root, service, config):
    monitor = load(repo_root, "monitoring/servicemonitor.yaml")
    assert monitor["apiVersion"] == "monitoring.coreos.com/v1"
    assert monitor["kind"] == "ServiceMonitor"
    assert monitor["spec"]["selector"]["matchLabels"].items() <= service["metadata"]["labels"].items()
    assert monitor["spec"]["namespaceSelector"]["matchNames"] == [config["app"]["namespace"]]
    endpoints = monitor["spec"]["endpoints"]
    assert len(endpoints) == 1
    assert endpoints[0]["port"] == service["spec"]["ports"][0]["name"]
    assert endpoints[0]["path"] == "/metrics"
    assert endpoints[0]["interval"] == config["monitoring"]["scrape_interval"]


def test_adapter_points_to_prometheus(repo_root, config):
    values = load(repo_root, "monitoring/prometheus-adapter-values.yaml")
    monitoring = config["monitoring"]
    expected = f"http://{monitoring['prometheus_release']}-prometheus.{monitoring['namespace']}.svc"
    assert values["prometheus"]["url"] == expected
    assert values["prometheus"]["port"] == 9090
    assert values["metricsRelistInterval"] == monitoring["adapter_relist_interval"]


def test_adapter_rule_builds_rps_metric(repo_root, config):
    values = load(repo_root, "monitoring/prometheus-adapter-values.yaml")
    assert values["rules"]["default"] is False
    rules = values["rules"]["custom"]
    assert len(rules) == 1
    rule = rules[0]
    source = config["monitoring"]["metric"]
    assert rule["seriesQuery"].startswith(source + "{")
    assert set(rule["resources"]["overrides"]) == {"namespace", "pod"}
    produced = re.sub(rule["name"]["matches"], rule["name"]["as"].replace("${1}", r"\1"), source)
    assert produced == config["rps_hpa"]["metric_name"]
    window = config["rps_hpa"]["rate_window"]
    assert f"rate(<<.Series>>{{<<.LabelMatchers>>}}[{window}])" in rule["metricsQuery"]
    assert "by (<<.GroupBy>>)" in rule["metricsQuery"]


def test_readme_commands_match_config(repo_root, config):
    path = repo_root / TASK2 / "README.md"
    if not path.exists():
        pytest.skip("Task2/README.md еще не добавлен")
    text = path.read_text(encoding="utf-8")
    monitoring = config["monitoring"]
    installs = [line for line in text.splitlines() if line.startswith("helm upgrade --install")]
    assert len(installs) == 2
    releases = {line.split()[3] for line in installs}
    assert releases == {monitoring["prometheus_release"], monitoring["adapter_release"]}
    for line in installs:
        assert f"-n {monitoring['namespace']}" in line
        assert "--version \"$(python scripts/_common.py monitoring." in line
    assert config["rps_hpa"]["metric_name"] in text


# Скрипты нагрузки и сбора логов (2.6, 2.7, 2.14)


@pytest.mark.parametrize(
    "text, seconds", [("30s", 30), ("7m", 420), ("1h", 3600), ("15", 15), (" 3m ", 180)]
)
def test_parse_duration(text, seconds):
    parse_duration = pytest.importorskip("run_load").parse_duration

    assert parse_duration(text) == seconds


@pytest.mark.parametrize("text", ["", "m", "3 m", "1.5m", "3d"])
def test_parse_duration_rejects(text):
    parse_duration = pytest.importorskip("run_load").parse_duration

    with pytest.raises(ValueError):
        parse_duration(text)


def test_config_durations_are_valid(config):
    parse_duration = pytest.importorskip("run_load").parse_duration

    for value in (
        config["locust"]["run_time"],
        config["capture"]["baseline"],
        config["capture"]["after_load"],
        config["capture"]["sample_interval"],
    ):
        assert parse_duration(value) > 0


def test_capture_waits_for_scale_down_window(config):
    parse_duration = pytest.importorskip("run_load").parse_duration

    # Окно стабилизации снижения HPA по умолчанию 300 секунд.
    assert parse_duration(config["capture"]["after_load"]) > 300


def test_locust_command(config):
    LOCUSTFILE = pytest.importorskip("run_load").LOCUSTFILE
    build_command = pytest.importorskip("run_load").build_command

    command = build_command("http://127.0.0.1:1234/", 100, 10, "3m")
    assert command[1:3] == ["-m", "locust"]
    assert str(LOCUSTFILE) in command
    assert command[command.index("--host") + 1] == "http://127.0.0.1:1234"
    assert command[command.index("-u") + 1] == "100"
    assert "--headless" in command


def test_load_bypasses_proxy():
    direct_env = pytest.importorskip("run_load").direct_env

    env = direct_env("http://127.0.0.1:56704", {"HTTPS_PROXY": "http://proxy:3128", "NO_PROXY": "corp"})
    for key in ("NO_PROXY", "no_proxy"):
        items = env[key].split(",")
        assert {"127.0.0.1", "localhost"} <= set(items)
    assert env["NO_PROXY"].startswith("corp,")
    assert env["HTTPS_PROXY"] == "http://proxy:3128"


def test_check_host_ignores_proxy(monkeypatch):
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    run_load = pytest.importorskip("run_load")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = "Идентификатор пода: test\n".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # Неработающий прокси в окружении: проверка должна идти мимо него.
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    try:
        answer = run_load.check_host(f"http://127.0.0.1:{server.server_port}")
    finally:
        server.shutdown()
    assert answer == "Идентификатор пода: test"


def test_capture_log_names_follow_repo_map():
    log_names = pytest.importorskip("capture_scaling").log_names

    assert set(log_names(1).values()) == {
        "part1-hpa.log",
        "part1-pods.log",
        "part1-top.log",
        "part1-describe-pod.log",
    }
    assert set(log_names(2).values()) == {
        "part2-hpa.log",
        "part2-pods.log",
        "part2-custom-metrics.log",
    }


def test_capture_commands_use_config(config):
    sample_commands = pytest.importorskip("capture_scaling").sample_commands
    watch_commands = pytest.importorskip("capture_scaling").watch_commands

    app = config["app"]
    watch = watch_commands(config)
    assert watch["hpa"][:4] == ["kubectl", "get", "hpa", app["name"]]
    assert "-w" in watch["hpa"] and "-w" in watch["pods"]
    assert f"app={app['name']}" in watch["pods"]
    raw = sample_commands(2, config)["custom"][-1]
    assert raw.endswith("/pods/*/" + config["rps_hpa"]["metric_name"])
    assert sample_commands(1, config)["top"][:3] == ["kubectl", "top", "pods"]


@pytest.mark.parametrize(
    "line, expected",
    [
        ("12:00:00 NAME REFERENCE TARGETS MINPODS MAXPODS REPLICAS AGE", None),
        ("12:00:15 scaletestapp Deployment/scaletestapp memory: 40%/80% 1 10 3 5m", 3),
        ("12:00:30 scaletestapp Deployment/scaletestapp 2500m/5 1 10 7 9m", 7),
        ("12:00:45 --- нагрузка остановлена, код locust 0", None),
        ("12:01:00 $ kubectl get hpa scaletestapp -n default -w", None),
    ],
)
def test_parse_replicas(line, expected):
    parse_replicas = pytest.importorskip("capture_scaling").parse_replicas

    assert parse_replicas(line) == expected


def test_config_cli(capsys):
    import _common

    assert _common.main(["app.name"]) == 0
    assert capsys.readouterr().out.strip() == "scaletestapp"
    assert _common.main(["app.missing"]) == 1
