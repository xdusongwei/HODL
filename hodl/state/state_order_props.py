from dataclasses import dataclass, field


@dataclass
class OrderProps:
    """
    这个结构用于记录订单需要更新的属性
    """
    qty: int
    trade_time: float
    filled_qty: int = field(default=0)
    avg_price: float = field(default=0.0)
    is_canceled: bool = field(default=False)
    reason: str | None = field(default=None)

    @property
    def remaining(self):
        return self.qty - self.filled_qty


__all__ = ['OrderProps']
