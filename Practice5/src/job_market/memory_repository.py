from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import date
from statistics import fmean
from uuid import UUID

from .models import Employer, RegionStats, Vacancy, utcnow
from .repository import JobMarketRepository
from .services import now_utc, normalize_text


class InMemoryJobMarketRepository(JobMarketRepository):
    def __init__(self) -> None:
        self._employers: dict[UUID, Employer] = {}
        self._vacancies: dict[UUID, Vacancy] = {}
        self._region_stats: dict[tuple[str, str], RegionStats] = {}

    def upsert_employer(self, employer: Employer) -> Employer:
        updated = replace(employer, updated_at=now_utc())
        if employer.employer_id in self._employers:
            created_at = self._employers[employer.employer_id].created_at
            updated = replace(updated, created_at=created_at)
        self._employers[updated.employer_id] = updated
        return updated

    def get_employer(self, employer_id: UUID) -> Employer | None:
        return self._employers.get(employer_id)

    def delete_employer(self, employer_id: UUID) -> bool:
        return self._employers.pop(employer_id, None) is not None

    def list_employers(self) -> list[Employer]:
        return sorted(self._employers.values(), key=lambda item: item.name.lower())

    def upsert_vacancy(self, vacancy: Vacancy) -> Vacancy:
        old = self._vacancies.get(vacancy.vacancy_id)
        updated = replace(vacancy, updated_at=now_utc())
        if old is not None:
            updated = replace(updated, posted_at=old.posted_at) if vacancy.posted_at == old.posted_at else updated
        self._vacancies[updated.vacancy_id] = updated
        for country, region in self._affected_regions(old, updated):
            self.rebuild_region_stats(country, region)
        return updated

    def get_vacancy(self, vacancy_id: UUID) -> Vacancy | None:
        return self._vacancies.get(vacancy_id)

    def delete_vacancy(self, vacancy_id: UUID) -> bool:
        old = self._vacancies.pop(vacancy_id, None)
        if old is None:
            return False
        for country, region in self._affected_regions(old, None):
            self.rebuild_region_stats(country, region)
        return True

    def list_vacancies_by_employer(self, employer_id: UUID, limit: int = 50) -> list[Vacancy]:
        items = [item for item in self._vacancies.values() if item.employer_id == employer_id]
        return self._sorted_vacancies(items)[:limit]

    def list_vacancies_by_profession(self, profession: str, limit: int = 50) -> list[Vacancy]:
        normalized = normalize_text(profession)
        items = [item for item in self._vacancies.values() if item.profession == normalized]
        return self._sorted_vacancies(items)[:limit]

    def list_vacancies_by_region(self, country: str, region: str, limit: int = 50) -> list[Vacancy]:
        normalized_country = normalize_text(country)
        normalized_region = normalize_text(region)
        items = [
            item
            for item in self._vacancies.values()
            if item.country == normalized_country and item.region == normalized_region
        ]
        return self._sorted_vacancies(items)[:limit]

    def list_remote_vacancies(self, remote: bool, limit: int = 50) -> list[Vacancy]:
        items = [item for item in self._vacancies.values() if item.remote == remote]
        return self._sorted_vacancies(items)[:limit]

    def get_region_stats(self, country: str, region: str) -> RegionStats | None:
        key = (normalize_text(country), normalize_text(region))
        return self._region_stats.get(key)

    def rebuild_region_stats(self, country: str, region: str) -> RegionStats | None:
        normalized_country = normalize_text(country)
        normalized_region = normalize_text(region)
        items = [
            item
            for item in self._vacancies.values()
            if item.country == normalized_country and item.region == normalized_region and item.active
        ]
        if not items:
            self._region_stats.pop((normalized_country, normalized_region), None)
            return None

        salaries_from = [item.salary_from for item in items if item.salary_from is not None]
        salaries_to = [item.salary_to for item in items if item.salary_to is not None]
        stats = RegionStats(
            country=normalized_country,
            region=normalized_region,
            posted_date=max(item.posted_date for item in items),
            vacancy_count=len(items),
            average_salary_from=fmean(salaries_from) if salaries_from else None,
            average_salary_to=fmean(salaries_to) if salaries_to else None,
            remote_count=sum(1 for item in items if item.remote),
            active_count=sum(1 for item in items if item.active),
        )
        self._region_stats[(normalized_country, normalized_region)] = stats
        return stats

    def list_region_stats(self) -> list[RegionStats]:
        return sorted(self._region_stats.values(), key=lambda item: (item.country, item.region))

    def _affected_regions(
        self, old: Vacancy | None, new: Vacancy | None
    ) -> set[tuple[str, str]]:
        regions: set[tuple[str, str]] = set()
        if old is not None:
            regions.add((old.country, old.region))
        if new is not None:
            regions.add((new.country, new.region))
        return regions

    def _sorted_vacancies(self, items: list[Vacancy]) -> list[Vacancy]:
        return sorted(items, key=lambda item: (item.posted_at, item.vacancy_id), reverse=True)
