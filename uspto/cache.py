"""Local file cache for USPTO API responses."""

import hashlib
import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".uspto_cache")
DEFAULT_TTL = 86400  # 24 hours — patent data doesn't change frequently


class PatentCache:
    """File-based cache for API responses."""

    def __init__(self, cache_dir: str = None, ttl: int = DEFAULT_TTL):
        self.cache_dir = Path(cache_dir or DEFAULT_CACHE_DIR)
        self.ttl = ttl
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, endpoint: str, params: dict = None) -> str:
        raw = f"{endpoint}:{json.dumps(params or {}, sort_keys=True)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, endpoint: str, params: dict = None) -> dict | None:
        path = self.cache_dir / f"{self._key(endpoint, params)}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            if time.time() - data.get("_cached_at", 0) > self.ttl:
                path.unlink(missing_ok=True)
                return None
            return data.get("response")
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, endpoint: str, params: dict, response: dict) -> None:
        path = self.cache_dir / f"{self._key(endpoint, params)}.json"
        try:
            path.write_text(json.dumps({
                "_cached_at": time.time(),
                "endpoint": endpoint,
                "response": response,
            }, indent=2))
        except OSError as e:
            logger.warning("Cache write failed: %s", e)

    def clear(self) -> int:
        count = 0
        for f in self.cache_dir.glob("*.json"):
            f.unlink(missing_ok=True)
            count += 1
        return count
