"""Запись поведения HPA под нагрузкой в Task2/logs (2.2, 2.7, 2.12, 2.14).

Порядок работы:
1. Проверка, что HPA в кластере соответствует части задания (часть 1 - память, часть 2 - RPS).
2. Запуск kubectl get hpa -w и kubectl get pods -w с записью в логи части.
3. Запись состояния до нагрузки (capture.baseline), затем нагрузка locust с параметрами из конфига.
4. После остановки нагрузки запись идет еще capture.after_load, чтобы в лог попало снижение реплик.

Каждая строка лога начинается со времени. Моменты запуска и остановки нагрузки отмечены в логах.
Часть 1 дополнительно пишет kubectl top pods и в конце kubectl describe pods.
Часть 2 дополнительно пишет ответы custom.metrics.k8s.io: список метрик и значения по подам.
"""

import argparse
import shutil
import subprocess
import sys
import threading
import time

from _common import ROOT, load_config
from run_load import add_load_arguments, check_host, parse_duration, run_load

LOG_DIR = ROOT / "Task2" / "logs"
EXPECTED_METRIC_TYPE = {1: "Resource", 2: "Pods"}
CUSTOM_METRICS_API = "/apis/custom.metrics.k8s.io/v1beta1"


def timestamp():
    return time.strftime("%H:%M:%S")


class LogFile:
    """Файл лога, в который безопасно пишут несколько потоков."""

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self._handle = open(path, "w", encoding="utf-8", newline="\n")

    def line(self, text):
        with self._lock:
            self._handle.write(f"{timestamp()} {text}\n")
            self._handle.flush()

    def block(self, title, text):
        with self._lock:
            self._handle.write(f"=== {timestamp()} {title}\n{text.rstrip()}\n")
            self._handle.flush()

    def close(self):
        with self._lock:
            self._handle.close()


def log_names(part):
    """Имена файлов логов части задания, как в 04_repo_map."""
    names = {"hpa": f"part{part}-hpa.log", "pods": f"part{part}-pods.log"}
    if part == 1:
        names["top"] = "part1-top.log"
        names["describe"] = "part1-describe-pod.log"
    else:
        names["custom"] = "part2-custom-metrics.log"
    return names


def watch_commands(config):
    app = config["app"]
    return {
        "hpa": ["kubectl", "get", "hpa", app["name"], "-n", app["namespace"], "-w"],
        "pods": ["kubectl", "get", "pods", "-l", f"app={app['name']}", "-n", app["namespace"], "-w"],
    }


def sample_commands(part, config):
    """Команды, которые выполняются периодически во время записи."""
    app = config["app"]
    if part == 1:
        return {"top": ["kubectl", "top", "pods", "-l", f"app={app['name']}", "-n", app["namespace"]]}
    metric = config["rps_hpa"]["metric_name"]
    path = f"{CUSTOM_METRICS_API}/namespaces/{app['namespace']}/pods/*/{metric}"
    return {"custom": ["kubectl", "get", "--raw", path]}


def run_text(command):
    """Выполняет команду и возвращает вывод вместе с ошибками."""
    result = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return (result.stdout + result.stderr).strip() or "(пустой вывод)"


def parse_replicas(line):
    """Число реплик из строки kubectl get hpa -w с отметкой времени или None."""
    tokens = line.split()
    if len(tokens) < 3 or "NAME" in tokens or tokens[0] == "===":
        return None
    candidate = tokens[-2]
    return int(candidate) if candidate.isdigit() else None


def replicas_range(path):
    """Минимум и максимум реплик по логу HPA или None, если строк с репликами нет."""
    values = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = parse_replicas(line)
        if value is not None:
            values.append(value)
    return (min(values), max(values)) if values else None


def hpa_metric_type(config):
    app = config["app"]
    command = [
        "kubectl", "get", "hpa", app["name"], "-n", app["namespace"],
        "-o", "jsonpath={.spec.metrics[0].type}",
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise SystemExit("HPA не найден: " + result.stderr.strip())
    return result.stdout.strip()


def stream(command, log):
    """Пишет построчный вывод команды в лог до ее остановки."""
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    def pump():
        for raw in process.stdout:
            log.line(raw.rstrip("\n"))

    thread = threading.Thread(target=pump, daemon=True)
    thread.start()
    return process, thread


def sample(command, log, interval, stop):
    """Выполняет команду раз в interval секунд до сигнала остановки."""
    title = " ".join(command)
    while True:
        log.block(title, run_text(command))
        if stop.wait(interval):
            return


def wait_with_progress(seconds, label):
    end = time.monotonic() + seconds
    while True:
        left = end - time.monotonic()
        if left <= 0:
            return
        print(f"{timestamp()} {label}: осталось {int(left // 60)} мин {int(left % 60)} с", flush=True)
        time.sleep(min(60, left))


def main(argv=None):
    config = load_config()
    capture = config["capture"]
    parser = argparse.ArgumentParser(description="Запись масштабирования HPA под нагрузкой")
    parser.add_argument("--part", type=int, choices=(1, 2), required=True, help="часть задания")
    add_load_arguments(parser, config)
    parser.add_argument("--baseline", default=capture["baseline"], help="запись до нагрузки")
    parser.add_argument("--after-load", default=capture["after_load"], help="запись после нагрузки")
    args = parser.parse_args(argv)

    baseline = parse_duration(args.baseline)
    after_load = parse_duration(args.after_load)
    interval = parse_duration(capture["sample_interval"])

    if shutil.which("kubectl") is None:
        raise SystemExit("kubectl не найден в PATH")
    metric_type = hpa_metric_type(config)
    if metric_type != EXPECTED_METRIC_TYPE[args.part]:
        raise SystemExit(
            f"в кластере HPA с метрикой {metric_type}, для части {args.part} "
            f"нужна {EXPECTED_METRIC_TYPE[args.part]}"
        )
    print("ответ сервиса: " + check_host(args.host), flush=True)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    names = log_names(args.part)
    logs = {key: LogFile(LOG_DIR / name) for key, name in names.items()}
    stop = threading.Event()
    processes = []
    samplers = []
    try:
        if args.part == 2:
            logs["custom"].block(
                f"kubectl get --raw {CUSTOM_METRICS_API}",
                run_text(["kubectl", "get", "--raw", CUSTOM_METRICS_API]),
            )
        for key, command in watch_commands(config).items():
            logs[key].line("$ " + " ".join(command))
            processes.append(stream(command, logs[key]))
        for key, command in sample_commands(args.part, config).items():
            thread = threading.Thread(
                target=sample, args=(command, logs[key], interval, stop), daemon=True
            )
            thread.start()
            samplers.append(thread)

        wait_with_progress(baseline, "запись до нагрузки")
        for key in ("hpa", "pods"):
            logs[key].line(f"--- нагрузка запущена: {args.users} пользователей, {args.run_time}")
        code = run_load(args)
        for key in ("hpa", "pods"):
            logs[key].line(f"--- нагрузка остановлена, код locust {code}")
        wait_with_progress(after_load, "запись после нагрузки")
    finally:
        stop.set()
        for thread in samplers:
            thread.join(timeout=30)
        for process, thread in processes:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
            thread.join(timeout=5)
        if args.part == 1:
            app = config["app"]
            command = ["kubectl", "describe", "pods", "-l", f"app={app['name']}", "-n", app["namespace"]]
            logs["describe"].block(" ".join(command), run_text(command))
        for log in logs.values():
            log.close()

    for log in logs.values():
        print("записан " + log.path.relative_to(ROOT).as_posix())
    found = replicas_range(logs["hpa"].path)
    if found:
        print(f"реплики по логу HPA: минимум {found[0]}, максимум {found[1]}")
    else:
        print("в логе HPA нет строк с числом реплик")
    return 0


if __name__ == "__main__":
    sys.exit(main())
