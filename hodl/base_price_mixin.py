from abc import ABC
from collections import defaultdict
from hodl.store_base import *
from hodl.storage import *
from hodl.tools import *


class BasePriceMixin(StoreBase, ABC):

    def prepare_ta(self):
        self._set_up_ta_info()

    def calc_base_price(self) -> float:
        """
        计算基准价格，
        触发此方法的条件，一个是盘中无任何有效订单时base_price字段无值，也就是未开始执行套利计划；另一个是套利后设定rework_price。
        正因为如此，其在状态文件中记录的一部分ta字段信息，在套利任务工作时，是不会更新的。
        Returns
        -------

        """
        self._set_up_base_price_ta_info()

        state = self.state
        store_config = self.store_config
        symbol = store_config.symbol
        quote_pre_close = self.state.quote_pre_close
        low_price = self.state.quote_low_price
        db = self.db
        match store_config.trade_strategy:
            case TradeStrategyEnum.HODL:
                if db:
                    con = db.conn
                    base_price_row = TempBasePriceRow.query_by_symbol(con=con, symbol=symbol)
                    if base_price_row and base_price_row.price > 0:
                        return base_price_row.price

                price_list = [quote_pre_close, ]
                if db and store_config.base_price_last_buy:
                    con = db.conn
                    days = store_config.base_price_last_buy_days
                    earning_row = EarningRow.latest_earning_by_symbol(con=con, symbol=symbol, days=days)
                    if earning_row and earning_row.buyback_price and earning_row.buyback_price > 0:
                        price_list.append(earning_row.buyback_price)
                if store_config.base_price_day_low:
                    if low_price is not None:
                        price_list.append(low_price)
                if state.ta_tumble_protect_alert_price is not None:
                    price_list.append(state.ta_tumble_protect_alert_price)
                    price = max(price_list)
                else:
                    price = min(price_list)

                assert price > 0.0
                return price
            case _:
                raise NotImplementedError

    def _set_up_ta_info(self):
        """
        在盘中触发的技术分析计算
        Returns
        -------

        """
        state = self.state
        store_config = self.store_config

        state.ta_vix_high = None
        if store_config.vix_tumble_protect is not None:
            vix_quote = self.market_status_proxy.query_vix(store_config)
            if vix_quote:
                state.ta_vix_high = vix_quote.day_high
                state.ta_vix_time = vix_quote.time.timestamp()

        state.ta_tumble_protect_rsi_current = None
        if state.ta_tumble_protect_rsi is not None:
            # RSI TP locked
            unlock_limit = state.ta_tumble_protect_rsi
            assert state.ta_tumble_protect_rsi_day
            assert state.ta_tumble_protect_rsi_period
            rsi_period = state.ta_tumble_protect_rsi_period
            rsi_day = state.ta_tumble_protect_rsi_day
            points = self._query_day_avg(days=rsi_period * 20, asc=True)
            rsi_points = self._rsi(points, period=store_config.tumble_protect_rsi_period)
            if store_config.tumble_protect_rsi:
                # 可以随时更新上限阈值
                state.ta_tumble_protect_rsi = store_config.tumble_protect_rsi
            if any(point for point in rsi_points if point[0] > rsi_day and point[1] >= unlock_limit):
                state.ta_tumble_protect_rsi = None
                state.ta_tumble_protect_rsi_day = None
                state.ta_tumble_protect_rsi_period = None
            if rsi_points:
                state.ta_tumble_protect_rsi_current = rsi_points[-1][1]
        elif store_config.tumble_protect_rsi:
            # RSI TP unlocked
            rsi_period = store_config.tumble_protect_rsi_period
            points = self._query_day_avg(days=rsi_period * 20, asc=True)
            rsi_points = self._rsi(points, period=store_config.tumble_protect_rsi_period)
            if rsi_points:
                rsi_day = rsi_points[-1][0]
                rsi = rsi_points[-1][1]
                lock_limit = store_config.tumble_protect_rsi_lock_limit
                unlock_limit = store_config.tumble_protect_rsi_unlock_limit
                assert lock_limit < unlock_limit
                if rsi <= lock_limit:
                    state.ta_tumble_protect_rsi = unlock_limit
                    state.ta_tumble_protect_rsi_period = rsi_period
                    state.ta_tumble_protect_rsi_day = rsi_day
            if rsi_points:
                state.ta_tumble_protect_rsi_current = rsi_points[-1][1]
        else:
            state.ta_tumble_protect_rsi = None
            state.ta_tumble_protect_rsi_day = None
            state.ta_tumble_protect_rsi_period = None

    def _set_up_base_price_ta_info(self):
        """
        当基准价格字段无效时触发的技术分析计算,
        这个过程要晚于_set_up_ta_info方法被调用。
        Returns
        -------

        """
        state = self.state
        state.ta_tumble_protect_flag = self._detect_lowest_days()
        state.ta_tumble_protect_alert_price = None
        if state.ta_tumble_protect_flag:
            state.ta_tumble_protect_alert_price = self._tumble_protect_alert_price()

    def _query_history(self, days: int, day_low=True, asc=False):
        db = self.db
        if not db:
            return list()
        store_config = self.store_config
        end_day = TimeTools.us_time_now()
        begin_day = TimeTools.timedelta(end_day, days=-days)
        args = dict(
            con=db.conn,
            broker=store_config.broker,
            region=store_config.region,
            symbol=store_config.symbol,
            begin_day=int(TimeTools.date_to_ymd(begin_day, join=False)),
            end_day=int(TimeTools.date_to_ymd(end_day, join=False)),
        )
        if day_low:
            history = QuoteLowHistoryRow.query_by_symbol(**args)
        else:
            history = QuoteHighHistoryRow.query_by_symbol(**args)
        if asc:
            history = history[::-1]
        return history

    def _query_day_avg(self, days: int, asc=True):
        low_his: list[QuoteLowHistoryRow] = self._query_history(days=days, day_low=True, asc=True)
        high_his: list[QuoteHighHistoryRow] = self._query_history(days=days, day_low=False, asc=True)
        d: dict[int, list[float]] = defaultdict(list)
        for item in low_his:
            d[item.day].append(item.low_price)
        for item in high_his:
            d[item.day].append(item.high_price)
        result = [(day, sum(nums) / len(nums), ) for day, nums in d.items() if len(nums) > 1]
        result = sorted(result, key=lambda i: i[0], reverse=not asc)
        return result

    def _detect_lowest_days(self) -> bool:
        store_config = self.store_config
        history: list[QuoteLowHistoryRow] = self._query_history(days=store_config.tumble_protect_day_range * 9)
        if len(history) <= store_config.tumble_protect_day_range:
            return False
        recent = history[:store_config.tumble_protect_day_range]
        return min(day.low_price for day in history) * 1.01 >= min(day.low_price for day in recent)

    def _tumble_protect_alert_price(self):
        ma5_days: list[QuoteHighHistoryRow] = self._query_history(days=5, day_low=False)
        ma5_price_list = [day.high_price for day in ma5_days]
        ma10_days: list[QuoteHighHistoryRow] = self._query_history(days=10, day_low=False)
        ma10_price_list = [day.high_price for day in ma10_days]
        if not ma5_price_list or not ma10_price_list:
            return None
        ma5 = sum(ma5_price_list) / len(ma5_price_list)
        ma5 = FormatTool.adjust_precision(ma5, precision=self.store_config.precision)
        self.state.ta_tumble_protect_ma5 = ma5
        ma10 = sum(ma10_price_list) / len(ma10_price_list)
        ma10 = FormatTool.adjust_precision(ma10, precision=self.store_config.precision)
        self.state.ta_tumble_protect_ma10 = ma10
        assert ma5 > 0
        assert ma10 > 0
        return max(ma5, ma10)

    @classmethod
    def _rsi(cls, points: list[tuple[int, float]], period: int = 6) -> list[tuple[int, float]]:
        init_value = 0.5
        rsi_points: list[tuple[int, float]] = list()
        if len(points) < period:
            for day, _ in points:
                rsi_points.append((day, init_value, ))
            return cls._transform_rsi_rate(rsi_points)
        t_max = cls._rsi_t(points, period=period, t_max=True)
        t_abs = cls._rsi_t(points, period=period, t_max=False)
        assert len(t_max) == len(t_abs)
        for idx in range(len(t_max)):
            max_item = t_max[idx]
            abs_item = t_abs[idx]
            max_value = max_item[1]
            abs_value = abs_item[1]
            assert max_item[0] == abs_item[0]
            if abs_value:
                rsi_point = (max_item[0], max_value / abs_value,)
                rsi_points.append(rsi_point)
            else:
                rsi_point = (max_item[0], init_value,)
                rsi_points.append(rsi_point)
        return cls._transform_rsi_rate(rsi_points)

    @classmethod
    def _rsi_t(cls, points: list[tuple[int, float]], period: int = 6, t_max=True) -> list[tuple[int, float]]:
        sma_points: list[tuple[int, float]] = list()
        # 返回一个由后一日期，和后一日价格减去前一日价格的二元组列表
        diff_points = [(n[0], n[1] - p[1],) for p, n in zip(points[:-1], points[1:])]
        for idx in range(len(diff_points)):
            day = diff_points[idx][0]
            diff = diff_points[idx][1]
            if not diff:
                if idx:
                    last_sma_point = sma_points[-1]
                    sma_point = (day, last_sma_point[1],)
                    sma_points.append(sma_point)
                else:
                    sma_point = (day, 0,)
                    sma_points.append(sma_point)
                continue
            if t_max:
                t = max(0.0, diff)
            else:
                t = abs(diff)
            s = t
            if idx:
                last_sma_point = sma_points[-1]
                s += last_sma_point[1] * (period - 1)
            sma_point = (day, s / period,)
            sma_points.append(sma_point)
        return sma_points

    @classmethod
    def _transform_rsi_rate(cls, sma_points: list[tuple[int, float]]) -> list[tuple[int, float]]:
        return [(day, FormatTool.adjust_precision(rate * 100, precision=2), ) for day, rate in sma_points]


__all__ = ['BasePriceMixin', ]


