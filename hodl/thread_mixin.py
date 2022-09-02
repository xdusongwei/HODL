import threading
from dataclasses import dataclass


@dataclass
class BarElementDesc:
    content: str = ''
    tooltip: str = None

    @property
    def tooltip_attr(self):
        if not self.tooltip:
            return ''
        return f'data-bs-toggle="tooltip" data-bs-placement="bottom" data-bs-title="{self.tooltip}"'


class ThreadMixin:
    _THREADS = set()

    @classmethod
    def threads(cls) -> list['ThreadMixin']:
        return sorted(ThreadMixin._THREADS, key=lambda i: i.current_thread.name if i.current_thread else '')

    @property
    def current_thread(self) -> None | threading.Thread:
        return getattr(self, '__thread', None)

    def _register_thread(self):
        ThreadMixin._THREADS.add(self)

    def primary_bar(self) -> list[BarElementDesc]:
        return list()

    def secondary_bar(self) -> list[BarElementDesc]:
        return list()

    def prepare(self):
        pass

    def run(self):
        thread = threading.current_thread()
        setattr(self, '__thread', thread)
        self._register_thread()

    def unmount(self):
        ThreadMixin._THREADS.remove(self)
        if hasattr(self, '__thread'):
            delattr(self, '__thread')


__all__ = ['BarElementDesc', 'ThreadMixin', ]
