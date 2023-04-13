import csv
import random
from decimal import Decimal
from collections import namedtuple
from dataclasses import *
from datetime import timedelta, datetime
from hodl.tools import TimeTools


FakeQuote = namedtuple('FakeQuote', ['time', 'price', 'market_status', 'open', 'pre_close', 'quote_status', ])


def _build_item(
        time: datetime,
        price: float,
        market_status: str,
        open: float,
        pre_close: float,
        quote_status: str = 'NORMAL',
):
    return FakeQuote(
        time=time,
        price=float(Decimal(price).quantize(Decimal("0.00"))),
        market_status=market_status,
        open=open,
        pre_close=pre_close,
        quote_status=quote_status,
    )


@dataclass
class Ticket:
    day: str = field()
    pre_close: float = field()
    open: float = field()
    latest: float = field()
    ms: str = field(default='TRADING')
    qs: str = field(default='NORMAL')

    def to_fake_quote(self) -> FakeQuote:
        time = datetime.fromisoformat(self.day)
        return _build_item(
            time=time,
            price=self.latest,
            market_status=self.ms,
            open=self.open,
            pre_close=self.pre_close,
            quote_status=self.qs,
        )


def generate_from_tickets(tickets: list[Ticket]):
    for ticket in tickets:
        yield ticket.to_fake_quote()


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
                seq.append(_build_item(time, p, 'POST_HOUR_TRADING', open=o, pre_close=pre_close))
                s += 1
            for _ in range(5):
                time = date + t + timedelta(seconds=s)
                seq.append(_build_item(time, p, 'CLOSING', open=o, pre_close=pre_close))
                s += 1
            for fake_quote in seq:
                yield fake_quote


__all__ = [
    'generate_quote',
    'generate_from_tickets',
    'FakeQuote',
    'Ticket',
]
