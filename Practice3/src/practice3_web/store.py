from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


USERS_LIST_KEY = "practice3:users:ids"
USER_KEY_PREFIX = "practice3:user:"


@dataclass(frozen=True)
class UserRecord:
    id: str
    name: str
    created_at: str


class UserStore:
    def __init__(self, client: Any) -> None:
        self._client = client

    def add_user(self, name: str) -> UserRecord:
        normalized = name.strip()
        if not normalized:
            raise ValueError("Name must not be empty")

        record = UserRecord(
            id=uuid4().hex,
            name=normalized,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._client.hset(
            self._user_key(record.id),
            mapping={"id": record.id, "name": record.name, "created_at": record.created_at},
        )
        self._client.rpush(USERS_LIST_KEY, record.id)
        return record

    def list_users(self) -> list[dict[str, str]]:
        users: list[dict[str, str]] = []
        for user_id in self._client.lrange(USERS_LIST_KEY, 0, -1):
            data = self._client.hgetall(self._user_key(user_id))
            if data:
                users.append(
                    {
                        "id": data.get("id", user_id),
                        "name": data.get("name", ""),
                        "created_at": data.get("created_at", ""),
                    }
                )
        return users

    def count_users(self) -> int:
        return int(self._client.llen(USERS_LIST_KEY))

    def clear(self) -> None:
        for user_id in self._client.lrange(USERS_LIST_KEY, 0, -1):
            self._client.delete(self._user_key(user_id))
        self._client.delete(USERS_LIST_KEY)

    @staticmethod
    def _user_key(user_id: str) -> str:
        return f"{USER_KEY_PREFIX}{user_id}"


def create_redis_client(url: str):
    import redis

    return redis.Redis.from_url(url, decode_responses=True)

