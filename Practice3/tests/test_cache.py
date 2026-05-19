from __future__ import annotations

import time
import unittest

from src.cache_demo.cache import InMemoryCache
from src.cache_demo.decorators import _build_cache_key, redis_cached
from src.practice3_web.store import UserStore


class CacheDemoTests(unittest.TestCase):
    def test_cached_function_returns_same_result_and_skips_second_execution(self) -> None:
        cache = InMemoryCache()
        calls = {"count": 0}

        @redis_cached(cache, ttl_seconds=60)
        def multiply(value: int) -> int:
            calls["count"] += 1
            return value * 2

        first = multiply(21)
        second = multiply(21)

        self.assertEqual(first, 42)
        self.assertEqual(second, 42)
        self.assertEqual(calls["count"], 1)

    def test_cache_key_depends_on_function_name_and_arguments(self) -> None:
        key_a = _build_cache_key("fn_a", (1, 2), {"x": 3})
        key_b = _build_cache_key("fn_a", (1, 2), {"x": 4})
        key_c = _build_cache_key("fn_b", (1, 2), {"x": 3})

        self.assertNotEqual(key_a, key_b)
        self.assertNotEqual(key_a, key_c)

    def test_ttl_expires_value(self) -> None:
        cache = InMemoryCache()
        cache.set("demo", "value", ttl_seconds=1)
        self.assertEqual(cache.get("demo"), "value")

        time.sleep(1.1)
        self.assertIsNone(cache.get("demo"))

    def test_none_result_is_cached(self) -> None:
        cache = InMemoryCache()
        calls = {"count": 0}

        @redis_cached(cache, ttl_seconds=60)
        def maybe_none(flag: bool):
            calls["count"] += 1
            return None if flag else "ok"

        self.assertIsNone(maybe_none(True))
        self.assertIsNone(maybe_none(True))
        self.assertEqual(calls["count"], 1)

    def test_user_store_adds_and_lists_users(self) -> None:
        class FakeRedis:
            def __init__(self) -> None:
                self.hashes: dict[str, dict[str, str]] = {}
                self.lists: dict[str, list[str]] = {}

            def hset(self, key, mapping):
                self.hashes[key] = dict(mapping)

            def rpush(self, key, value):
                self.lists.setdefault(key, []).append(value)

            def lrange(self, key, start, end):
                values = self.lists.get(key, [])
                if end == -1:
                    return values[start:]
                return values[start : end + 1]

            def hgetall(self, key):
                return self.hashes.get(key, {})

            def llen(self, key):
                return len(self.lists.get(key, []))

            def delete(self, key):
                self.hashes.pop(key, None)
                self.lists.pop(key, None)

        store = UserStore(FakeRedis())
        store.add_user("Alice")
        store.add_user("Bob")

        users = store.list_users()
        self.assertEqual([user["name"] for user in users], ["Alice", "Bob"])
        self.assertEqual(store.count_users(), 2)


if __name__ == "__main__":
    unittest.main()
