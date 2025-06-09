import re
from typing import Type
from urllib.parse import urljoin
import requests
from hodl.quote import *
from hodl.tools import *
from hodl.state import *
from hodl.exception_tools import *
from hodl.broker.base import *


class HttpTradingBase(BrokerApiBase):
    """
    使用 HttpTrading 运行的 api 服务
    """
    @classmethod
    def _http_request(
            cls,
            method: str,
            url: str,
            json=None,
            timeout=30,
            session: requests.Session = None,
            token: str = '',
            raise_for_status=False,
    ):
        args = dict(
            method=method,
            url=url,
            timeout=timeout,
            json=json,
            headers={
                'User-Agent': 'tradebot',
                'HT-TOKEN': token,
            },
        )
        if session:
            resp = session.request(**args)
        else:
            resp = requests.request(**args)
        if raise_for_status:
            resp.raise_for_status()
        try:
            d: dict = resp.json()
            return d
        except requests.JSONDecodeError:
            return dict()

    def _http_get(self, uri: str, timeout: int = None, ex_type: Type[Exception] = PrepareError) -> dict:
        base_site = self.broker_config.get('base_site')
        instance_id = self.broker_config.get('instance_id')
        if timeout is None:
            timeout = self.broker_config.get('timeout', 20)
        token = self.broker_config.get('token', '')
        uri = uri.format(instance_id=instance_id)
        url = urljoin(base_site, uri)
        try:
            session = self.http_session
            try:
                d = HttpTradingBase._http_request(
                    method='GET',
                    url=url,
                    timeout=timeout,
                    session=session,
                    token=token,
                    raise_for_status=True,
                )
            except Exception as ex:
                raise ex_type(ex)
            ex: str = d.get('ex')
            if ex:
                raise ex_type(ex)
            return d
        except Exception as e:
            raise e

    def _http_post(self, uri: str, d: dict, ex_type: Type[Exception] = TradingError) -> dict:
        base_site = self.broker_config.get('base_site')
        instance_id = self.broker_config.get('instance_id')
        timeout = self.broker_config.get('timeout', 20)
        token = self.broker_config.get('token', '')
        uri = uri.format(instance_id=instance_id)
        url = urljoin(base_site, uri)
        session = self.http_session
        try:
            d = HttpTradingBase._http_request(
                method='POST',
                url=url,
                json=d,
                timeout=timeout,
                session=session,
                token=token,
                raise_for_status=True,
            )
        except Exception as ex:
            raise ex_type(ex)
        ex: str = d.get('ex')
        if ex:
            raise ex_type(ex)
        return d

    @classmethod
    def _get_region(cls, symbol: str) -> str:
        if re.match(r'^[56]\d{5}$', symbol):
            return 'CN'
        elif re.match(r'^[013]\d{5}$', symbol):
            return 'CN'
        elif re.match(r'^\d{5}$', symbol):
            return 'HK'
        elif re.match(r'^[A-Z]+$', symbol):
            return 'US'
        else:
            raise PrepareError(f'不能转换{symbol}为任何国家地区')

    @classmethod
    def _get_tz(cls, symbol: str) -> str:
        return TimeTools.region_to_tz(cls._get_region(symbol))

    def detect_plug_in(self):
        try:
            uri = '/httptrading/api/{instance_id}/ping/state'
            d = self._http_get(uri)
            return d.get('pong', False)
        except Exception as e:
            return False

    def fetch_market_status(self) -> BrokerMarketStatusResult:
        return BrokerMarketStatusResult()

    def fetch_quote(self) -> Quote:
        symbol = self.symbol
        region = self._get_region(symbol)
        tz = self._get_tz(symbol)
        uri = '/httptrading/api/{instance_id}/market/quote'
        query = '?tradeType={trade_type}&region={region}&ticker={ticker}'
        query = query.format(trade_type='Securities', region=region, ticker=symbol)
        d = self._http_get(uri + query)
        quote_d: dict = d.get('quote', dict())
        update_dt = TimeTools.from_timestamp(quote_d.get('timestamp') / 1000, tz=tz)
        is_tradable: bool = quote_d.get('isTradable')
        status = 'NORMAL' if is_tradable else 'DISABLED'
        return Quote(
            symbol=self.symbol,
            open=quote_d.get('openPrice'),
            pre_close=quote_d.get('preClose'),
            latest_price=quote_d.get('latest'),
            time=update_dt,
            status=status,
            day_low=quote_d.get('lowPrice'),
            day_high=quote_d.get('highPrice'),
            broker_name=self.BROKER_NAME,
            broker_display=self.BROKER_DISPLAY,
        )

    def query_cash(self):
        uri = '/httptrading/api/{instance_id}/cash/state'
        d = self._http_get(uri)
        cash_d: dict = d.get('cash', dict())
        currency = cash_d.get('currency')
        amount = cash_d.get('amount')
        assert currency == self.CASH_CURRENCY
        assert isinstance(amount, float)
        return amount

    def query_chips(self):
        symbol = self.symbol
        region = self._get_region(symbol)
        uri = '/httptrading/api/{instance_id}/position/state'
        d = self._http_get(uri)
        positions = d.get('positions', list())
        for position in positions:
            contract_d: dict = position.get('contract', dict())
            trade_type: str = contract_d.get('tradeType', '')
            contract_region: str = contract_d.get('region', '')
            ticker: str = contract_d.get('ticker', '')
            qty = position.get('qty')
            if trade_type != 'Securities':
                continue
            if contract_region != region:
                continue
            if ticker != symbol:
                continue
            return qty
        else:
            return 0

    def place_order(self, order: Order):
        symbol = self.symbol
        region = self._get_region(symbol)
        ticker = symbol
        uri = '/httptrading/api/{instance_id}/order/place'
        args = {
            'tradeType': 'Securities',
            'ticker': ticker,
            'region': region,
            'price': order.limit_price,
            'qty': order.qty,
            'orderType': 'Market' if order.limit_price is None else 'Limit',
            'timeInForce': 'DAY',
            'lifecycle': 'RTH',
            'direction': order.direction,
        }
        d = self._http_post(uri, args)
        order_id = d.get('orderId')
        assert order_id
        order.order_id = order_id

    def cancel_order(self, order: Order):
        uri = '/httptrading/api/{instance_id}/order/cancel'
        d = self._http_post(uri, {
            'orderId': order.order_id,
        })
        canceled: bool = d.get('canceled', False)
        assert canceled

    def refresh_order(self, order: Order):
        uri = '/httptrading/api/{instance_id}/order/state'
        query = '?orderId={order_id}'
        query = query.format(order_id=order.order_id)
        d = self._http_get(uri + query)
        order_d: dict = d.get('order', dict())
        qty = order_d.get('qty')
        filled_qty = order_d.get('filledQty')
        avg_price = order_d.get('avgPrice')
        error_reason = order_d.get('errorReason')
        is_canceled = order_d.get('isCanceled')
        self.modify_order_fields(
            order=order,
            qty=qty,
            filled_qty=filled_qty or 0,
            avg_fill_price=avg_price or 0.0,
            trade_timestamp=None,
            reason=error_reason,
            is_cancelled=is_canceled,
        )


__all__ = ['HttpTradingBase', ]
