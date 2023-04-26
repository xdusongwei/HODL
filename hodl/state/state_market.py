from hodl.quote import *
from hodl.tools import *


class MarketStatusResult(dict):
    def __init__(self, region: str, status: str):
        super().__init__()
        self['region'] = region
        self['status'] = status

    @property
    def region(self) -> str:
        return self.get('region', '--')

    @property
    def status(self) -> str:
        return self.get('status', '--')


class BrokerMarketStatusResult(dict):
    def append(self, trade_type: BrokerTradeType, rl: list[MarketStatusResult]):
        self[trade_type.value] = rl

    def trade_type_items(self) -> list[tuple[str, list[MarketStatusResult]]]:
        return [(key, self[key], ) for key in sorted(self.keys()) if key != 'vix']

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
