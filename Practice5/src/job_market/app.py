from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from .cassandra_repository import CassandraJobMarketRepository
from .memory_repository import InMemoryJobMarketRepository
from .repository import JobMarketRepository
from .services import (
    coerce_limit,
    employer_from_payload,
    parse_uuid,
    serialize_employer,
    serialize_stats,
    serialize_vacancy,
    vacancy_from_payload,
)


def _json_error(message: str, status: int = 400):
    response = jsonify({"error": message})
    response.status_code = status
    return response


def _get_repository(backend: str | None) -> JobMarketRepository:
    backend = (backend or "memory").lower().strip()
    if backend == "memory":
        return InMemoryJobMarketRepository()
    if backend == "cassandra":
        return CassandraJobMarketRepository.from_env()
    raise ValueError(f"Unknown backend '{backend}'")


def create_app(repository: JobMarketRepository | None = None, backend: str | None = None) -> Flask:
    app = Flask(__name__, template_folder="../../templates")
    repo = repository or _get_repository(backend)
    app.extensions["job_market_repository"] = repo

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith("/api/"):
            return _json_error("API endpoint not found", 404)
        return error

    @app.errorhandler(405)
    def method_not_allowed(error):
        if request.path.startswith("/api/"):
            return _json_error("Method not allowed", 405)
        return error

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "backend": repo.__class__.__name__})

    @app.post("/api/employers")
    def create_employer():
        try:
            employer = employer_from_payload(request.get_json(force=True, silent=False) or {})
        except (TypeError, ValueError) as exc:
            return _json_error(str(exc))
        return jsonify(serialize_employer(repo.upsert_employer(employer))), 201

    @app.get("/api/employers/<employer_id>")
    def get_employer(employer_id: str):
        try:
            employer = repo.get_employer(parse_uuid(employer_id))
        except ValueError:
            return _json_error("Invalid employer_id")
        if employer is None:
            return _json_error("Employer not found", 404)
        return jsonify(serialize_employer(employer))

    @app.put("/api/employers/<employer_id>")
    def update_employer(employer_id: str):
        try:
            payload = request.get_json(force=True, silent=False) or {}
            employer = employer_from_payload(payload, employer_id=parse_uuid(employer_id))
        except (TypeError, ValueError) as exc:
            return _json_error(str(exc))
        return jsonify(serialize_employer(repo.upsert_employer(employer)))

    @app.delete("/api/employers/<employer_id>")
    def delete_employer(employer_id: str):
        try:
            deleted = repo.delete_employer(parse_uuid(employer_id))
        except ValueError:
            return _json_error("Invalid employer_id")
        if not deleted:
            return _json_error("Employer not found", 404)
        return jsonify({"deleted": True})

    @app.post("/api/vacancies")
    def create_vacancy():
        try:
            vacancy = vacancy_from_payload(request.get_json(force=True, silent=False) or {})
        except (TypeError, ValueError) as exc:
            return _json_error(str(exc))
        return jsonify(serialize_vacancy(repo.upsert_vacancy(vacancy))), 201

    @app.get("/api/vacancies")
    @app.get("/api/vacancies/")
    def list_vacancies():
        try:
            items = repo.list_recent_vacancies(coerce_limit(request.args.get("limit")))
        except ValueError as exc:
            return _json_error(str(exc))
        return jsonify([serialize_vacancy(item) for item in items])

    @app.get("/api/vacancies/<vacancy_id>")
    def get_vacancy(vacancy_id: str):
        try:
            vacancy = repo.get_vacancy(parse_uuid(vacancy_id))
        except ValueError:
            return _json_error("Invalid vacancy_id")
        if vacancy is None:
            return _json_error("Vacancy not found", 404)
        return jsonify(serialize_vacancy(vacancy))

    @app.put("/api/vacancies/<vacancy_id>")
    def update_vacancy(vacancy_id: str):
        try:
            parsed_id = parse_uuid(vacancy_id)
            existing = repo.get_vacancy(parsed_id)
            payload = request.get_json(force=True, silent=False) or {}
            vacancy = vacancy_from_payload(
                payload,
                vacancy_id=parsed_id,
                existing_posted_at=existing.posted_at if existing is not None else None,
            )
        except (TypeError, ValueError) as exc:
            return _json_error(str(exc))
        return jsonify(serialize_vacancy(repo.upsert_vacancy(vacancy)))

    @app.delete("/api/vacancies/<vacancy_id>")
    def delete_vacancy(vacancy_id: str):
        try:
            deleted = repo.delete_vacancy(parse_uuid(vacancy_id))
        except ValueError:
            return _json_error("Invalid vacancy_id")
        if not deleted:
            return _json_error("Vacancy not found", 404)
        return jsonify({"deleted": True})

    @app.get("/api/vacancies/by-employer/<employer_id>")
    def vacancies_by_employer(employer_id: str):
        try:
            items = repo.list_vacancies_by_employer(parse_uuid(employer_id), coerce_limit(request.args.get("limit")))
        except ValueError as exc:
            return _json_error(str(exc))
        return jsonify([serialize_vacancy(item) for item in items])

    @app.get("/api/vacancies/by-profession/<profession>")
    def vacancies_by_profession(profession: str):
        try:
            items = repo.list_vacancies_by_profession(profession, coerce_limit(request.args.get("limit")))
        except ValueError as exc:
            return _json_error(str(exc))
        return jsonify([serialize_vacancy(item) for item in items])

    @app.get("/api/vacancies/by-region")
    def vacancies_by_region():
        country = request.args.get("country")
        region = request.args.get("region")
        if not country or not region:
            return _json_error("country and region are required")
        try:
            items = repo.list_vacancies_by_region(country, region, coerce_limit(request.args.get("limit")))
        except ValueError as exc:
            return _json_error(str(exc))
        return jsonify([serialize_vacancy(item) for item in items])

    @app.get("/api/vacancies/remote")
    def remote_vacancies():
        remote_value = request.args.get("remote", "true").strip().lower()
        remote = remote_value in {"true", "1", "yes", "y"}
        try:
            items = repo.list_remote_vacancies(remote, coerce_limit(request.args.get("limit")))
        except ValueError as exc:
            return _json_error(str(exc))
        return jsonify([serialize_vacancy(item) for item in items])

    @app.get("/api/vacancies/by-employment-type/<employment_type>")
    def vacancies_by_employment_type(employment_type: str):
        try:
            items = repo.list_vacancies_by_employment_type(employment_type, coerce_limit(request.args.get("limit")))
        except ValueError as exc:
            return _json_error(str(exc))
        return jsonify([serialize_vacancy(item) for item in items])

    @app.get("/api/vacancies/by-experience-level/<experience_level>")
    def vacancies_by_experience_level(experience_level: str):
        try:
            items = repo.list_vacancies_by_experience_level(experience_level, coerce_limit(request.args.get("limit")))
        except ValueError as exc:
            return _json_error(str(exc))
        return jsonify([serialize_vacancy(item) for item in items])

    @app.get("/api/vacancies/by-city")
    def vacancies_by_city():
        country = request.args.get("country")
        city = request.args.get("city")
        if not country or not city:
            return _json_error("country and city are required")
        try:
            items = repo.list_vacancies_by_city(country, city, coerce_limit(request.args.get("limit")))
        except ValueError as exc:
            return _json_error(str(exc))
        return jsonify([serialize_vacancy(item) for item in items])

    @app.get("/api/stats/regions")
    def region_stats():
        country = request.args.get("country")
        region = request.args.get("region")
        if not country or not region:
            return _json_error("country and region are required")
        stats = repo.get_region_stats(country, region)
        if stats is None:
            return _json_error("Stats not found", 404)
        return jsonify(serialize_stats(stats))

    @app.post("/api/admin/seed")
    def seed():
        from .seed import seed_repository

        return jsonify(seed_repository(repo))

    return app
