import os
import json
import threading
import requests
from hodl.risk_control import RiskControl
from hodl.tools import *
from hodl.storage import LocalDb, StateRow
from hodl.bot import AlertBot
from hodl.broker_proxy import BrokerProxy
from hodl.state import *


class StoreBase:
    STATE_SLEEP = '被抑制'
    STATE_TRADE = '监控中'
    STATE_GET_OFF = '已套利'

    ENABLE_LOG_ALIVE = True
    ENABLE_BROKER = True
    ENABLE_STATE_FILE = True
    ENABLE_PROCESS_TIME = True

    SESSION = requests.Session()

    def __init__(
            self,
            store_config: StoreConfig,
            db: LocalDb = None,
    ):
        self.runtime_state: StoreState = StoreState(store_config=store_config, http_session=self.SESSION)
        self.thread_context = self.runtime_state
        self.state: State = State()
        self.broker_proxy: BrokerProxy = None
        self.risk_control: RiskControl | None = None
        self.exception: Exception | None = None
        self.process_time: int = None
        self.db = db
        self.lock = threading.Lock()

        variable = self.runtime_state.variable
        self.bot = AlertBot(
            broker=store_config.broker,
            symbol=store_config.symbol,
            chat_id=variable.telegram_chat_id,
            updater=variable.telegram_updater(),
            db=self.db,
        )

        try:
            self.init_trade_service()
        except Exception as e:
            self.logger.exception(e)
            self.exception = e
            raise e

    def load_state(self):
        if not self.ENABLE_STATE_FILE:
            return
        if not self.state_file:
            return
        runtime_state = self.runtime_state
        state = dict()
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r', encoding='utf8') as f:
                text = f.read()
                runtime_state.state_compare = TimeTools.us_day_now(), text
            state = json.loads(text)
        self.state = State(state)
        self.state.name = self.store_config.name

    def save_state(self):
        if not self.ENABLE_STATE_FILE:
            return
        runtime_state = self.runtime_state
        text = json.dumps(self.state, indent=4, sort_keys=True)
        day = TimeTools.us_time_now()
        today = TimeTools.date_to_ymd(day)
        if (today, text,) != runtime_state.state_compare:
            if self.state_file:
                with open(self.state_file, 'w', encoding='utf8') as f:
                    f.write(text)
            if self.state_archive:
                archive_path = os.path.join(self.state_archive, f'{today}.json')
                with open(archive_path, 'w', encoding='utf8') as f:
                    f.write(text)
            if db := self.db:
                row = StateRow(
                    day=int(TimeTools.date_to_ymd(day, join=False)),
                    symbol=self.store_config.symbol,
                    content=text,
                    update_time=int(TimeTools.us_time_now().timestamp()),
                )
                row.save(con=db.conn)

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
        if self.ENABLE_PROCESS_TIME:
            setattr(self, '_begin_time', TimeTools.us_time_now())
        return True

    def after_loop(self):
        self.save_state()
        if self.ENABLE_PROCESS_TIME:
            now = TimeTools.us_time_now()
            begin_time = getattr(self, '_begin_time', now)
            self.process_time = (now - begin_time).total_seconds()

    @classmethod
    def build_table(cls, store_config: StoreConfig, plan: Plan):
        plan_calc = plan.plan_calc()
        profit_table = plan_calc.profit_rows(
            base_price=plan.base_price,
            max_shares=plan.total_chips,
            buy_spread=store_config.buy_spread,
            sell_spread=store_config.sell_spread,
            precision=store_config.precision,
            shares_per_unit=store_config.shares_per_unit,
        )
        return profit_table

    def init_trade_service(self):
        if not self.ENABLE_BROKER:
            return
        self.broker_proxy = BrokerProxy(
            store_config=self.store_config,
            runtime_state=self.runtime_state,
        )
        self.broker_proxy.on_init()


__all__ = ['StoreBase', ]
