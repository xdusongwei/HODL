from hodl.broker import *
from hodl.state import *
from hodl.exception_tools import *


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
            for meta in broker.broker_meta:
                if meta.trade_type.value != store_config.trade_type:
                    continue
                if broker.BROKER_NAME != store_config.broker and not meta.share_quote:
                    continue
                if store_config.region not in meta.quote_regions:
                    continue
                try:
                    quote = broker.fetch_quote()
                    assert isinstance(quote.pre_close, float)
                    assert isinstance(quote.latest_price, float)
                    assert isinstance(quote.day_high, float)
                    assert isinstance(quote.day_low, float)
                    assert isinstance(quote.open, float)
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
        chips = broker.query_chips()
        assert isinstance(chips, int)
        return chips

    def query_cash(self) -> float:
        broker = self._find_trade_broker()
        cash_amount = broker.query_cash()
        assert isinstance(cash_amount, float)
        return cash_amount

    def detect_plug_in(self) -> bool:
        broker = self._find_trade_broker()
        return broker.detect_plug_in()

    def on_init(self):
        broker = self._find_trade_broker()
        broker.on_init()
    # proxy APIs end

    def __init__(
        self,
        runtime_state: StoreState,
    ):
        store_config = runtime_state.store_config
        var = runtime_state.variable
        self.runtime_state = runtime_state
        self.store_config = store_config
        self.quote_brokers: list[BrokerApiBase] = list()
        prefer_list = store_config.prefer_quote_brokers or var.prefer_quote_brokers or list()
        broker_info = sort_brokers(var=var, prefer_list=prefer_list)
        brokers = [
            t(
                symbol=store_config.symbol,
                name=store_config.name,
                logger=self.runtime_state.log.logger(),
            )
            for t, d, m in broker_info
            if any(meta for meta in m if meta.quote_regions)
        ]
        self.quote_brokers = brokers

        self.trade_brokers = list()
        broker_info = sort_brokers(var=var)
        brokers = [
            t(
                symbol=store_config.symbol,
                name=store_config.name,
                logger=self.runtime_state.log.logger(),
            )
            for t, d, m in broker_info
            if t.BROKER_NAME == store_config.broker
        ]
        self.trade_brokers = brokers

    def _find_trade_broker(self):
        broker_name = self.store_config.broker
        brokers = self.trade_brokers
        for broker in brokers:
            if broker.BROKER_NAME != broker_name:
                continue
            for meta in broker.broker_meta:
                if meta.trade_type.value != self.store_config.trade_type:
                    continue
                if self.store_config.region not in meta.trade_regions:
                    continue
                return broker
        else:
            raise BrokerMismatchError(f'无法匹配到持仓需要的券商接口')

    @property
    def trade_broker(self):
        return self._find_trade_broker()


__all__ = [
    'BrokerProxy',
]
