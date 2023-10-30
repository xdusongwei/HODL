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
            text = FormatTool.json_dumps(order.d)
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

    def _submit_order(self, order: Order):
        self.broker_proxy.place_order(order=order)

    def submit_order(self, order: Order, wait=False):
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
            self._submit_order(order=order)

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
    def _should_buy_market_price(
            cls,
            want: float,
            limit_price: float,
            precision: int,
            market_price_rate: float,
    ) -> bool:
        if market_price_rate and 1 > market_price_rate > 0:
            market_price = FMT.adjust_precision((1 - market_price_rate) * want, precision)
            if limit_price < market_price:
                return True
        return False

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

    @classmethod
    def _should_sell_market_price(
            cls,
            want: float,
            limit_price: float,
            precision: int,
            market_price_rate: float,
    ) -> bool:
        if market_price_rate and market_price_rate > 0:
            market_price = FMT.adjust_precision((1 + market_price_rate) * want, precision)
            if limit_price > market_price:
                return True
        return False

    def _sell_conditions_orders(self, fire_state: StateFire):
        us_date = TimeTools.us_time_now()
        state = self.state
        config = self.store_config
        plan = state.plan
        fire_state.open_earlier = False
        fire_state.enable_sell = False
        if plan.today_not_contain_sell_order:
            fire_state.enable_sell = True
        if plan.all_today_sell_completed:
            fire_state.enable_sell = True
        if config.trade_type == 'stock' and config.region in {'CN', 'US', }:
            open_time_begin, open_time_end = time(hour=9, minute=30, second=30), time(hour=9, minute=32)
            if open_time_begin <= us_date.time() <= open_time_end:
                fire_state.open_earlier = True

        vix_limit = self.store_config.vix_tumble_protect
        if fire_state.enable_sell and not plan.current_sell_level() and vix_limit is not None:
            ta_vix_high = state.ta_vix_high
            if ta_vix_high is None:
                fire_state.enable_sell = False
            elif ta_vix_high >= vix_limit:
                fire_state.enable_sell = False

        rsi_limit = self.state.ta_tumble_protect_rsi
        if fire_state.enable_sell and rsi_limit:
            fire_state.enable_sell = False

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
        use_market_price = self._should_sell_market_price(
            want=row.sell_at,
            limit_price=limit_price,
            precision=precision,
            market_price_rate=fire_state.market_price_rate,
        )
        fire_state.sell_market_price = use_market_price
        sell_order_rate = self.store_config.sell_order_rate
        legal_rate_daily = self.store_config.legal_rate_daily
        pre_close_price = state.quote_pre_close
        if limit_price * (1 - sell_order_rate) > latest_price:
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
        state = self.state
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

        if fire_state.sell_market_price:
            self.logger.info(
                f'市场价格偏离市价单系数，采用市价单下卖单'
            )
            limit_price = None
        else:
            self.logger.info(
                f'参考当前等级规则设定设定卖出价:{FMT.pretty_price(row.sell_at, config=self.store_config)}, '
                f'实际下单价格:{FMT.pretty_price(limit_price, config=self.store_config)}'
            )
        legal_rate_daily = self.store_config.legal_rate_daily
        pre_close_price = state.quote_pre_close
        precision = self.store_config.precision
        protect_price = self._calc_protect_price(
            legal_rate=legal_rate_daily,
            base_price=pre_close_price,
            precision=precision,
            should_round=True,
            is_buy=False,
        )
        self.logger.info(f'保护限价{protect_price}')
        order = Order.new_config_order(
            store_config=self.store_config,
            level=fire_state.new_sell_level,
            direction='SELL',
            qty=qty,
            limit_price=limit_price,
            protect_price=protect_price
        )
        self.submit_order(
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
    def _calc_protect_price(
            cls,
            legal_rate,
            base_price,
            precision,
            should_round=True,
            is_buy=True,
    ) -> float | None:
        """
        中信证券需要填写保护限价
        """
        if not legal_rate:
            return None
        lower = (1.0 - legal_rate) * base_price
        higher = (1.0 + legal_rate) * base_price
        if should_round:
            lower = FMT.adjust_precision(lower, precision)
            higher = FMT.adjust_precision(higher, precision)
        if is_buy:
            return higher
        else:
            return lower

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
        return lower <= target_price <= higher

    @classmethod
    def _buy_want(cls, buy_at: float, give_up_price) -> float:
        if give_up_price:
            return give_up_price
        return buy_at

    def _buy_conditions_price_range(self, fire_state: StateFire):
        if not fire_state.enable_buy:
            return
        state = self.state
        plan = state.plan
        store_config = self.store_config
        buy_order_rate = store_config.buy_order_rate
        legal_rate_daily = store_config.legal_rate_daily
        pre_close_price = state.quote_pre_close
        precision = store_config.precision
        latest_price = state.quote_latest_price
        profit_table = fire_state.profit_table
        row = profit_table.row_by_level(level=fire_state.new_buy_level)
        want = self._buy_want(buy_at=row.buy_at, give_up_price=plan.give_up_price)
        limit_price = self._best_buy_price(
            want=want,
            open_price=state.quote_open,
            latest_price=latest_price,
            is_earlier=fire_state.buy_open_earlier,
            precision=precision,
        )
        use_market_price = self._should_buy_market_price(
            want=want,
            limit_price=limit_price,
            precision=precision,
            market_price_rate=fire_state.market_price_rate,
        )
        fire_state.buy_market_price = use_market_price
        if limit_price * (1 + buy_order_rate) < latest_price:
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
        if fire_state.buy_market_price:
            self.logger.info(f'市场价格偏离市价单系数，采用市价单下买单')
            limit_price = None
        else:
            self.logger.info(f'买单实际下单价格{FMT.pretty_price(limit_price, config=self.store_config)}')
        self.logger.info(f'买单下单数量{volume}')
        legal_rate_daily = self.store_config.legal_rate_daily
        pre_close_price = state.quote_pre_close
        precision = self.store_config.precision
        protect_price = self._calc_protect_price(
            legal_rate=legal_rate_daily,
            base_price=pre_close_price,
            precision=precision,
            should_round=True,
            is_buy=True,
        )
        self.logger.info(f'保护限价{protect_price}')
        order = Order.new_config_order(
            store_config=self.store_config,
            level=fire_state.new_buy_level,
            direction='BUY',
            qty=volume,
            limit_price=limit_price,
            protect_price=protect_price
        )
        self.submit_order(
            order=order,
        )
        self.logger.info(f'买单指令完成，订单:{order}')

    def try_fire_buy(self, fire_state: StateFire):
        self._buy_conditions_level_and_orders(fire_state=fire_state)
        self._buy_conditions_check_orders()
        self._buy_conditions_price_range(fire_state=fire_state)
        self._submit_buy_order(fire_state=fire_state)


__all__ = ['TradeMixin', ]
