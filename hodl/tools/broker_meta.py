import enum
from dataclasses import dataclass, field


class BrokerTradeType(enum.Enum):
    STOCK = 'stock'
    CRYPTO = 'crypto'


@dataclass
class BrokerMeta:
    """
    描述broker类型可以做什么，以便持仓配置可以匹配到正确的broker。
    一个Broker可以支持多个BrokerMeta，例如即是可以做证券交易，也可以做加密货币交易。
    每个BrokerMeta，定义了broker允许的行为：
    参与何种交易品种；
    是否可以共享市场状态信息给其他有需要的持仓；
    是否可以共享行情信息给其他有需要的持仓；
    允许的市场状态国家代码集合；
    允许的行情信息国家代码集合；
    允许的交易品种国家代码集合；
    broker支持获取vix波动率的代码；
    """
    trade_type: BrokerTradeType = field(default=BrokerTradeType.STOCK)
    share_market_state: bool = field(default=False)
    share_quote: bool = field(default=False)
    market_status_regions: set[str] = field(default_factory=set)
    quote_regions: set[str] = field(default_factory=set)
    trade_regions: set[str] = field(default_factory=set)
    vix_symbol: str | None = field(default=None)


__all__ = ['BrokerTradeType', 'BrokerMeta', ]
