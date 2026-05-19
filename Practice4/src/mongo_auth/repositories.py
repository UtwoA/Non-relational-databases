from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId


def _serialize_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    return value


def serialize_document(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    return {key: _serialize_value(value) for key, value in document.items()}


def parse_object_id(document_id: str) -> ObjectId:
    try:
        return ObjectId(document_id)
    except InvalidId as exc:
        raise ValueError("invalid id") from exc


class Repository:
    def __init__(self, collection):
        self.collection = collection

    def list(self, filter_: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        cursor = self.collection.find(filter_ or {}).sort("_id", 1)
        return [serialize_document(document) for document in cursor]

    def stream(self, filter_: dict[str, Any] | None = None) -> Iterable[dict[str, Any]]:
        cursor = self.collection.find(filter_ or {}).sort("_id", 1).batch_size(10)
        for document in cursor:
            yield serialize_document(document)

    def get(self, document_id: str) -> dict[str, Any] | None:
        return serialize_document(self.collection.find_one({"_id": parse_object_id(document_id)}))

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self.collection.insert_one(payload)
        return self.get(str(result.inserted_id))

    def replace(self, document_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        replacement = dict(payload)
        replacement["_id"] = parse_object_id(document_id)
        self.collection.replace_one({"_id": replacement["_id"]}, replacement)
        return self.get(document_id)

    def delete(self, document_id: str) -> bool:
        result = self.collection.delete_one({"_id": parse_object_id(document_id)})
        return result.deleted_count == 1


class UserRepository(Repository):
    pass
