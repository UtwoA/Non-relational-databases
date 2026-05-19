from __future__ import annotations

import json
import unittest

from src.job_market.app import create_app
from src.job_market.memory_repository import InMemoryJobMarketRepository
from src.job_market.seed import seed_repository


class JobMarketAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryJobMarketRepository()
        self.app = create_app(repository=self.repository)
        self.client = self.app.test_client()

    def test_seed_and_query_vacancies(self) -> None:
        seed_repository(self.repository)
        response = self.client.get("/api/vacancies/by-profession/python%20developer?limit=10")
        self.assertEqual(response.status_code, 200)
        items = response.get_json()
        self.assertGreaterEqual(len(items), 2)
        self.assertEqual(items[0]["profession"], "python developer")

    def test_create_update_and_delete_vacancy(self) -> None:
        employer = self.client.post(
            "/api/employers",
            json={
                "name": "Test Company",
                "industry": "IT",
                "website": "https://example.com",
                "country": "russia",
                "city": "moscow",
            },
        )
        self.assertEqual(employer.status_code, 201)
        employer_id = employer.get_json()["employer_id"]

        create = self.client.post(
            "/api/vacancies",
            json={
                "employer_id": employer_id,
                "employer_name": "Test Company",
                "title": "QA Engineer",
                "profession": "qa engineer",
                "country": "russia",
                "region": "moscow",
                "city": "moscow",
                "remote": False,
                "employment_type": "full-time",
                "experience_level": "middle",
                "salary_from": 120000,
                "salary_to": 150000,
                "currency": "RUB",
                "description": "Test products",
                "skills": ["pytest", "python"],
            },
        )
        self.assertEqual(create.status_code, 201)
        vacancy = create.get_json()
        vacancy_id = vacancy["vacancy_id"]

        fetched = self.client.get(f"/api/vacancies/{vacancy_id}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.get_json()["title"], "QA Engineer")

        update = self.client.put(
            f"/api/vacancies/{vacancy_id}",
            json={
                "employer_id": employer_id,
                "employer_name": "Test Company",
                "title": "QA Lead",
                "profession": "qa engineer",
                "country": "russia",
                "region": "moscow",
                "city": "moscow",
                "remote": True,
                "employment_type": "full-time",
                "experience_level": "senior",
                "salary_from": 170000,
                "salary_to": 210000,
                "currency": "RUB",
                "description": "Lead testing",
                "skills": ["pytest", "automation"],
            },
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.get_json()["title"], "QA Lead")

        delete = self.client.delete(f"/api/vacancies/{vacancy_id}")
        self.assertEqual(delete.status_code, 200)
        missing = self.client.get(f"/api/vacancies/{vacancy_id}")
        self.assertEqual(missing.status_code, 404)

    def test_region_stats(self) -> None:
        seed_repository(self.repository)
        response = self.client.get("/api/stats/regions?country=russia&region=moscow")
        self.assertEqual(response.status_code, 200)
        stats = response.get_json()
        self.assertEqual(stats["country"], "russia")
        self.assertEqual(stats["region"], "moscow")
        self.assertGreaterEqual(stats["vacancy_count"], 1)


if __name__ == "__main__":
    unittest.main()
