"""Rate limiter for USPTO API — shared cross-process via SQLite."""

import logging
import os
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_SHARED_DB = os.path.join(os.path.expanduser("~"), ".uspto", "rate_limit.db")
_rate_limiter = None


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, requests_per_second: float = 1.0, burst_size: int = 5):
        self.min_interval = 1.0 / requests_per_second
        self.burst_size = burst_size
        self._timestamps: list[float] = []

    def acquire(self) -> float:
        now = time.time()
        # Clean old timestamps
        cutoff = now - (self.burst_size * self.min_interval)
        self._timestamps = [t for t in self._timestamps if t > cutoff]

        if len(self._timestamps) >= self.burst_size:
            wait = self._timestamps[0] + (self.burst_size * self.min_interval) - now
            if wait > 0:
                logger.debug("Rate limiter: waiting %.2fs", wait)
                time.sleep(wait)

        self._timestamps.append(time.time())
        return 0.0


class SharedRateLimiter(RateLimiter):
    """Cross-process rate limiter backed by SQLite."""

    def __init__(self, requests_per_second: float = 1.0, burst_size: int = 5, db_path: str = None):
        super().__init__(requests_per_second, burst_size)
        self.db_path = db_path or _DEFAULT_SHARED_DB
        self.consecutive_errors = 0
        self.backoff_factor = 1.0
        self.max_backoff = 10.0
        self._db_available = self._init_db()

    def _init_db(self) -> bool:
        try:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path, timeout=5)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=3000")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS request_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    pid INTEGER NOT NULL
                )
            """)
            conn.commit()
            conn.close()
            return True
        except (sqlite3.Error, OSError) as e:
            logger.warning("Shared rate limiter DB init failed, falling back to in-memory: %s", e)
            return False

    def acquire(self) -> float:
        if not self._db_available:
            return super().acquire()

        try:
            conn = sqlite3.connect(self.db_path, timeout=5)
            conn.execute("PRAGMA busy_timeout=3000")
            now = time.time()

            # Cleanup entries older than 60s
            conn.execute("DELETE FROM request_log WHERE timestamp < ?", (now - 60,))

            # Check burst across all processes
            rows = conn.execute(
                "SELECT timestamp FROM request_log ORDER BY timestamp DESC LIMIT ?",
                (self.burst_size,),
            ).fetchall()

            if len(rows) >= self.burst_size:
                oldest = rows[-1][0]
                wait = oldest + (self.burst_size * self.min_interval) - now
                if wait > 0:
                    conn.close()
                    logger.debug("Shared rate limiter: waiting %.2fs", wait)
                    time.sleep(wait)
                    conn = sqlite3.connect(self.db_path, timeout=5)
                    conn.execute("PRAGMA busy_timeout=3000")

            # Record this request
            conn.execute(
                "INSERT INTO request_log (timestamp, pid) VALUES (?, ?)",
                (time.time(), os.getpid()),
            )
            conn.commit()
            conn.close()
            return 0.0

        except sqlite3.Error as e:
            logger.warning("Shared rate limiter error, falling back: %s", e)
            return super().acquire()

    def report_success(self):
        self.consecutive_errors = 0
        self.backoff_factor = max(1.0, self.backoff_factor * 0.8)

    def report_rate_limit(self):
        self.consecutive_errors += 1
        self.backoff_factor = min(self.max_backoff, self.backoff_factor * 2.0)


def get_rate_limiter(requests_per_second: float = 2.0, burst_size: int = 5, shared: bool = True):
    """Get or create the singleton rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        if shared:
            _rate_limiter = SharedRateLimiter(requests_per_second, burst_size)
        else:
            _rate_limiter = RateLimiter(requests_per_second, burst_size)
    return _rate_limiter
