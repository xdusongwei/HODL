from threading import RLock
from filelock import FileLock


class Filelock:
    """
    文件锁
    帮助实现多进程互斥, 没有提供锁的路径则降级为 RLock 对象
    """
    def __init__(self, lock_file: str = None):
        self.timeout = 30
        if lock_file is None:
            self.lock_file = RLock()
        else:
            self.lock_file = FileLock(lock_file, timeout=self.timeout)

    def __enter__(self):
        self.lock_file.acquire(timeout=self.timeout)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(self.lock_file, FileLock):
            if not self.lock_file.is_locked:
                return
        self.lock_file.release()


__all__ = ['Filelock']
