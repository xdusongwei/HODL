from typing import Generator, Any, Type, Self
from datetime import datetime, UTC
from collections import defaultdict
from pprint import pprint
from unittest.mock import patch, MagicMock, Mock
from tigeropen.common.consts import OrderStatus
from tigeropen.trade.domain.order import Order as TigerOrder
from hodl.risk_control import *
from hodl.storage import *
from hodl.quote import *
from hodl.state import *
from hodl.plan_calc import *
from hodl.quote_mixin import *
from hodl.tools import *
from hodl.store_hodl import *
from hodl.simulation.fake_quote import *


def basic_mock(client_type: type, method: str, side_effect=None, return_value=None, autospec=True):
    if side_effect is not None:
        m = Mock()
        m.side_effect = side_effect
        return patch.object(client_type, method, new=side_effect)
    else:
        return patch.object(client_type, method, side_effect=MagicMock(return_value=return_value), autospec=autospec)


def now_mock(new_function):
    return basic_mock(TimeTools, 'utc_now', side_effect=new_function)


def sleep_mock(new_function):
    return basic_mock(TimeTools, 'sleep', side_effect=new_function)


def quote_mock(new_function):
    return basic_mock(QuoteMixin, '_query_quote', side_effect=new_function)


def market_status_mock(new_function):
    return basic_mock(QuoteMixin, 'current_market_status', side_effect=new_function)


def refresh_order_mock(function):
    return basic_mock(StoreHodl, '_get_order', side_effect=function)


def cancel_order_mock(function):
    return basic_mock(StoreHodl, '_cancel_order', side_effect=function)


def submit_order_mock(function):
    return basic_mock(StoreHodl, '_submit_order', side_effect=function)


def cash_amount_mock(function):
    return basic_mock(StoreHodl, '_current_cash', side_effect=function)


def broker_cash_currency_mock(function):
    return basic_mock(StoreHodl, 'broker_cash_currency', side_effect=function)


def chip_count_mock(function):
    return basic_mock(StoreHodl, 'current_chip', side_effect=function)


def margin_mock(function):
    return basic_mock(StoreHodl, 'margin_amount', side_effect=function)


def file_read_mock(function):
    return basic_mock(LocateTools, 'read_file', side_effect=function)


def file_write_mock(function):
    return basic_mock(LocateTools, 'write_file', side_effect=function)


class SimulationStore(StoreHodl):
    ENABLE_LOG_ALIVE = False
    ENABLE_BROKER = False
    SHOW_EXCEPTION_DETAIL = True

    @classmethod
    def ci_config_path(cls):
        return LocateTools.locate_file('tests/ci/config.toml')

    @classmethod
    def config(cls):
        config_path = cls.ci_config_path()
        var = VariableTools(config_path)
        HotReloadVariableTools.set_up_var(var)
        return var

    def __init__(
            self,
            store_config: StoreConfig,
            quote_csv: str,
            ticks: list[Tick] = None,
            db: LocalDb = None,
            quote_length: int = 0,
            variable: VariableTools = None,
    ):
        super().__init__(store_config=store_config, db=db, variable=variable)
        self.mocks = list()
        self.history_quote: Generator[FakeQuote, Any, None] = \
            generate_quote(quote_csv, limit=quote_length) if quote_csv else generate_from_ticks(ticks)
        self.tiger_order_pool: dict[int, TigerOrder] = dict()
        self.order_pool: dict[int, Order] = dict()
        self.current_fake_quote: FakeQuote | None = None
        if ticks:
            self.current_fake_quote = ticks[0].to_fake_quote()
        self.order_seq = 1
        self.files: dict[str, str] = dict()

        self.earning = 0.0
        self.times_per_level = defaultdict(int)

    def reset_tickets(self, tickets: list[Tick]):
        self.history_quote = generate_from_ticks(tickets)

    def cancel_fake_order(self, order: Order):
        order_id = order.order_id
        self.tiger_order_pool[order_id].status = OrderStatus.CANCELLED
        self.order_pool[order_id].is_canceled = True

    def create_fake_order(self, order: Order):
        order_id = self.order_seq
        self.order_seq += 1
        tiger_order = TigerOrder(
            account=None,
            contract=None,
            action=None,
            order_type=None,
            quantity=order.qty,
            trade_time=int(TimeTools.us_time_now().timestamp() * 1000),
        )
        tiger_order.reason = None
        tiger_order.filled = 0
        tiger_order.avg_fill_price = None
        tiger_order.status = OrderStatus.HELD
        self.tiger_order_pool[order_id] = tiger_order
        order.order_id = order_id
        self.order_pool[order_id] = order

    def refresh_fake_order(self, order: Order):
        pass

    def before_loop(self):
        super(SimulationStore, self).before_loop()
        try:
            self.current_fake_quote = self.history_quote.__next__()
        except StopIteration:
            return False
        else:
            self.sleep_mock(0)
            return True

    def now_mock(self):
        return datetime.fromtimestamp(self.current_fake_quote.time.timestamp(), UTC)

    def quote_mock(self):
        fake_quote = self.current_fake_quote
        return Quote(
            symbol=self.store_config.symbol,
            open=fake_quote.open,
            pre_close=fake_quote.pre_close,
            latest_price=fake_quote.price,
            status=fake_quote.quote_status,
            time=fake_quote.time,
            day_low=fake_quote.day_low,
            day_high=fake_quote.day_high,
        )

    def sleep_mock(self, secs):
        orders = self.state.plan.orders
        for order in orders:
            if not order.is_waiting_filling:
                continue
            tiger_order = self.tiger_order_pool[order.order_id]
            tiger_order.trade_time = TimeTools.us_time_now().timestamp() * 1000
            pool_order = self.order_pool[order.order_id]
            pool_order.trade_timestamp = TimeTools.us_time_now().timestamp()
            if order.limit_price:
                if order.is_buy and order.limit_price >= self.current_fake_quote.price:
                    tiger_order.avg_fill_price = self.current_fake_quote.price
                    tiger_order.filled = tiger_order.quantity
                    pool_order.avg_price = self.current_fake_quote.price
                    pool_order.filled_qty = pool_order.qty
                if order.is_sell and order.limit_price <= self.current_fake_quote.price:
                    tiger_order.avg_fill_price = self.current_fake_quote.price
                    tiger_order.filled = tiger_order.quantity
                    pool_order.avg_price = self.current_fake_quote.price
                    pool_order.filled_qty = pool_order.qty
            else:
                tiger_order.avg_fill_price = self.current_fake_quote.price
                tiger_order.filled = tiger_order.quantity
                pool_order.avg_price = self.current_fake_quote.price
                pool_order.filled_qty = pool_order.qty

    def market_status_mock(self):
        return '--', '--', self.current_fake_quote.market_status

    def current_chip_mock(self) -> int:
        orders = self.state.plan.orders
        diff = sum(order.filled_qty * (1 if order.is_sell else -1) for order in orders)
        return self.store_config.max_shares - diff

    def broker_cash_currency_mock(self) -> str:
        return self.store_config.currency

    def read_file_mock(self, path: str):
        return self.files.get(path, None)

    def write_file_mock(self, path: str, text: str):
        assert isinstance(text, str)
        self.files[path] = text

    def set_up_earning(self):
        super(SimulationStore, self).set_up_earning()
        plan = self.state.plan
        last_order = None
        for order in plan.orders:
            if order.is_buy and order.is_filled:
                last_order = order
        assert last_order.avg_price
        level = plan.current_sell_level_filled()
        self.earning += plan.earning
        self.times_per_level[level] += 1

    def call_bars(self):
        self.primary_bar()
        self.secondary_bar()
        self.warning_alert_bar()

    def loop_finally(self):
        # 这里需要触发一次sleep，否则假如需要进行文件读写相关的测试，当前时间ticket的自动变动并未生效，写入文件的状态内容没有前进
        self.sleep()
        super().loop_finally()

    def run(self, output_state: bool = True):
        try:
            super().run()
            if self.exception:
                raise self.exception
        except Exception as e:
            if output_state:
                pprint(self.state)
            raise e

    def __enter__(self) -> Self:
        QuoteMixin.CACHE_MARKET_STATUS = False
        RiskControl.ORDER_DICT = dict()
        for mock in self.mocks:
            mock.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for mock in self.mocks:
            mock.stop()


class SimulationBuilder:
    @classmethod
    def _build(
        cls,
        symbol: str = None,
        ticks: list[Tick] = None,
        quote_csv: str = None,
        quote_length: int = 0,
        show_plan_table: bool = False,
        store: SimulationStore = None,
        store_config: StoreConfig = None,
        auto_run: bool = True,
        output_state: bool = True,
        store_type: Type[SimulationStore] = SimulationStore,
        db: LocalDb = None,
        broker_currency: str = None,
        cash_amount: float = 10_000_000.0,
        margin_amount: float = 0.0,
    ) -> SimulationStore:
        if ticks is None and quote_csv is None:
            raise ValueError(f'测试报价数据来源需要指定')

        if store is None:
            if not symbol and not store_config:
                raise ValueError(f'创建持仓对象需要指定symbol')
            var = SimulationStore.config()
            if store_config is None:
                store_config = var.store_configs[symbol]
            store = store_type(
                store_config=store_config,
                ticks=ticks,
                quote_csv=quote_csv,
                quote_length=quote_length,
                db=db,
                variable=var,
            )
            mocks = [
                sleep_mock(store.sleep_mock),
                now_mock(store.now_mock),
                quote_mock(store.quote_mock),
                market_status_mock(store.market_status_mock),
                cancel_order_mock(store.cancel_fake_order),
                submit_order_mock(store.create_fake_order),
                refresh_order_mock(store.refresh_fake_order),
                chip_count_mock(store.current_chip_mock),
                cash_amount_mock(lambda cls: cash_amount),
                file_read_mock(store.read_file_mock),
                file_write_mock(store.write_file_mock),
                margin_mock(lambda cls: margin_amount),
            ]
            if broker_currency:
                mocks.append(
                    broker_cash_currency_mock(lambda c: broker_currency),
                )
            else:
                mocks.append(
                    broker_cash_currency_mock(store.broker_cash_currency_mock),
                )
            store.mocks = mocks
        elif ticks:
            store.reset_tickets(ticks)

        if show_plan_table:
            store_config = store.store_config
            plan = Plan.new_plan(store_config)
            plan.base_price = 10.0
            store.state.plan = plan
            table = SimulationStore.build_table(store_config=store_config, plan=plan)
            for row in table:
                row: ProfitRow = row
                print(f'表格项: {row} totalRate:{row.total_rate}')

        if auto_run:
            with store:
                store.run(output_state=output_state)
        return store

    @classmethod
    def from_symbol(
        cls,
        symbol: str,
        ticks: list[Tick],
        auto_run: bool = True,
        output_state: bool = True,
        store_type: Type[SimulationStore] = SimulationStore,
        db: LocalDb = None,
    ):
        """
        直接读取配置文件中的持仓设定来运行测试, 即不会临时改动持仓配置的细节而运行
        """
        return cls._build(
            symbol=symbol,
            ticks=ticks,
            auto_run=auto_run,
            output_state=output_state,
            store_type=store_type,
            db=db,
        )

    @classmethod
    def from_symbol_csv(
        cls,
        symbol: str,
        quote_csv: str,
        quote_length: int,
    ):
        """
        直接读取配置文件中的持仓设定来运行测试, 但是使用 csv 行情源
        """
        return cls._build(
            symbol=symbol,
            quote_csv=quote_csv,
            quote_length=quote_length,
        )

    @classmethod
    def from_config(
        cls,
        store_config: StoreConfig,
        ticks: list[Tick],
        auto_run: bool = True,
        output_state: bool = True,
        store_type: Type[SimulationStore] = SimulationStore,
        db: LocalDb = None,
        broker_currency: str = None,
        cash_amount: float = 10_000_000.0,
        margin_amount: float = 0.0,
    ):
        """
        使用特定的持仓配置对象运行持仓
        """
        return cls._build(
            store_config=store_config,
            ticks=ticks,
            auto_run=auto_run,
            output_state=output_state,
            store_type=store_type,
            db=db,
            broker_currency=broker_currency,
            cash_amount=cash_amount,
            margin_amount=margin_amount,
        )

    @classmethod
    def resume(
        cls,
        store: SimulationStore,
        ticks: list[Tick],
        auto_run: bool = True,
        output_state: bool = True,
    ):
        """
        对已经创建的模拟持仓对象, 按照新的数据源继续执行
        """
        return cls._build(
            store=store,
            ticks=ticks,
            auto_run=auto_run,
            output_state=output_state,
        )


__all__ = [
    'now_mock',
    'sleep_mock',
    'quote_mock',
    'market_status_mock',
    'refresh_order_mock',
    'cancel_order_mock',
    'submit_order_mock',
    'cash_amount_mock',
    'chip_count_mock',
    'file_read_mock',
    'file_write_mock',
    'SimulationStore',
    'generate_quote',
    'generate_from_ticks',
    'FakeQuote',
    'Tick',
    'SimulationStore',
    'SimulationBuilder',
]
