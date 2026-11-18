# architecture-insuretech

Проектная работа 8 спринта курса "Архитектор ПО" (Яндекс Практикум). Компания InsureTech, агрегатор страховых услуг.

## Решения по заданиям

| Задание | Что сделано | Файлы |
| --- | --- | --- |
| Task1. Технологическая архитектура | Схема to-be в нотации Yandex Cloud: три зоны доступности, независимые кластеры Kubernetes, CDN и L7-балансировщик, health check, фейловер, PostgreSQL под управлением Patroni, резервное копирование, решение по шардированию | [схема draw.io](<Task1/InureTech_технологическая архитектура_to-be.drawio>), [PNG](docs/diagrams/task1-to-be.png) |
| Task2. Динамическое масштабирование | Deployment, Service, HPA по памяти и HPA по RPS на под через Prometheus и prometheus-adapter, нагрузка Locust, логи и скриншоты реальных прогонов | [Task2/README.md](Task2/README.md) |
| Task3. Event-Driven архитектура | Проблемы и риски текущей архитектуры, диаграмма контейнеров C4 с Apache Kafka и Transactional Outbox | [problems.md](Task3/problems.md), [схема draw.io](Task3/InsureTech_C4_container-diagram.drawio) |
| Task4. Продажа ОСАГО | Диаграмма контейнеров C4 с osago-aggregator, хранилищем Redis, асинхронным API через брокер, потоком SSE и паттернами отказоустойчивости | [схема draw.io](Task4/InsureTech_C4_container-diagram-osago.drawio) |
| Task5. GraphQL API | Схема GraphQL сервиса client-info, эквивалентная Swagger-контракту | [schema.graphql](Task5/schema.graphql) |
| Task6. Rate Limiting | Конфигурация nginx с ограничением запросов и ответом 429 | [nginx.conf](Task6/nginx.conf) |

Решения по неоднозначным местам задания, противоречия и опечатки собраны в [docs/decisions.md](docs/decisions.md).

## Структура репозитория

| Путь | Назначение |
| --- | --- |
| Task1 ... Task6 | решения заданий |
| [config/defaults.toml](config/defaults.toml) | параметры по умолчанию. Манифесты и nginx.conf содержат значения буквально, тесты сверяют их с конфигом |
| [docs/decisions.md](docs/decisions.md) | принятые решения и противоречия задания |
| [docs/checks.md](docs/checks.md) | пошаговая проверка решений: команды и ожидаемый результат |
| docs/diagrams | PNG-экспорт схем для просмотра без draw.io |
| logs | вывод проверочных запусков: статус Minikube, версии инструментов, проверка nginx |
| scripts | скрипты нагрузки, записи логов и проверок |
| tests | автотесты манифестов, схем, конфигурации nginx, схемы GraphQL и документов |

## Быстрая проверка

Нужен Python 3.11 и новее.

```bash
pip install -r requirements-dev.txt
python -m pytest
python scripts/check_style.py
python scripts/check_structure.py --final
```

Проверка Kubernetes, Prometheus и nginx на локальном стенде описана в [docs/checks.md](docs/checks.md).
