from __future__ import annotations

from datetime import UTC, datetime

from bson import BSON


def _build_permissions():
    return [
        {
            "code": "users:read",
            "description": "Read users",
            "resource": "users",
            "action": "read",
        },
        {
            "code": "users:write",
            "description": "Write users",
            "resource": "users",
            "action": "write",
        },
        {
            "code": "roles:manage",
            "description": "Manage roles",
            "resource": "roles",
            "action": "manage",
        },
    ]


def _build_roles(permission_ids):
    return [
        {
            "name": "admin",
            "description": "Full access",
            "permission_ids": [item for item in permission_ids],
        },
        {
            "name": "viewer",
            "description": "Read-only access",
            "permission_ids": [permission_ids[0]],
        },
    ]


def _build_base_users(admin_role_id, viewer_role_id):
    return [
        {
            "username": "admin",
            "email": "admin@example.com",
            "password_hash": "hash-admin",
            "active": True,
            "role_ids": [admin_role_id],
            "profile": {"full_name": "System Admin", "department": "IT"},
            "login_history": [
                {
                    "at": datetime.now(UTC).isoformat(),
                    "ip": "127.0.0.1",
                    "success": True,
                }
            ],
        },
        {
            "username": "guest",
            "email": "guest@example.com",
            "password_hash": "hash-guest",
            "active": True,
            "role_ids": [viewer_role_id],
            "profile": {"full_name": "Guest User", "department": "Support"},
            "login_history": [
                {
                    "at": datetime.now(UTC).isoformat(),
                    "ip": "127.0.0.1",
                    "success": True,
                }
            ],
        },
    ]


def _build_bulk_user(index: int, role_id, payload_size: int) -> dict:
    extra_text = "x" * payload_size
    return {
        "username": f"bulk_user_{index:08d}",
        "email": f"bulk_user_{index:08d}@example.com",
        "password_hash": f"hash-{index:08d}",
        "active": True,
        "role_ids": [role_id],
        "profile": {
            "full_name": f"Bulk User {index:08d}",
            "department": "LoadTest",
            "notes": extra_text,
        },
        "login_history": [
            {
                "at": datetime.now(UTC).isoformat(),
                "ip": "127.0.0.1",
                "success": True,
                "metadata": extra_text[:256],
            }
        ],
    }


def _approx_document_size(document: dict) -> int:
    return len(BSON.encode(document))


def seed_database(database):
    permissions = database["permissions"]
    roles = database["roles"]
    users = database["users"]

    if permissions.count_documents({}) == 0:
        permissions.insert_many(_build_permissions())

    if roles.count_documents({}) == 0:
        permission_ids = list(permissions.find({}, {"_id": 1}))
        roles.insert_many(_build_roles([item["_id"] for item in permission_ids]))

    if users.count_documents({}) == 0:
        admin_role = roles.find_one({"name": "admin"})
        viewer_role = roles.find_one({"name": "viewer"})
        users.insert_many(_build_base_users(admin_role["_id"], viewer_role["_id"]))

    return {
        "permissions": permissions.count_documents({}),
        "roles": roles.count_documents({}),
        "users": users.count_documents({}),
    }


def seed_bulk_users(database, target_bytes: int = 1_000_000_000, batch_size: int = 250) -> dict:
    permissions = database["permissions"]
    roles = database["roles"]
    users = database["users"]

    if permissions.count_documents({}) == 0:
        permissions.insert_many(_build_permissions())
    if roles.count_documents({}) == 0:
        permission_ids = list(permissions.find({}, {"_id": 1}))
        roles.insert_many(_build_roles([item["_id"] for item in permission_ids]))

    viewer_role = roles.find_one({"name": "viewer"})
    if viewer_role is None:
        viewer_role_id = roles.insert_one(
            {
                "name": "viewer",
                "description": "Read-only access",
                "permission_ids": [permissions.find_one({}, {"_id": 1})["_id"]],
            }
        ).inserted_id
        viewer_role = roles.find_one({"_id": viewer_role_id})

    current_bytes = 0
    total_inserted = 0
    index = users.count_documents({})

    while current_bytes < target_bytes:
        batch = []
        batch_bytes = 0
        for _ in range(batch_size):
            document = _build_bulk_user(index, viewer_role["_id"], payload_size=2048)
            batch.append(document)
            batch_bytes += _approx_document_size(document)
            index += 1
            if current_bytes + batch_bytes >= target_bytes:
                break

        if not batch:
            break

        users.insert_many(batch)
        current_bytes += batch_bytes
        total_inserted += len(batch)

    return {
        "target_bytes": target_bytes,
        "approx_inserted_bytes": current_bytes,
        "inserted_users": total_inserted,
        "permissions": permissions.count_documents({}),
        "roles": roles.count_documents({}),
        "users": users.count_documents({}),
    }
