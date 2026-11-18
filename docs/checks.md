# Пошаговая проверка решений

Команды выполняются из корня репозитория. Нужен Python 3.11 и новее, зависимости ставятся командой pip install -r requirements-dev.txt.

## Репозиторий

```bash
python scripts/check_structure.py --final
python scripts/check_style.py
python -m pytest
```

Ожидается: check_structure.py сообщает, что структура в порядке для Task1-Task6; check_style.py ничего не выводит и завершается с кодом 0; pytest завершается без ошибок. Тест запуска nginx пропускается, если nginx не установлен.

Логи и скриншоты не исключены из репозитория:

```bash
git check-ignore -v Task2/logs/part1-hpa.log Task2/screenshots/part1/01-dashboard-before.png
```

Ожидается пустой вывод и код возврата 1.

## Task1. Технологическая архитектура

1. Открыть [схему](<../Task1/InureTech_технологическая архитектура_to-be.drawio>) в draw.io или [PNG-экспорт](diagrams/task1-to-be.png).
2. На схеме найти: три зоны доступности и независимый кластер Kubernetes в каждой, CDN и Application Load Balancer на входе, подписанные стрелки health check, комментарий о фейловере, кластер PostgreSQL под управлением Patroni с синхронной и асинхронной репликами, архивацию WAL и ежедневный бэкап, решение по шардированию, комментарий с привязкой решений к RTO, RPO и доступности.

Автоматическая проверка подписей:

```bash
python -m pytest tests/test_diagrams.py -k task1
```

## Task2. Динамическое масштабирование

Порядок воспроизведения обеих частей с командами и ожидаемым выводом описан в [Task2/README.md](../Task2/README.md). Проверка манифестов без кластера:

```bash
python -m pytest tests/test_manifests.py
```

Результаты реальных прогонов:

| Что подтверждает | Файл |
| --- | --- |
| Рост числа реплик по памяти | [part1-hpa.log](../Task2/logs/part1-hpa.log), [part1-pods.log](../Task2/logs/part1-pods.log), скриншоты [part1](../Task2/screenshots/part1/02-dashboard-during.png) |
| Метрика приложения в Prometheus | [01-prometheus-targets.png](../Task2/screenshots/part2/01-prometheus-targets.png), [02-prometheus-graph.png](../Task2/screenshots/part2/02-prometheus-graph.png) |
| Метрика RPS на под доступна HPA | [part2-custom-metrics.log](../Task2/logs/part2-custom-metrics.log) |
| Рост и снижение числа реплик по RPS | [part2-hpa.log](../Task2/logs/part2-hpa.log), [part2-pods.log](../Task2/logs/part2-pods.log), скриншоты [part2](../Task2/screenshots/part2/04-scaling-during.png) |

## Task3. Event-Driven архитектура

1. Прочитать [problems.md](../Task3/problems.md): у каждой проблемы указан элемент схемы, который ее закрывает.
2. Открыть [схему](../Task3/InsureTech_C4_container-diagram.drawio) в draw.io: брокер Apache Kafka, стрелки событий подписаны темами, outbox в core-app, новых сервисов нет.

```bash
python -m pytest tests/test_diagrams.py -k task3 tests/test_docs.py
```

## Task4. Продажа ОСАГО

Открыть [схему](../Task4/InsureTech_C4_container-diagram-osago.drawio) в draw.io: сервис osago-aggregator и его хранилище, темы заявок и решений, отдельная стрелка SSE от core-app в веб-приложение, значки Timeout, Retry, Circuit Breaker и Rate Limiting у вызовов страховых компаний, комментарии о нескольких экземплярах и оценке нагрузки.

```bash
python -m pytest tests/test_diagrams.py -k "task4 or legend"
```

## Task5. GraphQL API

```bash
python -c "from graphql import build_schema; build_schema(open('Task5/schema.graphql', encoding='utf-8').read()); print('ok')"
python -m pytest tests/test_graphql_schema.py
```

Ожидается ok. Все три операции REST выражаются одним запросом:

```graphql
query {
  client(id: "1") {
    id
    name
    age
    documents { id type number issueDate expiryDate }
    relatives { id relationType name age }
  }
}
```

## Task6. Rate Limiting

```bash
grep -nE "limit_req_zone|limit_req |limit_req_status" Task6/nginx.conf
python -m pytest tests/test_nginx_conf.py
python scripts/check_nginx.py
```

check_nginx.py нужен установленный nginx. Скрипт проверяет временную копию конфига, сдаваемый файл не меняется. Результаты пишутся в [logs/nginx-t.log](../logs/nginx-t.log) и [logs/nginx-limit.log](../logs/nginx-limit.log): nginx -t завершается успешно, в быстрой серии проходит первый запрос, остальные получают 429, за минуту проходит не более лимита запросов.
