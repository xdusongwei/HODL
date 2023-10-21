import math
from threading import Lock
from hodl.tools.time import TimeTools


class LeakyBucket:
    def __init__(self, leak_rate: float = 10, capacity: int = None, used_tokens: int = None):
        assert isinstance(leak_rate, (int, float, ))
        assert leak_rate > 0

        if capacity is None:
            capacity = 1
        assert isinstance(capacity, int)
        assert capacity > 0

        if used_tokens is None:
            used_tokens = 0
        assert isinstance(used_tokens, int)
        assert used_tokens >= 0

        assert capacity >= used_tokens
        self._capacity = capacity
        self._used_tokens = used_tokens
        self._leak_rate = float(leak_rate)
        self._last_time = TimeTools.utc_now().timestamp()
        self._lock = Lock()

    def __enter__(self):
        self.consume()

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @property
    def used_tokens(self):
        return self._get_used_tokens(rewrite_tokens=False)

    @property
    def available_tokens(self):
        return self._capacity - self.used_tokens

    def _get_used_tokens(self, rewrite_tokens=False):
        now = TimeTools.utc_now().timestamp()
        delta = self._leak_rate / 60.0 * (now - self._last_time)
        delta = math.floor(delta)
        new_used_tokens = max(0, self._used_tokens - delta)
        if rewrite_tokens:
            self._used_tokens = new_used_tokens
        return new_used_tokens

    def _consume(self):
        while True:
            with self._lock:
                if 1 + self._get_used_tokens(rewrite_tokens=True) <= self._capacity:
                    self._used_tokens += 1
                    self._last_time = TimeTools.utc_now().timestamp()
                    break
                last_time = self._last_time
            now = TimeTools.utc_now().timestamp()
            secs = last_time + 60.0 / self._leak_rate - now
            TimeTools.sleep(secs=secs)

    def consume(self):
        self._consume()


__all__ = ["LeakyBucket", ]
