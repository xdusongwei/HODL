import random
import multiprocessing.pool
from requests import Session
from hodl.broker import *
from hodl.quote import *
from hodl.state import *
from hodl.tools import *
from hodl.exception_tools import *


def sort_brokers(var: VariableTools, prefer_list: list[str] = None) -> list[tuple[Type[BrokerApiBase], dict]]:
    brokers = BROKERS.copy()
    prefer_list = prefer_list or list()
    prefer_list = prefer_list.copy()
    prefer_list.reverse()

    def _key(item: Type[BrokerApiBase]) -> tuple[int, str]:
        rank = 0
        if item.BROKER_NAME in prefer_list:
            rank = prefer_list.index(item.BROKER_NAME) + 1
        return rank, item.BROKER_NAME,

    ordered_brokers = sorted(brokers, key=_key, reverse=True)
    ordered_brokers = [
        (broker, var.broker_config_dict(name=broker.BROKER_NAME),)
        for broker in ordered_brokers
        if var.broker_config_dict(name=broker.BROKER_NAME)
    ]
    return ordered_brokers


class MarketStatusProxy:
    THREAD_POOL = multiprocessing.pool.ThreadPool()
    MARKET_STATUS: dict[Type[BrokerApiBase], dict[str, dict[str, str]]] = dict()

    @classmethod
    def _market_status_thread(cls, b: BrokerApiBase) -> tuple[Type[BrokerApiBase], dict[str, dict[str, str]]]:
        d = dict()
        if any(meta for meta in b.META if meta.market_status_regions):
            try:
                d |= b.fetch_market_status()
            except Exception as e:
                d |= {
                    '_marketStatusException': {
                        'detail': str(e),
                    },
                }
        if any(meta for meta in b.META if meta.vix_symbol):
            vix_symbol = [meta.vix_symbol for meta in b.META if meta.vix_symbol][0]
            try:
                broker = type(b)(
                    broker_config=b.broker_config,
                    symbol=vix_symbol,
                    conid=vix_symbol,
                    name='VIX',
                    logger=b.logger,
                    session=b.http_session,
                )
                quote = broker.fetch_quote()
                d |= {
                    'vix': {
                        'latest': quote.latest_price,
                        'dayHigh': quote.day_high,
                        'dayLow': quote.day_low,
                        'time': int(quote.time.timestamp()),
                    }
                }
            except Exception as e:
                d |= {
                    '_vixException': {
                        'detail': str(e),
                    },
                }
        return type(b), d

    def pull_market_status(self):
        if not self.market_status_brokers:
            return None

        results: list[tuple[Type[BrokerApiBase], dict[str, dict[str, str]]]] = \
            MarketStatusProxy.THREAD_POOL.map(MarketStatusProxy._market_status_thread, self.market_status_brokers)
        all_status = dict(results)
        MarketStatusProxy.MARKET_STATUS = all_status
        return all_status

    def __init__(self, var: VariableTools, session: Session = None):
        self.market_status_brokers: list[BrokerApiBase] = list()
        prefer_list = var.prefer_market_state_brokers
        broker_info = sort_brokers(var=var, prefer_list=prefer_list)
        brokers = [
            t(
                broker_config=d,
                symbol=None,
                name='MarketStatus',
                logger=None,
                session=session,
            )
            for t, d in broker_info
            if any(meta for meta in t.META if meta.market_status_regions or meta.vix_symbol)
        ]
        self.market_status_brokers = brokers

    def query_status(self, store_config: StoreConfig) -> str:
        market_status_dict = self.all_status
        for broker in self.brokers:
            for meta in broker.META:
                if meta.trade_type.value != store_config.trade_type:
                    continue
                if broker.BROKER_NAME != store_config.broker and not meta.share_market_state:
                    continue
                if store_config.region not in meta.market_status_regions:
                    continue
                ms = market_status_dict \
                    .get(type(broker), dict()) \
                    .get(store_config.trade_type, dict()) \
                    .get(store_config.region, None)
                if ms:
                    return ms
        else:
            raise BrokerMismatchError(f'配置的所有broker没有任何可支持该品种获取其对应的市场状态')

    def query_vix(self, store_config: StoreConfig):
        market_status_dict = self.all_status
        for broker in self.brokers:
            for meta in broker.META:
                if meta.trade_type.value != store_config.trade_type:
                    continue
                if broker.BROKER_NAME != store_config.broker and not meta.share_market_state:
                    continue
                if store_config.region not in meta.market_status_regions:
                    continue
                d_vix = market_status_dict \
                    .get(type(broker), dict()) \
                    .get('vix', dict())
                if d_vix:
                    tz = TimeTools.region_to_tz(store_config.region)
                    vix_quote = VixQuote(
                        latest_price=float(d_vix['latest']),
                        day_high=float(d_vix['dayHigh']),
                        day_low=float(d_vix['dayLow']),
                        time=TimeTools.from_timestamp(d_vix['time'], tz=tz),
                    )
                    return vix_quote
        else:
            raise BrokerMismatchError(f'配置的所有broker没有VIX数据')

    @property
    def all_status(self):
        return MarketStatusProxy.MARKET_STATUS.copy()

    @property
    def brokers(self):
        return self.market_status_brokers.copy()


class BrokerProxy:
    """
    Broker代理中介了BrokerApiBase接口调用

    下单和账户资产类方法直接寻找对应broker类型的对象
    市场状态和行情因为可以共享给多个持仓，需要中介多个broker的结果
    行情方法请求时，根据broker的顺序列表逐个拉取，直至获取成功
    市场状态需要定时统一一次性全部broker触发拉取，按Broker种类汇总保存到 MARKET_STATUS
    特定持仓需要市场状态时，根据broker顺序列表从 MARKET_STATUS 尝试取特定交易品种特定region的状态
    """

    def _query_quote(self):
        exc = None
        store_config = self.store_config
        for broker in self.quote_brokers:
            for meta in broker.META:
                if meta.trade_type.value != store_config.trade_type:
                    continue
                if broker.BROKER_NAME != store_config.broker and not meta.share_quote:
                    continue
                if store_config.region not in meta.quote_regions:
                    continue
                if meta.need_conid and not store_config.conid:
                    continue
                try:
                    quote = broker.fetch_quote()
                except Exception as e:
                    quote = None
                    exc = e
                if quote:
                    return quote
        if exc:
            raise exc
        raise QuoteScheduleOver

    # proxy APIs begin
    def query_quote(self):
        return self._query_quote()

    def place_order(self, order: Order):
        broker = self._find_trade_broker()
        return broker.place_order(order=order)

    def cancel_order(self, order: Order):
        broker = self._find_trade_broker()
        return broker.cancel_order(order=order)

    def refresh_order(self, order: Order):
        broker = self._find_trade_broker()
        return broker.refresh_order(order=order)

    def query_chips(self) -> int:
        broker = self._find_trade_broker()
        return broker.query_chips()

    def query_cash(self) -> float:
        broker = self._find_trade_broker()
        return broker.query_cash()

    def detect_plug_in(self) -> bool:
        broker = self._find_trade_broker()
        return broker.detect_plug_in()

    def on_init(self):
        broker = self._find_trade_broker()
        broker.on_init()
    # proxy APIs end

    def __init__(
            self,
            store_config: StoreConfig,
            runtime_state: StoreState,
    ):
        var = runtime_state.variable
        self.runtime_state = runtime_state
        self.store_config = store_config
        self.quote_brokers: list[BrokerApiBase] = list()
        prefer_list = var.prefer_quote_brokers
        broker_info = sort_brokers(var=var, prefer_list=prefer_list)
        brokers = [
            t(
                broker_config=d,
                symbol=store_config.symbol,
                name=store_config.name,
                logger=self.runtime_state.log.logger(),
                session=self.runtime_state.http_session,
                conid=store_config.conid,
            )
            for t, d in broker_info
            if any(meta for meta in t.META if meta.quote_regions)
        ]
        random.shuffle(brokers)
        self.quote_brokers = brokers

        self.trade_brokers = list()
        broker_info = sort_brokers(var=var)
        brokers = [
            t(
                broker_config=d,
                symbol=store_config.symbol,
                name=store_config.name,
                logger=self.runtime_state.log.logger(),
                session=self.runtime_state.http_session,
            )
            for t, d in broker_info
            if t.BROKER_NAME == store_config.broker
        ]
        self.trade_brokers = brokers

    def _find_trade_broker(self):
        broker_name = self.store_config.broker
        brokers = self.trade_brokers
        for broker in brokers:
            if broker.BROKER_NAME == broker_name:
                for meta in broker.META:
                    if meta.trade_type.value != self.store_config.trade_type:
                        continue
                    if self.store_config.region not in meta.trade_regions:
                        continue
                    return broker
        else:
            raise BrokerMismatchError

    @property
    def trade_broker(self):
        return self._find_trade_broker()


__all__ = [
    'MarketStatusProxy',
    'BrokerProxy',
]
