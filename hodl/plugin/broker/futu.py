from hodl.broker import *
from hodl.quote import *
from hodl.state import *


@broker_api(name='futu', display='富途证券', booting_check=True, cash_currency='USD')
class FutuApi(HttpTradingBase):
    @track_api
    def detect_plug_in(self):
        return super().detect_plug_in()

    @track_api
    def fetch_market_status(self) -> BrokerMarketStatusResult:
        return super().fetch_market_status()

    @track_api
    def fetch_quote(self) -> Quote:
        return super().fetch_quote()

    @track_api
    def query_cash(self):
        return super().query_cash()

    @track_api
    def query_chips(self):
        return super().query_chips()

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
