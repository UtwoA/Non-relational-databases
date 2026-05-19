from __future__ import annotations

import time
from typing import Any

from .metrics import MetricsStore
from .models import Job


LIST_QUEUE = "additional:list:jobs"
PUBSUB_CHANNEL = "additional:pubsub:jobs"
STREAM_KEY = "additional:stream:jobs"
STREAM_GROUP = "llm-workers"
ZSET_QUEUE = "additional:zset:jobs"


class RedisBroker:
    def __init__(self, redis_client: Any, metrics: MetricsStore) -> None:
        self.redis = redis_client
        self.metrics = metrics

    def clear_list_queue(self) -> None:
        self.redis.delete(LIST_QUEUE)

    def clear_zset_queue(self) -> None:
        self.redis.delete(ZSET_QUEUE)

    def clear_stream_queue(self) -> None:
        self.redis.delete(STREAM_KEY)

    def publish_pubsub(self, job: Job) -> int:
        subscribers = int(self.redis.publish(PUBSUB_CHANNEL, job.to_json()))
        self.metrics.record_produced("pubsub")
        self.metrics.record_accepted("pubsub")
        if subscribers == 0:
            self.metrics.record_rejected("pubsub")
        return subscribers

    def enqueue_list(self, job: Job) -> None:
        self.redis.rpush(LIST_QUEUE, job.to_json())
        self.metrics.record_produced("list")
        self.metrics.record_accepted("list")

    def consume_list_once(self, block_timeout: int = 1, processing_ms: int = 300) -> bool:
        result = self.redis.blpop(LIST_QUEUE, timeout=block_timeout)
        if not result:
            return False

        _queue_name, raw_job = result
        try:
            job = Job.from_json(raw_job)
            self._simulate_llm(job, processing_ms)
            return True
        except Exception:
            self.metrics.record_error("list")
            return False

    def list_backlog(self) -> int:
        return int(self.redis.llen(LIST_QUEUE))

    def enqueue_zset(self, job: Job, delay_ms: int = 0) -> None:
        score = time.time() + delay_ms / 1000
        self.redis.zadd(ZSET_QUEUE, {job.to_json(): score})
        self.metrics.record_produced("zset")
        self.metrics.record_accepted("zset")

    def consume_zset_once(self, processing_ms: int = 300) -> bool:
        now = time.time()
        raw_jobs = self.redis.zrangebyscore(ZSET_QUEUE, "-inf", now, start=0, num=1)
        if not raw_jobs:
            return False

        raw_job = raw_jobs[0]
        if not self.redis.zrem(ZSET_QUEUE, raw_job):
            return False

        try:
            job = Job.from_json(raw_job)
            self._simulate_llm(job, processing_ms)
            return True
        except Exception:
            self.metrics.record_error("zset")
            return False

    def zset_backlog(self) -> int:
        return int(self.redis.zcard(ZSET_QUEUE))

    def ensure_stream_group(self) -> None:
        try:
            self.redis.xgroup_create(STREAM_KEY, STREAM_GROUP, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def enqueue_stream(self, job: Job) -> str:
        self.ensure_stream_group()
        message_id = self.redis.xadd(STREAM_KEY, {"job": job.to_json()})
        self.metrics.record_produced("stream")
        self.metrics.record_accepted("stream")
        return str(message_id)

    def consume_stream_once(
        self,
        consumer_name: str = "worker-1",
        count: int = 1,
        block_ms: int = 1000,
        processing_ms: int = 300,
    ) -> int:
        self.ensure_stream_group()
        result = self.redis.xreadgroup(
            groupname=STREAM_GROUP,
            consumername=consumer_name,
            streams={STREAM_KEY: ">"},
            count=count,
            block=block_ms,
        )
        if not result:
            return 0

        consumed = 0
        for _stream_name, messages in result:
            for message_id, fields in messages:
                try:
                    job = Job.from_json(fields["job"])
                    self._simulate_llm(job, processing_ms)
                    self.redis.xack(STREAM_KEY, STREAM_GROUP, message_id)
                    self.redis.xdel(STREAM_KEY, message_id)
                    consumed += 1
                except Exception:
                    self.metrics.record_error("stream")
        return consumed

    def stream_backlog(self) -> int:
        return int(self.redis.xlen(STREAM_KEY))

    def stream_pending(self) -> int:
        try:
            summary = self.redis.xpending(STREAM_KEY, STREAM_GROUP)
        except Exception:
            return 0
        if isinstance(summary, dict):
            return int(summary.get("pending", 0))
        if isinstance(summary, (tuple, list)) and summary:
            return int(summary[0])
        return 0

    def _simulate_llm(self, job: Job, processing_ms: int) -> None:
        time.sleep(processing_ms / 1000)
        latency_ms = (time.time() - job.created_at) * 1000
        self.metrics.record_processed(job.mode, latency_ms)
