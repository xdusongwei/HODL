from typing import Type
import os
import abc
from hodl.bot import *
from hodl.proxy import *
from hodl.risk_control import *
from hodl.state import *
from hodl.store_base import *
from hodl.tools import *
from hodl.storage import *


class StrategySelector(abc.ABC):
    """
    这个抽象类提供了一种机制,
    即不通过 @trade_strategy 装饰器而是分析持仓配置信息尝试去注册子类为一种策略.
    主要用途通常是, 比如现有的 hodl 策略, 特定持仓可能根据特定需要, 使用一个微调的版本策略去管理,
    哪些持仓需要特别管理, 则根据 config_filter 方法去尝试映射到自定义的策略类,
    这样不需要定义一个新策略名, 从而总体保留使用 hodl 的各种功能的权利, 好比原策略同名但是是继承关系的意思.
    """

    @classmethod
    def config_filter(cls, config: StoreConfig) -> Type['Store'] | None:
        return None


class Store(StoreBase):
    STRATEGY_SELECTOR_SET: set[Type[StrategySelector]] = set()
    STORE_TYPE_MAP: dict[str, Type['Store']] = dict()
    ENABLE_BROKER = True

    @classmethod
    def register_strategy(
            cls,
            strategy_name: str,
            store_type: Type['Store'],
            force_replace=False,
    ):
        assert issubclass(store_type, Store)
        if not force_replace and strategy_name in Store.STORE_TYPE_MAP:
            raise ValueError(f'注册{store_type} 使用的策略名: {strategy_name} 重复注册')
        Store.STORE_TYPE_MAP[strategy_name] = store_type

    @classmethod
    def factory(cls, store_config: StoreConfig, db: LocalDb, variable: VariableTools = None) -> 'Store':
        for t in Store.STRATEGY_SELECTOR_SET:
            c = t.config_filter(store_config)
            if c is not None:
                return c(store_config=store_config, db=db, variable=variable)
        strategy = store_config.trade_strategy
        if strategy not in Store.STORE_TYPE_MAP:
            raise NotImplementedError(f'策略{strategy}找不到对应的类型映射')
        t = Store.STORE_TYPE_MAP[strategy]
        return t(store_config=store_config, db=db, variable=variable)

    def __init__(
            self,
            store_config: StoreConfig,
            db: LocalDb = None,
            variable: VariableTools = None,
    ):
        super().__init__(store_config=store_config, db=db, variable=variable)
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

    @property
    def logger(self):
        return self.runtime_state.log.logger()

    @property
    def alive_logger(self):
        return self.runtime_state.alive_log.logger()


class IsolatedStoreBase(Store):
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

    def init_trade_service(self):
        self.broker_proxy = BrokerProxy(
            runtime_state=self.runtime_state,
        )
        self.market_status_proxy = MarketStatusProxy()
        self.broker_proxy.on_init()


def trade_strategy(name: str, force_replace=False):
    def decorator(cls: Type[Store]):
        Store.register_strategy(name, cls, force_replace=force_replace)
        return cls
    return decorator


__all__ = [
    'Store',
    'IsolatedStoreBase',
    'trade_strategy',
    'StrategySelector',
]
