from typing import Type
import abc
import time
import functools
import threading
from collections import defaultdict
from dataclasses import dataclass
import requests
from tigeropen.common.consts import OrderStatus
from tigeropen.trade.domain.order import Order as BrokerOrder
from hodl.quote import Quote
from hodl.tools import *
from hodl.state import *
from hodl.exception_tools import *
from hodl.tools.format import FormatTool as FMT


class BrokerApiMixin(abc.ABC):
    def fetch_market_status(self) -> BrokerMarketStatusResult:
        """
        返回此券商可以获得的市场状态，
        产生以region为键，市场状态为值的字典。
        市场状态有些值是重要的，如果券商的数据格式不一样，则它们需要做变换处理:
        TRADING: 开盘时段；
        CLOSING: 收盘时段，对于24小时全天可交易的交易所，closing_time配置项将可以自动把指定时段的TRADING状态变换为收盘，以便激活LSOD检查；
        其他值则按非活跃时段处理。
        如果该券商不支持市场状态，则返回空字典。
        """
        raise NotImplementedError

    def fetch_quote(self) -> Quote:
        """
        根据 self.symbol 拉取执行行情，返回已填充的 Quote 对象。
        """
        raise NotImplementedError

    def place_order(self, order: Order):
        """
        根据订单参数完成下单，并将订单号填充进 Order.order_id。
        """
        raise NotImplementedError

    def cancel_order(self, order: Order):
        """
        根据订单号执行撤单。
        """
        raise NotImplementedError

    def refresh_order(self, order: Order):
        """
        根据订单号更新订单。
        将订单需要的信息使用 self.modify_order_fields 方法填充进来。
        """
        raise NotImplementedError

    def query_chips(self) -> int:
        """
        返回 self.symbol 获取实际持仓数量。
        """
        raise NotImplementedError

    def query_cash(self) -> float:
        """
        获取可用资金数量。
        """
        raise NotImplementedError

    def detect_plug_in(self) -> bool:
        """
        如果需要持仓线程每次都要提前检查券商服务的连通，需要在此处完成类似ping接口的调用工作。
        """
        return True

    def on_init(self):
        """
        每当创建了一个持仓对象后，此方法会被调用。
        这里的场景多用于执行券商的操作动作，比如正式使用前必须去调用行情订阅接口；
        而BrokerApiBase.__post_init__多用于构建对象的成员变量。
        这两者不能混淆，例如测试时on_init通常不会触发，避免测试时接触到券商系统。
        """
        pass


class BrokerApiBase(BrokerApiMixin):
    BROKER_NAME = 'unknown'
    BROKER_DISPLAY = '未知'

    def __init__(
            self,
            broker_config: dict,
            broker_meta: list[BrokerMeta],
            symbol: None | str,
            name: None | str,
            logger: LoggerWrapper = None,
            session: requests.Session = None,
            conid: None | str = None,
    ):
        self.broker_config = broker_config.copy()
        self.broker_meta = broker_meta.copy()
        self.custom_client = None
        self.symbol = symbol
        self.conid = conid
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
            # tiger broker bypass，保留默认值
            broker_order: BrokerOrder = None,
    ):
        """
        更新订单信息的通用方法
        """
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
        """
        初始化对象的其他成员变量
        """
        pass

    def _override_order_fields(self, order: Order, broker_order: BrokerOrder):
        logger = self.logger
        new_order = order.copy()
        new_order.error_reason = broker_order.reason
        trade_timestamp = FMT.adjust_precision(broker_order.trade_time / 1000.0, 3) if broker_order.trade_time else None
        new_order.trade_timestamp = trade_timestamp
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


@dataclass
class TrackApi:
    api_type: Type[BrokerApiBase]
    api_name: str
    ok_times: int
    error_times: int
    # 平均TTL时间内每分钟调用次数
    frequency: int
    # 最慢的记录, 单位秒
    slowest_time: float | None


class _TrackApi:
    @dataclass
    class Node:
        api_type: Type[BrokerApiBase]
        api_name: str
        time: float
        time_use: float
        is_ok: bool

        def __hash__(self):
            return id(self)

    TTL = 600.0
    LOCK = threading.RLock()
    TIMES: dict[Type[BrokerApiBase], dict[str, set[Node]]] = defaultdict(dict)

    @classmethod
    def add(cls, node: Node):
        with _TrackApi.LOCK:
            times = _TrackApi.TIMES
            api_type_dict = times[node.api_type]
            api_type_dict.setdefault(node.api_name, set())
            removable = set()
            api_set = times[node.api_type][node.api_name]
            api_set.add(node)
            expiry_time = time.time() - _TrackApi.TTL
            api_set = _TrackApi.TIMES[node.api_type][node.api_name]
            for node in api_set:
                if node.time > expiry_time:
                    continue
                removable.add(node)
            for node in removable:
                api_set.remove(node)

    @classmethod
    def _clean_all_set(cls):
        times = _TrackApi.TIMES
        with _TrackApi.LOCK:
            for api_type, api_dict in times.items():
                for api_name, api_set in api_dict.items():
                    removable = set()
                    expiry_time = time.time() - _TrackApi.TTL
                    for node in api_set:
                        if node.time > expiry_time:
                            continue
                        removable.add(node)
                    for node in removable:
                        api_set.remove(node)

    @classmethod
    def api_report(cls):
        with _TrackApi.LOCK:
            cls._clean_all_set()
            ttl = _TrackApi.TTL
            times = _TrackApi.TIMES
            result = list()
            for api_type, api_dict in times.items():
                for api_name, api_set in api_dict.items():
                    result.append(TrackApi(
                        api_type=api_type,
                        api_name=api_name,
                        ok_times=sum(1 for i in api_set if i.is_ok),
                        error_times=sum(1 for i in api_set if not i.is_ok),
                        frequency=int(len(api_set) / ttl * 60),
                        slowest_time=max(i.time_use for i in api_set) if api_set else None,
                    ))
            result.sort(key=lambda i: (i.api_type.BROKER_DISPLAY, i.api_name, ))
            return result


def track_api(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        api_type = type(self)
        api_name = func.__name__
        is_ok = True
        start_time = time.time()
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            is_ok = False
            raise e
        finally:
            end_time = time.time()
            time_use = FormatTool.adjust_precision(max(0.0, end_time - start_time), precision=3)
            node = _TrackApi.Node(
                api_type=api_type,
                api_name=api_name,
                time=start_time,
                time_use=time_use,
                is_ok=is_ok,
            )
            _TrackApi.add(node)

    return wrapper


def track_api_report():
    return _TrackApi.api_report()


__all__ = [
    'BrokerApiMixin',
    'BrokerApiBase',
    'BrokerOrder',
    'track_api',
    'track_api_report',
]
