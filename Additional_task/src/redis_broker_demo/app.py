from __future__ import annotations

from typing import Any

from flask import Flask, jsonify, render_template, request

from .broker import RedisBroker
from .health import check_services
from .kafka_broker import KafkaBroker
from .metrics import MODES, MetricsStore
from .scenarios import (
    run_direct_scenario,
    run_all_scenarios,
    run_delayed_consumer_scenario,
    run_kafka_scenario,
    run_pubsub_scenario,
    run_queue_scenario,
)


def create_app(redis_client: Any) -> Flask:
    app = Flask(__name__, template_folder="../../templates")

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/metrics")
    def metrics():
        store = MetricsStore(redis_client)
        broker = RedisBroker(redis_client, store)
        payload = []
        for mode in MODES:
            if mode == "list":
                payload.append(store.read_mode(mode, backlog=broker.list_backlog()))
            elif mode == "stream":
                payload.append(
                    store.read_mode(
                        mode,
                        backlog=broker.stream_backlog(),
                        pending=broker.stream_pending(),
                    )
                )
            elif mode == "zset":
                payload.append(store.read_mode(mode, backlog=broker.zset_backlog()))
            elif mode == "kafka":
                payload.append(store.read_mode(mode, backlog=KafkaBroker(store).backlog()))
            else:
                payload.append(store.read_mode(mode))
        limit = int(request.args.get("limit", 1200))
        return jsonify({"metrics": payload, "measurements": store.measurements(limit=limit)})

    @app.post("/api/reset")
    def reset():
        deleted = MetricsStore(redis_client).reset_all()
        return jsonify({"deleted_keys": deleted})

    @app.get("/api/health")
    def health():
        return jsonify(check_services(redis_client))

    @app.post("/api/scenario")
    def scenario():
        payload = request.get_json(silent=True) or {}
        mode = str(payload.get("mode", "list"))
        jobs = int(payload.get("jobs", 40))
        burst = int(payload.get("burst", 20))
        workers = int(payload.get("workers", 2))
        processing_ms = int(payload.get("processing_ms", 300))
        raw_max_wait = payload.get("max_wait_seconds")
        max_wait_seconds = float(raw_max_wait) if raw_max_wait else None

        if mode == "all":
            result = run_all_scenarios(
                redis_client,
                jobs=jobs,
                burst=burst,
                workers=workers,
                processing_ms=processing_ms,
                max_wait_seconds=max_wait_seconds,
            )
        elif mode == "delayed":
            result = run_delayed_consumer_scenario(
                redis_client,
                mode=str(payload.get("delayed_mode", "stream")),
                jobs=jobs,
                burst=burst,
                workers=workers,
                processing_ms=processing_ms,
                consumer_delay_seconds=float(payload.get("consumer_delay_seconds", 2.0)),
                max_wait_seconds=max_wait_seconds,
            )
        elif mode == "direct":
            result = run_direct_scenario(
                redis_client,
                jobs=jobs,
                burst=burst,
                workers=workers,
                processing_ms=processing_ms,
            )
        elif mode == "pubsub":
            result = run_pubsub_scenario(
                redis_client,
                jobs=jobs,
                burst=burst,
                workers=workers,
                processing_ms=processing_ms,
                max_wait_seconds=max_wait_seconds,
            )
        elif mode == "kafka":
            result = run_kafka_scenario(
                redis_client,
                jobs=jobs,
                burst=burst,
                workers=workers,
                processing_ms=processing_ms,
                max_wait_seconds=max_wait_seconds,
            )
        elif mode in ("list", "stream", "zset"):
            result = run_queue_scenario(
                redis_client,
                mode=mode,
                jobs=jobs,
                burst=burst,
                workers=workers,
                processing_ms=processing_ms,
                max_wait_seconds=max_wait_seconds,
            )
        else:
            return jsonify(
                {"error": "mode must be all, delayed, direct, pubsub, list, stream, zset or kafka"}
            ), 400
        return jsonify(result)

    return app
