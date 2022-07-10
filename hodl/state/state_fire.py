from dataclasses import dataclass
from hodl.plan_calc import ProfitTable


@dataclass
class StateFire:
    profit_table: ProfitTable
    enable_buy: bool = False
    enable_sell: bool = False
    sell_open_earlier: bool = False
    buy_open_earlier: bool = False
    sell_remain_qty: int = 0
    sell_level: int = None
    new_sell_level: int = None
    new_buy_level: int = None
    sell_limit_price: float = None
    buy_limit_price: float = None


__all__ = ['StateFire', ]
