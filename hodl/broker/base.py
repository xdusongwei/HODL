from typing import Type
import abc
import enum
from dataclasses import dataclass, field
import requests
from tigeropen.common.consts import OrderStatus
from tigeropen.trade.domain.order import Order as BrokerOrder
from hodl.quote import Quote
from hodl.tools import *
from hodl.state import *
from hodl.exception_tools import *
from hodl.tools.format import FormatTool as FMT


class BrokerTradeType(enum.Enum):
    STOCK = 'stock'
    CRYPTO = 'crypto'


@dataclass
class ApiMeta:
    """
    描述broker类型可以做什么，以便持仓配置可以匹配到正确的broker。
    一个Broker可以支持多个ApiMeta，例如即是可以做证券交易，也可以做加密货币交易。
    每个ApiMeta，定义了broker允许的行为：
    参与何种交易品种；
    是否可以共享市场状态信息给其他有需要的持仓；
    是否可以共享行情信息给其他有需要的持仓；
    允许的市场状态国家代码集合；
    允许的行情信息国家代码集合；
    允许的交易品种国家代码集合；
    """
    trade_type: BrokerTradeType = field(default=BrokerTradeType.STOCK)
    share_market_state: bool = field(default=False)
    share_quote: bool = field(default=False)
    market_status_regions: set[str] = field(default_factory=set)
    quote_regions: set[str] = field(default_factory=set)
    trade_regions: set[str] = field(default_factory=set)


class BrokerApiMixin(abc.ABC):
    def fetch_market_status(self) -> dict:
        raise NotImplementedError

    def fetch_quote(self) -> Quote:
        raise NotImplementedError

    def place_order(self, order: Order):
        raise NotImplementedError

    def cancel_order(self, order: Order):
        raise NotImplementedError

    def refresh_order(self, order: Order):
        raise NotImplementedError

    def query_chips(self) -> int:
        raise NotImplementedError

    def query_cash(self) -> float:
        raise NotImplementedError

    def detect_plug_in(self) -> bool:
        return True

    def on_init(self):
        pass


class BrokerApiBase(BrokerApiMixin):
    BROKER_NAME = 'unknown'
    META: list[ApiMeta] = []

    def __init__(
            self,
            broker_config: dict,
            symbol: str,
            name: str,
            logger: LoggerWrapper = None,
            session: requests.Session = None,
    ):
        self.broker_config = broker_config
        self.custom_client = None
        self.symbol = symbol
        self.name = name
        self.http_session = session
        self.logger = logger
        self.__post_init__()

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f'<{type(self).__name__} symbol:{self.symbol} name:{self.name}>'

    def modify_order_fields(
            self,
            order: Order,
            qty: int,
            filled_qty: int,
            avg_fill_price: float,
            trade_timestamp: float = None,
            reason: str = '',
            is_cancelled: bool = False,
            # tiger broker bypass
            broker_order: BrokerOrder = None,
    ):
        if not broker_order:
            broker_order = BrokerOrder(
                account=None,
                contract=None,
                action=None,
                order_type=None,
                quantity=qty,
                trade_time=trade_timestamp,
                filled=filled_qty,
                avg_fill_price=avg_fill_price,
            )
        broker_order.reason = reason
        broker_order.status = OrderStatus.CANCELLED if is_cancelled else OrderStatus.NEW
        self._override_order_fields(order=order, broker_order=broker_order)
        return order

    def __post_init__(self):
        pass

    def _override_order_fields(self, order: Order, broker_order: BrokerOrder):
        logger = self.logger
        new_order = order.copy()
        new_order.error_reason = broker_order.reason
        new_order.trade_timestamp = broker_order.trade_time / 1000.0 if broker_order.trade_time else None
        new_order.avg_price = broker_order.avg_fill_price
        new_order.filled_qty = broker_order.filled
        new_order.remain_qty = broker_order.remaining
        if broker_order.status == OrderStatus.CANCELLED:
            new_order.is_canceled = True

        if logger:
            if broker_order.reason and not order.error_reason:
                logger.warning(f'订单{new_order} 返回了错误消息:{broker_order.reason}')
            if broker_order.trade_time and order.trade_timestamp:
                tiger_trade_time = broker_order.trade_time / 1000.0
                if tiger_trade_time < order.trade_timestamp:
                    raise OrderOutdatedError(
                        f'新请求的订单交易时间({FMT.pretty_dt(tiger_trade_time)})'
                        f'早于保存过的({order})最新交易时间({FMT.pretty_dt(order.trade_timestamp)})')
            if broker_order.filled > order.filled_qty:
                logger.info(f'订单{new_order} 正在持续成交')
            if broker_order.remaining == 0 and order.remain_qty:
                logger.info(f'订单{new_order} 全部成交')
            if broker_order.status == OrderStatus.CANCELLED and not order.is_canceled:
                logger.info(f'订单{new_order} 被取消')

        order.change_d(new_order)


__all__ = [
    'BrokerTradeType',
    'ApiMeta',
    'BrokerApiMixin',
    'BrokerApiBase',
    'BrokerOrder',
]
