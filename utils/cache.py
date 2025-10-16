import json
import os
import time
from typing import Any, Optional

from config import CACHE_DIR


def _ensure_cache_dir() -> None:
    if not os.path.isdir(CACHE_DIR):
        os.makedirs(CACHE_DIR, exist_ok=True)


def cache_path(key: str) -> str:
    _ensure_cache_dir()
    safe_key = key.replace("/", "_")
    return os.path.join(CACHE_DIR, f"{safe_key}.json")


def read_cache(key: str, ttl_seconds: int) -> Optional[Any]:
    path = cache_path(key)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        ts = payload.get("_ts", 0)
        if (time.time() - ts) > ttl_seconds:
            return None
        return payload.get("data")
    except Exception:
        return None


def write_cache(key: str, data: Any) -> None:
    path = cache_path(key)
    payload = {"_ts": time.time(), "data": data}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)


