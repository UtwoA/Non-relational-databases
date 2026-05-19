from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from .models import Employer, RegionStats, Vacancy


class JobMarketRepository(ABC):
    @abstractmethod
    def upsert_employer(self, employer: Employer) -> Employer:
        raise NotImplementedError

    @abstractmethod
    def get_employer(self, employer_id: UUID) -> Employer | None:
        raise NotImplementedError

    @abstractmethod
    def delete_employer(self, employer_id: UUID) -> bool:
        raise NotImplementedError

    @abstractmethod
    def upsert_vacancy(self, vacancy: Vacancy) -> Vacancy:
        raise NotImplementedError

    @abstractmethod
    def get_vacancy(self, vacancy_id: UUID) -> Vacancy | None:
        raise NotImplementedError

    @abstractmethod
    def delete_vacancy(self, vacancy_id: UUID) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_recent_vacancies(self, limit: int = 50) -> list[Vacancy]:
        raise NotImplementedError

    @abstractmethod
    def list_vacancies_by_employer(self, employer_id: UUID, limit: int = 50) -> list[Vacancy]:
        raise NotImplementedError

    @abstractmethod
    def list_vacancies_by_profession(self, profession: str, limit: int = 50) -> list[Vacancy]:
        raise NotImplementedError

    @abstractmethod
    def list_vacancies_by_region(self, country: str, region: str, limit: int = 50) -> list[Vacancy]:
        raise NotImplementedError

    @abstractmethod
    def list_remote_vacancies(self, remote: bool, limit: int = 50) -> list[Vacancy]:
        raise NotImplementedError

    @abstractmethod
    def list_vacancies_by_employment_type(self, employment_type: str, limit: int = 50) -> list[Vacancy]:
        raise NotImplementedError

    @abstractmethod
    def list_vacancies_by_experience_level(self, experience_level: str, limit: int = 50) -> list[Vacancy]:
        raise NotImplementedError

    @abstractmethod
    def list_vacancies_by_city(self, country: str, city: str, limit: int = 50) -> list[Vacancy]:
        raise NotImplementedError

    @abstractmethod
    def get_region_stats(self, country: str, region: str) -> RegionStats | None:
        raise NotImplementedError
