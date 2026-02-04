from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from typing import Any


def stable_uuid(seed: int, suffix: str) -> str:
    random.seed(f"{seed}:{suffix}")
    return str(uuid.UUID(int=random.getrandbits(128)))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def choose(random_state: random.Random, items: list[Any]) -> Any:
    return items[random_state.randrange(len(items))]

