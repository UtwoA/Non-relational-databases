from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from uuid import UUID


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_text(value: str) -> str:
    return " ".join(value.strip().split()).lower()


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return normalize_text(value)


@dataclass(slots=True)
class Employer:
    employer_id: UUID
    name: str
    industry: str
    website: str | None
    country: str
    city: str
    active: bool = True
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class Vacancy:
    vacancy_id: UUID
    employer_id: UUID
    employer_name: str
    title: str
    profession: str
    country: str
    region: str
    city: str
    remote: bool
    employment_type: str
    experience_level: str
    salary_from: int | None
    salary_to: int | None
    currency: str
    posted_at: datetime
    description: str
    skills: tuple[str, ...]
    active: bool = True
    updated_at: datetime = field(default_factory=utcnow)

    @property
    def posted_date(self) -> date:
        return self.posted_at.date()


@dataclass(slots=True)
class RegionStats:
    country: str
    region: str
    posted_date: date
    vacancy_count: int
    average_salary_from: float | None
    average_salary_to: float | None
    remote_count: int
    active_count: int
    updated_at: datetime = field(default_factory=utcnow)
