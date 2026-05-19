from __future__ import annotations

from uuid import uuid4

from .models import Employer, Vacancy
from .services import employer_from_payload, now_utc, vacancy_from_payload


def demo_employers() -> list[dict]:
    return [
        {
            "name": "Sky Analytics",
            "industry": "Data and BI",
            "website": "https://sky-analytics.example",
            "country": "russia",
            "city": "moscow",
        },
        {
            "name": "Northwind Hiring",
            "industry": "Recruiting",
            "website": "https://northwind.example",
            "country": "russia",
            "city": "saint petersburg",
        },
        {
            "name": "Cloud Harbor",
            "industry": "Cloud services",
            "website": "https://cloud-harbor.example",
            "country": "kazakhstan",
            "city": "almaty",
        },
    ]


def demo_vacancies(employer_ids: list[str]) -> list[dict]:
    return [
        {
            "employer_id": employer_ids[0],
            "employer_name": "Sky Analytics",
            "title": "Senior Python Developer",
            "profession": "python developer",
            "country": "russia",
            "region": "moscow",
            "city": "moscow",
            "remote": True,
            "employment_type": "full-time",
            "experience_level": "senior",
            "salary_from": 300000,
            "salary_to": 400000,
            "currency": "RUB",
            "description": "Build data products and APIs.",
            "skills": ["python", "sql", "cassandra", "flask"],
        },
        {
            "employer_id": employer_ids[0],
            "employer_name": "Sky Analytics",
            "title": "Data Engineer",
            "profession": "data engineer",
            "country": "russia",
            "region": "moscow",
            "city": "moscow",
            "remote": False,
            "employment_type": "full-time",
            "experience_level": "middle",
            "salary_from": 250000,
            "salary_to": 330000,
            "currency": "RUB",
            "description": "Support analytics pipelines.",
            "skills": ["python", "airflow", "spark"],
        },
        {
            "employer_id": employer_ids[1],
            "employer_name": "Northwind Hiring",
            "title": "Data Analyst",
            "profession": "data analyst",
            "country": "russia",
            "region": "saint petersburg",
            "city": "saint petersburg",
            "remote": False,
            "employment_type": "full-time",
            "experience_level": "junior",
            "salary_from": 140000,
            "salary_to": 180000,
            "currency": "RUB",
            "description": "Prepare business reports.",
            "skills": ["sql", "power bi", "statistics"],
        },
        {
            "employer_id": employer_ids[2],
            "employer_name": "Cloud Harbor",
            "title": "Remote Python Developer",
            "profession": "python developer",
            "country": "kazakhstan",
            "region": "almaty",
            "city": "almaty",
            "remote": True,
            "employment_type": "contract",
            "experience_level": "middle",
            "salary_from": 150000,
            "salary_to": 220000,
            "currency": "KZT",
            "description": "Support a cloud platform.",
            "skills": ["python", "docker", "postgresql"],
        },
        {
            "employer_id": employer_ids[2],
            "employer_name": "Cloud Harbor",
            "title": "Platform Engineer",
            "profession": "devops engineer",
            "country": "kazakhstan",
            "region": "almaty",
            "city": "almaty",
            "remote": True,
            "employment_type": "full-time",
            "experience_level": "senior",
            "salary_from": 280000,
            "salary_to": 360000,
            "currency": "KZT",
            "description": "Manage deployment pipelines.",
            "skills": ["kubernetes", "terraform", "linux"],
        },
    ]


def seed_repository(repository) -> dict[str, int]:
    employer_ids: list[str] = []
    for payload in demo_employers():
        employer = employer_from_payload(payload)
        saved = repository.upsert_employer(employer)
        employer_ids.append(str(saved.employer_id))

    vacancy_count = 0
    for payload in demo_vacancies(employer_ids):
        vacancy = vacancy_from_payload(payload)
        repository.upsert_vacancy(vacancy)
        vacancy_count += 1

    region_stats_count = len(repository.list_region_stats())
    return {
        "employers": len(employer_ids),
        "vacancies": vacancy_count,
        "region_stats": region_stats_count,
    }
