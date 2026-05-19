from __future__ import annotations

from typing import Any

from .kafka_broker import KafkaBroker


def check_services(redis_client: Any) -> dict:
    redis_status = {
        "service": "redis",
        "ok": False,
        "detail": "not checked",
    }
    kafka_status = {
        "service": "kafka",
        "ok": False,
        "detail": "not checked",
    }

    try:
        pong = redis_client.ping()
        redis_status = {
            "service": "redis",
            "ok": bool(pong),
            "detail": "127.0.0.1:6379 is reachable",
        }
    except Exception as exc:
        redis_status = {
            "service": "redis",
            "ok": False,
            "detail": str(exc),
        }

    try:
        KafkaBroker._require_kafka()
        from confluent_kafka.admin import AdminClient

        broker = KafkaBroker(metrics=None)
        admin = AdminClient({"bootstrap.servers": broker.bootstrap_servers})
        metadata = admin.list_topics(timeout=5)
        kafka_status = {
            "service": "kafka",
            "ok": bool(metadata.brokers),
            "detail": f"{broker.bootstrap_servers} brokers={len(metadata.brokers)}",
        }
    except Exception as exc:
        kafka_status = {
            "service": "kafka",
            "ok": False,
            "detail": str(exc),
        }

    statuses = [redis_status, kafka_status]
    return {
        "ok": all(item["ok"] for item in statuses),
        "services": statuses,
    }
