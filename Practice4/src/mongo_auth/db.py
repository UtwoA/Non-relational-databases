from __future__ import annotations

from dataclasses import dataclass
import os

import mongomock
from pymongo import MongoClient


@dataclass(frozen=True)
class MongoSettings:
    uri: str
    database: str


def build_settings() -> MongoSettings:
    return MongoSettings(
        uri=os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017"),
        database=os.getenv("MONGODB_DATABASE", "practice4_auth"),
    )


def create_mongo_client(uri: str | None = None):
    uri = uri or build_settings().uri
    if uri.startswith("mongomock://") or os.getenv("MONGODB_USE_MOCK") == "1":
        return mongomock.MongoClient()
    return MongoClient(uri)


def get_database(client, database_name: str):
    return client[database_name]


