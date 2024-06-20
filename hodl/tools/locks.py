from threading import RLock
from filelock import FileLock


class Filelock:
    def __init__(self, lock_file: str = None):
        self.timeout = 30
        if lock_file is None:
            self.lock_file = RLock()
        else:
            self.lock_file = FileLock(lock_file, timeout=self.timeout)

    def __enter__(self):
        if isinstance(self.lock_file, RLock):
            self.lock_file.acquire(timeout=self.timeout)
        elif isinstance(self.lock_file, FileLock):
            self.lock_file.acquire(timeout=self.timeout)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(self.lock_file, RLock):
            self.lock_file.release()
        elif isinstance(self.lock_file, FileLock):
            if self.lock_file.is_locked:
                self.lock_file.release()


__all__ = ['Filelock']
