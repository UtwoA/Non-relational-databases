from __future__ import annotations

import functools
import hashlib
import json
from typing import Any, Callable, TypeVar

from .cache import CacheBackend

F = TypeVar("F", bound=Callable[..., Any])


def _build_cache_key(function_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    payload = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, ensure_ascii=False, default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"cache:{function_name}:{digest}"


def redis_cached(cache: CacheBackend, ttl_seconds: int = 60) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            key = _build_cache_key(func.__name__, args, kwargs)
            cached_value = cache.get(key)
            if cached_value is not None or cache.contains(key):
                return cached_value

            result = func(*args, **kwargs)
            cache.set(key, result, ttl_seconds)
            return result

        return wrapper 

    return decorator
