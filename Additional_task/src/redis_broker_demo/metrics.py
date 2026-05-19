from __future__ import annotations

import json
import time
from typing import Any


PREFIX = "additional"
MEASUREMENTS_KEY = f"{PREFIX}:measurements"
MODES = ("direct", "pubsub", "list", "stream", "zset")


class MetricsStore:
    def __init__(self, redis_client: Any) -> None:
        self.redis = redis_client

    def reset_all(self) -> int:
        keys = list(self.redis.scan_iter(f"{PREFIX}:*"))
        if keys:
            return int(self.redis.delete(*keys))
        return 0

    def reset_mode(self, mode: str) -> None:
        self.redis.delete(self._hash_key(mode))
        self.redis.lrem(MEASUREMENTS_KEY, 0, "__never__")

    def record_produced(self, mode: str, count: int = 1) -> None:
        self.redis.hincrby(self._hash_key(mode), "produced", count)

    def record_accepted(self, mode: str, count: int = 1) -> None:
        self.redis.hincrby(self._hash_key(mode), "accepted", count)

    def record_rejected(self, mode: str, count: int = 1) -> None:
        self.redis.hincrby(self._hash_key(mode), "rejected", count)

    def record_error(self, mode: str, count: int = 1) -> None:
        self.redis.hincrby(self._hash_key(mode), "errors", count)

    def record_processed(self, mode: str, latency_ms: float) -> None:
        key = self._hash_key(mode)
        self.redis.hincrby(key, "processed", 1)
        self.redis.hincrbyfloat(key, "total_latency_ms", float(latency_ms))

    def read_mode(self, mode: str, backlog: int = 0, pending: int = 0) -> dict[str, Any]:
        raw = self.redis.hgetall(self._hash_key(mode))
        produced = self._int(raw.get("produced"))
        accepted = self._int(raw.get("accepted"))
        processed = self._int(raw.get("processed"))
        rejected = self._int(raw.get("rejected"))
        errors = self._int(raw.get("errors"))
        total_latency = self._float(raw.get("total_latency_ms"))
        avg_latency = total_latency / processed if processed else 0.0
        return {
            "mode": mode,
            "produced": produced,
            "accepted": accepted,
            "processed": processed,
            "rejected": rejected,
            "errors": errors,
            "backlog": int(backlog),
            "pending": int(pending),
            "avg_latency_ms": round(avg_latency, 2),
            "timestamp": time.time(),
        }

    def snapshot(self, mode: str, backlog: int = 0, pending: int = 0) -> dict[str, Any]:
        payload = self.read_mode(mode, backlog=backlog, pending=pending)
        self.redis.lpush(MEASUREMENTS_KEY, json.dumps(payload, ensure_ascii=False))
        self.redis.ltrim(MEASUREMENTS_KEY, 0, 199)
        return payload

    def measurements(self, limit: int = 80) -> list[dict[str, Any]]:
        rows = self.redis.lrange(MEASUREMENTS_KEY, 0, max(0, limit - 1))
        decoded = [json.loads(row) for row in rows]
        return list(reversed(decoded))

    @staticmethod
    def _hash_key(mode: str) -> str:
        return f"{PREFIX}:metrics:{mode}"

    @staticmethod
    def _int(value: Any) -> int:
        if value in (None, ""):
            return 0
        return int(float(value))

    @staticmethod
    def _float(value: Any) -> float:
        if value in (None, ""):
            return 0.0
        return float(value)
