"""
接入老虎证券的API文档
https://quant.itigerup.com/openapi/zh/python/overview/introduction.html
"""
import threading
import pandas
from tigeropen.common.util.contract_utils import stock_contract
from tigeropen.common.util.order_utils import market_order, limit_order
from tigeropen.quote.quote_client import QuoteClient
from tigeropen.tiger_open_config import get_client_config, TigerOpenClientConfig
from tigeropen.trade.domain.position import Position
from tigeropen.trade.trade_client import TradeClient
from tigeropen.push.push_client import PushClient
from tigeropen.common.consts import Market
from tigeropen.quote.domain.market_status import MarketStatus
from tigeropen.trade.domain.prime_account import PortfolioAccount, Segment
from tigeropen.trade.domain.order import Order as TigerOrder
from hodl.broker.base import *
from hodl.exception_tools import *
from hodl.quote import *
from hodl.state import *
from hodl.tools import *


THREAD_LOCAL = threading.local()


@broker_api
class TigerApi(BrokerApiBase):
    BROKER_NAME = 'tiger'
    BROKER_DISPLAY = '老虎国际'
    ENABLE_BOOTING_CHECK = True
    ORDER_ID_TYPE = int
    CASH_CURRENCY = 'USD'

    HAS_GRAB = False
    GRAB_LOCK = threading.Lock()
    # 老虎证券提供的文档限制频率，使用漏桶仍存在可能会触发超频，所以设定比其文档频率低一次
    MARKET_STATUS_BUCKET = LeakyBucket(9)
    QUOTE_BUCKET = LeakyBucket(119)
    ORDER_BUCKET = LeakyBucket(119)
    ASSET_BUCKET = LeakyBucket(59)

    QUOTE_CLIENT: QuoteClient = None
    TRADE_CLIENT: TradeClient = None
    PUSH_CLIENT: PushClient = None

    def __str__(self):
        return f'<' \
               f'{type(self).__name__} ' \
               f'symbol:{self.symbol} ' \
               f'name:{self.name} ' \
               f'>'

    def _grab_quote(self):
        with TigerApi.GRAB_LOCK:
            if TigerApi.HAS_GRAB:
                return
            try:
                config_dict = self.broker_config
                if mac_address := config_dict.get('mac_address', None):
                    TigerOpenClientConfig.__get_device_id = lambda: mac_address
            except Exception as e:
                pass
            self.quote_client.grab_quote_permission()
            TigerApi.HAS_GRAB = True

    def __post_init__(self):
        config_dict = self.broker_config
        pk_path = config_dict.get('pk_path')
        tiger_id = config_dict.get('tiger_id')
        account = config_dict.get('account')
        timeout = config_dict.get('timeout', 0)
        client_config = get_client_config(
            private_key_path=pk_path,
            tiger_id=tiger_id,
            account=account,
            timeout=timeout,
        )
        self.custom_client = client_config

        if TigerApi.QUOTE_CLIENT is None:
            TigerApi.QUOTE_CLIENT = QuoteClient(client_config, is_grab_permission=False)
        self.quote_client = TigerApi.QUOTE_CLIENT
        if TigerApi.TRADE_CLIENT is None:
            TigerApi.TRADE_CLIENT = TradeClient(client_config)
        self.trade_client = TigerApi.TRADE_CLIENT
        if TigerApi.PUSH_CLIENT is None:
            protocol, host, port = client_config.socket_host_port
            TigerApi.PUSH_CLIENT = PushClient(host, port, use_ssl=(protocol == 'ssl'))
        self.push_client = TigerApi.PUSH_CLIENT

    @classmethod
    def current_quote(cls, client: QuoteClient, symbol: str) -> Quote:
        pd: pandas.DataFrame = client.get_stock_briefs(symbols=[symbol, ])
        pd['us_date'] = pandas \
            .to_datetime(pd['latest_time'], unit='ms') \
            .dt.tz_localize('UTC') \
            .dt.tz_convert('US/Eastern')
        for index, row in pd.iterrows():
            us_date, pre_close, open_price, latest_price, status, low_price, high_price = (
                row['us_date'],
                row['pre_close'],
                row['open'],
                row['latest_price'],
                row['status'],
                row['low'],
                row['high'],
            )

            try:
                assert pre_close > 0.1
                assert open_price > 0.1
                assert latest_price > 0.1
                assert low_price > 0.1
                assert high_price > 0.1
            except Exception as e:
                raise QuoteFieldError(e)
            return Quote(
                symbol=symbol,
                open=open_price,
                pre_close=pre_close,
                latest_price=latest_price,
                status=status,
                time=us_date,
                day_low=low_price,
                day_high=high_price,
                broker_name=cls.BROKER_NAME,
                broker_display=cls.BROKER_DISPLAY,
            )

    @track_api
    def fetch_market_status(self) -> BrokerMarketStatusResult:
        region_map = {
            'CN': 'CN',
            'HK': 'HK',
            'US': 'US',
        }
        status_map = {
            'AFTER_HOURS_BEGIN': self.MS_CLOSED,
            'EARLY_CLOSED': self.MS_CLOSED,
            'MARKET_CLOSED': self.MS_CLOSED,
        }
        result = BrokerMarketStatusResult()
        client = self.quote_client
        with self.MARKET_STATUS_BUCKET:
            market_status_list: list[MarketStatus] = client.get_market_status(Market.ALL)
        rl = [
            MarketStatusResult(
                region=region_map[ms.market],
                status=status_map.get(ms.trading_status, ms.trading_status),
                display=ms.trading_status,
            )
            for ms in market_status_list
            if ms.market in region_map
        ]
        result.append(BrokerTradeType.STOCK, rl)
        return result

    @track_api
    def fetch_quote(self) -> Quote:
        symbol = self.symbol
        with self.QUOTE_BUCKET:
            return self.current_quote(client=self.quote_client, symbol=symbol)

    def on_init(self):
        self._grab_quote()

    @track_api
    def query_cash(self):
        with self.ASSET_BUCKET:
            portfolio_account: PortfolioAccount = self.trade_client.get_prime_assets()
        s: Segment = portfolio_account.segments.get('S')
        currency = s.currency
        assert currency == 'USD'
        cash_balance = s.cash_balance
        return cash_balance

    @track_api
    def query_chips(self):
        symbol = self.symbol
        with self.ASSET_BUCKET:
            # 传入symbol参数返回空列表，不设置symbol参数则返回数据没问题
            positions: list[Position] = self.trade_client.get_positions()
        if positions:
            for p in positions:
                if p.contract.symbol == symbol:
                    return p.quantity
        return 0

    @track_api
    def place_order(self, order: Order):
        client = self.trade_client
        contract = stock_contract(symbol=order.symbol, currency='USD')
        if order.limit_price is None:
            client_order = market_order(
                account=client._account,
                contract=contract,
                action=order.direction,
                quantity=order.qty,
            )
        else:
            client_order = limit_order(
                account=client._account,
                contract=contract,
                action=order.direction,
                quantity=order.qty,
                limit_price=order.limit_price,
            )
        client_order.time_in_force = 'DAY'
        client_order.outside_rth = False
        with self.ORDER_BUCKET:
            client.place_order(client_order)
        order.order_id = client_order.id

    @track_api
    def cancel_order(self, order: Order):
        with self.ORDER_BUCKET:
            self.trade_client.cancel_order(id=order.order_id)

    @track_api
    def refresh_order(self, order: Order):
        with self.ORDER_BUCKET:
            tiger_order: TigerOrder = self.trade_client.get_order(id=order.order_id)
        if tiger_order is None:
            raise ValueError(f'订单{order}在tiger交易系统查询不到')
        self._override_order_fields(order=order, broker_order=tiger_order)


TigerQuoteClient = QuoteClient


__all__ = [
    'TigerApi',
    'TigerQuoteClient',
]
