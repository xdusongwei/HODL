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
    """
    券商通道包含8个重要的操作方法, 和 on_init, 用于交易持仓相关的初始化函数
    8个方法,可根据对券商的实际需要进行部分开发, 比如这个券商只提供行情数据, 不提供交易, 那么仅实现行情获取功能即可.
    关于市场状态: fetch_market_status;
    关于行情: fetch_quote;
    关于交易: place_order cancel_order refresh_order query_chips query_cash detect_plug_in;
    """

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
        根据 self.symbol 拉取执行行情，返回已填充好的 Quote 对象。
        """
        raise NotImplementedError

    def place_order(self, order: Order):
        """
        根据订单参数完成下单，并将订单号填充进 Order.order_id 属性。
        注意系统支持限价单和市价单，这两种下单种类必须都支持。
        """
        raise NotImplementedError

    def cancel_order(self, order: Order):
        """
        根据订单号(Order.order_id)执行撤单。
        """
        raise NotImplementedError

    def refresh_order(self, order: Order):
        """
        根据订单号(Order.order_id)更新订单。
        将订单需要的信息使用 self.modify_order_fields 方法填充进来。
        如果即方法引发了非项目定制的异常, 此次持仓循环将中止.

        提示, 虽然众多券商提供了带有各种各自标准的订单状态分类, 接入会十分麻烦,
        这里有一些处理原则, 因为该方法主要集中在如何更新 Order 对象的:
        filled_qty: 最新已成交数量
        avg_fill_price: 最新的成交均价
        is_cancelled: 是否已经撤销
        reason: 如果订单有返回错误

        所以为了处理这些字段, 需要按顺序去分析每家券商的订单数据:
        1. 把成交均价和已成交数量填充到指定字段, 无数据则填充 0
        2. 订单是否进入券商定义的'已取消'状态, 如果是, 要填充 is_cancelled = True, 避免系统撤销不能执行撤销的订单
        3. 如果命中了券商定义的各种订单状态的终结态,并且是消极的, 比如 '已过期', '已拒绝'. 再或者订单返回了人类可读的错误描述, 应该填充到 reason
        剩下的状态由框架根据 Order 属性自己判断:
        如果 filled_qty 等于 qty, 自动判断订单'已完成'
        否则, 自动判断订单'待成交'
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
        如果需要持仓线程每次都要提前检查券商服务的连通，需要在此处完成类似 ping 接口的调用工作。
        如果券商提供了类似的接口, 应尽量实现这个方法, 以避免 SDK 的连接断开时系统触发下单动作, 系统无法确认下单成否, 而引发持仓线程崩溃.
        """
        return True

    def on_init(self):
        """
        每当创建了一个持仓对象后，此方法会被调用。
        这里的场景多用于执行券商的交易操作的初始化动作，比如正式使用前必须创建交易对象；
        而BrokerApiBase.__post_init__多用于构建券商通道对象的成员变量。
        这两者不能混淆，如果初始化工作部分是持仓交易相关的, 应使用on_init, 每个持仓线程启动后会执行一次;
        如果初始化工作有关行情、市场状态, 因为它们可能因为配置上的原因, 和持仓线程并不是耦合的, 应使用__post_init__。
        """
        pass


class BrokerApiBase(BrokerApiMixin):
    BROKER_NAME = 'unknown'
    BROKER_DISPLAY = '未知'
    """
    是否在持仓进程启动后开始做broker联通性检查。
    通常建议每个持仓都需要执行检查，保证市场状态/行情/持仓/资金可正常访问， 否则持仓线程中止。

    注意：
    有些持仓的broker联通方面可能需要其他的维护动作，例如券商通道服务不是24小时随时可用，如果在broker对应的券商系统并未准备好的情况下，
    启动了本系统，该持仓的联通性检查必然失败，导致持仓线程自杀；
    反而需要等到券商通道可用时，本系统进程方可开始启动, 搞得事情很复杂，所以不需要启用这种检查。
    另外的，对于这类broker，建议完善 detect_plug_in 方法，使得在持仓线程循环里提前ping一下broker系统，
    如果不可用时不影响持仓线程存活，而是中止此次循环。
    """
    ENABLE_BOOTING_CHECK = False

    """
    交易通道的订单编号数据类型，
    默认订单号是字符串，
    如果有些交易通道必须使用数字型为参数，那么这个变量需要覆盖为int，以便系统存储合适的数据类型
    """
    ORDER_ID_TYPE = str

    # 该转换表用于将各通道的地区格式进行转换, 不在此表中的地区将被忽略
    MS_REGION_TABLE = {
        # futu region
        'market_sh': 'CN',
        'market_hk': 'HK',
        'market_us': 'US',
        # tiger region
        'CN': 'CN',
        'HK': 'HK',
        'US': 'US',
    }

    # 该转换表用于将各通道的市场状态值进行转换, 不在此表中的状态值将保留
    MS_STATUS_TABLE = {
        # futu status
        'CLOSED': 'CLOSING',
        'AFTER_HOURS_END': 'CLOSING',
        'MORNING': 'TRADING',
        'AFTERNOON': 'TRADING',
        # 如果不映射盘后时段, 盘后时间段不会更新订单信息, 这段时间即不会用来记录lsod当日的有效检查
        'AFTER_HOURS_BEGIN': 'POST_HOUR_TRADING',
        # tiger status
        'EARLY_CLOSED': 'CLOSING',
        'MARKET_CLOSED': 'CLOSING',
        # longport status
        'Normal': 'TRADING',
        'Post': 'POST_HOUR_TRADING',
    }

    @classmethod
    def set_up_var(cls, var: VariableTools):
        setattr(BrokerApiBase, '__var', var)

    @classmethod
    def query_broker_config(cls) -> dict:
        var: VariableTools = getattr(BrokerApiBase, '__var', None)
        if var is None:
            var = VariableTools()
            cls.set_up_var(var)
        return var.broker_config_dict(cls.BROKER_NAME) or dict()

    @classmethod
    def query_broker_meta(cls) -> list[BrokerMeta]:
        var: VariableTools = getattr(BrokerApiBase, '__var', None)
        if var is None:
            var = VariableTools()
        return var.broker_meta(cls.BROKER_NAME)

    def __init__(
            self,
            symbol: None | str,
            name: None | str,
            broker_config: dict = None,
            broker_meta: list[BrokerMeta] = None,
            logger: LoggerWrapper = None,
            session: requests.Session = None,
    ):
        if broker_config is None:
            broker_config = self.query_broker_config()
        if broker_meta is None:
            broker_meta = self.query_broker_meta()
        self.broker_config = broker_config.copy()
        self.broker_meta = broker_meta.copy()
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
    frequency: float
    avg_time: float | None
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
                    match api_name:
                        case 'detect_plug_in':
                            api_name = '连通测试'
                        case 'fetch_market_status':
                            api_name = '市场状态'
                        case 'fetch_quote':
                            api_name = '行情快照'
                        case 'query_cash':
                            api_name = '可用资金'
                        case 'query_chips':
                            api_name = '持仓量'
                        case 'place_order':
                            api_name = '下单'
                        case 'cancel_order':
                            api_name = '撤单'
                        case 'refresh_order':
                            api_name = '刷新订单'
                        case _:
                            api_name = api_name
                    avg_time = sum(i.time_use for i in api_set) / len(api_set) if api_set else None
                    result.append(TrackApi(
                        api_type=api_type,
                        api_name=api_name,
                        ok_times=sum(1 for i in api_set if i.is_ok),
                        error_times=sum(1 for i in api_set if not i.is_ok),
                        frequency=FormatTool.adjust_precision(len(api_set) / ttl * 60, precision=1),
                        avg_time=FormatTool.adjust_precision(avg_time, precision=3) if api_set else None,
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
            result = func(self, *args, **kwargs)
            if api_name == 'detect_plug_in' and result is False:
                is_ok = False
            return result
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
