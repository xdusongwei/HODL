from hodl.broker import *
from hodl.quote import *
from hodl.state import *
from hodl.tools import *


@broker_api(name='futu', display='富途证券', booting_check=True, cash_currency='USD')
class FutuApi(HttpTradingBase):
    @track_api
    def detect_plug_in(self):
        return super().detect_plug_in()

    @track_api
    def fetch_market_status(self) -> BrokerMarketStatusResult:
        region_set = {'CN', 'HK', 'US', }
        status_map = {
            'UNKNOWN': self.MS_CLOSED,
            'CLOSED': self.MS_CLOSED,
            'AFTER_HOURS_BEGIN': self.MS_CLOSED,
            'AFTER_HOURS_END': self.MS_CLOSED,
            'MORNING': self.MS_TRADING,
            'AFTERNOON': self.MS_TRADING,
        }
        result = BrokerMarketStatusResult()
        uri = '/httptrading/api/{instance_id}/market/state'
        d = self._http_get(uri)
        sec_d: dict[str, dict[str, dict]] = d.get('marketStatus', dict()).get('securities', dict())
        rl: list[MarketStatusResult] = list()
        for region, v in sec_d.items():
            if region not in region_set:
                continue
            origin_status = v.get('originStatus', '--')
            status = status_map.get(origin_status, origin_status)
            display = origin_status
            rl.append(MarketStatusResult(region=region, status=status, display=display))

        result.append(BrokerTradeType.STOCK, rl)
        return result

    @track_api
    def fetch_quote(self) -> Quote:
        return super().fetch_quote()

    @track_api
    def query_cash(self):
        return super().query_cash()

    @track_api
    def query_chips(self, symbol=None):
        return super().query_chips(symbol=symbol)

    @track_api
    def place_order(self, order: Order):
        super().place_order(order=order)

    @track_api
    def cancel_order(self, order: Order):
        super().cancel_order(order=order)

    @track_api
    def refresh_order(self, order: Order):
        super().refresh_order(order=order)


__all__ = ['FutuApi', ]
