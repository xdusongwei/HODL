from datetime import datetime
from collections import defaultdict
from pprint import pprint
from tigeropen.common.consts import OrderStatus
from tigeropen.trade.domain.order import Order as TigerOrder
from hodl.quote import Quote
from hodl.quote_mixin import QuoteMixin
from hodl.tools import TimeTools, VariableTools
from hodl.store import Store
from hodl.state import *
from hodl.plan_calc import ProfitRow
from hodl.simulation.fake_quote import generate_quote, FakeQuote
from hodl.unit_test import *


class SimulationStore(Store):
    TIMES_PER_LEVEL = defaultdict(int)
    EARNING = 0
    ORDER_SEQ = 1
    TIGER_ORDER_POOL: dict[int, TigerOrder] = dict()
    ORDER_POOL: dict[int, Order] = dict()
    HISTORY_QUOTE = generate_quote()
    FAKE_QUOTE: FakeQuote = None
    ENABLE_LOG_ALIVE = False
    ENABLE_BROKER = False
    ENABLE_STATE_FILE = False
    ENABLE_PROCESS_TIME = False
    PLAN = None

    def cancel_fake_order(self, order: Order):
        order_id = order.order_id
        self.TIGER_ORDER_POOL[order_id].status = OrderStatus.CANCELLED
        self.ORDER_POOL[order_id].is_canceled = True

    def create_fake_order(self, order: Order):
        order_id = self.ORDER_SEQ
        self.ORDER_SEQ += 1
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
        self.TIGER_ORDER_POOL[order_id] = tiger_order
        order.order_id = order_id
        self.ORDER_POOL[order_id] = order

    def refresh_fake_order(self, order: Order):
        pass

    def before_loop(self):
        super(SimulationStore, self).before_loop()
        try:
            self.FAKE_QUOTE = self.HISTORY_QUOTE.__next__()
        except StopIteration:
            return False
        else:
            self.sleep_mock(0)
            return True

    def now_mock(self):
        return datetime.utcfromtimestamp(self.FAKE_QUOTE.time.timestamp())

    def quote_mock(self):
        return Quote(
            symbol=self.store_config.symbol,
            open=self.FAKE_QUOTE.open,
            pre_close=self.FAKE_QUOTE.pre_close,
            latest_price=self.FAKE_QUOTE.price,
            status='NORMAL',
            time=self.FAKE_QUOTE.time,
        )

    def sleep_mock(self, secs):
        orders = self.state.plan.orders
        for order in orders:
            if not order.is_waiting_filling:
                continue
            tiger_order = self.TIGER_ORDER_POOL[order.order_id]
            tiger_order.trade_time = TimeTools.us_time_now().timestamp() * 1000
            pool_order = self.ORDER_POOL[order.order_id]
            pool_order.trade_timestamp = TimeTools.us_time_now().timestamp()
            if order.limit_price:
                if order.is_buy and order.limit_price >= self.FAKE_QUOTE.price:
                    tiger_order.avg_fill_price = self.FAKE_QUOTE.price
                    tiger_order.filled = tiger_order.quantity
                    pool_order.avg_price = self.FAKE_QUOTE.price
                    pool_order.filled_qty = pool_order.qty
                if order.is_sell and order.limit_price <= self.FAKE_QUOTE.price:
                    tiger_order.avg_fill_price = self.FAKE_QUOTE.price
                    tiger_order.filled = tiger_order.quantity
                    pool_order.avg_price = self.FAKE_QUOTE.price
                    pool_order.filled_qty = pool_order.qty
            else:
                tiger_order.avg_fill_price = self.FAKE_QUOTE.price
                tiger_order.filled = tiger_order.quantity
                pool_order.avg_price = self.FAKE_QUOTE.price
                pool_order.filled_qty = pool_order.qty

    def market_status_mock(self):
        return self.FAKE_QUOTE.market_status

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
        SimulationStore.EARNING = SimulationStore.EARNING + plan.earning
        SimulationStore.TIMES_PER_LEVEL[level] += 1


def start_simulation():
    var = VariableTools()
    store_config = var.store_configs['TIGR']
    store = SimulationStore(
        store_config=store_config,
    )

    QuoteMixin.CACHE_MARKET_STATUS = False

    mocks = [
        sleep_mock(store.sleep_mock),
        now_mock(store.now_mock),
        quote_mock(store.quote_mock),
        market_status_mock(store.market_status_mock),
        cancel_order_mock(store.cancel_fake_order),
        create_order_mock(store.create_fake_order),
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
        SimulationStore.PLAN = table
        store.run()
        if store.exception:
            raise store.exception
    except Exception as e:
        pprint(store.state)
        raise e
    finally:
        for mock in mocks:
            mock.stop()


__all__ = ['start_simulation', ]
