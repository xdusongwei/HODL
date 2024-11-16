import enum
from dataclasses import dataclass, field


class BrokerTradeType(enum.Enum):
    STOCK = 'stock'
    CRYPTO = 'crypto'


@dataclass
class BrokerMeta:
    """
    描述 broker 类型可以做什么，以便持仓配置可以匹配到正确的 broker。
    一个 Broker 可以支持多个 BrokerMeta，例如即是可以做证券交易，也可以做加密货币交易。
    每个 BrokerMeta，定义了 broker 允许的行为：
    trade_type: 此项设置是参与何种交易品种的；
    share_market_status: 是否可以共享市场状态信息给其他有需要的持仓；
    share_quote: 是否可以共享行情信息给其他有需要的持仓；
    market_status_regions: 允许的市场状态国家代码集合；
    quote_regions: 允许的行情信息国家代码集合；
    trade_regions: 允许的交易品种国家代码集合；
    vix_symbol: broker支持获取vix波动率的代码；

    通过描述需要的券商 Meta 信息, 可以让系统明白这家券商能交易什么地区证券, 购买了那些地区市场的行情, 行情与市场状态信息能否共享给其他券商的持仓.
    以此描述用户实际情况来限制定制券商的功能范围, 以及提供市场状态和行情报价多备份线路高可用.
    """
    trade_type: BrokerTradeType = field(default=BrokerTradeType.STOCK)

    share_market_status: bool = field(default=False)
    share_quote: bool = field(default=False)
    market_status_regions: set[str] = field(default_factory=set)
    quote_regions: set[str] = field(default_factory=set)
    trade_regions: set[str] = field(default_factory=set)
    vix_symbol: str | None = field(default=None)


__all__ = ['BrokerTradeType', 'BrokerMeta', ]
