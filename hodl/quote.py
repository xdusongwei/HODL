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


__all__ = ['Quote', ]
