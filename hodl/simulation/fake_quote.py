import re
import csv
import random
from collections import namedtuple
from dataclasses import *
from datetime import timedelta, datetime
from hodl.tools import *


FakeQuote = namedtuple(
    'FakeQuote',
    ['time', 'price', 'market_status', 'open', 'pre_close', 'quote_status', 'day_low', 'day_high', ]
)


def _build_item(
        time: datetime,
        price: float,
        market_status: str,
        open: float,
        pre_close: float,
        quote_status: str = 'NORMAL',
        day_low: float = None,
        day_high: float = None,
):
    return FakeQuote(
        time=time,
        price=FormatTool.adjust_precision(price, 2),
        market_status=market_status,
        open=open,
        pre_close=pre_close,
        quote_status=quote_status,
        day_low=day_low,
        day_high=day_high,
    )


@dataclass
class Tick:
    """
    测试使用的行情时间片,
    这是策略的唯一输入来源, 一些时间相关的股价模拟信息和市场标的状态信息.
    """
    time: str = field()
    "时间片的时间, 格式类似: 23-04-10T09:30:00-04:00:00"
    pre_close: float = field()
    "昨日收盘价"
    open: float = field()
    "开盘价"
    latest: float = field()
    "最新价"
    ms: str = field(default='TRADING')
    "此刻市场状态"
    qs: str = field(default='NORMAL')
    "此刻标的状态"
    low: float = field(default=None)
    "日最低价"
    high: float = field(default=None)
    "日最高价"

    def to_fake_quote(self) -> FakeQuote:
        if re.match(r'^\d{2}-\d{2}-\d{2}', self.time):
            day = f'20{self.time}'
        else:
            day = self.time
        time = datetime.fromisoformat(day)
        return _build_item(
            time=time,
            price=self.latest,
            market_status=self.ms,
            open=self.open,
            pre_close=self.pre_close,
            quote_status=self.qs,
            day_low=self.low,
            day_high=self.high,
        )


def generate_from_ticks(ticks: list[Tick]):
    for tick in ticks:
        yield tick.to_fake_quote()


def generate_quote(csv_path, coin=None, limit: int = 0):
    with open(csv_path, newline='') as csvfile:
        spamreader = csv.reader(csvfile, delimiter=',', quotechar='|')
        for idx, row in enumerate(spamreader):
            if limit and limit <= idx:
                break
            timestamp, o, h, l, c, pc = row
            date = TimeTools.from_timestamp(int(timestamp) / 1000.0)
            o = float(o)
            high = float(h)
            low = float(l)
            c = float(c)
            pre_close = float(pc)

            seq = list()
            t = timedelta(hours=9, minutes=0, seconds=0)
            s = 0
            p = o

            for _ in range(5):
                time = date + t + timedelta(seconds=s)
                seq.append(_build_item(time, p, 'PRE_HOUR_TRADING', open=o, pre_close=pre_close))
                s += 1

            t = timedelta(hours=9, minutes=30, seconds=0)
            s = 0
            for _ in range(5):
                time = date + t + timedelta(seconds=s)
                seq.append(_build_item(time, p, 'TRADING', open=o, pre_close=pre_close))
                s += 1

            t = timedelta(hours=9, minutes=30, seconds=30)
            s = 0
            if coin is None:
                coin = random.randint(0, 1)
            p = o
            if coin:
                while p <= high:
                    time = date + t + timedelta(seconds=s)
                    seq.append(_build_item(time, p, 'TRADING', open=o, pre_close=pre_close))
                    p += 0.01
                    s += 1
                while p >= low:
                    time = date + t + timedelta(seconds=s)
                    seq.append(_build_item(time, p, 'TRADING', open=o, pre_close=pre_close))
                    p -= 0.01
                    s += 1
            else:
                while p >= low:
                    time = date + t + timedelta(seconds=s)
                    seq.append(_build_item(time, p, 'TRADING', open=o, pre_close=pre_close))
                    p -= 0.01
                    s += 1
                while p <= high:
                    time = date + t + timedelta(seconds=s)
                    seq.append(_build_item(time, p, 'TRADING', open=o, pre_close=pre_close))
                    p += 0.01
                    s += 1
            if p >= c:
                while p >= c:
                    time = date + t + timedelta(seconds=s)
                    seq.append(_build_item(time, p, 'TRADING', open=o, pre_close=pre_close))
                    p -= 0.01
                    s += 1
            else:
                while p <= c:
                    time = date + t + timedelta(seconds=s)
                    seq.append(_build_item(time, p, 'TRADING', open=o, pre_close=pre_close))
                    p += 0.01
                    s += 1
            for _ in range(5):
                time = date + t + timedelta(seconds=s)
                seq.append(_build_item(time, p, 'TRADING', open=o, pre_close=pre_close))
                s += 1

            t = timedelta(hours=16, minutes=0, seconds=0)
            s = 0
            for _ in range(5):
                time = date + t + timedelta(seconds=s)
                seq.append(_build_item(time, p, 'CLOSING', open=o, pre_close=pre_close))
                s += 1
            for _ in range(5):
                time = date + t + timedelta(seconds=s)
                seq.append(_build_item(time, p, 'CLOSING', open=o, pre_close=pre_close))
                s += 1
            for fake_quote in seq:
                yield fake_quote


__all__ = [
    'generate_quote',
    'generate_from_ticks',
    'FakeQuote',
    'Tick',
]
