"""
接入币安交易所的API文档
https://binance-docs.github.io/apidocs/spot/cn/
"""
from binance.spot import Spot
from hodl.broker.base import *
from hodl.quote import Quote
from hodl.tools import TimeTools


class BinanceApi(BrokerApiBase):
    BROKER_NAME = 'binance'
    META = [
        ApiMeta(
            trade_type=BrokerTradeType.CRYPTO,
            share_market_state=False,
            share_quote=False,
            market_status_regions={'US', },
            quote_regions={'US', },
            trade_regions={'US', },
        ),
    ]

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
            key=api_key,
            secret=secret_key,
            base_url=base_url,
            timeout=timeout,
            proxies=proxies,
        )

    def fetch_market_status(self) -> dict:
        resp: dict = self.custom_client.system_status()
        status = resp.get('status', -1)
        if status == 0:
            market_status = 'TRADING'
        else:
            market_status = 'UNAVAILABLE'
        return {
            BrokerTradeType.CRYPTO.value: {
                'US': market_status,
            },
        }

    def fetch_quote(self) -> Quote:
        symbol = self.symbol
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
