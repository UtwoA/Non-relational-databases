from __future__ import annotations

import argparse
import os
import time

from src.cache_demo.cache import RedisCache
from src.cache_demo.decorators import redis_cached
from src.cache_demo.services import analyze_text, slow_fibonacci
from src.practice3_web.app import create_app


def build_cache() -> RedisCache:
    return RedisCache(url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))


def run_demo() -> None:
    cache = build_cache()

    cached_fib = redis_cached(cache, ttl_seconds=120)(slow_fibonacci)
    cached_stats = redis_cached(cache, ttl_seconds=120)(analyze_text)

    print("Running fibonacci demo twice...")
    for run in range(1, 3):
        started = time.perf_counter()
        result = cached_fib(35)
        duration = time.perf_counter() - started
        print(f"Run {run}: fib(35) = {result} in {duration:.4f}s")

    print()
    print("Running text statistics demo twice...")
    sample = "Redis stores results so repeated work is faster."
    for run in range(1, 3):
        started = time.perf_counter()
        result = cached_stats(sample)
        duration = time.perf_counter() - started
        print(f"Run {run}: stats = {result} in {duration:.4f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Redis cache demo")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("demo", help="Run both cached demo functions")
    subparsers.add_parser("web", help="Run the Redis web admin app")

    fib_parser = subparsers.add_parser("fib", help="Calculate Fibonacci with Redis cache")
    fib_parser.add_argument("n", type=int)

    stats_parser = subparsers.add_parser("stats", help="Analyze text with Redis cache")
    stats_parser.add_argument("text", type=str)

    args = parser.parse_args()
    cache = build_cache()

    if args.command == "demo":
        run_demo()
        return

    if args.command == "web":
        app = create_app()
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
        return

    if args.command == "fib":
        cached_fib = redis_cached(cache, ttl_seconds=120)(slow_fibonacci)
        started = time.perf_counter()
        result = cached_fib(args.n)
        duration = time.perf_counter() - started
        print(f"fib({args.n}) = {result}")
        print(f"elapsed = {duration:.4f}s")
        return

    if args.command == "stats":
        cached_stats = redis_cached(cache, ttl_seconds=120)(analyze_text)
        started = time.perf_counter()
        result = cached_stats(args.text)
        duration = time.perf_counter() - started
        print(result)
        print(f"elapsed = {duration:.4f}s")


if __name__ == "__main__":
    main()
