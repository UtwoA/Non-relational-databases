from __future__ import annotations

import json
import unittest

import mongomock
from bson import ObjectId

from src.mongo_auth.app import create_app


class AuthApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = mongomock.MongoClient()
        self.app = create_app(client=self.client, database_name="tests")
        self.app.config["TESTING"] = True
        self.http = self.app.test_client()

    def _create_permission(self, code: str = "users:read"):
        response = self.http.post(
            "/api/permissions",
            json={
                "code": code,
                "description": "Read users",
                "resource": "users",
                "action": "read",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def _create_role(self, permission_id: str):
        response = self.http.post(
            "/api/roles",
            json={
                "name": "auditor",
                "description": "Can inspect data",
                "permission_ids": [permission_id],
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def _create_user(self, role_id: str, username: str = "ivan"):
        response = self.http.post(
            "/api/users",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password_hash": f"hash-{username}",
                "role_ids": [role_id],
                "profile": {"full_name": "Ivan Petrov", "department": "Support"},
                "login_history": [{"at": "2026-05-12T12:00:00Z", "ip": "127.0.0.1", "success": True}],
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def test_permissions_crud(self):
        permission = self._create_permission("audit:read")
        permission_id = permission["_id"]
        self.assertIsInstance(permission_id, str)
        raw_permission = self.app.extensions["mongo_db"]["permissions"].find_one({"_id": ObjectId(permission_id)})
        self.assertIsNotNone(raw_permission)
        self.assertEqual(raw_permission["code"], "audit:read")

        fetched = self.http.get(f"/api/permissions/{permission_id}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.get_json()["code"], "audit:read")

        updated = self.http.put(
            f"/api/permissions/{permission_id}",
            json={
                "code": "audit:read",
                "description": "Read all audit logs",
                "resource": "audit",
                "action": "read",
            },
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["description"], "Read all audit logs")

        deleted = self.http.delete(f"/api/permissions/{permission_id}")
        self.assertEqual(deleted.status_code, 204)

    def test_roles_crud_and_user_nested_data(self):
        permission = self._create_permission()
        role = self._create_role(permission["_id"])
        role_id = role["_id"]
        self.assertIsInstance(role_id, str)
        raw_role = self.app.extensions["mongo_db"]["roles"].find_one({"_id": ObjectId(role_id)})
        self.assertIsNotNone(raw_role)
        self.assertIsInstance(raw_role["permission_ids"][0], ObjectId)

        fetched = self.http.get(f"/api/roles/{role_id}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.get_json()["name"], "auditor")

        updated_role = self.http.put(
            f"/api/roles/{role_id}",
            json={
                "name": "auditor",
                "description": "Read-only access",
                "permission_ids": [permission["_id"]],
            },
        )
        self.assertEqual(updated_role.status_code, 200)
        self.assertEqual(updated_role.get_json()["description"], "Read-only access")

        user = self._create_user(role_id)
        user_id = user["_id"]
        self.assertIsInstance(user_id, str)
        raw_user = self.app.extensions["mongo_db"]["users"].find_one({"_id": ObjectId(user_id)})
        self.assertIsNotNone(raw_user)
        self.assertIsInstance(raw_user["role_ids"][0], ObjectId)
        self.assertEqual(user["profile"]["full_name"], "Ivan Petrov")
        self.assertEqual(len(user["login_history"]), 1)

        fetched_user = self.http.get(f"/api/users/{user_id}")
        self.assertEqual(fetched_user.status_code, 200)
        self.assertEqual(fetched_user.get_json()["email"], "ivan@example.com")

        updated_user = self.http.put(
            f"/api/users/{user_id}",
            json={
                "username": "ivan",
                "email": "ivan@example.com",
                "password_hash": "hash-ivan",
                "active": False,
                "role_ids": [role_id],
                "profile": {"full_name": "Ivan Petrov", "department": "Support"},
                "login_history": [{"at": "2026-05-12T12:00:00Z", "ip": "127.0.0.1", "success": True}],
            },
        )
        self.assertEqual(updated_user.status_code, 200)
        self.assertFalse(updated_user.get_json()["active"])

        deleted_user = self.http.delete(f"/api/users/{user_id}")
        self.assertEqual(deleted_user.status_code, 204)

    def test_stream_users(self):
        permission = self._create_permission()
        role = self._create_role(permission["_id"])
        self._create_user(role["_id"], username="ivan")
        self._create_user(role["_id"], username="petr")

        stream_response = self.http.get("/api/users/stream")
        self.assertEqual(stream_response.status_code, 200)

        lines = [line for line in stream_response.data.decode("utf-8").splitlines() if line.strip()]
        self.assertGreaterEqual(len(lines), 2)
        first = json.loads(lines[0])
        self.assertIn("username", first)

    def test_docs_are_available(self):
        response = self.http.get("/docs")
        self.assertEqual(response.status_code, 200)
        self.assertIn("SwaggerUIBundle", response.data.decode("utf-8"))

        spec = self.http.get("/openapi.json")
        self.assertEqual(spec.status_code, 200)
        self.assertIn("/api/users", spec.get_json()["paths"])


if __name__ == "__main__":
    unittest.main()
