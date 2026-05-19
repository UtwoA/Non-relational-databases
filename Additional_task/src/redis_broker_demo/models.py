from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class Job:
    job_id: str
    created_at: float
    payload: str
    mode: str

    @classmethod
    def create(cls, mode: str, payload: str | None = None) -> "Job":
        job_id = str(uuid4())
        return cls(
            job_id=job_id,
            created_at=time.time(),
            payload=payload or f"Generate an LLM answer for request {job_id}",
            mode=mode,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "created_at": self.created_at,
            "payload": self.payload,
            "mode": self.mode,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "Job":
        payload = json.loads(raw)
        return cls(
            job_id=str(payload["job_id"]),
            created_at=float(payload["created_at"]),
            payload=str(payload["payload"]),
            mode=str(payload["mode"]),
        )
