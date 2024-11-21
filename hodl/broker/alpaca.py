"""
接入 alpaca 的 API 文档
https://docs.alpaca.markets/docs/getting-started
"""
import threading
from alpaca.trading.client import TradingClient
from hodl.broker.base import *
from hodl.state import *
from hodl.tools import *


@broker_api(broker_name='alpaca', broker_display='alpaca')
class AlpacaApi(BrokerApiBase):
    MARKET_STATUS_BUCKET = LeakyBucket(12)

    LOCK = threading.RLock()
    TRADING_CLIENT: TradingClient | None = None

    def __post_init__(self):
        super().__post_init__()
        with AlpacaApi.LOCK:
            if AlpacaApi.TRADING_CLIENT:
                return
            api_key = self.broker_config.get('api_key', '')
            secret_key = self.broker_config.get('secret_key', '')
            paper = self.broker_config.get('paper', True)
            trading_client = TradingClient(
                api_key=api_key,
                secret_key=secret_key,
                paper=paper,
            )
            AlpacaApi.TRADING_CLIENT = trading_client

    @property
    def trading_client(self):
        return AlpacaApi.TRADING_CLIENT

    @track_api
    def fetch_market_status(self) -> BrokerMarketStatusResult:
        result = BrokerMarketStatusResult()
        with self.MARKET_STATUS_BUCKET:
            us_clock = self.trading_client.get_clock()
        is_open = us_clock.is_open
        k = 'US'
        if is_open:
            v = self.MS_TRADING
        elif us_clock.timestamp.date() == us_clock.next_open.date():
            v = 'NOT_YET_OPEN'
        else:
            v = self.MS_CLOSED
        result.append(
            BrokerTradeType.STOCK,
            [
                MarketStatusResult(region=k, status=v),
            ]
        )
        result.append(
            BrokerTradeType.CRYPTO,
            [
                MarketStatusResult(region=k, status=self.MS_TRADING),
            ]
        )
        return result


__all__ = ['AlpacaApi', ]
