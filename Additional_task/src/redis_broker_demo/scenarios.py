from __future__ import annotations

import threading
import time
from typing import Any

from .broker import PUBSUB_CHANNEL, RedisBroker
from .direct import run_direct_load
from .metrics import MetricsStore
from .models import Job


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
    else:
        raise ValueError("mode must be pubsub, list, stream or zset")

    for index in range(jobs):
        enqueue(Job.create(mode, payload=f"LLM request #{index + 1}"))
        if burst > 0 and (index + 1) % burst == 0:
            metrics.snapshot(mode, backlog=backlog())
            time.sleep(0.02)

    return metrics.snapshot(mode, backlog=backlog())


def run_pubsub_scenario(
    redis_client: Any,
    jobs: int = 100,
    burst: int = 50,
    workers: int = 2,
    processing_ms: int = 300,
    sample_interval: float = 0.25,
    max_wait_seconds: float = 30.0,
) -> dict:
    metrics = MetricsStore(redis_client)
    broker = RedisBroker(redis_client, metrics)
    metrics.reset_mode("pubsub")

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
    max_wait_seconds: float = 60.0,
) -> dict:
    if mode not in ("list", "stream", "zset"):
        raise ValueError("mode must be list, stream or zset")

    metrics = MetricsStore(redis_client)
    broker = RedisBroker(redis_client, metrics)
    metrics.reset_mode(mode)

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
                raise ValueError("mode must be pubsub, list, stream or zset")
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
