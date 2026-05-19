from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from .models import Employer, RegionStats, Vacancy, normalize_text


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: str | None) -> datetime:
    if value is None:
        return now_utc()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_uuid(value: str | UUID | None) -> UUID:
    if value is None:
        return uuid4()
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def parse_bool(value: Any, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    raise ValueError(f"Field '{field_name}' must be boolean")


def coerce_limit(value: str | None, default: int = 50, maximum: int = 200) -> int:
    if value is None:
        return default
    limit = int(value)
    if limit < 1:
        raise ValueError("limit must be positive")
    return min(limit, maximum)


def employer_from_payload(payload: dict[str, Any], employer_id: UUID | None = None) -> Employer:
    for field_name in ["name", "industry", "country", "city"]:
        if not payload.get(field_name):
            raise ValueError(f"Field '{field_name}' is required")
    return Employer(
        employer_id=parse_uuid(employer_id or payload.get("employer_id")),
        name=str(payload["name"]).strip(),
        industry=str(payload["industry"]).strip(),
        website=str(payload["website"]).strip() if payload.get("website") else None,
        country=normalize_text(str(payload["country"])),
        city=normalize_text(str(payload["city"])),
        active=parse_bool(payload.get("active", True), "active"),
    )


def vacancy_from_payload(
    payload: dict[str, Any],
    vacancy_id: UUID | None = None,
    existing_posted_at: datetime | None = None,
) -> Vacancy:
    required = [
        "employer_id",
        "employer_name",
        "title",
        "profession",
        "country",
        "region",
        "city",
        "employment_type",
        "experience_level",
        "currency",
        "description",
    ]
    for field_name in required:
        if not payload.get(field_name):
            raise ValueError(f"Field '{field_name}' is required")

    skills = payload.get("skills", [])
    if isinstance(skills, str):
        skills = [skills]
    if not isinstance(skills, list):
        raise ValueError("Field 'skills' must be a list")

    return Vacancy(
        vacancy_id=parse_uuid(vacancy_id or payload.get("vacancy_id")),
        employer_id=parse_uuid(payload["employer_id"]),
        employer_name=str(payload["employer_name"]).strip(),
        title=str(payload["title"]).strip(),
        profession=normalize_text(str(payload["profession"])),
        country=normalize_text(str(payload["country"])),
        region=normalize_text(str(payload["region"])),
        city=normalize_text(str(payload["city"])),
        remote=parse_bool(payload.get("remote", False), "remote"),
        employment_type=str(payload["employment_type"]).strip(),
        experience_level=str(payload["experience_level"]).strip(),
        salary_from=payload.get("salary_from"),
        salary_to=payload.get("salary_to"),
        currency=str(payload["currency"]).strip().upper(),
        posted_at=parse_datetime(payload.get("posted_at")) if payload.get("posted_at") else existing_posted_at or now_utc(),
        description=str(payload["description"]).strip(),
        skills=tuple(sorted({str(skill).strip().lower() for skill in skills if str(skill).strip()})),
        active=parse_bool(payload.get("active", True), "active"),
    )


def serialize_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def serialize_date(value: date) -> str:
    if hasattr(value, "date") and not isinstance(value.date, int):
        value = value.date()
    return value.isoformat()


def serialize_employer(employer: Employer) -> dict[str, Any]:
    return {
        "employer_id": str(employer.employer_id),
        "name": employer.name,
        "industry": employer.industry,
        "website": employer.website,
        "country": employer.country,
        "city": employer.city,
        "active": employer.active,
        "created_at": serialize_datetime(employer.created_at),
        "updated_at": serialize_datetime(employer.updated_at),
    }


def serialize_vacancy(vacancy: Vacancy) -> dict[str, Any]:
    return {
        "vacancy_id": str(vacancy.vacancy_id),
        "employer_id": str(vacancy.employer_id),
        "employer_name": vacancy.employer_name,
        "title": vacancy.title,
        "profession": vacancy.profession,
        "country": vacancy.country,
        "region": vacancy.region,
        "city": vacancy.city,
        "remote": vacancy.remote,
        "employment_type": vacancy.employment_type,
        "experience_level": vacancy.experience_level,
        "salary_from": vacancy.salary_from,
        "salary_to": vacancy.salary_to,
        "currency": vacancy.currency,
        "posted_at": serialize_datetime(vacancy.posted_at),
        "description": vacancy.description,
        "skills": list(vacancy.skills),
        "active": vacancy.active,
        "updated_at": serialize_datetime(vacancy.updated_at),
    }


def serialize_stats(stats: RegionStats) -> dict[str, Any]:
    return {
        "country": stats.country,
        "region": stats.region,
        "posted_date": serialize_date(stats.posted_date),
        "vacancy_count": stats.vacancy_count,
        "average_salary_from": stats.average_salary_from,
        "average_salary_to": stats.average_salary_to,
        "remote_count": stats.remote_count,
        "active_count": stats.active_count,
        "updated_at": serialize_datetime(stats.updated_at),
    }
