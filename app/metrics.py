import threading
import time
from collections import deque

WINDOW_SECONDS = 60
PRUNE_EVERY_SECONDS = 60


class Metrics:
    """Rolling per-client ALLOW/DENY counts for the last 60 seconds."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # client_key -> deque of [second, allowed, denied], oldest first
        self._data: dict[str, deque] = {}
        self._last_prune = time.time()

    def record(self, client_key: str, allowed: bool, now: float | None = None) -> None:
        now = time.time() if now is None else now
        second = int(now)
        with self._lock:
            buckets = self._data.get(client_key)
            if buckets is None:
                buckets = self._data[client_key] = deque()
            if buckets and buckets[-1][0] == second:
                bucket = buckets[-1]
            else:
                bucket = [second, 0, 0]
                buckets.append(bucket)
            bucket[1 if allowed else 2] += 1
            self._drop_old(buckets, second)
            if now - self._last_prune >= PRUNE_EVERY_SECONDS:
                self._prune_all(second)
                self._last_prune = now

    @staticmethod
    def _drop_old(buckets: deque, second: int) -> None:
        while buckets and buckets[0][0] <= second - WINDOW_SECONDS:
            buckets.popleft()

    def _prune_all(self, second: int) -> None:
        for key in list(self._data):
            self._drop_old(self._data[key], second)
            if not self._data[key]:
                del self._data[key]

    def snapshot(self, now: float | None = None, top: int = 50) -> dict:
        now = time.time() if now is None else now
        second = int(now)
        rows = []
        with self._lock:
            self._prune_all(second)
            for key, buckets in self._data.items():
                allowed = sum(b[1] for b in buckets)
                denied = sum(b[2] for b in buckets)
                recent = [b for b in buckets if b[0] > second - 10]
                allowed_10 = sum(b[1] for b in recent)
                denied_10 = sum(b[2] for b in recent)
                total = allowed + denied
                rows.append(
                    {
                        "client_key": key,
                        "allowed_60s": allowed,
                        "denied_60s": denied,
                        "requests_60s": total,
                        "deny_rate_60s": round(denied / total, 3) if total else 0.0,
                        "requests_per_sec_10s": round((allowed_10 + denied_10) / 10, 1),
                        "denied_per_sec_10s": round(denied_10 / 10, 1),
                    }
                )
        rows.sort(key=lambda r: r["requests_60s"], reverse=True)
        return {
            "window_seconds": WINDOW_SECONDS,
            "tracked_clients": len(rows),
            "clients": rows[:top],
        }