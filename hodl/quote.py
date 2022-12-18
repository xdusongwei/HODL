from datetime import datetime
from dataclasses import dataclass


@dataclass
class Quote:
    symbol: str
    open: float
    pre_close: float
    latest_price: float
    time: datetime
    status: str
    day_low: float = None
    day_high: float = None


@dataclass
class VixQuote:
    latest_price: float
    day_low: float
    day_high: float
    time: datetime


__all__ = ['Quote', 'VixQuote', ]
