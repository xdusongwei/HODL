"""
接入老虎证券的API文档
https://quant.itigerup.com/openapi/zh/python/overview/introduction.html
"""
import uuid
import threading
import pandas
import requests
from tigeropen.common.util import web_utils
from tigeropen.common.util.contract_utils import stock_contract
from tigeropen.common.util.order_utils import market_order, limit_order
from tigeropen.quote.quote_client import QuoteClient
from tigeropen.tiger_open_config import get_client_config
from tigeropen.trade.domain.position import Position
from tigeropen.trade.trade_client import TradeClient
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


class _SpeedupMixin:
    SESSION = None

    @classmethod
    def _do_post_session(
            cls,
            url,
            query_string=None,
            headers=None,
            params=None,
            timeout=15,
            charset=None,
    ) -> str:
        url, _ = web_utils.get_http_connection(url, query_string, timeout)
        args = dict(
            url=url,
            json=params or dict(),
            header=headers,
            timeout=timeout,
        )
        if session := cls.SESSION:
            resp = session.post(**args)
        else:
            resp = requests.post(**args)
        resp.raise_for_status()
        return resp.text

    def _execute(self, request):
        THREAD_LOCAL.uuid = str(uuid.uuid1())
        query_string = None
        params = self.__prepare_request(request)

        response = self._do_post_session(
            self.__config.server_url, query_string, self.__headers, params, self.__config.timeout,
            self.__config.charset,
        )

        return self.__parse_response(response, params.get('timestamp'))

    def __fetch_data__(self, request):
        try:
            response = self._execute(request=request)
            return response
        except Exception as e:
            if hasattr(THREAD_LOCAL, 'logger') and THREAD_LOCAL.logger:
                THREAD_LOCAL.logger.error(e, exc_info=True)
            raise e


class SpeedupQuoteClient(QuoteClient, _SpeedupMixin):
    def __fetch_data(self, request):
        return self.__fetch_data__(request=request)


class SpeedupTradeClient(TradeClient, _SpeedupMixin):
    def __fetch_data(self, request):
        return self.__fetch_data__(request=request)


class TigerApi(BrokerApiBase):
    BROKER_NAME = 'tiger'
    META = [
        ApiMeta(
            trade_type=BrokerTradeType.STOCK,
            share_market_state=True,
            share_quote=True,
            market_status_regions={'US', 'HK', 'CN', },
            quote_regions={'US', 'HK', 'CN', },
            trade_regions={'US', 'HK', },
        ),
    ]

    HAS_GRAB = False
    GRAB_LOCK = threading.Lock()
    # 老虎证券提供的文档限制频率，使用漏桶可能会触发超频，所以设定比其文档频率低一次
    MARKET_STATUS_BUCKET = LeakyBucket(9)
    QUOTE_BUCKET = LeakyBucket(119)
    ORDER_BUCKET = LeakyBucket(119)
    ASSET_BUCKET = LeakyBucket(59)

    def __str__(self):
        return f'<' \
               f'{type(self).__name__} ' \
               f'symbol:{self.symbol} ' \
               f'name:{self.name} ' \
               f'mktStatus:{self.MARKET_STATUS_BUCKET.available_tokens} ' \
               f'quote:{self.QUOTE_BUCKET.available_tokens} ' \
               f'order:{self.ORDER_BUCKET.available_tokens} ' \
               f'asset:{self.ASSET_BUCKET.available_tokens} ' \
               f'>'

    def _grab_quote(self):
        with TigerApi.GRAB_LOCK:
            if TigerApi.HAS_GRAB:
                return
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
        _SpeedupMixin.SESSION = self.http_session
        self.trade_client = SpeedupTradeClient(client_config)
        self.quote_client = SpeedupQuoteClient(client_config, is_grab_permission=False)

    @classmethod
    def current_quote(cls, client: QuoteClient, symbol: str) -> Quote:
        pd: pandas.DataFrame = client.get_stock_briefs(symbols=[symbol, ])
        pd['us_date'] = pandas \
            .to_datetime(pd['latest_time'], unit='ms') \
            .dt.tz_localize('UTC') \
            .dt.tz_convert('US/Eastern')
        for index, row in pd.iterrows():
            us_date, pre_close, open_price, latest_price, status, low_price = \
                row['us_date'], row['pre_close'], row['open'], row['latest_price'], row['status'], row['low']
            try:
                assert pre_close > 0.4
                assert open_price > 0.4
                assert latest_price > 0.4
                assert low_price > 0.4
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
            )

    @classmethod
    def market_status(cls, client: QuoteClient) -> dict[str, str]:
        market_status_list: list[MarketStatus] = client.get_market_status(Market.ALL)
        result = {ms.market: ms.trading_status for ms in market_status_list}
        return result

    def fetch_market_status(self) -> dict:
        client = self.quote_client
        with self.MARKET_STATUS_BUCKET:
            market_status_list: list[MarketStatus] = client.get_market_status(Market.ALL)
        return {
            BrokerTradeType.STOCK.value: {ms.market: ms.trading_status for ms in market_status_list},
        }

    def fetch_quote(self) -> Quote:
        symbol = self.symbol
        with self.QUOTE_BUCKET:
            return self.current_quote(client=self.quote_client, symbol=symbol)

    def on_init(self):
        self._grab_quote()

    def query_cash(self):
        with self.ASSET_BUCKET:
            portfolio_account: PortfolioAccount = self.trade_client.get_prime_assets()
        s: Segment = portfolio_account.segments.get('S')
        currency = s.currency
        assert currency == 'USD'
        cash_balance = s.cash_balance
        return cash_balance

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

    def cancel_order(self, order: Order):
        with self.ORDER_BUCKET:
            self.trade_client.cancel_order(id=order.order_id)

    def refresh_order(self, order: Order):
        with self.ORDER_BUCKET:
            tiger_order: TigerOrder = self.trade_client.get_order(id=order.order_id)
        if tiger_order is None:
            raise ValueError(f'订单{order}在tiger交易系统查询不到')
        self._override_order_fields(order=order, broker_order=tiger_order)


TigerQuoteClient = QuoteClient


__all__ = [
    'SpeedupQuoteClient',
    'SpeedupTradeClient',
    'TigerApi',
    'TigerQuoteClient',
]
