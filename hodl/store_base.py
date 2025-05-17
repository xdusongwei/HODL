import threading
from hodl.tools import *
from hodl.storage import *
from hodl.thread_mixin import *
from hodl.state import *


class StoreBase(ThreadMixin):
    def __init__(
            self,
            store_config: StoreConfig,
            db: LocalDb = None,
            variable: VariableTools = None,
    ):
        self.runtime_state: StoreState = StoreState(
            store_config=store_config,
            calendar=store_config.trading_calendar,
            variable=variable,
        )
        self.thread_context = self.runtime_state
        self.state: State = State.new()
        self.db = db
        self.lock = threading.RLock()

        self.thread_version = 0

    def prepare(self):
        super().prepare()
        self.thread_version += 1

    def kill(self):
        super().kill()

    def init_trade_service(self):
        raise NotImplementedError

    @property
    def store_config(self) -> StoreConfig:
        return self.runtime_state.store_config

    @property
    def state_file(self) -> str | None:
        return self.store_config.state_file_path

    @property
    def state_archive(self) -> str | None:
        return self.store_config.state_archive_folder

    @property
    def thread_context(self) -> StoreState:
        ctx = threading.local()
        return ctx.runtime_store_state

    @thread_context.setter
    def thread_context(self, runtime_state: StoreState):
        ctx = threading.local()
        ctx.runtime_store_state = runtime_state

    def thread_lock(self) -> threading.RLock:
        return self.lock

    def thread_tags(self) -> tuple:
        config = self.store_config
        return 'Store', config.broker, config.region, config.symbol,

    @property
    def process_time(self) -> float | None:
        return getattr(self, '_process_time', None)

    @process_time.setter
    def process_time(self, v: float):
        setattr(self, '_process_time', v)


__all__ = ['StoreBase', ]
