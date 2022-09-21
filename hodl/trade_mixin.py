import json
from abc import ABC
from datetime import time
from expiringdict import ExpiringDict
from hodl.store_base import StoreBase
from hodl.state import *
from hodl.storage import *
from hodl.tools import *
from hodl.tools import FormatTool as FMT


class TradeMixin(StoreBase, ABC):
    __ORDER_DUMPS = ExpiringDict(max_len=1000, max_age_seconds=24 * 60 * 60)

    def _get_order(self, order: Order):
        self.broker_proxy.refresh_order(order=order)
        return order

    def refresh_order(self, order: Order):
        symbol = order.symbol
        if order.refreshable:
            self._get_order(order=order)
        if db := self.db:
            unique_id = order.unique_id
            text = json.dumps(order.d, indent=4, sort_keys=True)
            if self.__ORDER_DUMPS.get(unique_id) != text:
                row = OrderRow(
                    unique_id=unique_id,
                    symbol=symbol,
                    order_id=str(order.order_id),
                    region=order.region,
                    broker=order.broker,
                    content=text,
                    create_time=int(order.create_timestamp),
                    update_time=int(TimeTools.us_time_now().timestamp()),
                )
                row.save(con=db.conn)
                self.__ORDER_DUMPS[unique_id] = text

    def refresh_orders(self):
        plan = self.state.plan
        orders = plan.orders
        for order in orders:
            self.refresh_order(order=order)

    def _cancel_order(self, order: Order):
        assert order.order_id
        self.broker_proxy.cancel_order(order=order)

    def cancel_order(self, order: Order, wait=False):
        if not order.cancelable:
            raise ValueError(f'订单状态不支持撤销')
        self._cancel_order(order=order)
        if wait:
            TimeTools.sleep(10.0)
            self.refresh_order(order=order)
            assert order.is_canceled
        order.is_canceled = True

    def _create_order(self, order: Order):
        self.broker_proxy.place_order(order=order)

    def create_order(self, order: Order, wait=False):
        assert order.qty > 0
        order.region = self.store_config.region
        order.broker = self.store_config.broker
        if order.create_timestamp is None:
            order.create_timestamp = TimeTools.us_time_now().timestamp()
        if order.order_day is None:
            order.order_day = TimeTools.us_day_now()
        order.currency = self.store_config.currency
        order.filled_qty = 0
        order.remain_qty = order.qty
        order.avg_price = None

        def _wrap():
            self._create_order(order=order)

        self.risk_control.place_order_check(
            order=order,
            function=_wrap,
        )
        plan = self.state.plan
        plan.latest_order_day = TimeTools.us_day_now()
        self.state.plan.append_order(order=order)
        if wait:
            TimeTools.sleep(8)
            self.refresh_order(order=order)
            assert order.is_filled
        return order.order_id

    def current_chip(self) -> int:
        return self.broker_proxy.query_chips()

    def current_cash(self) -> float:
        return self.broker_proxy.query_cash()

    @classmethod
    def _best_buy_price(
            cls,
            want: float,
            open_price: float,
            latest_price: float,
            is_earlier: bool,
            precision: int,
    ) -> float:
        limit_price = want
        if is_earlier and open_price < limit_price:
            limit_price = open_price
        if latest_price and latest_price < limit_price:
            limit_price = latest_price
        limit_price = FMT.adjust_precision(limit_price, precision)
        return limit_price

    @classmethod
    def _best_sell_price(
            cls,
            want: float,
            open_price: float,
            latest_price: float,
            is_earlier: bool,
            precision: int,
    ) -> float:
        limit_price = want
        if is_earlier and open_price > limit_price:
            limit_price = open_price
        if latest_price and latest_price > limit_price:
            limit_price = latest_price
        limit_price = FMT.adjust_precision(limit_price, precision)
        return limit_price

    def _sell_conditions_orders(self, fire_state: StateFire):
        us_date = TimeTools.us_time_now()
        state = self.state
        plan = state.plan
        fire_state.open_earlier = False
        fire_state.enable_sell = False
        if plan.today_not_contain_sell_order:
            fire_state.enable_sell = True
            if time(hour=9, minute=30, second=30) <= us_date.time() <= time(hour=9, minute=32):
                fire_state.open_earlier = True
        if plan.all_today_sell_completed:
            fire_state.enable_sell = True

    def _sell_conditions_check_qty(self, fire_state: StateFire):
        state = self.state
        plan = state.plan
        profit_table = fire_state.profit_table
        fire_state.sell_level = plan.current_sell_level()
        assert fire_state.sell_level >= 0
        fire_state.new_sell_level = fire_state.sell_level

        if not fire_state.enable_sell:
            return

        assert plan.sell_order_active_count() == 0
        if fire_state.sell_level > profit_table.size:
            raise ValueError(f'历史订单最高level({fire_state.sell_level})超过了设计上限{profit_table.size}')

        if fire_state.sell_level > 0:
            volume = plan.total_sell_by_level(level=fire_state.sell_level)
            row = profit_table.row_by_level(level=fire_state.sell_level)
            if volume > row.shares:
                raise ValueError(f'level{fire_state.sell_level}总成交卖出量{volume}超过了设定数量{row.shares}股')
            elif volume == row.shares:
                fire_state.new_sell_level = fire_state.sell_level + 1
            elif volume < row.shares:
                fire_state.sell_remain_qty = row.shares - volume
        else:
            fire_state.new_sell_level = 1

    @classmethod
    def _sell_conditions_skip_new_level_overflow(cls, fire_state: StateFire):
        if not fire_state.enable_sell:
            return

        profit_table = fire_state.profit_table
        # new_sell_level 可能会超过计划表项目数，超界的情形在这里显式排除，在挂买单逻辑处会需要特殊这个情形
        assert 1 <= fire_state.new_sell_level <= profit_table.size + 1
        if fire_state.new_sell_level > profit_table.size:
            fire_state.enable_sell = False

    def _sell_conditions_price_range(self, fire_state: StateFire):
        if not fire_state.enable_sell:
            return
        state = self.state
        latest_price = state.quote_latest_price
        profit_table = fire_state.profit_table
        precision = self.store_config.precision
        row = profit_table.row_by_level(level=fire_state.new_sell_level)
        assert row.sell_at
        limit_price = self._best_sell_price(
            want=row.sell_at,
            open_price=state.quote_open,
            latest_price=latest_price,
            is_earlier=fire_state.sell_open_earlier,
            precision=precision,
        )
        sell_order_rate = self.store_config.sell_order_rate
        legal_rate_daily = self.store_config.legal_rate_daily
        pre_close_price = state.quote_pre_close
        if limit_price > sell_order_rate * latest_price:
            fire_state.enable_sell = False
        elif not self._legal_price_limit(
                    target_price=limit_price,
                    legal_rate=legal_rate_daily,
                    base_price=pre_close_price,
                    precision=precision,
                    should_round=True,
                ):
            fire_state.enable_sell = False
        else:
            fire_state.sell_limit_price = limit_price

    def _submit_sell_order(self, fire_state: StateFire):
        if not fire_state.enable_sell:
            return

        profit_table = fire_state.profit_table
        self.logger.info(f'根据level{fire_state.new_sell_level}设置新卖单')
        row = profit_table.row_by_level(level=fire_state.new_sell_level)
        if fire_state.sell_remain_qty:
            self.logger.info(f'参考上次剩余未成交设定新卖单数量:{fire_state.sell_remain_qty}')
            qty = fire_state.sell_remain_qty
        else:
            self.logger.info(f'参考当前等级规则设定新卖单数量:{row.shares}')
            qty = row.shares
        assert qty
        assert row.sell_at
        limit_price = fire_state.sell_limit_price
        assert limit_price
        self.logger.info(
            f'参考当前等级规则设定设定卖出价:{FMT.pretty_price(row.sell_at, config=self.store_config)}, '
            f'实际下单价格:{FMT.pretty_price(limit_price, config=self.store_config)}'
        )
        order = Order.new_order(
            symbol=self.store_config.symbol,
            region=self.store_config.region,
            broker=self.store_config.broker,
            currency=self.store_config.currency,
            level=fire_state.new_sell_level,
            direction='SELL',
            qty=qty,
            limit_price=limit_price,
            precision=self.store_config.precision,
            spread=self.store_config.sell_spread,
        )
        self.create_order(
            order=order,
        )
        self.logger.info(f'下新卖单成功,订单:{order}')

    def try_fire_sell(self, fire_state: StateFire):
        self._sell_conditions_orders(fire_state=fire_state)
        self._sell_conditions_check_qty(fire_state=fire_state)
        self._sell_conditions_skip_new_level_overflow(fire_state=fire_state)
        self._sell_conditions_price_range(fire_state=fire_state)
        self._submit_sell_order(fire_state=fire_state)

    def _buy_conditions_level_and_orders(self, fire_state: StateFire):
        us_date = TimeTools.us_time_now()
        state = self.state
        plan = state.plan
        fire_state.enable_buy = False
        fire_state.buy_open_earlier = False

        if plan.current_sell_level_filled() > 0:
            fire_state.new_buy_level = plan.current_sell_level_filled()
            if not plan.today_contains_buy_level(level=fire_state.new_buy_level):
                if time(hour=9, minute=30, second=20) <= us_date.time():
                    fire_state.enable_buy = True
        if time(hour=9, minute=30, second=30) <= us_date.time() <= time(hour=9, minute=32):
            fire_state.buy_open_earlier = True

    def _buy_conditions_check_orders(self):
        plan = self.state.plan
        assert plan.sell_order_active_count() <= 1
        assert plan.buy_order_active_count() <= 1

    @classmethod
    def _legal_price_limit(
            cls,
            target_price,
            legal_rate,
            base_price,
            precision,
            should_round=True,
    ) -> bool:
        if not legal_rate:
            return True
        lower = (1.0 - legal_rate) * base_price
        higher = (1.0 + legal_rate) * base_price
        if should_round:
            lower = FMT.adjust_precision(lower, precision)
            higher = FMT.adjust_precision(higher, precision)
        else:
            lower = (1.0 - legal_rate) * base_price
            higher = (1.0 + legal_rate) * base_price
        return lower <= target_price <= higher

    def _buy_conditions_price_range(self, fire_state: StateFire):
        if not fire_state.enable_buy:
            return
        state = self.state
        store_config = self.store_config
        buy_order_rate = store_config.buy_order_rate
        legal_rate_daily = store_config.legal_rate_daily
        pre_close_price = state.quote_pre_close
        precision = store_config.precision
        latest_price = state.quote_latest_price
        profit_table = fire_state.profit_table
        row = profit_table.row_by_level(level=fire_state.new_buy_level)
        limit_price = self._best_buy_price(
            want=row.buy_at,
            open_price=state.quote_open,
            latest_price=latest_price,
            is_earlier=fire_state.buy_open_earlier,
            precision=precision,
        )
        if limit_price < buy_order_rate * latest_price:
            fire_state.enable_buy = False
        elif not self._legal_price_limit(
                    target_price=limit_price,
                    legal_rate=legal_rate_daily,
                    base_price=pre_close_price,
                    precision=precision,
                    should_round=True,
                ):
            fire_state.enable_buy = False
        else:
            fire_state.buy_limit_price = limit_price

    def _submit_buy_order(self, fire_state: StateFire):
        if not fire_state.enable_buy:
            return

        state = self.state
        plan = state.plan
        profit_table = fire_state.profit_table
        self.logger.info(f'准备下level{fire_state.new_buy_level}买单')
        assert 0 < fire_state.new_buy_level <= profit_table.size
        latest_order = plan.latest_today_buy_order()
        if latest_order and latest_order.is_waiting_filling:
            self.logger.info(f'需要对当前买单{latest_order}执行撤销')
            self.cancel_order(order=latest_order, wait=True)
            self.logger.info(f'撤销当前买单{latest_order}结束, 成交{latest_order.filled_qty}股')
        assert plan.buy_order_not_active()
        volume = plan.total_volume_not_active()
        row = profit_table.row_by_level(level=fire_state.new_buy_level)
        limit_price = fire_state.buy_limit_price
        self.logger.info(f'买单计划下单价格{FMT.pretty_price(row.buy_at, config=self.store_config)}')
        self.logger.info(f'买单实际下单价格{FMT.pretty_price(limit_price, config=self.store_config)}')
        self.logger.info(f'买单下单数量{volume}')
        order = Order.new_order(
            symbol=self.store_config.symbol,
            region=self.store_config.region,
            broker=self.store_config.broker,
            currency=self.store_config.currency,
            level=fire_state.new_buy_level,
            direction='BUY',
            qty=volume,
            limit_price=limit_price,
            precision=self.store_config.precision,
            spread=self.store_config.buy_spread,
        )
        self.create_order(
            order=order,
        )
        self.logger.info(f'买单指令完成，订单:{order}')

    def try_fire_buy(self, fire_state: StateFire):
        self._buy_conditions_level_and_orders(fire_state=fire_state)
        self._buy_conditions_check_orders()
        self._buy_conditions_price_range(fire_state=fire_state)
        self._submit_buy_order(fire_state=fire_state)

    def try_slaving(self, hedge_config: HedgeConfig):
        if hedge_config.type != 'oneSide':
            return
        plan = self.state.plan
        master_symbol = hedge_config.master
        db = self.db
        if not db:
            return
        master_row = StateRow.query_by_symbol_latest(con=db.conn, symbol=master_symbol)
        if not master_row:
            return
        master_state = self.read_state(master_row.content)
        master_plan = master_state.plan
        master_total_chips = master_plan.total_chips
        master_sold_chips = master_plan.total_volume_not_active()
        assert master_total_chips >= master_sold_chips >= 0
        if plan.master_total_chips:
            assert master_total_chips == plan.master_total_chips

        try:
            if not master_total_chips:
                return
            if not plan.total_chips:
                return

            shares_per_unit = self.store_config.shares_per_unit
            sold_diff = master_sold_chips - plan.master_sold_chips
            assert abs(sold_diff) <= master_total_chips
            qty = int(abs(sold_diff) / master_total_chips * plan.total_chips)
            qty = (qty // shares_per_unit) * shares_per_unit
            if qty <= 0:
                return
            if sold_diff > 0:
                direction = 'BUY'
            elif sold_diff < 0:
                direction = 'SELL'
            else:
                return
            self.logger.info(f'slave持仓准备追踪变动，方向:{direction}, 数量:{qty}')
            order = Order.new_order(
                symbol=self.store_config.symbol,
                region=self.store_config.region,
                broker=self.store_config.broker,
                currency=self.store_config.currency,
                level=0,
                direction=direction,
                qty=qty,
                limit_price=None,
                precision=self.store_config.precision,
                spread=self.store_config.buy_spread,
            )
            self.create_order(
                order=order,
            )
            self.create_order(order=order)
            self.logger.info(f'slave市价下单完毕: {order}')
        finally:
            plan.master_total_chips = master_total_chips
            plan.master_sold_chips = master_sold_chips


__all__ = ['TradeMixin', ]
