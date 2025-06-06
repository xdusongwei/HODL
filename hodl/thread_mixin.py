from typing import Type, Self
import threading
from dataclasses import dataclass
from typing import Optional


@dataclass
class BarElementDesc:
    content: str = ''
    tooltip: str = None

    @property
    def tooltip_attr(self):
        if not self.tooltip:
            return ''
        return f'data-bs-toggle="tooltip" data-bs-placement="bottom" data-bs-title="{self.tooltip}"'


class ThreadUI:
    def primary_bar(self) -> list[BarElementDesc]:
        return list()

    def secondary_bar(self) -> list[BarElementDesc]:
        return list()

    def extra_html(self) -> None | str:
        return None

    def warning_alert_bar(self) -> list[str]:
        return list()


class ThreadMixin(ThreadUI):
    """
    所有线程(包括 MainThread)级对象的基类
    这样可以在网页中观察到所有相关线程的存活
    查找特定 tag 的线程, 以及类似 erlang 机制强制 MFA 调用对象方法.
    """
    _THREADS: set['ThreadMixin'] = set()

    @classmethod
    def threads(cls) -> list['ThreadMixin']:
        return sorted(ThreadMixin._THREADS, key=lambda i: i.current_thread.name if i.current_thread else '')

    @property
    def current_thread(self) -> None | threading.Thread:
        return getattr(self, '__thread', None)

    def _register_thread(self):
        ThreadMixin._THREADS.add(self)

    def prepare(self):
        """
        这个方法不在线程管理的机制中被调用, 需要在创建该线程的线程中按需要显式调用
        """
        pass

    def run(self):
        thread = threading.current_thread()
        setattr(self, '__thread', thread)
        self._register_thread()

    def unmount(self):
        if self in ThreadMixin._THREADS:
            ThreadMixin._THREADS.remove(self)
        if hasattr(self, '__thread'):
            delattr(self, '__thread')

    def start(self, name: str, daemon: bool = True, start=True) -> threading.Thread:
        self.unmount()
        thread = threading.Thread(
            name=name,
            target=self.run,
            daemon=daemon,
        )
        if start:
            thread.start()
        return thread

    def kill(self):
        if thread := self.current_thread:
            if thread.is_alive():
                thread.join(0)

    def thread_lock(self) -> Optional[threading.RLock]:
        return None

    def thread_action(self, method: str, **kwargs):
        if not hasattr(self, method):
            raise NotImplementedError
        method = getattr(self, method)
        return method(**kwargs)

    def thread_tags(self) -> tuple:
        thread: threading.Thread = getattr(self, '__thread', None)
        if thread:
            return (thread.native_id, )
        return tuple()

    @classmethod
    def find_by_tags(cls, tags: tuple):
        threads = ThreadMixin._THREADS.copy()
        for thread in threads:
            if thread.thread_tags() == tags:
                return thread
        return None

    @classmethod
    def find_by_type(cls, t: Type) -> list:
        result = list()
        threads = ThreadMixin._THREADS.copy()
        for thread in threads:
            if isinstance(thread, t):
                result.append(thread)
        result.sort(key=lambda i: i.thread_tags())
        return result


__all__ = [
    'BarElementDesc',
    'ThreadMixin',
]
