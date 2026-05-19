# Нереляционные базы данных

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-cache%20%7C%20queues-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-document%20DB-47A248?style=for-the-badge&logo=mongodb&logoColor=white)
![Apache Cassandra](https://img.shields.io/badge/Apache%20Cassandra-query--first-1287B1?style=for-the-badge&logo=apachecassandra&logoColor=white)
![Apache Kafka](https://img.shields.io/badge/Apache%20Kafka-broker-231F20?style=for-the-badge&logo=apachekafka&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)

![Practices](https://img.shields.io/badge/Практики-5%20%2B%20доп.%20задание-7C3AED?style=flat-square)
![XML](https://img.shields.io/badge/XML%20%2F%20XSD-validation-F59E0B?style=flat-square)
![Flask](https://img.shields.io/badge/Flask-web%20API-000000?style=flat-square&logo=flask&logoColor=white)
![Tests](https://img.shields.io/badge/tests-unittest-16A34A?style=flat-square)
![Status](https://img.shields.io/badge/status-учебный%20проект-2563EB?style=flat-square)

Репозиторий содержит комплект практических работ по дисциплине «Нереляционные базы данных»: от подготовки XML/DSV-данных и XSD-схем до прикладных решений на Redis, MongoDB, Apache Cassandra, Kafka и Redis Streams. Каждая работа оформлена как самостоятельный мини-проект с исходным кодом, материалами задания, демонстрационными данными и инструкциями по запуску.

## Содержание

| Работа | Тема | Что реализовано | Ссылки |
| --- | --- | --- | --- |
| Практика 1 | DSV и XML | Генерация набора пользователей, публикаций и отзывов в TSV/DSV; чтение DSV; фильтрация подтвержденных пользователей; выгрузка результата в XML. | [папка](Practice1/), [задание](Practice1/Практическая%20работа%201.pdf) |
| Практика 2 | XSD-схема и XML-валидация | XSD-схема датасета чат-бота с пользователями, диалогами, сообщениями, вложениями, реакциями и ссылочной целостностью; валидные и невалидные XML-примеры; скрипт проверки. | [папка](Practice2/), [задание](Practice2/Практическая%20работа%202.pdf) |
| Практика 3 | Redis как key-value хранилище | Кеширование результатов функций через Redis, TTL, декоратор кеширования, хранение пользователей в Redis и небольшой Flask-интерфейс. | [README](Practice3/README.md), [задание](Practice3/Практическая%20работа%203.pdf) |
| Практика 4 | MongoDB | Документо-ориентированная модель пользователей, ролей и прав доступа; вложенные документы; CRUD API; потоковое чтение; Swagger UI. | [README](Practice4/README.md), [задание](Practice4/Практическая%20работа%204.pdf) |
| Практика 5 | Apache Cassandra | Query-first проектирование Cassandra для статистики вакансий: денормализованные таблицы под пользовательские запросы, REST API, UI, CRUD, CQL-схема и MCP-сервер. | [README](Practice5/README.md), [задание](Practice5/Практическая%20работа%205.pdf) |
| Дополнительное задание | Redis и Kafka как брокеры сообщений | Демонстрация сглаживания пиков нагрузки через Redis Lists, Streams, ZSET, Pub/Sub и Apache Kafka; сравнение режимов, delayed consumer, метрики и web UI. | [README](Additional_task/README.md) |

## Общая идея

Работы последовательно показывают разные стороны нереляционного подхода:

- подготовка и формальная проверка структурированных XML-данных;
- использование Redis как быстрого key-value хранилища и кеша;
- моделирование документов и вложенных структур в MongoDB;
- проектирование Cassandra «от запросов» с денормализацией данных;
- применение очередей и брокеров сообщений для обработки пиков нагрузки.

Репозиторий можно использовать как учебную подборку небольших, независимых примеров. Практики 3-5 и дополнительное задание содержат собственные инструкции по запуску и тестированию в локальных README.

## Структура репозитория

```text
Non-relational-databases/
  Practice1/          # генерация DSV и преобразование в XML
  Practice2/          # XSD-схема и XML-валидация
  Practice3/          # Redis cache + web-интерфейс
  Practice4/          # MongoDB CRUD API + streaming
  Practice5/          # Apache Cassandra, query-first модель вакансий
  Additional_task/    # Redis/Kafka брокеры и сглаживание пиков
  reports/            # отчеты по отдельным практикам
```

## Технологии

- Python 3
- XML, XSD, DSV/TSV
- Redis
- MongoDB
- Apache Cassandra и CQL
- Apache Kafka
- Flask
- Docker Compose
- unittest

## Быстрый старт

Каждая работа запускается из своей директории. Общий шаблон:

```bash
cd Practice3
python -m pip install -r requirements.txt
docker compose up -d
python main.py web
```

Для работ без контейнеров достаточно перейти в папку практики и запустить соответствующий скрипт:

```bash
cd Practice1
python run_all.py
```

```bash
cd Practice2
python -m pip install -r requirements.txt
python scripts/validate_xml.py
```

Подробные команды для Redis, MongoDB, Cassandra, Kafka, тестов и API-запросов находятся в README конкретных работ.

## Отчеты

В каталоге [reports](reports/) лежат готовые отчеты:

- [report3.docx](reports/report3.docx)
- [report3.pdf](reports/report3.pdf)
- [report4.docx](reports/report4.docx)
- [report4.pdf](reports/report4.pdf)

## Что смотреть в первую очередь

Если нужна быстрая навигация по проекту:

1. [Practice3/README.md](Practice3/README.md) — Redis как кеш и key-value хранилище.
2. [Practice4/README.md](Practice4/README.md) — MongoDB и документо-ориентированная модель.
3. [Practice5/README.md](Practice5/README.md) — полноценный пример проектирования Cassandra.
4. [Additional_task/README.md](Additional_task/README.md) — сравнение Redis и Kafka для брокерских сценариев.
