from collections import defaultdict
from dataclasses import dataclass, field
from hodl.storage import *
from hodl.tools import *


@dataclass
class Candle:
    time: int
    high_price: float = field(default=None)
    low_price: float = field(default=None)

    @property
    def avg_price(self) -> None | float:
        if not isinstance(self.high_price, float) or not isinstance(self.low_price, float):
            return None
        if self.high_price <= 0.0 or self.low_price <= 0.0:
            return None
        return (self.high_price + self.low_price) / 2.0


@dataclass
class MA:
    time: int
    period: int
    price: float


@dataclass
class RSI:
    time: int
    period: int
    v: float = field(default=None)


class TaTools:
    def __init__(self, cfg: StoreConfig, db: LocalDb):
        self.db = db
        self.cfg = cfg

    def _query_history(self, days: int, day_low=True, asc=False):
        db = self.db
        if not db:
            return list()
        store_config = self.cfg
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

    def query_days(self, days: int, asc=True) -> list[Candle]:
        low_his: list[QuoteLowHistoryRow] = self._query_history(days=days, day_low=True, asc=True)
        high_his: list[QuoteHighHistoryRow] = self._query_history(days=days, day_low=False, asc=True)
        d: dict[int, list[float]] = defaultdict(list)
        for item in low_his:
            d[item.day].append(item.low_price)
        for item in high_his:
            d[item.day].append(item.high_price)
        result = [
            Candle(time=day, high_price=max(nums), low_price=min(nums))
            for day, nums in d.items() if len(nums) > 1
        ]
        result = sorted(result, key=lambda i: i.time, reverse=not asc)
        return result

    @classmethod
    def ma(cls, candles: list[Candle], period: int = 5, precision: int = 3) -> MA | None:
        if not candles or not period:
            return None
        period = abs(period)
        candles = candles.copy()
        candles.sort(key=lambda i: i.time, reverse=False)
        candles = candles[-period:]
        price = sum(i.avg_price for i in candles) / len(candles)
        price = FormatTool.adjust_precision(price, precision=precision)
        return MA(
            time=candles[-1].time,
            period=period,
            price=price,
        )

    @classmethod
    def rsi(cls, candles: list[Candle], period: int = 6) -> list[RSI]:
        init_value = 0.5
        rsi_points: list[RSI] = list()
        if len(candles) < period:
            for candle in candles:
                rsi_points.append(RSI(time=candle.time, period=period, v=init_value, ))
            return cls._transform_rsi_rate(rsi_points)
        t_max = cls._rsi_t(candles, period=period, t_max=True)
        t_abs = cls._rsi_t(candles, period=period, t_max=False)
        assert len(t_max) == len(t_abs)
        for idx in range(len(t_max)):
            max_item = t_max[idx]
            abs_item = t_abs[idx]
            max_value = max_item[1]
            abs_value = abs_item[1]
            t = max_item[0]
            assert max_item[0] == abs_item[0]
            if abs_value:
                rsi_points.append(RSI(time=t, period=period, v=max_value / abs_value))
            else:
                rsi_points.append(RSI(time=t, period=period, v=init_value))
        return cls._transform_rsi_rate(rsi_points)

    @classmethod
    def _rsi_t(cls, points: list[Candle], period: int = 6, t_max=True) -> list[tuple[int, float]]:
        sma_points: list[tuple[int, float]] = list()
        points = points.copy()
        points.sort(key=lambda i: i.time)
        # 返回一个由后一日期，和后一日价格减去前一日价格的二元组列表
        lp = points[:-1]
        ln = points[1:]
        diff_points: list[tuple[int, float]] = [(n.time, n.avg_price - p.avg_price,) for p, n in zip(lp, ln)]

        for idx in range(len(diff_points)):
            day, diff = diff_points[idx][0], diff_points[idx][1]
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
    def _transform_rsi_rate(cls, points: list[RSI]) -> list[RSI]:
        for point in points:
            point.v = FormatTool.adjust_precision(point.v * 100, precision=2)
        return points


__all__ = [
    'Candle',
    'MA',
    'RSI',
    'TaTools',
]
