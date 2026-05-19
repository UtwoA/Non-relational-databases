from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from statistics import fmean
from uuid import UUID

from .models import Employer, RegionStats, Vacancy
from .repository import JobMarketRepository
from .services import normalize_text, now_utc


class CassandraJobMarketRepository(JobMarketRepository):
    def __init__(self, session) -> None:
        self.session = session
        self._prepare_statements()

    @classmethod
    def from_env(cls) -> "CassandraJobMarketRepository":
        from cassandra.cluster import Cluster
        from cassandra.auth import PlainTextAuthProvider

        contact_points = [host.strip() for host in __import__("os").getenv("CASSANDRA_HOSTS", "127.0.0.1").split(",")]
        port = int(__import__("os").getenv("CASSANDRA_PORT", "9042"))
        username = __import__("os").getenv("CASSANDRA_USERNAME")
        password = __import__("os").getenv("CASSANDRA_PASSWORD")
        keyspace = __import__("os").getenv("CASSANDRA_KEYSPACE", "job_market")
        auth_provider = None
        if username and password:
            auth_provider = PlainTextAuthProvider(username=username, password=password)
        cluster = Cluster(contact_points=contact_points, port=port, auth_provider=auth_provider)
        session = cluster.connect()
        cls._ensure_schema(session, keyspace)
        session.set_keyspace(keyspace)
        return cls(session)

    @staticmethod
    def _ensure_schema(session, keyspace: str) -> None:
        session.execute(
            f"""
            CREATE KEYSPACE IF NOT EXISTS {keyspace}
            WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 1}}
            """
        )
        session.set_keyspace(keyspace)
        schema_path = Path(__file__).resolve().parents[2] / "cassandra" / "schema.cql"
        if schema_path.exists():
            for statement in schema_path.read_text(encoding="utf-8").split(";"):
                cleaned = statement.strip()
                if cleaned:
                    session.execute(cleaned)
        else:
            for statement in CassandraJobMarketRepository._inline_schema():
                session.execute(statement)

    @staticmethod
    def _inline_schema() -> list[str]:
        return [
            """
            CREATE TABLE IF NOT EXISTS employers_by_id (
                employer_id uuid PRIMARY KEY,
                name text,
                industry text,
                website text,
                country text,
                city text,
                active boolean,
                created_at timestamp,
                updated_at timestamp
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS vacancies_by_id (
                vacancy_id uuid PRIMARY KEY,
                employer_id uuid,
                employer_name text,
                title text,
                profession text,
                country text,
                region text,
                city text,
                remote boolean,
                employment_type text,
                experience_level text,
                salary_from int,
                salary_to int,
                currency text,
                posted_at timestamp,
                description text,
                skills set<text>,
                active boolean,
                updated_at timestamp
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS vacancies_by_employer (
                employer_id uuid,
                posted_date date,
                posted_at timestamp,
                vacancy_id uuid,
                title text,
                profession text,
                country text,
                region text,
                city text,
                remote boolean,
                salary_from int,
                salary_to int,
                currency text,
                active boolean,
                PRIMARY KEY ((employer_id), posted_date, posted_at, vacancy_id)
            ) WITH CLUSTERING ORDER BY (posted_date DESC, posted_at DESC, vacancy_id ASC)
            """,
            """
            CREATE TABLE IF NOT EXISTS vacancies_by_profession (
                profession text,
                posted_date date,
                posted_at timestamp,
                vacancy_id uuid,
                employer_id uuid,
                employer_name text,
                title text,
                country text,
                region text,
                city text,
                remote boolean,
                salary_from int,
                salary_to int,
                currency text,
                active boolean,
                PRIMARY KEY ((profession), posted_date, posted_at, vacancy_id)
            ) WITH CLUSTERING ORDER BY (posted_date DESC, posted_at DESC, vacancy_id ASC)
            """,
            """
            CREATE TABLE IF NOT EXISTS vacancies_by_region (
                country text,
                region text,
                posted_date date,
                posted_at timestamp,
                vacancy_id uuid,
                employer_id uuid,
                employer_name text,
                title text,
                profession text,
                city text,
                remote boolean,
                salary_from int,
                salary_to int,
                currency text,
                active boolean,
                PRIMARY KEY ((country, region), posted_date, posted_at, vacancy_id)
            ) WITH CLUSTERING ORDER BY (posted_date DESC, posted_at DESC, vacancy_id ASC)
            """,
            """
            CREATE TABLE IF NOT EXISTS vacancies_by_remote (
                remote boolean,
                posted_date date,
                posted_at timestamp,
                vacancy_id uuid,
                employer_id uuid,
                employer_name text,
                title text,
                profession text,
                country text,
                region text,
                city text,
                salary_from int,
                salary_to int,
                currency text,
                active boolean,
                PRIMARY KEY ((remote), posted_date, posted_at, vacancy_id)
            ) WITH CLUSTERING ORDER BY (posted_date DESC, posted_at DESC, vacancy_id ASC)
            """,
            """
            CREATE TABLE IF NOT EXISTS region_stats_by_key (
                country text,
                region text,
                posted_date date,
                vacancy_count int,
                average_salary_from double,
                average_salary_to double,
                remote_count int,
                active_count int,
                updated_at timestamp,
                PRIMARY KEY ((country, region), posted_date)
            ) WITH CLUSTERING ORDER BY (posted_date DESC)
            """,
        ]

    def _prepare_statements(self) -> None:
        self._insert_employer = self.session.prepare(
            """
            INSERT INTO employers_by_id
            (employer_id, name, industry, website, country, city, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        self._select_employer = self.session.prepare("SELECT * FROM employers_by_id WHERE employer_id = ?")
        self._delete_employer = self.session.prepare("DELETE FROM employers_by_id WHERE employer_id = ?")
        self._select_all_employers = self.session.prepare("SELECT * FROM employers_by_id")

        self._select_vacancy = self.session.prepare("SELECT * FROM vacancies_by_id WHERE vacancy_id = ?")
        self._delete_vacancy = self.session.prepare("DELETE FROM vacancies_by_id WHERE vacancy_id = ?")
        self._insert_vacancy = self.session.prepare(
            """
            INSERT INTO vacancies_by_id
            (vacancy_id, employer_id, employer_name, title, profession, country, region, city, remote,
             employment_type, experience_level, salary_from, salary_to, currency, posted_at, description,
             skills, active, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )

        self._insert_vacancy_employer = self.session.prepare(
            """
            INSERT INTO vacancies_by_employer
            (employer_id, posted_date, posted_at, vacancy_id, title, profession, country, region, city,
             remote, salary_from, salary_to, currency, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        self._delete_vacancy_employer = self.session.prepare(
            """
            DELETE FROM vacancies_by_employer
            WHERE employer_id = ? AND posted_date = ? AND posted_at = ? AND vacancy_id = ?
            """
        )
        self._select_vacancies_by_employer = self.session.prepare(
            """
            SELECT * FROM vacancies_by_employer WHERE employer_id = ?
            """
        )

        self._insert_vacancy_profession = self.session.prepare(
            """
            INSERT INTO vacancies_by_profession
            (profession, posted_date, posted_at, vacancy_id, employer_id, employer_name, title, country,
             region, city, remote, salary_from, salary_to, currency, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        self._delete_vacancy_profession = self.session.prepare(
            """
            DELETE FROM vacancies_by_profession
            WHERE profession = ? AND posted_date = ? AND posted_at = ? AND vacancy_id = ?
            """
        )
        self._select_vacancies_by_profession = self.session.prepare(
            "SELECT * FROM vacancies_by_profession WHERE profession = ?"
        )

        self._insert_vacancy_region = self.session.prepare(
            """
            INSERT INTO vacancies_by_region
            (country, region, posted_date, posted_at, vacancy_id, employer_id, employer_name, title,
             profession, city, remote, salary_from, salary_to, currency, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        self._delete_vacancy_region = self.session.prepare(
            """
            DELETE FROM vacancies_by_region
            WHERE country = ? AND region = ? AND posted_date = ? AND posted_at = ? AND vacancy_id = ?
            """
        )
        self._select_vacancies_by_region = self.session.prepare(
            "SELECT * FROM vacancies_by_region WHERE country = ? AND region = ?"
        )

        self._insert_vacancy_remote = self.session.prepare(
            """
            INSERT INTO vacancies_by_remote
            (remote, posted_date, posted_at, vacancy_id, employer_id, employer_name, title, profession,
             country, region, city, salary_from, salary_to, currency, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        self._delete_vacancy_remote = self.session.prepare(
            """
            DELETE FROM vacancies_by_remote
            WHERE remote = ? AND posted_date = ? AND posted_at = ? AND vacancy_id = ?
            """
        )
        self._select_vacancies_by_remote = self.session.prepare(
            "SELECT * FROM vacancies_by_remote WHERE remote = ?"
        )

        self._insert_region_stats = self.session.prepare(
            """
            INSERT INTO region_stats_by_key
            (country, region, posted_date, vacancy_count, average_salary_from, average_salary_to,
             remote_count, active_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        self._delete_region_stats = self.session.prepare(
            "DELETE FROM region_stats_by_key WHERE country = ? AND region = ? AND posted_date = ?"
        )
        self._select_region_stats = self.session.prepare(
            "SELECT * FROM region_stats_by_key WHERE country = ? AND region = ?"
        )
        self._select_all_region_stats = self.session.prepare("SELECT * FROM region_stats_by_key")

    def upsert_employer(self, employer: Employer) -> Employer:
        updated = replace(employer, updated_at=now_utc())
        existing = self.get_employer(updated.employer_id)
        if existing is not None:
            updated = replace(updated, created_at=existing.created_at)
        self.session.execute(
            self._insert_employer,
            (
                updated.employer_id,
                updated.name,
                updated.industry,
                updated.website,
                updated.country,
                updated.city,
                updated.active,
                updated.created_at,
                updated.updated_at,
            ),
        )
        return updated

    def get_employer(self, employer_id: UUID) -> Employer | None:
        row = self.session.execute(self._select_employer, (employer_id,)).one()
        if row is None:
            return None
        return Employer(
            employer_id=row.employer_id,
            name=row.name,
            industry=row.industry,
            website=row.website,
            country=row.country,
            city=row.city,
            active=row.active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def delete_employer(self, employer_id: UUID) -> bool:
        self.session.execute(self._delete_employer, (employer_id,))
        return True

    def list_employers(self) -> list[Employer]:
        rows = self.session.execute(self._select_all_employers)
        return [
            Employer(
                employer_id=row.employer_id,
                name=row.name,
                industry=row.industry,
                website=row.website,
                country=row.country,
                city=row.city,
                active=row.active,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]

    def upsert_vacancy(self, vacancy: Vacancy) -> Vacancy:
        updated = replace(vacancy, updated_at=now_utc())
        existing = self.get_vacancy(updated.vacancy_id)
        if existing is not None:
            self._delete_denormalized(existing)
        self.session.execute(
            self._insert_vacancy,
            (
                updated.vacancy_id,
                updated.employer_id,
                updated.employer_name,
                updated.title,
                updated.profession,
                updated.country,
                updated.region,
                updated.city,
                updated.remote,
                updated.employment_type,
                updated.experience_level,
                updated.salary_from,
                updated.salary_to,
                updated.currency,
                updated.posted_at,
                updated.description,
                set(updated.skills),
                updated.active,
                updated.updated_at,
            ),
        )
        self._insert_denormalized(updated)
        self._rebuild_region_stats(updated.country, updated.region)
        if existing is not None and (existing.country, existing.region) != (updated.country, updated.region):
            self._rebuild_region_stats(existing.country, existing.region)
        return updated

    def get_vacancy(self, vacancy_id: UUID) -> Vacancy | None:
        row = self.session.execute(self._select_vacancy, (vacancy_id,)).one()
        if row is None:
            return None
        return self._vacancy_from_row(row)

    def delete_vacancy(self, vacancy_id: UUID) -> bool:
        existing = self.get_vacancy(vacancy_id)
        if existing is None:
            return False
        self._delete_denormalized(existing)
        self.session.execute(self._delete_vacancy, (vacancy_id,))
        self._rebuild_region_stats(existing.country, existing.region)
        return True

    def list_vacancies_by_employer(self, employer_id: UUID, limit: int = 50) -> list[Vacancy]:
        rows = self.session.execute(self._select_vacancies_by_employer, (employer_id,))
        return [self._vacancy_from_employer_row(row) for row in rows][:limit]

    def list_vacancies_by_profession(self, profession: str, limit: int = 50) -> list[Vacancy]:
        rows = self.session.execute(self._select_vacancies_by_profession, (normalize_text(profession),))
        return [self._vacancy_from_profession_row(row) for row in rows][:limit]

    def list_vacancies_by_region(self, country: str, region: str, limit: int = 50) -> list[Vacancy]:
        rows = self.session.execute(self._select_vacancies_by_region, (normalize_text(country), normalize_text(region)))
        return [self._vacancy_from_region_row(row) for row in rows][:limit]

    def list_remote_vacancies(self, remote: bool, limit: int = 50) -> list[Vacancy]:
        rows = self.session.execute(self._select_vacancies_by_remote, (remote,))
        return [self._vacancy_from_remote_row(row) for row in rows][:limit]

    def get_region_stats(self, country: str, region: str) -> RegionStats | None:
        row = self.session.execute(
            self._select_region_stats,
            (normalize_text(country), normalize_text(region)),
        ).one()
        if row is None:
            return None
        return RegionStats(
            country=row.country,
            region=row.region,
            posted_date=row.posted_date,
            vacancy_count=row.vacancy_count,
            average_salary_from=row.average_salary_from,
            average_salary_to=row.average_salary_to,
            remote_count=row.remote_count,
            active_count=row.active_count,
            updated_at=row.updated_at,
        )

    def rebuild_region_stats(self, country: str, region: str) -> RegionStats | None:
        return self._rebuild_region_stats(normalize_text(country), normalize_text(region))

    def list_region_stats(self) -> list[RegionStats]:
        rows = self.session.execute(self._select_all_region_stats)
        return [
            RegionStats(
                country=row.country,
                region=row.region,
                posted_date=row.posted_date,
                vacancy_count=row.vacancy_count,
                average_salary_from=row.average_salary_from,
                average_salary_to=row.average_salary_to,
                remote_count=row.remote_count,
                active_count=row.active_count,
                updated_at=row.updated_at,
            )
            for row in rows
        ]

    def _insert_denormalized(self, vacancy: Vacancy) -> None:
        row = self._vacancy_tuple(vacancy)
        self.session.execute(self._insert_vacancy_employer, row["employer"])
        self.session.execute(self._insert_vacancy_profession, row["profession"])
        self.session.execute(self._insert_vacancy_region, row["region"])
        self.session.execute(self._insert_vacancy_remote, row["remote"])

    def _delete_denormalized(self, vacancy: Vacancy) -> None:
        self.session.execute(
            self._delete_vacancy_employer,
            (vacancy.employer_id, vacancy.posted_date, vacancy.posted_at, vacancy.vacancy_id),
        )
        self.session.execute(
            self._delete_vacancy_profession,
            (vacancy.profession, vacancy.posted_date, vacancy.posted_at, vacancy.vacancy_id),
        )
        self.session.execute(
            self._delete_vacancy_region,
            (vacancy.country, vacancy.region, vacancy.posted_date, vacancy.posted_at, vacancy.vacancy_id),
        )
        self.session.execute(
            self._delete_vacancy_remote,
            (vacancy.remote, vacancy.posted_date, vacancy.posted_at, vacancy.vacancy_id),
        )

    def _rebuild_region_stats(self, country: str, region: str) -> RegionStats | None:
        rows = self.session.execute(self._select_vacancies_by_region, (country, region))
        vacancies = [self._vacancy_from_region_row(row) for row in rows if row.active]
        if not vacancies:
            existing = self.get_region_stats(country, region)
            if existing is not None:
                self.session.execute(self._delete_region_stats, (country, region, existing.posted_date))
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
        existing = self.get_region_stats(country, region)
        if existing is not None and existing.posted_date != stats.posted_date:
            self.session.execute(self._delete_region_stats, (country, region, existing.posted_date))
        self.session.execute(
            self._insert_region_stats,
            (
                stats.country,
                stats.region,
                stats.posted_date,
                stats.vacancy_count,
                stats.average_salary_from,
                stats.average_salary_to,
                stats.remote_count,
                stats.active_count,
                stats.updated_at,
            ),
        )
        return stats

    def _vacancy_tuple(self, vacancy: Vacancy) -> dict[str, tuple]:
        return {
            "employer": (
                vacancy.employer_id,
                vacancy.posted_date,
                vacancy.posted_at,
                vacancy.vacancy_id,
                vacancy.title,
                vacancy.profession,
                vacancy.country,
                vacancy.region,
                vacancy.city,
                vacancy.remote,
                vacancy.salary_from,
                vacancy.salary_to,
                vacancy.currency,
                vacancy.active,
            ),
            "profession": (
                vacancy.profession,
                vacancy.posted_date,
                vacancy.posted_at,
                vacancy.vacancy_id,
                vacancy.employer_id,
                vacancy.employer_name,
                vacancy.title,
                vacancy.country,
                vacancy.region,
                vacancy.city,
                vacancy.remote,
                vacancy.salary_from,
                vacancy.salary_to,
                vacancy.currency,
                vacancy.active,
            ),
            "region": (
                vacancy.country,
                vacancy.region,
                vacancy.posted_date,
                vacancy.posted_at,
                vacancy.vacancy_id,
                vacancy.employer_id,
                vacancy.employer_name,
                vacancy.title,
                vacancy.profession,
                vacancy.city,
                vacancy.remote,
                vacancy.salary_from,
                vacancy.salary_to,
                vacancy.currency,
                vacancy.active,
            ),
            "remote": (
                vacancy.remote,
                vacancy.posted_date,
                vacancy.posted_at,
                vacancy.vacancy_id,
                vacancy.employer_id,
                vacancy.employer_name,
                vacancy.title,
                vacancy.profession,
                vacancy.country,
                vacancy.region,
                vacancy.city,
                vacancy.salary_from,
                vacancy.salary_to,
                vacancy.currency,
                vacancy.active,
            ),
        }

    def _vacancy_from_row(self, row) -> Vacancy:
        return Vacancy(
            vacancy_id=row.vacancy_id,
            employer_id=row.employer_id,
            employer_name=row.employer_name,
            title=row.title,
            profession=row.profession,
            country=row.country,
            region=row.region,
            city=row.city,
            remote=row.remote,
            employment_type=row.employment_type,
            experience_level=row.experience_level,
            salary_from=row.salary_from,
            salary_to=row.salary_to,
            currency=row.currency,
            posted_at=row.posted_at,
            description=row.description,
            skills=tuple(sorted(row.skills or [])),
            active=row.active,
            updated_at=row.updated_at,
        )

    def _vacancy_from_employer_row(self, row) -> Vacancy:
        full = self.get_vacancy(row.vacancy_id)
        if full is not None:
            return full
        return Vacancy(
            vacancy_id=row.vacancy_id,
            employer_id=row.employer_id,
            employer_name=row.title,
            title=row.title,
            profession=row.profession,
            country=row.country,
            region=row.region,
            city=row.city,
            remote=row.remote,
            employment_type="",
            experience_level="",
            salary_from=row.salary_from,
            salary_to=row.salary_to,
            currency=row.currency,
            posted_at=row.posted_at,
            description="",
            skills=tuple(),
            active=row.active,
            updated_at=now_utc(),
        )

    def _vacancy_from_profession_row(self, row) -> Vacancy:
        full = self.get_vacancy(row.vacancy_id)
        return full if full is not None else self._vacancy_from_employer_row(row)

    def _vacancy_from_region_row(self, row) -> Vacancy:
        full = self.get_vacancy(row.vacancy_id)
        return full if full is not None else self._vacancy_from_employer_row(row)

    def _vacancy_from_remote_row(self, row) -> Vacancy:
        full = self.get_vacancy(row.vacancy_id)
        return full if full is not None else self._vacancy_from_employer_row(row)
