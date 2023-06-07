"""
接入币安交易所的API文档
https://binance-docs.github.io/apidocs/spot/cn/
"""
from binance.spot import Spot
from hodl.broker.base import *
from hodl.quote import *
from hodl.state import *
from hodl.tools import *


class BinanceApi(BrokerApiBase):
    BROKER_NAME = 'binance'
    BROKER_DISPLAY = '币安'
    ENABLE_BOOTING_CHECK = True
    MARKET_STATUS_BUCKET = LeakyBucket(12)
    QUOTE_BUCKET = LeakyBucket(600)

    def __post_init__(self):
        config_dict = self.broker_config
        api_key = config_dict.get('api_key')
        secret_key = config_dict.get('secret_key')
        base_url = config_dict.get('base_url', None)
        timeout = config_dict.get('timeout', 10)
        proxy = config_dict.get('proxy', None)
        if proxy:
            proxies = {
                'https': proxy,
                'http': proxy,
            }
        else:
            proxies = None
        self.custom_client = Spot(
            api_key=api_key,
            api_secret=secret_key,
            base_url=base_url,
            timeout=timeout,
            proxies=proxies,
        )

    @track_api
    def fetch_market_status(self) -> BrokerMarketStatusResult:
        result = BrokerMarketStatusResult()
        with self.MARKET_STATUS_BUCKET:
            resp: dict = self.custom_client.system_status()
        status = resp.get('status', -1)
        if status == 0:
            market_status = 'TRADING'
        else:
            market_status = 'UNAVAILABLE'
        result.append(
            BrokerTradeType.CRYPTO, [MarketStatusResult(region='US', status=market_status)]
        )
        return result

    @track_api
    def fetch_quote(self) -> Quote:
        symbol = self.symbol
        with self.QUOTE_BUCKET:
            resp: dict = self.custom_client.exchange_info()
            server_timestamp = resp.get('serverTime') / 1000
            lines = self.custom_client.klines(symbol=symbol, interval='1d', limit=1)
            line: list = lines[0]
            open_price = float(line[1])
            latest_price = float(line[4])
            us_date = TimeTools.from_timestamp(timestamp=server_timestamp, tz='US/Eastern')
        return Quote(
            symbol=symbol,
            open=open_price,
            pre_close=open_price,
            latest_price=latest_price,
            status='NORMAL',
            time=us_date,
        )

    def query_cash(self):
        return 0

    def query_chips(self):
        return 0


__all__ = ['BinanceApi', ]
