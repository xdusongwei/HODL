from hodl.quote import *
from hodl.tools import *


class MarketStatusResult(dict):
    def __init__(self, region: str, status: str, display: str = None):
        super().__init__()
        self['region'] = region
        self['status'] = status
        self['display'] = display or status

    @property
    def region(self) -> str:
        """
        当前市场状态项的国家标识
        """
        return self.get('region', '--')

    @property
    def status(self) -> str:
        """
        经过状态重新映射的状态, 也就是统一了各个平台的交易中和收盘两个状态的结果
        """
        return self.get('status', '--')

    @property
    def display(self) -> str:
        """
        未经状态重新映射的状态, 是各个平台提供的国家市场状态的原始值, 作为 HTML 展示使用
        """
        return self.get('display', '--')


class BrokerMarketStatusResult(dict):
    def append(self, trade_type: BrokerTradeType, rl: list[MarketStatusResult]):
        rl = sorted(rl, key=lambda i: i.region)
        self[trade_type.value] = rl

    def trade_type_items(self) -> list[tuple[str, list[MarketStatusResult]]]:
        return [(key, self[key], ) for key in sorted(self.keys()) if key != 'vix' and not key.startswith('_')]

    def append_vix(self, quote: Quote):
        self['vix'] = {
            'latest': quote.latest_price,
            'dayHigh': quote.day_high,
            'dayLow': quote.day_low,
            'time': int(quote.time.timestamp()),
        }

    @property
    def vix(self):
        return self.get('vix', dict())

    @property
    def market_error(self):
        return self.get('_marketStatusException', None)

    @market_error.setter
    def market_error(self, d: dict):
        self['_marketStatusException'] = d

    @property
    def vix_error(self):
        return self.get('_vixException', None)

    @vix_error.setter
    def vix_error(self, v: dict):
        self['_vixException'] = v

    @property
    def has_error(self) -> bool:
        return bool(self.market_error or self.vix_error)


__all__ = [
    'MarketStatusResult',
    'BrokerMarketStatusResult',
]
