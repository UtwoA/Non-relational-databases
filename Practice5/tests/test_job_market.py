from __future__ import annotations

import unittest

from src.job_market.app import create_app
from src.job_market.memory_repository import InMemoryJobMarketRepository
from src.job_market.seed import seed_repository


class JobMarketAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryJobMarketRepository()
        self.app = create_app(repository=self.repository)
        self.client = self.app.test_client()

    def test_seed_and_query_vacancies_by_primary_key_tables(self) -> None:
        seed_report = seed_repository(self.repository)
        self.assertEqual(seed_report["employers"], 8)
        self.assertEqual(seed_report["vacancies"], 15)
        self.assertIn("sample_employer_id", seed_report)
        self.assertIn("sample_vacancy_id", seed_report)

        index = self.client.get("/")
        self.assertEqual(index.status_code, 200)
        self.assertIn("Статистика вакансий".encode("utf-8"), index.data)
        self.assertIn("Первичный ключ".encode("utf-8"), index.data)
        self.assertIn("Все вакансии".encode("utf-8"), index.data)
        self.assertIn("Операции с данными".encode("utf-8"), index.data)
        self.assertIn("Создать вакансию".encode("utf-8"), index.data)
        self.assertIn(b"queryForInput", index.data)

        all_vacancies = self.client.get("/api/vacancies?limit=50")
        self.assertEqual(all_vacancies.status_code, 200)
        self.assertEqual(len(all_vacancies.get_json()), 15)

        by_profession = self.client.get("/api/vacancies/by-profession/python%20developer?limit=10")
        self.assertEqual(by_profession.status_code, 200)
        self.assertGreaterEqual(len(by_profession.get_json()), 2)

        by_region = self.client.get("/api/vacancies/by-region?country=russia&region=moscow&limit=10")
        self.assertEqual(by_region.status_code, 200)
        self.assertGreaterEqual(len(by_region.get_json()), 2)

        remote = self.client.get("/api/vacancies/remote?remote=true&limit=10")
        self.assertEqual(remote.status_code, 200)
        self.assertGreaterEqual(len(remote.get_json()), 1)

        by_employment = self.client.get("/api/vacancies/by-employment-type/full-time?limit=10")
        self.assertEqual(by_employment.status_code, 200)
        self.assertGreaterEqual(len(by_employment.get_json()), 1)

        by_experience = self.client.get("/api/vacancies/by-experience-level/senior?limit=10")
        self.assertEqual(by_experience.status_code, 200)
        self.assertGreaterEqual(len(by_experience.get_json()), 1)

        by_city = self.client.get("/api/vacancies/by-city?country=russia&city=moscow&limit=10")
        self.assertEqual(by_city.status_code, 200)
        self.assertGreaterEqual(len(by_city.get_json()), 2)

    def test_trailing_slash_vacancies_returns_json(self) -> None:
        seed_repository(self.repository)
        response = self.client.get("/api/vacancies/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(len(response.get_json()), 15)

    def test_api_not_found_returns_json(self) -> None:
        response = self.client.get("/api/no-such-endpoint")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content_type, "application/json")
        self.assertEqual(response.get_json()["error"], "API endpoint not found")

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
        vacancy_id = create.get_json()["vacancy_id"]

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

    def test_create_update_and_delete_employer(self) -> None:
        create = self.client.post(
            "/api/employers",
            json={
                "name": "CRUD Employer",
                "industry": "Analytics",
                "website": "https://crud-employer.example",
                "country": "russia",
                "city": "kazan",
            },
        )
        self.assertEqual(create.status_code, 201)
        employer_id = create.get_json()["employer_id"]

        update = self.client.put(
            f"/api/employers/{employer_id}",
            json={
                "name": "CRUD Employer Updated",
                "industry": "Analytics",
                "website": "https://crud-employer.example",
                "country": "russia",
                "city": "kazan",
            },
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.get_json()["name"], "CRUD Employer Updated")

        delete = self.client.delete(f"/api/employers/{employer_id}")
        self.assertEqual(delete.status_code, 200)
        missing = self.client.get(f"/api/employers/{employer_id}")
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
