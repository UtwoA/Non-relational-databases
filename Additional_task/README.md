# Дополнительное задание: брокер сообщений на Redis

Проект максимально широко интерпретирует задание про сглаживание пиков нагрузки. Вместо одной очереди реализовано несколько подходов на Redis и показано, чем они отличаются при имитации медленного LLM-обработчика.

## Идея

Генератор нагрузки быстро создает задания, а обработчик имитирует LLM и работает медленно. При пике без брокера запросы отклоняются. С брокером задания накапливаются в Redis, consumer не падает и постепенно разгребает накопление.

## Реализованные режимы

| Режим | Интерпретация | Что демонстрирует |
| --- | --- | --- |
| Без очереди | Нагрузка идет напрямую в обработчик | При пике часть запросов отклоняется |
| Redis Pub/Sub | Redis как канал событий без хранения | Если подписчика нет, сообщения теряются; backlog не появляется |
| Redis Lists | Redis как простая FIFO-очередь | `LLEN` растет на пике и падает после обработки |
| Redis Streams | Redis как брокер с consumer group | Видны `XLEN`, `XPENDING`, `XACK`, consumer group `llm-workers` |
| Redis Sorted Set | Redis как отложенная очередь | `ZSET` хранит задания по времени готовности, backlog постепенно снижается |

Так покрываются разные практические паттерны: прямой вызов, fire-and-forget события, простая очередь, надежный stream-брокер и delayed queue.

## Что показывает демонстрация

- брокер отделяет прием пикового потока от медленной обработки;
- consumer продолжает стабильно работать и не падает при перегрузке;
- Redis Lists, Streams и ZSET показывают накопление, которое затем спадает;
- Pub/Sub специально показывает антипример: без подписчика Redis не хранит сообщения;
- Streams показывает более “брокерную” модель: consumer group, pending-сообщения и подтверждение обработки.

## Состав проекта

```text
Additional_task/
  docker-compose.yml
  main.py
  requirements.txt
  README.md
  src/redis_broker_demo/
    app.py
    broker.py
    direct.py
    metrics.py
    models.py
    scenarios.py
  templates/
    index.html
  tests/
    test_broker_demo.py
```

## Установка

```bash
cd Additional_task
python -m pip install -r requirements.txt
docker compose up -d
```

Redis будет доступен на `127.0.0.1:6379`.

## Web UI

```bash
python main.py web
```

Открыть:

```text
http://127.0.0.1:5000/
```

В интерфейсе есть запуск всех пяти режимов, карточки метрик, история измерений и визуализация накопления/спада.

## CLI-сценарии

Сбросить данные задания:

```bash
python main.py reset
```

Запустить прямой режим без очереди:

```bash
python main.py scenario --mode direct --jobs 100 --burst 50
```

Показать Pub/Sub как канал без накопления:

```bash
python main.py scenario --mode pubsub --jobs 100 --burst 50
```

Показать простую очередь Redis List:

```bash
python main.py scenario --mode list --jobs 100 --burst 50
```

Показать Redis Stream с consumer group:

```bash
python main.py scenario --mode stream --jobs 100 --burst 50
```

Показать отложенную очередь через Sorted Set:

```bash
python main.py scenario --mode zset --jobs 100 --burst 50
```

Отдельный producer:

```bash
python main.py producer --mode pubsub --jobs 100 --burst 50
python main.py producer --mode list --jobs 100 --burst 50
python main.py producer --mode stream --jobs 100 --burst 50
python main.py producer --mode zset --jobs 100 --burst 50
```

Отдельный consumer:

```bash
python main.py consumer --mode pubsub
python main.py consumer --mode list
python main.py consumer --mode stream
python main.py consumer --mode zset
```

## Проверка Redis вручную

```bash
docker compose exec -T redis redis-cli LLEN additional:list:jobs
docker compose exec -T redis redis-cli XLEN additional:stream:jobs
docker compose exec -T redis redis-cli XPENDING additional:stream:jobs llm-workers
docker compose exec -T redis redis-cli ZCARD additional:zset:jobs
docker compose exec -T redis redis-cli HGETALL additional:metrics:direct
docker compose exec -T redis redis-cli HGETALL additional:metrics:pubsub
docker compose exec -T redis redis-cli HGETALL additional:metrics:list
docker compose exec -T redis redis-cli HGETALL additional:metrics:stream
docker compose exec -T redis redis-cli HGETALL additional:metrics:zset
```

## Архитектура

```text
Load generator
   |
   | direct
   v
LLM simulator
   |
   v
accepted / rejected

Load generator
   |
   | pubsub / list / stream / zset
   v
Redis
   |
   v
Consumer workers
   |
   v
LLM simulator
```

## Ключи Redis

| Назначение | Ключ |
| --- | --- |
| Pub/Sub канал | `additional:pubsub:jobs` |
| Очередь List | `additional:list:jobs` |
| Очередь Stream | `additional:stream:jobs` |
| Consumer group Stream | `llm-workers` |
| Отложенная очередь ZSET | `additional:zset:jobs` |
| Метрики | `additional:metrics:*` |
| История измерений | `additional:measurements` |

## Kafka и Redis

В исходной формулировке было “накопление в Кафке или где-то”, затем уточнение “в Redis”. Поэтому Kafka не поднимается как отдельный сервис, но Redis Streams используется как близкий по смыслу брокерный паттерн: есть append-only stream, consumer group, pending-сообщения и подтверждение обработки через `XACK`.

## Тестирование

```bash
python -m unittest discover -s tests -v
```

Тесты проверяют:

- сериализацию задания;
- перегрузку direct-режима;
- накопление и спад Redis List;
- обработку Redis Stream через `XACK`;
- потерю Pub/Sub-сообщения без подписчика;
- накопление и спад ZSET-очереди;
- очистку ключей `additional:*`.

## Вывод

Redis можно использовать как брокер сообщений несколькими способами. Для сглаживания пиков лучше подходят Lists, Streams и ZSET, потому что они хранят накопление и позволяют consumer-ам постепенно разгребать нагрузку. Pub/Sub полезен для событий в реальном времени, но не подходит для надежной очереди: если consumer отсутствует, сообщения теряются. Redis Streams наиболее близок к Kafka-подходу внутри Redis, так как поддерживает consumer groups, pending и ack.
