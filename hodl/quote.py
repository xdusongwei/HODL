from datetime import datetime
from dataclasses import dataclass


@dataclass
class Quote:
    symbol: str
    open: float
    pre_close: float
    latest_price: float
    time: datetime
    status: str # 如果证券状态正常, 此字段填充 NORMAL, 停牌熔断等情形填充非 NORMAL 即可
    day_low: float = None
    day_high: float = None
    broker_name: str = '--'
    broker_display: str = '--'


@dataclass
class VixQuote:
    latest_price: float
    day_low: float
    day_high: float
    time: datetime


__all__ = ['Quote', 'VixQuote', ]
