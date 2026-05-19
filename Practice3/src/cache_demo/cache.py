from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol


class CacheBackend(Protocol):
    def get(self, key: str) -> Any: ...

    def set(self, key: str, value: Any, ttl_seconds: int) -> None: ...

    def contains(self, key: str) -> bool: ...


class RedisCache:
    def __init__(self, url: str) -> None:
        self._url = url
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import redis
            except ImportError as exc: 
                raise RuntimeError(
                    "redis net"
                ) from exc

            self._client = redis.Redis.from_url(self._url, decode_responses=True)
        return self._client

    def get(self, key: str) -> Any:
        raw = self._get_client().get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True)
        self._get_client().set(key, payload, ex=ttl_seconds)

    def exists(self, key: str) -> bool:
        return bool(self._get_client().exists(key))

    def contains(self, key: str) -> bool:
        return self.exists(key)

    def keys(self, pattern: str = "*") -> list[str]:
        return list(self._get_client().keys(pattern))


@dataclass
class _MemoryEntry:
    value: Any
    expires_at: float | None


class InMemoryCache:
    def __init__(self) -> None:
        self._items: dict[str, _MemoryEntry] = {}

    def get(self, key: str) -> Any:
        entry = self._items.get(key)
        if entry is None:
            return None
        if entry.expires_at is not None and time.time() >= entry.expires_at:
            del self._items[key]
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._items[key] = _MemoryEntry(value=value, expires_at=time.time() + ttl_seconds)

    def contains(self, key: str) -> bool:
        entry = self._items.get(key)
        if entry is None:
            return False
        if entry.expires_at is not None and time.time() >= entry.expires_at:
            del self._items[key]
            return False
        return True
