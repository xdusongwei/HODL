import os
import threading
from hodl.risk_control import *
from hodl.tools import *
from hodl.storage import *
from hodl.bot import *
from hodl.proxy import *
from hodl.thread_mixin import *
from hodl.state import *


class StoreBase(ThreadMixin):
    ENABLE_LOG_ALIVE = True
    ENABLE_BROKER = True
    SHOW_EXCEPTION_DETAIL = False

    def __init__(
            self,
            store_config: StoreConfig,
            db: LocalDb = None,
    ):
        self.runtime_state: StoreState = StoreState(
            store_config=store_config,
            calendar=store_config.trading_calendar,
        )
        self.thread_context = self.runtime_state
        self.state: State = State.new()
        self.db = db
        self.lock = threading.RLock()
        self.on_state_changed = set()

        variable = self.runtime_state.variable
        self.bot = AlertBot(
            broker=store_config.broker,
            symbol=store_config.symbol,
            chat_id=variable.telegram_chat_id,
            db=db,
        )

        try:
            if self.ENABLE_BROKER:
                self.init_trade_service()
        except Exception as e:
            self.logger.exception(e)
            self.exception = e
            raise e

    @property
    def market_status_proxy(self) -> MarketStatusProxy:
        return getattr(self, '_market_status_proxy', None)

    @market_status_proxy.setter
    def market_status_proxy(self, v: MarketStatusProxy):
        setattr(self, '_market_status_proxy', v)

    @property
    def broker_proxy(self) -> BrokerProxy:
        return getattr(self, '_broker_proxy', None)

    @broker_proxy.setter
    def broker_proxy(self, v: BrokerProxy):
        setattr(self, '_broker_proxy', v)

    @property
    def risk_control(self) -> RiskControl:
        return getattr(self, '_risk_control', None)

    @risk_control.setter
    def risk_control(self, v: RiskControl):
        setattr(self, '_risk_control', v)

    @property
    def process_time(self) -> float | None:
        return getattr(self, '_process_time', None)

    @process_time.setter
    def process_time(self, v: float):
        setattr(self, '_process_time', v)

    @property
    def exception(self) -> Exception | None:
        return getattr(self, '_exception', None)

    @exception.setter
    def exception(self, v: Exception):
        setattr(self, '_exception', v)

    @classmethod
    def read_state(cls, content: str):
        state = FormatTool.json_loads(content)
        return State.new(state)

    def load_state(self):
        if not self.state_file:
            return
        text = LocateTools.read_file(self.state_file)
        if text is None:
            self.state = State.new()
        else:
            runtime_state = self.runtime_state
            runtime_state.state_compare = TimeTools.us_day_now(), text
            self.state = self.read_state(text)
        self.state.name = self.store_config.name

    def save_state(self):
        runtime_state = self.runtime_state
        text = FormatTool.json_dumps(self.state)
        day = TimeTools.us_time_now()
        today = TimeTools.date_to_ymd(day)
        changed = (today, text,) != runtime_state.state_compare
        if changed:
            if self.state_file:
                LocateTools.write_file(self.state_file, text)
            if self.state_archive:
                archive_path = os.path.join(self.state_archive, f'{today}.json')
                LocateTools.write_file(archive_path, text)
            if db := self.db:
                row = StateRow(
                    version=self.state.version,
                    day=int(TimeTools.date_to_ymd(day, join=False)),
                    symbol=self.store_config.symbol,
                    content=text,
                    update_time=int(TimeTools.us_time_now().timestamp()),
                )
                row.save(con=db.conn)
        for cb in self.on_state_changed:
            if not changed:
                continue
            try:
                cb(self)
            except Exception as e:
                self.logger.exception(f'回调状态文件变更时遇到异常{e}')

    @property
    def logger(self):
        return self.runtime_state.log.logger()

    @property
    def alive_logger(self):
        return self.runtime_state.alive_log.logger()

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

    def before_loop(self):
        self.load_state()
        setattr(self, '_begin_time', TimeTools.get_utc())
        return True

    def after_loop(self):
        self.save_state()
        now = TimeTools.get_utc()
        begin_time = getattr(self, '_begin_time', now)
        process_time = FormatTool.adjust_precision((now - begin_time).total_seconds(), 3)
        self.process_time = process_time

    def init_trade_service(self):
        self.broker_proxy = BrokerProxy(
            runtime_state=self.runtime_state,
        )
        self.market_status_proxy = MarketStatusProxy()
        self.broker_proxy.on_init()

    def thread_lock(self) -> threading.RLock:
        return self.lock

    def thread_tags(self) -> tuple:
        config = self.store_config
        return 'Store', config.broker, config.region, config.symbol,

    def args(self) -> tuple[StoreConfig, State, Plan, ]:
        return self.store_config, self.state, self.state.plan,


__all__ = ['StoreBase', ]
