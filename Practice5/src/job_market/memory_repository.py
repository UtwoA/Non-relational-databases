from __future__ import annotations

from dataclasses import replace
from statistics import fmean
from uuid import UUID

from .models import Employer, RegionStats, Vacancy, normalize_text
from .repository import JobMarketRepository
from .services import now_utc


class InMemoryJobMarketRepository(JobMarketRepository):
    def __init__(self) -> None:
        self._employers: dict[UUID, Employer] = {}
        self._vacancies: dict[UUID, Vacancy] = {}
        self._region_stats: dict[tuple[str, str], RegionStats] = {}

    def upsert_employer(self, employer: Employer) -> Employer:
        updated = replace(employer, updated_at=now_utc())
        existing = self._employers.get(employer.employer_id)
        if existing is not None:
            updated = replace(updated, created_at=existing.created_at)
        self._employers[updated.employer_id] = updated
        return updated

    def get_employer(self, employer_id: UUID) -> Employer | None:
        return self._employers.get(employer_id)

    def delete_employer(self, employer_id: UUID) -> bool:
        return self._employers.pop(employer_id, None) is not None

    def upsert_vacancy(self, vacancy: Vacancy) -> Vacancy:
        existing = self._vacancies.get(vacancy.vacancy_id)
        updated = replace(vacancy, updated_at=now_utc())
        if existing is not None and vacancy.posted_at == existing.posted_at:
            updated = replace(updated, posted_at=existing.posted_at)
        self._vacancies[updated.vacancy_id] = updated
        for country, region in self._affected_regions(existing, updated):
            self._rebuild_region_stats(country, region)
        return updated

    def get_vacancy(self, vacancy_id: UUID) -> Vacancy | None:
        return self._vacancies.get(vacancy_id)

    def delete_vacancy(self, vacancy_id: UUID) -> bool:
        existing = self._vacancies.pop(vacancy_id, None)
        if existing is None:
            return False
        self._rebuild_region_stats(existing.country, existing.region)
        return True

    def list_recent_vacancies(self, limit: int = 50) -> list[Vacancy]:
        return self._sorted(list(self._vacancies.values()))[:limit]

    def list_vacancies_by_employer(self, employer_id: UUID, limit: int = 50) -> list[Vacancy]:
        return self._sorted([item for item in self._vacancies.values() if item.employer_id == employer_id])[:limit]

    def list_vacancies_by_profession(self, profession: str, limit: int = 50) -> list[Vacancy]:
        profession = normalize_text(profession)
        return self._sorted([item for item in self._vacancies.values() if item.profession == profession])[:limit]

    def list_vacancies_by_region(self, country: str, region: str, limit: int = 50) -> list[Vacancy]:
        country = normalize_text(country)
        region = normalize_text(region)
        return self._sorted(
            [item for item in self._vacancies.values() if item.country == country and item.region == region]
        )[:limit]

    def list_remote_vacancies(self, remote: bool, limit: int = 50) -> list[Vacancy]:
        return self._sorted([item for item in self._vacancies.values() if item.remote == remote])[:limit]

    def list_vacancies_by_employment_type(self, employment_type: str, limit: int = 50) -> list[Vacancy]:
        employment_type = normalize_text(employment_type)
        return self._sorted(
            [item for item in self._vacancies.values() if normalize_text(item.employment_type) == employment_type]
        )[:limit]

    def list_vacancies_by_experience_level(self, experience_level: str, limit: int = 50) -> list[Vacancy]:
        experience_level = normalize_text(experience_level)
        return self._sorted(
            [item for item in self._vacancies.values() if normalize_text(item.experience_level) == experience_level]
        )[:limit]

    def list_vacancies_by_city(self, country: str, city: str, limit: int = 50) -> list[Vacancy]:
        country = normalize_text(country)
        city = normalize_text(city)
        return self._sorted(
            [item for item in self._vacancies.values() if item.country == country and item.city == city]
        )[:limit]

    def get_region_stats(self, country: str, region: str) -> RegionStats | None:
        return self._region_stats.get((normalize_text(country), normalize_text(region)))

    def _rebuild_region_stats(self, country: str, region: str) -> RegionStats | None:
        country = normalize_text(country)
        region = normalize_text(region)
        vacancies = [
            item
            for item in self._vacancies.values()
            if item.country == country and item.region == region and item.active
        ]
        if not vacancies:
            self._region_stats.pop((country, region), None)
            return None

        salaries_from = [item.salary_from for item in vacancies if item.salary_from is not None]
        salaries_to = [item.salary_to for item in vacancies if item.salary_to is not None]
        stats = RegionStats(
            country=country,
            region=region,
            posted_date=max(item.posted_date for item in vacancies),
            vacancy_count=len(vacancies),
            average_salary_from=fmean(salaries_from) if salaries_from else None,
            average_salary_to=fmean(salaries_to) if salaries_to else None,
            remote_count=sum(1 for item in vacancies if item.remote),
            active_count=sum(1 for item in vacancies if item.active),
        )
        self._region_stats[(country, region)] = stats
        return stats

    def _affected_regions(self, old: Vacancy | None, new: Vacancy | None) -> set[tuple[str, str]]:
        regions: set[tuple[str, str]] = set()
        if old is not None:
            regions.add((old.country, old.region))
        if new is not None:
            regions.add((new.country, new.region))
        return regions

    @staticmethod
    def _sorted(items: list[Vacancy]) -> list[Vacancy]:
        return sorted(items, key=lambda item: (item.posted_at, item.vacancy_id), reverse=True)
