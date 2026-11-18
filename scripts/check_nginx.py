"""Проверка Task6/nginx.conf (6.4, 6.5): синтаксис и работа лимита на локальном стенде.

Сдаваемый файл не меняется. Скрипт собирает временную копию конфига:
1. Хосты upstream заменяются на локальную заглушку, которая отвечает 200.
2. Порт 80 заменяется на свободный локальный порт.
3. Добавляются блок events, пути pid, журналов и временных файлов во временном каталоге.

Затем выполняются nginx -t, запуск nginx и два прогона:
1. Быстрая серия из nginx.check_fast_requests запросов подряд.
2. Серия в течение nginx.check_series_seconds с интервалом nginx.check_series_interval_seconds.

Вывод nginx -t пишется в logs/nginx-t.log, результаты прогонов в logs/nginx-limit.log.
Путь временного каталога в логах заменяется словом tmp.
"""

import argparse
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from _common import ROOT, load_config

CONF_PATH = ROOT / "Task6" / "nginx.conf"
LOG_DIR = ROOT / "logs"
NGINX_CANDIDATES = ("/usr/sbin/nginx", "/usr/local/bin/nginx", "/opt/homebrew/bin/nginx", "/usr/local/sbin/nginx")
TEMP_DIRS = ("client_body", "proxy", "fastcgi", "uwsgi", "scgi")

# Запросы идут напрямую, без системного прокси.
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def rate_interval_seconds(rate):
    """Интервал между принимаемыми запросами для значения вида 10r/m или 5r/s."""
    match = re.fullmatch(r"(\d+)r/([ms])", rate)
    if not match:
        raise ValueError(f"неизвестный формат rate: {rate}")
    count, unit = int(match.group(1)), match.group(2)
    return (60 if unit == "m" else 1) / count


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def build_check_config(text, nginx_cfg, prefix, listen_port, stub_port):
    """Возвращает текст временной копии конфига для проверки на локальном стенде."""
    prefix = Path(prefix).as_posix()
    result = text
    for host in nginx_cfg["servers"]:
        pattern = rf"server\s+{re.escape(host)}\s*;"
        result, count = re.subn(pattern, f"server 127.0.0.1:{stub_port};", result)
        if count != 1:
            raise ValueError(f"в конфиге не найдена строка server {host};")

    result, count = re.subn(rf"listen\s+{nginx_cfg['listen']}\s*;", f"listen 127.0.0.1:{listen_port};", result)
    if count != 1:
        raise ValueError(f"в конфиге не найдена строка listen {nginx_cfg['listen']};")

    temp_paths = "".join(f"    {name}_temp_path {prefix}/{name};\n" for name in TEMP_DIRS)
    http_head = (
        "http {\n"
        f"    access_log {prefix}/access.log;\n"
        f"{temp_paths}"
        "    server {\n"
        f"        listen 127.0.0.1:{stub_port};\n"
        '        location / { return 200 "ok\\n"; }\n'
        "    }\n"
    )
    result, count = re.subn(r"^http\s*\{\n", lambda _: http_head, result, flags=re.MULTILINE)
    if count != 1:
        raise ValueError("в конфиге не найден блок http")

    main_head = f"pid {prefix}/nginx.pid;\nerror_log {prefix}/error.log;\nevents {{}}\n\n"
    return main_head + result


def find_nginx(explicit):
    if explicit:
        return explicit
    found = shutil.which("nginx")
    if found:
        return found
    for candidate in NGINX_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


def request_status(url):
    try:
        with OPENER.open(url, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def wait_ready(url, process, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            OPENER.open(url, timeout=1).close()
            return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.2)
    return False


def now():
    moment = time.time()
    return time.strftime("%H:%M:%S", time.localtime(moment)) + f".{int(moment % 1 * 1000):03d}"


class Log:
    def __init__(self, path):
        self.path = path
        self.lines = []

    def add(self, text):
        print(text)
        self.lines.append(text)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(self.lines) + "\n", encoding="utf-8", newline="\n")


def run_series(url, count, interval, log):
    """Отправляет count запросов с интервалом interval секунд. Возвращает список кодов."""
    codes = []
    start = time.monotonic()
    for number in range(1, count + 1):
        target = start + (number - 1) * interval
        delay = target - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        code = request_status(url)
        codes.append(code)
        log.add(f"{now()} запрос {number:>3} код {code}")
    return codes


def summary(codes):
    counts = {}
    for code in codes:
        counts[code] = counts.get(code, 0) + 1
    return ", ".join(f"{code}: {counts[code]}" for code in sorted(counts))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Проверка Task6/nginx.conf на временной копии")
    parser.add_argument("--nginx", help="путь к nginx, если его нет в PATH")
    parser.add_argument("--fast-only", action="store_true", help="только быстрая серия, без серии на минуту")
    args = parser.parse_args(argv)

    nginx_cfg = load_config()["nginx"]
    nginx = find_nginx(args.nginx)
    if not nginx:
        print("nginx не найден. Установка: brew install nginx или sudo apt install nginx", file=sys.stderr)
        return 2

    interval = rate_interval_seconds(nginx_cfg["rate"])
    prefix = Path(tempfile.mkdtemp(prefix="nginx-check-")).resolve()
    listen_port, stub_port = free_port(), free_port()
    conf = prefix / "nginx.conf"
    conf.write_text(
        build_check_config(CONF_PATH.read_text(encoding="utf-8"), nginx_cfg, prefix, listen_port, stub_port),
        encoding="utf-8",
    )
    base = [nginx, "-p", str(prefix), "-e", str(prefix / "error.log"), "-c", str(conf)]

    def hide_prefix(text):
        return text.replace(str(prefix), "tmp")

    t_log = Log(LOG_DIR / "nginx-t.log")
    version = subprocess.run([nginx, "-v"], capture_output=True, text=True)
    t_log.add(f"{now()} {hide_prefix((version.stderr or version.stdout).strip())}")
    t_log.add(f"{now()} nginx -t для временной копии Task6/nginx.conf")
    tested = subprocess.run(base + ["-t"], capture_output=True, text=True)
    for line in hide_prefix(tested.stderr + tested.stdout).strip().splitlines():
        t_log.add(line)
    t_log.add(f"{now()} код возврата {tested.returncode}")
    t_log.save()
    if tested.returncode != 0:
        shutil.rmtree(prefix, ignore_errors=True)
        return 1

    url = f"http://127.0.0.1:{listen_port}{nginx_cfg['location']}"
    process = subprocess.Popen(base + ["-g", "daemon off;"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    log = Log(LOG_DIR / "nginx-limit.log")
    ok = True
    try:
        if not wait_ready(f"http://127.0.0.1:{stub_port}/", process):
            err = process.stderr.read().decode() if process.poll() is not None else ""
            print(f"nginx не запустился {hide_prefix(err)}", file=sys.stderr)
            return 1

        log.add(f"{now()} лимит rate={nginx_cfg['rate']}, интервал {interval:g} с, код отказа {nginx_cfg['status']}")
        fast = nginx_cfg["check_fast_requests"]
        log.add(f"{now()} серия 1: {fast} запросов подряд")
        codes = run_series(url, fast, 0, log)
        log.add(f"{now()} итог серии 1: {summary(codes)}")
        expected = [200] + [nginx_cfg["status"]] * (fast - 1)
        fast_ok = codes == expected
        log.add(f"{now()} ожидалось: первый 200, остальные {nginx_cfg['status']}; совпало: {'да' if fast_ok else 'нет'}")
        ok = fast_ok

        if not args.fast_only:
            pause = interval + 1
            log.add(f"{now()} пауза {pause:g} с")
            time.sleep(pause)
            seconds = nginx_cfg["check_series_seconds"]
            step = nginx_cfg["check_series_interval_seconds"]
            count = int(seconds / step)
            limit = int(round(seconds / interval))
            log.add(f"{now()} серия 2: {count} запросов за {seconds} с, интервал {step} с")
            codes = run_series(url, count, step, log)
            accepted = codes.count(200)
            log.add(f"{now()} итог серии 2: {summary(codes)}")
            series_ok = accepted <= limit and set(codes) <= {200, nginx_cfg["status"]}
            log.add(f"{now()} ожидалось: не более {limit} ответов 200 за {seconds} с; совпало: {'да' if series_ok else 'нет'}")
            ok = ok and series_ok
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        log.save()
        shutil.rmtree(prefix, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
