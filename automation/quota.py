# automation/quota.py
import time
import threading

class QuotaManager:
    def __init__(self, max_calls=1000, refresh_hours=5):
        self.max_calls = max_calls
        self.refresh_seconds = refresh_hours * 3600
        self.remaining = max_calls
        self.total_used = 0
        self._lock = threading.Lock()
        self._last_refresh = time.time()
        self._next_refresh = self._last_refresh + self.refresh_seconds

    def consume(self):
        with self._lock:
            self._check_pending_refresh()
            if self.remaining <= 0:
                return False
            self.remaining -= 1
            self.total_used += 1
            return True

    def _check_pending_refresh(self):
        now = time.time()
        if now >= self._next_refresh:
            self.remaining = self.max_calls
            self.total_used = 0
            self._last_refresh = now
            self._next_refresh = now + self.refresh_seconds

    def is_pending(self):
        self._check_pending_refresh()
        return self.remaining > 0

    def wait_until_refresh(self, poll_interval=60):
        while True:
            now = time.time()
            if now >= self._next_refresh:
                self._check_pending_refresh()
                return
            time.sleep(poll_interval)

    def get_state(self):
        with self._lock:
            self._check_pending_refresh()
            return {
                "remaining": self.remaining,
                "total_used": self.total_used,
                "max_calls": self.max_calls,
                "next_refresh_at": self._next_refresh,
            }


    async def wait_until_refresh_async(self, poll_interval=60):
        import asyncio
        while True:
            now = time.time()
            if now >= self._next_refresh:
                self._check_pending_refresh()
                return
            await asyncio.sleep(poll_interval)

    def _force_refresh(self):
        self.remaining = self.max_calls
        self.total_used = 0
        self._last_refresh = time.time()
        self._next_refresh = time.time() + self.refresh_seconds
