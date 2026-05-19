from __future__ import annotations

import os
import time
from pathlib import Path
from flask import Flask, redirect, render_template, request, url_for

from src.cache_demo.cache import RedisCache
from src.cache_demo.decorators import redis_cached
from .report import build_directory_report
from .store import UserStore, create_redis_client


def create_app() -> Flask:
    base_dir = Path(__file__).resolve().parents[2]
    app = Flask(__name__, template_folder=str(base_dir / "templates"))
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "practice3-secret-key")

    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    client = create_redis_client(redis_url)
    store = UserStore(client)
    cache = RedisCache(url=redis_url)
    cached_report = redis_cached(cache, ttl_seconds=30)(build_directory_report)

    @app.get("/")
    def index():
        users = store.list_users()
        started = time.perf_counter()
        report = cached_report(users)
        elapsed = time.perf_counter() - started
        return render_template(
            "index.html",
            users=users,
            report=report,
            elapsed=elapsed,
            message=request.args.get("message", ""),
        )

    @app.post("/users")
    def add_user():
        name = request.form.get("name", "")
        try:
            user = store.add_user(name)
        except ValueError as exc:
            return redirect(url_for("index", message=str(exc)))
        return redirect(url_for("index", message=f"User {user.name} added"))

    @app.post("/reset")
    def reset():
        store.clear()
        return redirect(url_for("index", message="All users remved"))

    return app
