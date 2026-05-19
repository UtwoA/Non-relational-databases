from __future__ import annotations

import argparse
import json
import os

import redis

from src.redis_broker_demo.app import create_app
from src.redis_broker_demo.health import check_services
from src.redis_broker_demo.metrics import MetricsStore
from src.redis_broker_demo.scenarios import (
    produce_jobs,
    run_consumer_forever,
    run_all_scenarios,
    run_delayed_consumer_scenario,
    run_direct_scenario,
    run_kafka_scenario,
    run_pubsub_scenario,
    run_queue_scenario,
)


def build_redis() -> redis.Redis:
    return redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
        decode_responses=True,
    )


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Redis broker demo: peak smoothing with direct calls and Redis patterns"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    web_parser = subparsers.add_parser("web", help="Run web dashboard")
    web_parser.add_argument("--host", default="0.0.0.0")
    web_parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "5000")))

    subparsers.add_parser("reset", help="Delete Additional_task demo keys from Redis")
    subparsers.add_parser("doctor", help="Check Redis and Kafka availability")

    producer_parser = subparsers.add_parser("producer", help="Produce jobs into Redis")
    producer_parser.add_argument(
        "--mode",
        choices=["pubsub", "list", "stream", "zset", "kafka"],
        required=True,
    )
    producer_parser.add_argument("--jobs", type=int, default=100)
    producer_parser.add_argument("--burst", type=int, default=50)

    consumer_parser = subparsers.add_parser("consumer", help="Run a Redis consumer")
    consumer_parser.add_argument(
        "--mode",
        choices=["pubsub", "list", "stream", "zset", "kafka"],
        required=True,
    )
    consumer_parser.add_argument("--processing-ms", type=int, default=300)
    consumer_parser.add_argument("--consumer-name", default="cli-consumer")

    scenario_parser = subparsers.add_parser("scenario", help="Run a full load scenario")
    scenario_parser.add_argument(
        "--mode",
        choices=["direct", "pubsub", "list", "stream", "zset", "kafka"],
        required=True,
    )
    scenario_parser.add_argument("--jobs", type=int, default=100)
    scenario_parser.add_argument("--burst", type=int, default=50)
    scenario_parser.add_argument("--workers", type=int, default=2)
    scenario_parser.add_argument("--processing-ms", type=int, default=300)
    scenario_parser.add_argument("--acquire-timeout-ms", type=int, default=10)
    scenario_parser.add_argument("--max-wait-seconds", type=float)

    compare_parser = subparsers.add_parser("compare", help="Run all modes sequentially")
    compare_parser.add_argument("--jobs", type=int, default=60)
    compare_parser.add_argument("--burst", type=int, default=30)
    compare_parser.add_argument("--workers", type=int, default=2)
    compare_parser.add_argument("--processing-ms", type=int, default=150)
    compare_parser.add_argument("--max-wait-seconds", type=float)

    delayed_parser = subparsers.add_parser(
        "delayed",
        help="Produce first, start consumer later, then show backlog decay",
    )
    delayed_parser.add_argument("--mode", choices=["list", "stream", "zset", "kafka"], default="stream")
    delayed_parser.add_argument("--jobs", type=int, default=60)
    delayed_parser.add_argument("--burst", type=int, default=30)
    delayed_parser.add_argument("--workers", type=int, default=2)
    delayed_parser.add_argument("--processing-ms", type=int, default=150)
    delayed_parser.add_argument("--consumer-delay-seconds", type=float, default=2.0)
    delayed_parser.add_argument("--max-wait-seconds", type=float)

    args = parser.parse_args()
    redis_client = build_redis()

    if args.command == "web":
        app = create_app(redis_client)
        app.run(host=args.host, port=args.port, debug=False)
        return

    metrics = MetricsStore(redis_client)

    if args.command == "reset":
        deleted = metrics.reset_all()
        print_json({"deleted_keys": deleted})
        return

    if args.command == "doctor":
        print_json(check_services(redis_client))
        return

    if args.command == "producer":
        result = produce_jobs(
            redis_client,
            mode=args.mode,
            jobs=args.jobs,
            burst=args.burst,
        )
        print_json(result)
        return

    if args.command == "consumer":
        run_consumer_forever(
            redis_client,
            mode=args.mode,
            processing_ms=args.processing_ms,
            consumer_name=args.consumer_name,
        )
        return

    if args.command == "scenario":
        if args.mode == "direct":
            result = run_direct_scenario(
                redis_client,
                jobs=args.jobs,
                burst=args.burst,
                workers=args.workers,
                processing_ms=args.processing_ms,
                acquire_timeout_ms=args.acquire_timeout_ms,
            )
        elif args.mode == "pubsub":
            result = run_pubsub_scenario(
                redis_client,
                jobs=args.jobs,
                burst=args.burst,
                workers=args.workers,
                processing_ms=args.processing_ms,
                max_wait_seconds=args.max_wait_seconds,
            )
        elif args.mode == "kafka":
            result = run_kafka_scenario(
                redis_client,
                jobs=args.jobs,
                burst=args.burst,
                workers=args.workers,
                processing_ms=args.processing_ms,
                max_wait_seconds=args.max_wait_seconds,
            )
        else:
            result = run_queue_scenario(
                redis_client,
                mode=args.mode,
                jobs=args.jobs,
                burst=args.burst,
                workers=args.workers,
                processing_ms=args.processing_ms,
                max_wait_seconds=args.max_wait_seconds,
            )
        print_json(result)
        return

    if args.command == "compare":
        result = run_all_scenarios(
            redis_client,
            jobs=args.jobs,
            burst=args.burst,
            workers=args.workers,
            processing_ms=args.processing_ms,
            max_wait_seconds=args.max_wait_seconds,
        )
        print_json(result)
        return

    if args.command == "delayed":
        result = run_delayed_consumer_scenario(
            redis_client,
            mode=args.mode,
            jobs=args.jobs,
            burst=args.burst,
            workers=args.workers,
            processing_ms=args.processing_ms,
            consumer_delay_seconds=args.consumer_delay_seconds,
            max_wait_seconds=args.max_wait_seconds,
        )
        print_json(result)
        return

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
