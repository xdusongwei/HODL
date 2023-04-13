from typing import Self, Generator, Any
from datetime import datetime
from collections import defaultdict
from pprint import pprint
from hodl.storage import *
from tigeropen.common.consts import OrderStatus
from tigeropen.trade.domain.order import Order as TigerOrder
from hodl.quote import Quote
from hodl.quote_mixin import QuoteMixin
from hodl.tools import *
from hodl.store import Store
from hodl.state import *
from hodl.plan_calc import ProfitRow
from hodl.simulation.fake_quote import generate_quote, FakeQuote
from hodl.unit_test import *


class SimulationStore(Store):
    ENABLE_LOG_ALIVE = False
    ENABLE_BROKER = False
    ENABLE_STATE_FILE = False
    ENABLE_PROCESS_TIME = False

    def __init__(
            self,
            store_config: StoreConfig,
            quote_csv: str,
            db: LocalDb = None,
            quote_length: int = 0,
    ):
        super().__init__(store_config=store_config, db=db)
        self.history_quote: Generator[FakeQuote, Any, None] = generate_quote(quote_csv, limit=quote_length)
        self.tiger_order_pool: dict[int, TigerOrder] = dict()
        self.order_pool: dict[int, Order] = dict()
        self.current_fake_quote: FakeQuote = None
        self.order_seq = 1

        self.earning = 0.0
        self.times_per_level = defaultdict(int)

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
        return datetime.utcfromtimestamp(self.current_fake_quote.time.timestamp())

    def quote_mock(self):
        return Quote(
            symbol=self.store_config.symbol,
            open=self.current_fake_quote.open,
            pre_close=self.current_fake_quote.pre_close,
            latest_price=self.current_fake_quote.price,
            status='NORMAL',
            time=self.current_fake_quote.time,
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
        return self.current_fake_quote.market_status

    def current_chip_mock(self) -> int:
        orders = self.state.plan.orders
        diff = sum(order.filled_qty * (1 if order.is_sell else -1) for order in orders)
        return self.store_config.max_shares - diff

    def current_cash_mock(self) -> float:
        return 10_000_000.0

    def set_up_earning(self):
        super(SimulationStore, self).set_up_earning()
        plan = self.state.plan
        last_order = None
        for order in plan.orders:
            if order.is_buy and order.is_filled:
                last_order = order
        assert last_order.avg_price
        level = plan.current_sell_level_filled()
        print(f"earning({TimeTools.us_day_now()} Lv{level}): ${plan.earning}, buyback:${last_order.avg_price}")
        self.earning += plan.earning
        self.times_per_level[level] += 1


def start_simulation(symbol: str, quote_csv: str, quote_length: int = 0):
    var = VariableTools()
    store_config = var.store_configs[symbol]
    store = SimulationStore(
        store_config=store_config,
        quote_csv=quote_csv,
        quote_length=quote_length,
    )

    QuoteMixin.CACHE_MARKET_STATUS = False

    mocks = [
        sleep_mock(store.sleep_mock),
        now_mock(store.now_mock),
        quote_mock(store.quote_mock),
        market_status_mock(store.market_status_mock),
        cancel_order_mock(store.cancel_fake_order),
        submit_order_mock(store.create_fake_order),
        refresh_order_mock(store.refresh_fake_order),
        chip_count_mock(store.current_chip_mock),
        cash_amount_mock(store.current_cash_mock),
    ]
    for mock in mocks:
        mock.start()
    try:
        plan = Plan.new_plan(store_config)
        plan.base_price = 10.0
        store.state.plan = plan
        table = SimulationStore.build_table(store_config=store_config, plan=plan)
        for row in table:
            row: ProfitRow = row
            print(f'表格项: {row} totalRate:{row.total_rate}')
        store.run()
        if store.exception:
            raise store.exception
    except Exception as e:
        pprint(store.state)
        raise e
    finally:
        for mock in mocks:
            mock.stop()
    return store


__all__ = [
    'start_simulation',
    'SimulationStore',
]
