from __future__ import annotations

import json
from datetime import UTC, datetime

from bson import ObjectId
from flask import Flask, Response, abort, jsonify, redirect, render_template_string, request, stream_with_context, url_for
from pymongo.errors import DuplicateKeyError

from .db import build_settings, create_mongo_client, get_database
from .repositories import Repository, UserRepository


def _parse_object_id_list(values):
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError("expected a list")
    return [ObjectId(value) if not isinstance(value, ObjectId) else value for value in values]


def _create_user_payload(payload: dict) -> dict:
    return {
        "username": payload["username"],
        "email": payload["email"],
        "password_hash": payload["password_hash"],
        "active": bool(payload.get("active", True)),
        "role_ids": _parse_object_id_list(payload.get("role_ids")),
        "profile": payload.get("profile", {}),
        "login_history": payload.get("login_history", []),
    }


def _create_role_payload(payload: dict) -> dict:
    return {
        "name": payload["name"],
        "description": payload.get("description", ""),
        "permission_ids": _parse_object_id_list(payload.get("permission_ids")),
    }


def _create_permission_payload(payload: dict) -> dict:
    return {
        "code": payload["code"],
        "description": payload.get("description", ""),
        "resource": payload["resource"],
        "action": payload["action"],
    }


def _openapi_spec() -> dict:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "MongoDB Practice 4",
            "version": "1.0.0",
            "description": "CRUD for users, roles, permissions and users streaming.",
        },
        "paths": {
            "/api/users": {
                "get": {"summary": "List users", "responses": {"200": {"description": "OK"}}},
                "post": {
                    "summary": "Create user",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "example": {
                                    "username": "ivan",
                                    "email": "ivan@example.com",
                                    "password_hash": "hash-ivan",
                                    "role_ids": [],
                                    "profile": {"full_name": "Ivan Petrov"},
                                    "login_history": [],
                                }
                            }
                        },
                    },
                    "responses": {"201": {"description": "Created"}},
                },
            },
            "/api/users/{document_id}": {
                "get": {
                    "summary": "Get user",
                    "parameters": [{"name": "document_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "OK"}},
                },
                "put": {
                    "summary": "Replace user",
                    "parameters": [{"name": "document_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "Updated"}},
                },
                "delete": {
                    "summary": "Delete user",
                    "parameters": [{"name": "document_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"204": {"description": "Deleted"}},
                },
            },
            "/api/roles": {
                "get": {"summary": "List roles", "responses": {"200": {"description": "OK"}}},
                "post": {
                    "summary": "Create role",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "example": {
                                    "name": "auditor",
                                    "description": "Read-only access",
                                    "permission_ids": [],
                                }
                            }
                        },
                    },
                    "responses": {"201": {"description": "Created"}},
                },
            },
            "/api/roles/{document_id}": {
                "get": {
                    "summary": "Get role",
                    "parameters": [{"name": "document_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "OK"}},
                },
                "put": {
                    "summary": "Replace role",
                    "parameters": [{"name": "document_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "Updated"}},
                },
                "delete": {
                    "summary": "Delete role",
                    "parameters": [{"name": "document_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"204": {"description": "Deleted"}},
                },
            },
            "/api/permissions": {
                "get": {"summary": "List permissions", "responses": {"200": {"description": "OK"}}},
                "post": {
                    "summary": "Create permission",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "example": {
                                    "code": "users:read",
                                    "description": "Read users",
                                    "resource": "users",
                                    "action": "read",
                                }
                            }
                        },
                    },
                    "responses": {"201": {"description": "Created"}},
                },
            },
            "/api/permissions/{document_id}": {
                "get": {
                    "summary": "Get permission",
                    "parameters": [{"name": "document_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "OK"}},
                },
                "put": {
                    "summary": "Replace permission",
                    "parameters": [{"name": "document_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "Updated"}},
                },
                "delete": {
                    "summary": "Delete permission",
                    "parameters": [{"name": "document_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"204": {"description": "Deleted"}},
                },
            },
            "/api/users/stream": {
                "get": {"summary": "Stream users", "responses": {"200": {"description": "NDJSON stream"}}},
            },
        },
    }


def _create_app_with_database(database) -> Flask:
    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False
    app.extensions["mongo_db"] = database

    users = UserRepository(database["users"])
    roles = Repository(database["roles"])
    permissions = Repository(database["permissions"])

    database["users"].create_index("username", unique=True)
    database["users"].create_index("email", unique=True)
    database["roles"].create_index("name", unique=True)
    database["permissions"].create_index("code", unique=True)

    def register_routes(collection_name: str, repository: Repository, create_payload_factory):
        base_path = f"/api/{collection_name}"

        def list_documents():
            return jsonify(repository.list())

        def create_document():
            payload = request.get_json(silent=True) or {}
            try:
                document = repository.create(create_payload_factory(payload))
            except KeyError as exc:
                return jsonify({"error": f"missing field: {exc.args[0]}"}), 400
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            except DuplicateKeyError as exc:
                return jsonify({"error": str(exc)}), 409
            return jsonify(document), 201

        def get_document(document_id: str):
            try:
                document = repository.get(document_id)
            except ValueError:
                return jsonify({"error": "invalid id"}), 400
            if document is None:
                abort(404)
            return jsonify(document)

        def replace_document(document_id: str):
            payload = request.get_json(silent=True) or {}
            try:
                document = repository.replace(document_id, create_payload_factory(payload))
            except KeyError as exc:
                return jsonify({"error": f"missing field: {exc.args[0]}"}), 400
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            except DuplicateKeyError as exc:
                return jsonify({"error": str(exc)}), 409
            if document is None:
                abort(404)
            return jsonify(document)

        def delete_document(document_id: str):
            try:
                deleted = repository.delete(document_id)
            except ValueError:
                return jsonify({"error": "invalid id"}), 400
            if not deleted:
                abort(404)
            return "", 204

        app.add_url_rule(base_path, endpoint=f"{collection_name}_list", view_func=list_documents, methods=["GET"])
        app.add_url_rule(base_path, endpoint=f"{collection_name}_create", view_func=create_document, methods=["POST"])
        app.add_url_rule(
            f"{base_path}/<document_id>",
            endpoint=f"{collection_name}_get",
            view_func=get_document,
            methods=["GET"],
        )
        app.add_url_rule(
            f"{base_path}/<document_id>",
            endpoint=f"{collection_name}_replace",
            view_func=replace_document,
            methods=["PUT"],
        )
        app.add_url_rule(
            f"{base_path}/<document_id>",
            endpoint=f"{collection_name}_delete",
            view_func=delete_document,
            methods=["DELETE"],
        )

    register_routes("users", users, _create_user_payload)
    register_routes("roles", roles, _create_role_payload)
    register_routes("permissions", permissions, _create_permission_payload)

    @app.get("/api/users/stream")
    def stream_users():
        def generate():
            for document in users.stream():
                yield json.dumps(document, ensure_ascii=False, default=str) + "\n"

        return Response(stream_with_context(generate()), mimetype="application/x-ndjson")

    @app.get("/openapi.json")
    def openapi_json():
        return jsonify(_openapi_spec())

    @app.get("/docs")
    def docs():
        return render_template_string(
            """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Practice 4 API Docs</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
    <style>body { margin: 0; }</style>
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      window.onload = function() {
        SwaggerUIBundle({
          url: "{{ spec_url }}",
          dom_id: '#swagger-ui'
        });
      };
    </script>
  </body>
</html>
            """,
            spec_url=url_for("openapi_json"),
        )

    @app.get("/")
    def index():
        return redirect(url_for("docs"))

    return app


def create_app(client=None, database_name: str | None = None) -> Flask:
    settings = build_settings()
    mongo_client = client or create_mongo_client(settings.uri)
    database = get_database(mongo_client, database_name or settings.database)
    return _create_app_with_database(database)
