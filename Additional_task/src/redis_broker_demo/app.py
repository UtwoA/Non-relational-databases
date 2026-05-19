from __future__ import annotations

from typing import Any

from flask import Flask, jsonify, render_template, request

from .broker import RedisBroker
from .metrics import MODES, MetricsStore
from .scenarios import run_direct_scenario, run_pubsub_scenario, run_queue_scenario


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
            else:
                payload.append(store.read_mode(mode))
        return jsonify({"metrics": payload, "measurements": store.measurements()})

    @app.post("/api/reset")
    def reset():
        deleted = MetricsStore(redis_client).reset_all()
        return jsonify({"deleted_keys": deleted})

    @app.post("/api/scenario")
    def scenario():
        payload = request.get_json(silent=True) or {}
        mode = str(payload.get("mode", "list"))
        jobs = int(payload.get("jobs", 40))
        burst = int(payload.get("burst", 20))
        workers = int(payload.get("workers", 2))
        processing_ms = int(payload.get("processing_ms", 300))

        if mode == "direct":
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
            )
        elif mode in ("list", "stream", "zset"):
            result = run_queue_scenario(
                redis_client,
                mode=mode,
                jobs=jobs,
                burst=burst,
                workers=workers,
                processing_ms=processing_ms,
            )
        else:
            return jsonify({"error": "mode must be direct, pubsub, list, stream or zset"}), 400
        return jsonify(result)

    return app
