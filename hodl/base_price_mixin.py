from abc import ABC
from dataclasses import dataclass, field, asdict
import numpy
from hodl.quote import *
from hodl.store_base import *
from hodl.storage import *
from hodl.tools import *
from hodl.ta import *


@dataclass
class BasePriceItem:
    v: float = field()
    desc: str = field()
    name: str = field()


class BasePriceMixin(StoreBase, ABC):
    @property
    def enable_rework(self) -> bool:
        return not self.is_rsi_tp

    @property
    def is_rsi_tp(self) -> bool:
        return bool(self.state.ta_tumble_protect_rsi)

    def _try_reset_bp_function(self):
        date = TimeTools.date_to_ymd(TimeTools.us_time_now())
        state = self.state
        if state.bp_function_day == date:
            return
        state.bp_function = 'min'
        state.bp_function_day = date

    def _set_bp_function(self, func_name: str):
        date = TimeTools.date_to_ymd(TimeTools.us_time_now())
        state = self.state
        if state.bp_function_day != date:
            return
        state.bp_function = func_name

    def _get_bp_function(self):
        date = TimeTools.date_to_ymd(TimeTools.us_time_now())
        state = self.state
        if state.bp_function_day != date:
            return min
        if state.bp_function == 'max':
            return max
        elif state.bp_function == 'min':
            return min
        elif state.bp_function == 'median':
            return numpy.median
        else:
            return min

    def prepare_ta(self):
        self._try_reset_bp_function()
        self._set_up_ta_info()

    def _calc_hodl_price_list(self) -> list[BasePriceItem]:
        store_config, state, _ = self.args()
        symbol = store_config.symbol
        db = self.db
        quote_pre_close = state.quote_pre_close
        quote_open = state.quote_open
        low_price = state.quote_low_price
        items: list[BasePriceItem] = list()

        if db:
            con = db.conn
            base_price_row = TempBasePriceRow.query_by_symbol(con=con, symbol=symbol)
            if base_price_row and base_price_row.price > 0:
                items.append(BasePriceItem(v=base_price_row.price, desc='TempPrice', name='临时基准价'))
                return items

        items.append(BasePriceItem(v=quote_pre_close, desc='PreClosePrice', name='昨收价'))
        if quote_open:
            items.append(BasePriceItem(v=quote_open, desc='OpenPrice', name='开盘价'))
        if db and store_config.base_price_last_buy:
            con = db.conn
            days = store_config.base_price_last_buy_days
            earning_row = EarningRow.latest_earning_by_symbol(con=con, symbol=symbol, days=days)
            if earning_row and earning_row.buyback_price and earning_row.buyback_price > 0:
                items.append(BasePriceItem(v=earning_row.buyback_price, desc='BuybackPrice', name='买回价'))
        if store_config.base_price_day_low:
            if low_price is not None:
                items.append(BasePriceItem(v=low_price, desc='LowPrice', name='日最低价'))
        if state.ta_tumble_protect_alert_price is not None:
            items.append(BasePriceItem(v=state.ta_tumble_protect_alert_price, desc='TpMaPrice', name='多日均价'))

        items.sort(key=lambda i: i.v)
        return items

    def calc_base_price(self) -> float:
        """
        计算基准价格，
        触发此方法的条件，一个是盘中无任何有效订单时base_price字段无值，也就是未开始执行套利计划；另一个是套利后设定rework_price。
        正因为如此，其在状态文件中记录的一部分ta字段信息，在套利任务工作时，是不会更新的。
        Returns
        -------

        """
        self._set_up_base_price_ta_info()

        store_config, state, _ = self.args()
        match store_config.trade_strategy:
            case TradeStrategyEnum.HODL:
                items = self._calc_hodl_price_list()
            case _:
                raise NotImplementedError

        state.bp_items = [asdict(item) for item in items]
        func = self._get_bp_function()
        price = func([item.v for item in items])
        price = FormatTool.adjust_precision(price, precision=store_config.precision)

        assert price > 0.0
        return price

    def _set_up_ta_info(self):
        """
        在盘中触发的技术分析计算
        Returns
        -------

        """
        self._vix_tp_check()
        self._rsi_tp_check()

    def _set_up_base_price_ta_info(self):
        """
        当基准价格字段无效时触发的技术分析计算,
        这个过程要晚于_set_up_ta_info方法被调用。
        Returns
        -------

        """
        self._ma_tp_check()

    def _ma_tp_check(self):
        sc, state, _ = self.args()
        if not sc.base_price_tumble_protect:
            state.ta_tumble_protect_flag = None
            state.ta_tumble_protect_alert_price = None
            return
        state.ta_tumble_protect_flag = self._detect_lowest_days()
        state.ta_tumble_protect_alert_price = None
        if not sc.base_price_tumble_protect:
            return
        if not state.ta_tumble_protect_flag:
            return
        state.ta_tumble_protect_alert_price = self._tumble_protect_alert_price()
        self._set_bp_function('max')

    def _query_vix(self) -> VixQuote:
        store_config = self.store_config
        vix_quote = self.market_status_proxy.query_vix(store_config)
        return vix_quote

    def _vix_tp_check(self):
        state = self.state
        store_config = self.store_config

        state.ta_vix_high = None
        vix_limit = store_config.vix_tumble_protect
        if vix_limit is not None and vix_limit > 0.0:
            vix_quote = self._query_vix()
            if vix_quote:
                state.ta_vix_high = vix_quote.day_high
                state.ta_vix_time = FormatTool.adjust_precision(vix_quote.time.timestamp(), precision=3)
                if state.ta_vix_high >= vix_limit:
                    self._set_bp_function('max')

    def _rsi_tp_check(self):
        state = self.state
        store_config = self.store_config
        ta = TaTools(cfg=self.store_config, db=self.db)

        state.ta_tumble_protect_rsi_current = None
        if state.ta_tumble_protect_rsi is not None:
            # RSI TP locked
            self._set_bp_function('max')
            unlock_limit = state.ta_tumble_protect_rsi
            assert state.ta_tumble_protect_rsi_day
            assert state.ta_tumble_protect_rsi_period
            rsi_period = state.ta_tumble_protect_rsi_period
            rsi_day = state.ta_tumble_protect_rsi_day
            candles = ta.query_days(days=rsi_period * 20, asc=True)
            rsi_list = ta.rsi(candles, period=rsi_period)
            if store_config.tumble_protect_rsi_unlock_limit:
                # 可以随时更新上限阈值
                state.ta_tumble_protect_rsi = store_config.tumble_protect_rsi_unlock_limit
            if any(point for point in rsi_list if point.time > rsi_day and point.v >= unlock_limit):
                state.ta_tumble_protect_rsi = None
                state.ta_tumble_protect_rsi_day = None
                state.ta_tumble_protect_rsi_period = None
            if rsi_list:
                state.ta_tumble_protect_rsi_current = rsi_list[-1].v
        elif store_config.tumble_protect_rsi and state.plan.cleanable:
            # RSI TP unlocked
            # 没有有效计划时, 再判断触发RSI的逻辑, 防止计划执行中触发RSI保护
            rsi_period = store_config.tumble_protect_rsi_period
            candles = ta.query_days(days=rsi_period * 20, asc=True)
            rsi_list = ta.rsi(candles, period=store_config.tumble_protect_rsi_period)
            if rsi_list:
                rsi_day = rsi_list[-1].time
                rsi = rsi_list[-1].v
                lock_limit = store_config.tumble_protect_rsi_lock_limit
                unlock_limit = store_config.tumble_protect_rsi_unlock_limit
                assert lock_limit < unlock_limit
                if rsi <= lock_limit:
                    state.ta_tumble_protect_rsi = unlock_limit
                    state.ta_tumble_protect_rsi_period = rsi_period
                    state.ta_tumble_protect_rsi_day = rsi_day
                    self._set_bp_function('max')
                elif store_config.tumble_protect_rsi_warning_limit is not None:
                    if rsi <= store_config.tumble_protect_rsi_warning_limit:
                        self._set_bp_function('median')
            if rsi_list:
                state.ta_tumble_protect_rsi_current = rsi_list[-1].v
        else:
            state.ta_tumble_protect_rsi = None
            state.ta_tumble_protect_rsi_day = None
            state.ta_tumble_protect_rsi_period = None

    def _detect_lowest_days(self) -> bool:
        store_config = self.store_config
        ta = TaTools(cfg=store_config, db=self.db)
        tumble_protect_day_range = store_config.tumble_protect_day_range
        tumble_protect_sample_range = store_config.tumble_protect_sample_range
        history = ta.query_days(days=tumble_protect_sample_range)
        if len(history) <= tumble_protect_day_range:
            return False
        history_low = min(day.low_price for day in history) * 1.01
        recent = history[-tumble_protect_day_range:]
        recent_low = min(day.low_price for day in recent)
        return history_low >= recent_low

    def _tumble_protect_alert_price(self):
        ta = TaTools(cfg=self.store_config, db=self.db)
        candles = ta.query_days(days=10)
        if not candles:
            self.state.ta_tumble_protect_ma5 = None
            self.state.ta_tumble_protect_ma10 = None
            return None
        ma5 = ta.ma(candles, period=5, precision=self.store_config.precision)
        ma10 = ta.ma(candles, period=10, precision=self.store_config.precision)
        assert ma5.price > 0
        assert ma10.price > 0
        self.state.ta_tumble_protect_ma5 = ma5.price
        self.state.ta_tumble_protect_ma10 = ma10.price
        return max(ma5.price, ma10.price)


__all__ = ['BasePriceMixin', ]
