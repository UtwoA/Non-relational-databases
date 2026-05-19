from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.redis_broker_demo.broker import RedisBroker
from src.redis_broker_demo.direct import run_direct_load
from src.redis_broker_demo.kafka_broker import KafkaBroker
from src.redis_broker_demo.metrics import MetricsStore
from src.redis_broker_demo.models import Job
from src.redis_broker_demo.scenarios import (
    InMemoryRedis,
    run_all_scenarios,
    run_delayed_consumer_scenario,
)


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

    def test_delayed_consumer_accumulates_then_drains_stream(self) -> None:
        result = run_delayed_consumer_scenario(
            self.redis,
            mode="stream",
            jobs=6,
            burst=3,
            workers=2,
            processing_ms=1,
            consumer_delay_seconds=0.01,
        )
        self.assertEqual(result["summary"]["processed"], 6)
        self.assertEqual(result["summary"]["backlog"], 0)
        self.assertTrue(any(sample["backlog"] > 0 for sample in result["samples"]))


def kafka_or_skip(test_case: unittest.TestCase) -> KafkaBroker:
    try:
        import confluent_kafka  # noqa: F401
    except ImportError:
        test_case.skipTest("confluent-kafka package is not installed")

    metrics = MetricsStore(InMemoryRedis())
    broker = KafkaBroker(metrics)
    try:
        broker.reset_topic()
    except Exception as exc:
        test_case.skipTest(f"Kafka is not available: {exc}")
    return broker


class KafkaIntegrationTests(unittest.TestCase):
    def test_kafka_topic_accumulates_and_consumer_decreases_lag(self) -> None:
        broker = kafka_or_skip(self)
        for index in range(3):
            broker.enqueue(Job.create("kafka", payload=f"job {index}"))

        self.assertGreaterEqual(broker.backlog(), 1)
        consumer = broker.create_consumer("test-kafka-consumer")
        try:
            deadline = 20
            consumed = 0
            while deadline > 0 and consumed < 3:
                if broker.consume_once(consumer, processing_ms=1):
                    consumed += 1
                deadline -= 1
            self.assertEqual(consumed, 3)
            self.assertEqual(broker.backlog(), 0)
        finally:
            consumer.close()

    def test_compare_runs_all_modes(self) -> None:
        redis_client = redis_client_or_skip(self)
        result = run_all_scenarios(
            redis_client,
            jobs=3,
            burst=3,
            workers=1,
            processing_ms=1,
        )
        self.assertIn("direct", result["summary"])
        self.assertIn("stream", result["summary"])
        self.assertIn("kafka", result["summary"])


if __name__ == "__main__":
    unittest.main()
