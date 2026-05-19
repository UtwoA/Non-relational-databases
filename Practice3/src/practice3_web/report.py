from __future__ import annotations

import time
from collections import Counter
from typing import Any


def build_directory_report(users: list[dict[str, str]]) -> dict[str, Any]:
    time.sleep(0.2)

    names = [user["name"] for user in users if user.get("name")]
    initials = Counter(name[0].upper() for name in names if name)

    return {
        "total_users": len(users),
        "names": names,
        "first_user": users[0]["name"] if users else None,
        "last_user": users[-1]["name"] if users else None,
        "initials": dict(sorted(initials.items())),
    }

