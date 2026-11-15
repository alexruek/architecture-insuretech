# Task2. Динамическое масштабирование

Тестовое приложение scaletestapp масштабируется двумя HPA: в части 1 по утилизации памяти, в части 2 по числу запросов в секунду на один под. Параметры заданы в [config/defaults.toml](../config/defaults.toml), разделы app, memory_hpa, rps_hpa, monitoring, locust, capture.

## Состав

| Файл | Назначение |
| --- | --- |
| [deployment.yaml](deployment.yaml) | Deployment приложения, одна реплика, requests и limits памяти |
| [service.yaml](service.yaml) | Service типа NodePort для доступа через minikube service |
| [hpa-memory.yaml](hpa-memory.yaml) | HPA по памяти, часть 1 |
| [hpa-rps.yaml](hpa-rps.yaml) | HPA по RPS на под, часть 2 |
| [locustfile.py](locustfile.py) | сценарий нагрузки из задания |
| [monitoring/prometheus-values.yaml](monitoring/prometheus-values.yaml) | значения чарта kube-prometheus-stack |
| [monitoring/servicemonitor.yaml](monitoring/servicemonitor.yaml) | сбор /metrics приложения в Prometheus |
| [monitoring/prometheus-adapter-values.yaml](monitoring/prometheus-adapter-values.yaml) | правило расчета RPS на под для custom.metrics.k8s.io |
| logs | логи прогонов, пишет scripts/capture_scaling.py |
| screenshots | скриншоты дашборда и Prometheus |

Оба HPA называются scaletestapp. Применение hpa-rps.yaml заменяет hpa-memory.yaml, поэтому логи и скриншоты части 1 снимаются до перехода к части 2.

## Подготовка

```bash
minikube start --cpus=4 --memory=6144
minikube addons enable metrics-server
pip install -r requirements-dev.txt
```

## Часть 1. Масштабирование по памяти

Образ приложения опубликован только для linux/amd64. На компьютере с процессором arm64 (команда minikube ssh -- uname -m выводит aarch64) образ собирается из исходников внутри Minikube, имя и тег совпадают с манифестом:

```bash
git clone https://github.com/yandex-practicum/scaletestapp.git /tmp/scaletestapp
minikube image build -t ghcr.io/yandex-practicum/scaletestapp:latest /tmp/scaletestapp
minikube image ls | grep scaletestapp
```

```bash
kubectl apply -f Task2/deployment.yaml -f Task2/service.yaml
kubectl rollout status deployment/scaletestapp
```

Адрес сервиса выдает minikube service. На Linux команда сразу завершается:

```bash
URL=$(minikube service scaletestapp --url)
```

С драйвером docker на macOS и Windows команда держит туннель. Она запускается в отдельном терминале, который не закрывается до конца прогона, а выведенный адрес присваивается переменной URL во втором терминале.

Для нагрузки не используется kubectl port-forward: он направляет весь трафик в один под, и новые реплики не получают запросов.

```bash
curl "$URL/"
curl -s "$URL/metrics" | grep http_requests_total
kubectl apply -f Task2/hpa-memory.yaml
kubectl get hpa scaletestapp
kubectl top pods -l app=scaletestapp
```

Значение памяти в колонке TARGETS появляется после первого сбора metrics-server, обычно через одну-две минуты. До этого там стоит unknown.

Прогон с записью логов:

```bash
python scripts/capture_scaling.py --part 1 --host "$URL"
```

Скрипт пишет состояние до нагрузки, запускает locust с параметрами раздела locust, после остановки нагрузки продолжает запись на время capture.after_load, чтобы в лог попало снижение реплик (окно стабилизации HPA при снижении 300 секунд). Число пользователей можно задать ключом --users.

Пока идет прогон, в отдельном терминале открывается дашборд:

```bash
minikube dashboard
```

Скриншоты части 1 (раздел Workloads - Deployments и Horizontal Pod Autoscalers):

| Файл | Что на снимке |
| --- | --- |
| screenshots/part1/01-dashboard-before.png | одна реплика до нагрузки |
| screenshots/part1/02-dashboard-during.png | рост числа реплик под нагрузкой |
| screenshots/part1/03-dashboard-after.png | состояние после нагрузки |
| screenshots/part1/04-kubectl-get-hpa.png | вывод kubectl get hpa scaletestapp под нагрузкой |

## Часть 2. Масштабирование по RPS

Перед началом число реплик должно вернуться к одной:

```bash
kubectl get hpa scaletestapp
```

Установка Prometheus:

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack -n monitoring --create-namespace --version "$(python scripts/_common.py monitoring.prometheus_chart_version)" -f Task2/monitoring/prometheus-values.yaml
kubectl get pods -n monitoring
kubectl apply -f Task2/monitoring/servicemonitor.yaml
```

Проверка сбора метрик идет по цепочке, следующий шаг имеет смысл только после успешного предыдущего.

1. Prometheus Web UI:

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090
```

В браузере http://localhost:9090, раздел Status - Targets: цель serviceMonitor/default/scaletestapp/0 в состоянии UP. Раздел Graph: запрос http_requests_total возвращает ряд с метками namespace и pod.

2. Адаптер метрик:

```bash
helm upgrade --install prometheus-adapter prometheus-community/prometheus-adapter -n monitoring --version "$(python scripts/_common.py monitoring.adapter_chart_version)" -f Task2/monitoring/prometheus-adapter-values.yaml
kubectl get apiservice v1beta1.custom.metrics.k8s.io
kubectl get --raw "/apis/custom.metrics.k8s.io/v1beta1/namespaces/default/pods/*/http_requests_per_second"
```

APIService должен быть в состоянии AVAILABLE True, ответ последней команды содержит значение метрики для каждого пода. Значение записывается в тысячных долях: 2500m означает 2,5 запроса в секунду.

3. HPA по RPS и прогон:

```bash
kubectl apply -f Task2/hpa-rps.yaml
kubectl get hpa scaletestapp
python scripts/capture_scaling.py --part 2 --host "$URL"
```

Скрипт проверяет, что в кластере применен HPA нужной части, и отказывается писать логи, если это не так.

Скриншоты части 2:

| Файл | Что на снимке |
| --- | --- |
| screenshots/part2/01-prometheus-targets.png | Status - Targets, цель приложения UP |
| screenshots/part2/02-prometheus-graph.png | Query, ряд http_requests_total с метками namespace и pod |
| screenshots/part2/03-scaling-before.png | дашборд до нагрузки |
| screenshots/part2/04-scaling-during.png | рост числа реплик под нагрузкой |
| screenshots/part2/05-scaling-after.png | снижение реплик после нагрузки |
| screenshots/part2/06-prometheus-rps.png | Graph, rate(http_requests_total[1m]) по поду |

## Логи

| Файл | Содержимое |
| --- | --- |
| logs/part1-hpa.log, logs/part2-hpa.log | kubectl get hpa -w |
| logs/part1-pods.log, logs/part2-pods.log | kubectl get pods -w |
| logs/part1-top.log | kubectl top pods во время прогона |
| logs/part1-describe-pod.log | kubectl describe pods после прогона, причины перезапусков |
| logs/part2-custom-metrics.log | ответы custom.metrics.k8s.io |

Каждая строка логов начинается со времени, моменты запуска и остановки нагрузки отмечены строками с тремя дефисами.
