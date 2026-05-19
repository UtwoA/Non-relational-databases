from __future__ import annotations

import math
import time
from collections import Counter


def slow_fibonacci(n: int) -> int:
    if n < 0:
        raise ValueError("n must be non-negative")

    time.sleep(0.15)

    if n < 2:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def analyze_text(text: str) -> dict[str, object]:
    time.sleep(0.12)

    words = [word.strip(".,!?;:()[]{}\"'").lower() for word in text.split() if word.strip()]
    counter = Counter(words)
    return {
        "characters": len(text),
        "words": len(words),
        "unique_words": len(counter),
        "most_common": [[word, count] for word, count in counter.most_common(3)],
        "reading_time_minutes": round(len(words) / 200, 4),
        "sqrt_characters": round(math.sqrt(len(text)), 4),
    }
