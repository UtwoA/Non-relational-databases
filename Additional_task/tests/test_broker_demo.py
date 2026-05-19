from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.redis_broker_demo.broker import RedisBroker
from src.redis_broker_demo.direct import run_direct_load
from src.redis_broker_demo.metrics import MetricsStore
from src.redis_broker_demo.models import Job
from src.redis_broker_demo.scenarios import InMemoryRedis


class UnitTests(unittest.TestCase):
    def test_job_json_roundtrip(self) -> None:
        job = Job.create("list", payload="demo")
        restored = Job.from_json(job.to_json())
        self.assertEqual(restored.job_id, job.job_id)
        self.assertEqual(restored.payload, "demo")
        self.assertEqual(restored.mode, "list")

    def test_direct_overload_rejects_requests(self) -> None:
        metrics = MetricsStore(InMemoryRedis())
        result = run_direct_load(
            metrics=metrics,
            jobs=20,
            burst=20,
            workers=1,
            processing_ms=50,
            acquire_timeout_ms=1,
        )
        summary = result["summary"]
        self.assertGreater(summary["processed"], 0)
        self.assertGreater(summary["rejected"], 0)
        self.assertEqual(summary["produced"], 20)


def redis_client_or_skip(test_case: unittest.TestCase):
    try:
        import redis
    except ImportError:
        test_case.skipTest("redis package is not installed")

    client = redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://127.0.0.1:6379/15"),
        decode_responses=True,
    )
    try:
        client.ping()
    except Exception as exc:
        test_case.skipTest(f"Redis is not available: {exc}")
    return client


class RedisIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.redis = redis_client_or_skip(self)
        self.metrics = MetricsStore(self.redis)
        self.metrics.reset_all()
        self.broker = RedisBroker(self.redis, self.metrics)

    def tearDown(self) -> None:
        self.metrics.reset_all()

    def test_list_queue_accumulates_and_consumer_decreases_it(self) -> None:
        for index in range(5):
            self.broker.enqueue_list(Job.create("list", payload=f"job {index}"))

        self.assertEqual(self.broker.list_backlog(), 5)
        consumed = self.broker.consume_list_once(block_timeout=1, processing_ms=1)
        self.assertTrue(consumed)
        self.assertEqual(self.broker.list_backlog(), 4)

    def test_stream_queue_accumulates_and_consumer_acknowledges_it(self) -> None:
        self.broker.clear_stream_queue()
        for index in range(5):
            self.broker.enqueue_stream(Job.create("stream", payload=f"job {index}"))

        self.assertEqual(self.broker.stream_backlog(), 5)
        consumed = self.broker.consume_stream_once(
            consumer_name="test-consumer",
            count=1,
            block_ms=10,
            processing_ms=1,
        )
        self.assertEqual(consumed, 1)
        self.assertEqual(self.broker.stream_backlog(), 4)

    def test_zset_queue_accumulates_and_consumer_decreases_it(self) -> None:
        self.broker.clear_zset_queue()
        for index in range(5):
            self.broker.enqueue_zset(Job.create("zset", payload=f"job {index}"))

        self.assertEqual(self.broker.zset_backlog(), 5)
        consumed = self.broker.consume_zset_once(processing_ms=1)
        self.assertTrue(consumed)
        self.assertEqual(self.broker.zset_backlog(), 4)

    def test_pubsub_without_subscriber_records_lost_message(self) -> None:
        self.broker.publish_pubsub(Job.create("pubsub", payload="lost"))
        summary = self.metrics.read_mode("pubsub")
        self.assertEqual(summary["produced"], 1)
        self.assertEqual(summary["rejected"], 1)

    def test_reset_removes_demo_keys(self) -> None:
        self.redis.set("additional:demo:key", "value")
        deleted = self.metrics.reset_all()
        self.assertGreaterEqual(deleted, 1)
        self.assertEqual(list(self.redis.scan_iter("additional:*")), [])


if __name__ == "__main__":
    unittest.main()
