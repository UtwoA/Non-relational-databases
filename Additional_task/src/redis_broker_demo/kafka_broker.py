from __future__ import annotations

import os
import time
from typing import Any

from .metrics import MetricsStore
from .models import Job


KAFKA_TOPIC = "additional.kafka.jobs"
KAFKA_GROUP = "additional-kafka-workers"


class KafkaUnavailable(RuntimeError):
    pass


class KafkaBroker:
    def __init__(
        self,
        metrics: MetricsStore,
        bootstrap_servers: str | None = None,
        topic: str = KAFKA_TOPIC,
        group_id: str = KAFKA_GROUP,
    ) -> None:
        self.metrics = metrics
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS",
            "127.0.0.1:9092",
        )
        self.topic = topic
        self.group_id = group_id

    def reset_topic(self, num_partitions: int = 1) -> None:
        self._require_kafka()
        from confluent_kafka.admin import AdminClient, NewTopic

        admin = AdminClient({"bootstrap.servers": self.bootstrap_servers})
        metadata = admin.list_topics(timeout=5)
        if self.topic in metadata.topics:
            futures = admin.delete_topics([self.topic], operation_timeout=10)
            for future in futures.values():
                try:
                    future.result(timeout=15)
                except Exception:
                    pass
            for _attempt in range(30):
                metadata = admin.list_topics(timeout=3)
                if self.topic not in metadata.topics:
                    break
                time.sleep(0.5)

        futures = admin.create_topics(
            [NewTopic(self.topic, num_partitions=max(1, num_partitions), replication_factor=1)],
            operation_timeout=10,
        )
        for future in futures.values():
            try:
                future.result(timeout=15)
            except Exception as exc:
                if "Topic already exists" not in str(exc) and "TOPIC_ALREADY_EXISTS" not in str(exc):
                    raise

    def enqueue(self, job: Job) -> None:
        self._require_kafka()
        from confluent_kafka import Producer

        producer = Producer({"bootstrap.servers": self.bootstrap_servers})
        producer.produce(self.topic, key=job.job_id, value=job.to_json())
        producer.flush(10)
        self.metrics.record_produced("kafka")
        self.metrics.record_accepted("kafka")

    def create_consumer(self, consumer_name: str):
        self._require_kafka()
        from confluent_kafka import Consumer

        consumer = Consumer(
            {
                "bootstrap.servers": self.bootstrap_servers,
                "group.id": self.group_id,
                "client.id": consumer_name,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )
        consumer.subscribe([self.topic])
        return consumer

    def consume_once(self, consumer: Any, processing_ms: int = 300) -> bool:
        message = consumer.poll(1.0)
        if message is None:
            return False
        if message.error():
            self.metrics.record_error("kafka")
            return False

        try:
            raw = message.value()
            job = Job.from_json(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            time.sleep(processing_ms / 1000)
            latency_ms = (time.time() - job.created_at) * 1000
            self.metrics.record_processed("kafka", latency_ms)
            consumer.commit(message=message, asynchronous=False)
            return True
        except Exception:
            self.metrics.record_error("kafka")
            return False

    def backlog(self) -> int:
        try:
            self._require_kafka()
            from confluent_kafka import Consumer, TopicPartition

            consumer = Consumer(
                {
                    "bootstrap.servers": self.bootstrap_servers,
                    "group.id": self.group_id,
                    "enable.auto.commit": False,
                    "auto.offset.reset": "earliest",
                }
            )
            try:
                metadata = consumer.list_topics(self.topic, timeout=3)
                topic = metadata.topics.get(self.topic)
                if topic is None or topic.error is not None:
                    return 0
                partitions = [
                    TopicPartition(self.topic, partition_id)
                    for partition_id in topic.partitions
                ]
                committed = {
                    partition.partition: partition.offset
                    for partition in consumer.committed(partitions, timeout=3)
                }
                lag = 0
                for partition in partitions:
                    low, high = consumer.get_watermark_offsets(partition, timeout=3)
                    offset = committed.get(partition.partition, -1001)
                    if offset is None or offset < 0:
                        offset = low
                    lag += max(0, high - offset)
                return int(lag)
            finally:
                consumer.close()
        except Exception:
            return 0

    @staticmethod
    def _require_kafka() -> None:
        try:
            import confluent_kafka  # noqa: F401
        except ImportError as exc:
            raise KafkaUnavailable("Install confluent-kafka to use Kafka mode") from exc
