from __future__ import annotations

import threading
import time
from typing import Any

from .broker import PUBSUB_CHANNEL, RedisBroker
from .direct import run_direct_load
from .kafka_broker import KafkaBroker
from .metrics import MetricsStore
from .models import Job


BROKER_MODES = ("list", "stream", "zset", "kafka")
ALL_MODES = ("direct", "pubsub", "list", "stream", "zset", "kafka")


def estimate_drain_wait_seconds(
    jobs: int,
    workers: int,
    processing_ms: int,
    *,
    minimum: float = 60.0,
    multiplier: float = 1.6,
    extra_seconds: float = 10.0,
) -> float:
    effective_workers = max(1, workers)
    processing_seconds = max(0.001, processing_ms / 1000)
    expected_seconds = jobs * processing_seconds / effective_workers
    return max(minimum, expected_seconds * multiplier + extra_seconds)


def run_direct_scenario(
    redis_client: Any | None = None,
    jobs: int = 100,
    burst: int = 50,
    workers: int = 2,
    processing_ms: int = 300,
    acquire_timeout_ms: int = 10,
) -> dict:
    metrics = MetricsStore(redis_client or InMemoryRedis())
    return run_direct_load(
        metrics=metrics,
        jobs=jobs,
        burst=burst,
        workers=workers,
        processing_ms=processing_ms,
        acquire_timeout_ms=acquire_timeout_ms,
    )


def produce_jobs(redis_client: Any, mode: str, jobs: int, burst: int = 50) -> dict:
    metrics = MetricsStore(redis_client)
    broker = RedisBroker(redis_client, metrics)

    if mode == "pubsub":
        backlog = lambda: 0
        enqueue = broker.publish_pubsub
    elif mode == "list":
        backlog = broker.list_backlog
        enqueue = broker.enqueue_list
    elif mode == "stream":
        broker.ensure_stream_group()
        backlog = broker.stream_backlog
        enqueue = broker.enqueue_stream
    elif mode == "zset":
        backlog = broker.zset_backlog
        enqueue = broker.enqueue_zset
    elif mode == "kafka":
        kafka = KafkaBroker(metrics)
        backlog = kafka.backlog
        enqueue = kafka.enqueue
    else:
        raise ValueError("mode must be pubsub, list, stream, zset or kafka")

    for index in range(jobs):
        enqueue(Job.create(mode, payload=f"LLM request #{index + 1}"))
        if burst > 0 and (index + 1) % burst == 0:
            metrics.snapshot(mode, backlog=backlog())
            time.sleep(0.02)

    return metrics.snapshot(mode, backlog=backlog())


def run_kafka_scenario(
    redis_client: Any,
    jobs: int = 100,
    burst: int = 50,
    workers: int = 2,
    processing_ms: int = 300,
    sample_interval: float = 0.25,
    max_wait_seconds: float | None = None,
) -> dict:
    metrics = MetricsStore(redis_client)
    kafka = KafkaBroker(metrics)
    metrics.reset_mode("kafka")
    kafka.reset_topic(num_partitions=max(1, workers))
    max_wait_seconds = max_wait_seconds or estimate_drain_wait_seconds(
        jobs,
        workers,
        processing_ms,
    )

    stop_event = threading.Event()

    def worker_loop(worker_index: int) -> None:
        consumer = kafka.create_consumer(f"scenario-kafka-{worker_index}")
        try:
            while not stop_event.is_set():
                if not kafka.consume_once(consumer, processing_ms=processing_ms):
                    time.sleep(0.01)
        finally:
            consumer.close()

    threads = [
        threading.Thread(target=worker_loop, args=(index,), daemon=True)
        for index in range(max(1, workers))
    ]
    for thread in threads:
        thread.start()

    samples = [metrics.snapshot("kafka", backlog=kafka.backlog())]
    for index in range(jobs):
        kafka.enqueue(Job.create("kafka", payload=f"LLM request #{index + 1}"))
        if burst > 0 and (index + 1) % burst == 0:
            samples.append(metrics.snapshot("kafka", backlog=kafka.backlog()))
            time.sleep(0.02)

    started = time.time()
    while time.time() - started < max_wait_seconds:
        sample = metrics.snapshot("kafka", backlog=kafka.backlog())
        samples.append(sample)
        completed = sample["processed"] + sample["errors"]
        if completed >= jobs and sample["backlog"] == 0:
            break
        time.sleep(sample_interval)

    stop_event.set()
    for thread in threads:
        thread.join(timeout=2.0)

    return {
        "summary": metrics.read_mode("kafka", backlog=kafka.backlog()),
        "samples": samples,
    }


def run_all_scenarios(
    redis_client: Any,
    jobs: int = 60,
    burst: int = 30,
    workers: int = 2,
    processing_ms: int = 150,
    acquire_timeout_ms: int = 10,
    max_wait_seconds: float | None = None,
) -> dict:
    MetricsStore(redis_client).reset_all()
    results = {}
    for mode in ALL_MODES:
        if mode == "direct":
            result = run_direct_scenario(
                redis_client,
                jobs=jobs,
                burst=burst,
                workers=workers,
                processing_ms=processing_ms,
                acquire_timeout_ms=acquire_timeout_ms,
            )
        elif mode == "pubsub":
            result = run_pubsub_scenario(
                redis_client,
                jobs=jobs,
                burst=burst,
                workers=workers,
                processing_ms=processing_ms,
                max_wait_seconds=max_wait_seconds,
            )
        elif mode == "kafka":
            result = run_kafka_scenario(
                redis_client,
                jobs=jobs,
                burst=burst,
                workers=workers,
                processing_ms=processing_ms,
                max_wait_seconds=max_wait_seconds,
            )
        else:
            result = run_queue_scenario(
                redis_client,
                mode=mode,
                jobs=jobs,
                burst=burst,
                workers=workers,
                processing_ms=processing_ms,
                max_wait_seconds=max_wait_seconds,
            )
        results[mode] = result["summary"]
    return {"summary": results, "modes": list(ALL_MODES)}


def run_delayed_consumer_scenario(
    redis_client: Any,
    mode: str = "stream",
    jobs: int = 60,
    burst: int = 30,
    workers: int = 2,
    processing_ms: int = 150,
    consumer_delay_seconds: float = 2.0,
    sample_interval: float = 0.25,
    max_wait_seconds: float | None = None,
) -> dict:
    if mode not in BROKER_MODES:
        raise ValueError("delayed scenario supports list, stream, zset or kafka")

    metrics = MetricsStore(redis_client)
    metrics.reset_mode(mode)
    samples = []

    if mode == "kafka":
        kafka = KafkaBroker(metrics)
        kafka.reset_topic(num_partitions=max(1, workers))
        kafka_wait = max_wait_seconds or estimate_drain_wait_seconds(
            jobs,
            workers,
            processing_ms,
        )
        for index in range(jobs):
            kafka.enqueue(Job.create("kafka", payload=f"Delayed LLM request #{index + 1}"))
            if burst > 0 and (index + 1) % burst == 0:
                samples.append(metrics.snapshot("kafka", backlog=kafka.backlog()))
        samples.append(metrics.snapshot("kafka", backlog=kafka.backlog()))
        time.sleep(consumer_delay_seconds)
        samples.append(metrics.snapshot("kafka", backlog=kafka.backlog()))
        return _drain_delayed_kafka(
            kafka,
            metrics,
            samples,
            jobs,
            workers,
            processing_ms,
            consumer_delay_seconds,
            sample_interval,
            kafka_wait,
        )

    broker = RedisBroker(redis_client, metrics)
    if mode == "list":
        broker.clear_list_queue()
        backlog = broker.list_backlog
        pending = lambda: 0
        enqueue = lambda index: broker.enqueue_list(
            Job.create("list", payload=f"Delayed LLM request #{index + 1}")
        )
        consume = lambda name: broker.consume_list_once(block_timeout=1, processing_ms=processing_ms)
    elif mode == "stream":
        broker.clear_stream_queue()
        broker.ensure_stream_group()
        backlog = broker.stream_backlog
        pending = broker.stream_pending
        enqueue = lambda index: broker.enqueue_stream(
            Job.create("stream", payload=f"Delayed LLM request #{index + 1}")
        )
        consume = lambda name: broker.consume_stream_once(
            consumer_name=name,
            count=1,
            block_ms=1000,
            processing_ms=processing_ms,
        )
    else:
        broker.clear_zset_queue()
        backlog = broker.zset_backlog
        pending = lambda: 0
        enqueue = lambda index: broker.enqueue_zset(
            Job.create("zset", payload=f"Delayed LLM request #{index + 1}"),
            delay_ms=(index % max(1, burst)) * 5,
        )
        consume = lambda name: broker.consume_zset_once(processing_ms=processing_ms)

    for index in range(jobs):
        enqueue(index)
        if burst > 0 and (index + 1) % burst == 0:
            samples.append(metrics.snapshot(mode, backlog=backlog(), pending=pending()))
    samples.append(metrics.snapshot(mode, backlog=backlog(), pending=pending()))
    time.sleep(consumer_delay_seconds)
    samples.append(metrics.snapshot(mode, backlog=backlog(), pending=pending()))
    max_wait_seconds = max_wait_seconds or estimate_drain_wait_seconds(
        jobs,
        workers,
        processing_ms,
    )

    stop_event = threading.Event()

    def worker_loop(worker_index: int) -> None:
        consumer_name = f"delayed-{mode}-{worker_index}"
        while not stop_event.is_set():
            if not consume(consumer_name):
                time.sleep(0.01)

    threads = [
        threading.Thread(target=worker_loop, args=(index,), daemon=True)
        for index in range(max(1, workers))
    ]
    for thread in threads:
        thread.start()

    started = time.time()
    while time.time() - started < max_wait_seconds:
        sample = metrics.snapshot(mode, backlog=backlog(), pending=pending())
        samples.append(sample)
        completed = sample["processed"] + sample["errors"]
        if completed >= jobs and sample["backlog"] == 0 and sample["pending"] == 0:
            break
        time.sleep(sample_interval)

    stop_event.set()
    for thread in threads:
        thread.join(timeout=1.5)

    return {
        "summary": metrics.read_mode(mode, backlog=backlog(), pending=pending()),
        "samples": samples,
        "consumer_delay_seconds": consumer_delay_seconds,
    }


def _drain_delayed_kafka(
    kafka: KafkaBroker,
    metrics: MetricsStore,
    samples: list[dict],
    jobs: int,
    workers: int,
    processing_ms: int,
    consumer_delay_seconds: float,
    sample_interval: float,
    max_wait_seconds: float,
) -> dict:
    stop_event = threading.Event()

    def worker_loop(worker_index: int) -> None:
        consumer = kafka.create_consumer(f"delayed-kafka-{worker_index}")
        try:
            while not stop_event.is_set():
                if not kafka.consume_once(consumer, processing_ms=processing_ms):
                    time.sleep(0.01)
        finally:
            consumer.close()

    threads = [
        threading.Thread(target=worker_loop, args=(index,), daemon=True)
        for index in range(max(1, workers))
    ]
    for thread in threads:
        thread.start()

    started = time.time()
    while time.time() - started < max_wait_seconds:
        sample = metrics.snapshot("kafka", backlog=kafka.backlog())
        samples.append(sample)
        completed = sample["processed"] + sample["errors"]
        if completed >= jobs and sample["backlog"] == 0:
            break
        time.sleep(sample_interval)

    stop_event.set()
    for thread in threads:
        thread.join(timeout=2.0)

    return {
        "summary": metrics.read_mode("kafka", backlog=kafka.backlog()),
        "samples": samples,
        "consumer_delay_seconds": consumer_delay_seconds,
    }


def run_pubsub_scenario(
    redis_client: Any,
    jobs: int = 100,
    burst: int = 50,
    workers: int = 2,
    processing_ms: int = 300,
    sample_interval: float = 0.25,
    max_wait_seconds: float | None = None,
) -> dict:
    metrics = MetricsStore(redis_client)
    broker = RedisBroker(redis_client, metrics)
    metrics.reset_mode("pubsub")
    max_wait_seconds = max_wait_seconds or estimate_drain_wait_seconds(
        jobs,
        1,
        processing_ms,
        minimum=30.0,
    )

    stop_event = threading.Event()
    samples = [metrics.snapshot("pubsub")]

    lost_before_subscribe = max(1, jobs // 3)
    for index in range(lost_before_subscribe):
        broker.publish_pubsub(
            Job.create("pubsub", payload=f"LLM request without subscriber #{index + 1}")
        )
    samples.append(metrics.snapshot("pubsub"))

    def worker_loop(worker_index: int) -> None:
        pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(PUBSUB_CHANNEL)
        try:
            while not stop_event.is_set():
                message = pubsub.get_message(timeout=0.1)
                if not message or message.get("type") != "message":
                    continue
                try:
                    job = Job.from_json(message["data"])
                    broker._simulate_llm(job, processing_ms)
                except Exception:
                    metrics.record_error("pubsub")
        finally:
            pubsub.close()

    threads = [threading.Thread(target=worker_loop, args=(0,), daemon=True)]
    for thread in threads:
        thread.start()

    time.sleep(0.15)
    for index in range(lost_before_subscribe, jobs):
        broker.publish_pubsub(Job.create("pubsub", payload=f"LLM request #{index + 1}"))
        if burst > 0 and (index + 1) % burst == 0:
            samples.append(metrics.snapshot("pubsub"))
            time.sleep(0.02)

    started = time.time()
    while time.time() - started < max_wait_seconds:
        sample = metrics.snapshot("pubsub")
        samples.append(sample)
        completed = sample["processed"] + sample["rejected"] + sample["errors"]
        if completed >= jobs:
            break
        time.sleep(sample_interval)

    stop_event.set()
    for thread in threads:
        thread.join(timeout=1.5)

    return {"summary": metrics.read_mode("pubsub"), "samples": samples}


def run_queue_scenario(
    redis_client: Any,
    mode: str,
    jobs: int = 100,
    burst: int = 50,
    workers: int = 2,
    processing_ms: int = 300,
    sample_interval: float = 0.25,
    max_wait_seconds: float | None = None,
) -> dict:
    if mode not in ("list", "stream", "zset"):
        raise ValueError("mode must be list, stream or zset")

    metrics = MetricsStore(redis_client)
    broker = RedisBroker(redis_client, metrics)
    metrics.reset_mode(mode)
    max_wait_seconds = max_wait_seconds or estimate_drain_wait_seconds(
        jobs,
        workers,
        processing_ms,
    )

    if mode == "list":
        broker.clear_list_queue()
        backlog = broker.list_backlog
        pending = lambda: 0
        consume = lambda name: broker.consume_list_once(block_timeout=1, processing_ms=processing_ms)
        enqueue = lambda index: broker.enqueue_list(
            Job.create("list", payload=f"LLM request #{index + 1}")
        )
    elif mode == "stream":
        broker.clear_stream_queue()
        broker.ensure_stream_group()
        backlog = broker.stream_backlog
        pending = broker.stream_pending
        consume = lambda name: broker.consume_stream_once(
            consumer_name=name,
            count=1,
            block_ms=1000,
            processing_ms=processing_ms,
        )
        enqueue = lambda index: broker.enqueue_stream(
            Job.create("stream", payload=f"LLM request #{index + 1}")
        )
    else:
        broker.clear_zset_queue()
        backlog = broker.zset_backlog
        pending = lambda: 0
        consume = lambda name: broker.consume_zset_once(processing_ms=processing_ms)
        enqueue = lambda index: broker.enqueue_zset(
            Job.create("zset", payload=f"LLM request #{index + 1}"),
            delay_ms=(index % max(1, burst)) * 5,
        )

    stop_event = threading.Event()

    def worker_loop(worker_index: int) -> None:
        consumer_name = f"scenario-{mode}-{worker_index}"
        while not stop_event.is_set():
            if not consume(consumer_name):
                time.sleep(0.01)

    threads = [
        threading.Thread(target=worker_loop, args=(index,), daemon=True)
        for index in range(max(1, workers))
    ]
    for thread in threads:
        thread.start()

    samples = [metrics.snapshot(mode, backlog=backlog(), pending=pending())]
    for index in range(jobs):
        enqueue(index)
        if burst > 0 and (index + 1) % burst == 0:
            samples.append(metrics.snapshot(mode, backlog=backlog(), pending=pending()))
            time.sleep(0.02)

    started = time.time()
    while time.time() - started < max_wait_seconds:
        sample = metrics.snapshot(mode, backlog=backlog(), pending=pending())
        samples.append(sample)
        completed = sample["processed"] + sample["errors"]
        if completed >= jobs and sample["backlog"] == 0 and sample["pending"] == 0:
            break
        time.sleep(sample_interval)

    stop_event.set()
    for thread in threads:
        thread.join(timeout=1.5)

    return {
        "summary": metrics.read_mode(mode, backlog=backlog(), pending=pending()),
        "samples": samples,
    }


def run_consumer_forever(
    redis_client: Any,
    mode: str,
    processing_ms: int = 300,
    consumer_name: str = "cli-consumer",
) -> None:
    metrics = MetricsStore(redis_client)
    broker = RedisBroker(redis_client, metrics)
    print(f"Consumer started: mode={mode}, processing_ms={processing_ms}")
    try:
        if mode == "pubsub":
            _run_pubsub_consumer_forever(redis_client, metrics, broker, processing_ms)
            return
        if mode == "kafka":
            _run_kafka_consumer_forever(metrics, processing_ms, consumer_name)
            return

        while True:
            if mode == "list":
                consumed = broker.consume_list_once(block_timeout=1, processing_ms=processing_ms)
                backlog = broker.list_backlog()
                pending = 0
            elif mode == "stream":
                consumed = broker.consume_stream_once(
                    consumer_name=consumer_name,
                    count=1,
                    block_ms=1000,
                    processing_ms=processing_ms,
                )
                backlog = broker.stream_backlog()
                pending = broker.stream_pending()
            elif mode == "zset":
                consumed = broker.consume_zset_once(processing_ms=processing_ms)
                backlog = broker.zset_backlog()
                pending = 0
            else:
                raise ValueError("mode must be pubsub, list, stream, zset or kafka")
            if consumed:
                snapshot = metrics.snapshot(mode, backlog=backlog, pending=pending)
                print(
                    f"processed={snapshot['processed']} backlog={snapshot['backlog']} "
                    f"pending={snapshot['pending']} avg_latency_ms={snapshot['avg_latency_ms']}"
                )
    except KeyboardInterrupt:
        print("Consumer stopped")


def _run_pubsub_consumer_forever(
    redis_client: Any,
    metrics: MetricsStore,
    broker: RedisBroker,
    processing_ms: int,
) -> None:
    pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(PUBSUB_CHANNEL)
    try:
        while True:
            message = pubsub.get_message(timeout=1)
            if not message or message.get("type") != "message":
                continue
            job = Job.from_json(message["data"])
            broker._simulate_llm(job, processing_ms)
            snapshot = metrics.snapshot("pubsub")
            print(
                f"processed={snapshot['processed']} lost={snapshot['rejected']} "
                f"avg_latency_ms={snapshot['avg_latency_ms']}"
            )
    finally:
        pubsub.close()


def _run_kafka_consumer_forever(
    metrics: MetricsStore,
    processing_ms: int,
    consumer_name: str,
) -> None:
    kafka = KafkaBroker(metrics)
    consumer = kafka.create_consumer(consumer_name)
    try:
        while True:
            consumed = kafka.consume_once(consumer, processing_ms=processing_ms)
            if consumed:
                snapshot = metrics.snapshot("kafka", backlog=kafka.backlog())
                print(
                    f"processed={snapshot['processed']} backlog={snapshot['backlog']} "
                    f"avg_latency_ms={snapshot['avg_latency_ms']}"
                )
    finally:
        consumer.close()


class InMemoryRedis:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, float]] = {}
        self.lists: dict[str, list[str]] = {}

    def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self.hashes:
                del self.hashes[key]
                deleted += 1
            if key in self.lists:
                del self.lists[key]
                deleted += 1
        return deleted

    def scan_iter(self, pattern: str):
        prefix = pattern.rstrip("*")
        for key in list(self.hashes) + list(self.lists):
            if key.startswith(prefix):
                yield key

    def hgetall(self, key: str) -> dict[str, str]:
        return {field: str(value) for field, value in self.hashes.get(key, {}).items()}

    def hincrby(self, key: str, field: str, amount: int) -> int:
        self.hashes.setdefault(key, {})
        self.hashes[key][field] = self.hashes[key].get(field, 0) + amount
        return int(self.hashes[key][field])

    def hincrbyfloat(self, key: str, field: str, amount: float) -> float:
        self.hashes.setdefault(key, {})
        self.hashes[key][field] = self.hashes[key].get(field, 0.0) + amount
        return float(self.hashes[key][field])

    def lpush(self, key: str, value: str) -> int:
        self.lists.setdefault(key, []).insert(0, value)
        return len(self.lists[key])

    def ltrim(self, key: str, start: int, stop: int) -> None:
        self.lists[key] = self.lists.get(key, [])[start : stop + 1]

    def lrange(self, key: str, start: int, stop: int) -> list[str]:
        return self.lists.get(key, [])[start : stop + 1]

    def lrem(self, key: str, count: int, value: str) -> int:
        return 0
