"""Нагрузочный тест Task2 (2.6, 2.14): locust в режиме headless с параметрами из config/defaults.toml.

Адрес сервиса передается параметром --host: его выдает minikube service scaletestapp --url
в отдельном открытом терминале.
"""

import argparse
import re
import subprocess
import sys
import urllib.error
import urllib.request

from _common import ROOT, load_config

LOCUSTFILE = ROOT / "Task2" / "locustfile.py"
POD_ANSWER = "Идентификатор пода"
DURATION_RE = re.compile(r"^(\d+)([smh]?)$")
UNIT_SECONDS = {"": 1, "s": 1, "m": 60, "h": 3600}


def parse_duration(text):
    """Переводит длительность вида 30s, 7m, 1h или число секунд в секунды."""
    match = DURATION_RE.match(str(text).strip())
    if not match:
        raise ValueError(f"неверная длительность: {text}")
    return int(match.group(1)) * UNIT_SECONDS[match.group(2)]


def build_command(host, users, spawn_rate, run_time):
    """Собирает команду запуска locust без интерфейса."""
    return [
        sys.executable,
        "-m",
        "locust",
        "-f",
        str(LOCUSTFILE),
        "--headless",
        "-u",
        str(users),
        "-r",
        str(spawn_rate),
        "-t",
        str(run_time),
        "--host",
        host.rstrip("/"),
        "--only-summary",
    ]


def check_host(host, timeout=5):
    """Проверяет, что по адресу отвечает тестовое приложение. Возвращает первую строку ответа."""
    url = host.rstrip("/") + "/"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as error:
        raise SystemExit(f"сервис по адресу {url} не отвечает: {error}") from error
    if POD_ANSWER not in text:
        raise SystemExit(f"по адресу {url} отвечает не scaletestapp")
    return text.strip().splitlines()[0]


def add_load_arguments(parser, config):
    """Параметры нагрузки, общие для run_load.py и capture_scaling.py."""
    locust = config["locust"]
    parser.add_argument("--host", required=True, help="адрес сервиса из minikube service --url")
    parser.add_argument("--users", type=int, default=locust["users"], help="число пользователей")
    parser.add_argument(
        "--spawn-rate", type=int, default=locust["spawn_rate"], help="пользователей в секунду"
    )
    parser.add_argument("--run-time", default=locust["run_time"], help="длительность нагрузки")


def run_load(args):
    """Запускает locust и возвращает его код завершения."""
    parse_duration(args.run_time)
    command = build_command(args.host, args.users, args.spawn_rate, args.run_time)
    print(
        f"нагрузка: {args.users} пользователей, {args.spawn_rate} в секунду, {args.run_time}",
        flush=True,
    )
    return subprocess.call(command, cwd=ROOT)


def main(argv=None):
    config = load_config()
    parser = argparse.ArgumentParser(description="Нагрузочный тест scaletestapp")
    add_load_arguments(parser, config)
    args = parser.parse_args(argv)

    print("ответ сервиса: " + check_host(args.host), flush=True)
    return run_load(args)


if __name__ == "__main__":
    sys.exit(main())
