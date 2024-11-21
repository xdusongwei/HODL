import multiprocessing.pool
from typing import Type
from hodl.broker import *
from hodl.quote import *
from hodl.state import *
from hodl.tools import *
from hodl.exception_tools import *


class MarketStatusProxy:
    THREAD_POOL = multiprocessing.pool.ThreadPool()
    MARKET_STATUS: dict[Type[BrokerApiBase], BrokerMarketStatusResult] = dict()

    @classmethod
    def _market_status_thread(cls, b: BrokerApiBase) -> tuple[Type[BrokerApiBase], BrokerMarketStatusResult]:
        d = BrokerMarketStatusResult()
        if any(meta for meta in b.broker_meta if meta.market_status_regions):
            try:
                d.update(b.fetch_market_status())
            except Exception as e:
                d.market_error = {
                    'detail': str(e),
                }
        if any(meta for meta in b.broker_meta if meta.vix_symbol):
            vix_symbol = [meta.vix_symbol for meta in b.broker_meta if meta.vix_symbol][0]
            try:
                broker = type(b)(
                    symbol=vix_symbol,
                    name='VIX',
                    logger=b.logger,
                )
                quote = broker.fetch_quote()
                d.append_vix(quote)
            except Exception as e:
                d.vix_error = {
                    'detail': str(e),
                }
        return type(b), d

    def pull_market_status(self):
        if not self.market_status_brokers:
            return None

        results: list[tuple[Type[BrokerApiBase], BrokerMarketStatusResult]] = \
            MarketStatusProxy.THREAD_POOL.map(MarketStatusProxy._market_status_thread, self.market_status_brokers)
        all_status = dict(results)
        MarketStatusProxy.MARKET_STATUS = all_status
        return all_status

    def __init__(self, var: VariableTools = None):
        self.market_status_brokers: list[BrokerApiBase] = list()
        var = var or HotReloadVariableTools.config()
        prefer_list = var.prefer_market_status_brokers
        broker_info = sort_brokers(var=var, prefer_list=prefer_list)
        brokers = [
            t(
                symbol=None,
                name='MarketStatus',
                logger=None,
            )
            for t, d, m in broker_info
            if any(meta for meta in m if meta.market_status_regions or meta.vix_symbol)
        ]
        self.market_status_brokers = brokers

    def query_status(self, store_config: StoreConfig) -> tuple[str, str, str, ]:
        market_status_dict = self.all_status
        for broker in self.brokers:
            for meta in broker.broker_meta:
                if meta.trade_type.value != store_config.trade_type:
                    continue
                if broker.BROKER_NAME != store_config.broker and not meta.share_market_status:
                    continue
                if store_config.region not in meta.market_status_regions:
                    continue
                ms = None
                for msr in market_status_dict.get(type(broker), dict()).get(meta.trade_type.value, list()):
                    msr: MarketStatusResult = msr
                    if msr.region == store_config.region:
                        ms = msr.status
                if ms:
                    return broker.BROKER_NAME, broker.BROKER_DISPLAY, ms
        else:
            raise BrokerMismatchError(f'配置的所有broker没有任何可支持该品种获取其对应的市场状态')

    def query_vix(self, store_config: StoreConfig):
        market_status_dict = self.all_status
        for broker in self.brokers:
            for meta in broker.broker_meta:
                if meta.trade_type.value != store_config.trade_type:
                    continue
                if broker.BROKER_NAME != store_config.broker and not meta.share_market_status:
                    continue
                if store_config.region not in meta.market_status_regions:
                    continue
                d_vix = market_status_dict \
                    .get(type(broker), BrokerMarketStatusResult()) \
                    .vix
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


__all__ = [
    'MarketStatusProxy',
]
