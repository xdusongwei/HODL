from typing import Self
import asyncio
import threading
import dataclasses
from hodl.thread_mixin import *


@dataclasses.dataclass
class _CallResult:
    result = None
    ex = None


class AsyncioProxyThread(ThreadMixin):
    LOCK = threading.RLock()
    THREAD = None
    INSTANCE = None
    COUNTER_CORO_FUNC = 0
    COUNTER_FROM_SYNC = 0
    COUNTER_CALL = 0

    def __init__(self):
        self.loop: asyncio.AbstractEventLoop = None
        self.ready = threading.Event()
        AsyncioProxyThread.INSTANCE = self

    def primary_bar(self) -> list[BarElementDesc]:
        bar = [
            BarElementDesc(
                content=f'call: {AsyncioProxyThread.COUNTER_CALL}',
                tooltip=f'异步函数处理量',
            ),
            BarElementDesc(
                content=f'future: {AsyncioProxyThread.COUNTER_CORO_FUNC}',
                tooltip=f'Future构造函数处理量',
            ),
            BarElementDesc(
                content=f'sync: {AsyncioProxyThread.COUNTER_FROM_SYNC}',
                tooltip=f'阻塞函数处理量',
            ),
        ]
        return bar

    @classmethod
    def instance(cls) -> Self:
        return AsyncioProxyThread.INSTANCE

    @classmethod
    def _try_create(cls):
        lock = AsyncioProxyThread.LOCK
        thread = AsyncioProxyThread.THREAD
        if thread is not None and cls.instance().ready.is_set():
            return
        with lock:
            if thread is None:
                thread = AsyncioProxyThread().start(name='asyncioProxy')
                AsyncioProxyThread.THREAD = thread
            cls.instance().ready.wait()

    @classmethod
    def call_coro_func(cls, func, *args):
        cls._try_create()
        instance = cls.instance()
        evt = threading.Event()

        response = _CallResult()

        def _wrap(resp: _CallResult):
            async def _aio_wrap():
                try:
                    fut = func(*args)
                    result = await fut
                    resp.result = result
                    resp.ex = None
                except Exception as ex:
                    resp.result = None
                    resp.ex = ex
                finally:
                    evt.set()
                    AsyncioProxyThread.COUNTER_CORO_FUNC += 1

            instance.loop.call_soon_threadsafe(
                instance.loop.create_task, _aio_wrap()
            )

        instance.loop.call_soon_threadsafe(
            _wrap, response,
        )
        evt.wait()
        if response.ex:
            raise response.ex
        else:
            return response.result

    @classmethod
    def call_from_sync(cls, func, *args):
        cls._try_create()
        instance = cls.instance()
        evt = threading.Event()

        response = _CallResult()

        def _wrap(resp: _CallResult):
            try:
                result = func(*args)
                resp.result = result
                resp.ex = None
            except Exception as ex:
                resp.result = None
                resp.ex = ex
            finally:
                evt.set()
                AsyncioProxyThread.COUNTER_FROM_SYNC += 1

        instance.loop.call_soon_threadsafe(
            _wrap, response,
        )
        evt.wait()
        if response.ex:
            raise response.ex
        else:
            return response.result

    @classmethod
    def call(cls, coro):
        cls._try_create()
        instance = cls.instance()
        evt = threading.Event()

        response = _CallResult()

        def _wrap(resp: _CallResult):
            async def _aio_wrap():
                try:
                    result = await coro
                    resp.result = result
                    resp.ex = None
                except Exception as ex:
                    resp.result = None
                    resp.ex = ex
                finally:
                    evt.set()
                    AsyncioProxyThread.COUNTER_CALL += 1

            instance.loop.call_soon_threadsafe(
                instance.loop.create_task, _aio_wrap()
            )

        instance.loop.call_soon_threadsafe(
            _wrap, response,
        )
        evt.wait()
        if response.ex:
            raise response.ex
        else:
            return response.result

    async def _run(self):
        self.ready.set()
        while True:
            await asyncio.sleep(1)

    def run(self):
        super().run()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._run())


__all__ = ['AsyncioProxyThread', ]
