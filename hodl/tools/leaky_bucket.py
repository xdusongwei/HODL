import math
from hodl.tools.time import TimeTools
from threading import Lock


class LeakyBucket:
    def __init__(self, capacity: int = 10, leak_rate: float = None):
        assert isinstance(capacity, int)
        assert capacity > 0
        if leak_rate is None:
            leak_rate = capacity
        self._capacity = float(capacity)
        self._used_tokens = 0
        self._leak_rate = float(leak_rate)
        self._last_time = TimeTools.utc_now().timestamp()
        self._lock = Lock()

    def __enter__(self):
        self.consume()

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def _get_used_tokens(self):
        now = TimeTools.utc_now().timestamp()
        delta = self._leak_rate / 60.0 * (now - self._last_time)
        delta = math.floor(delta)
        self._used_tokens = max(0, self._used_tokens - delta)
        return self._used_tokens

    def _consume(self):
        while True:
            with self._lock:
                if 1 + self._get_used_tokens() <= self._capacity:
                    self._used_tokens += 1
                    self._last_time = TimeTools.utc_now().timestamp()
                    break
                last_time = self._last_time
            now = TimeTools.utc_now().timestamp()
            secs = last_time + self._leak_rate / 60.0 - now
            TimeTools.sleep(secs=secs)

    def consume(self):
        self._consume()


__all__ = ["LeakyBucket", ]
