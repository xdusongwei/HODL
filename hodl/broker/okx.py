"""
接入OKX交易所的API文档
https://www.okx.com/docs-v5/zh/#rest-api
"""
import base64
import datetime
import hmac
from urllib.parse import urljoin
import requests
from hodl.broker.base import *
from hodl.exception_tools import QuoteFieldError
from hodl.quote import Quote
from hodl.state import *
from hodl.tools import *


@broker_api(name='okx', display='OKX', booting_check=True, cash_currency='USDT')
class OkxRestApi(BrokerApiBase):
    MARKET_STATUS_BUCKET = LeakyBucket(12)
    QUOTE_BUCKET = LeakyBucket(600)
    ORDER_BUCKET = LeakyBucket(120)
    ASSET_BUCKET = LeakyBucket(60)

    @classmethod
    def _get_timestamp(cls):
        now = datetime.datetime.utcnow()
        t = now.isoformat("T", "milliseconds")
        return t + "Z"

    @classmethod
    def _signature(cls, timestamp, method, request_path, body, secret_key):
        if str(body) == '{}' or str(body) == 'None':
            body = ''
        message = str(timestamp) + str.upper(method) + request_path + str(body)
        mac = hmac.new(bytes(secret_key, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
        d = mac.digest()
        return base64.b64encode(d)

    @classmethod
    def http_request(
            cls,
            okx_config: dict,
            path: str,
            method: str,
            data: dict | str | None = None,
            session: requests.Session = None,
    ) -> dict:
        if data is None:
            data = ''
        elif isinstance(data, dict):
            data = FormatTool.json_dumps(data)
        site = okx_config.get('site')
        url = urljoin(site, path)
        api_key = okx_config.get('api_key')
        secret_key = okx_config.get('secret_key')
        passphrase = okx_config.get('passphrase')
        proxy = okx_config.get('proxy')
        timeout = okx_config.get('timeout', 16)
        assert api_key
        assert secret_key
        assert passphrase
        timestamp = cls._get_timestamp()
        signature = cls._signature(
            timestamp=timestamp,
            method=method,
            request_path=path,
            body=data,
            secret_key=secret_key,
        )
        headers = {
            'OK-ACCESS-KEY': api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': passphrase,
            'Content-Type': 'application/json',
        }
        if proxy:
            proxies = {
                'https': proxy,
                'http': proxy,
            }
        else:
            proxies = None
        if not isinstance(data, bytes):
            data = bytes(data, encoding='utf8')
        args = dict(
            method=method,
            url=url,
            headers=headers,
            data=data,
            proxies=proxies,
            verify=True,
            timeout=timeout,
        )
        if session:
            resp = session.request(**args)
        else:
            resp = requests.request(**args)
        resp.raise_for_status()
        return resp.json()

    @classmethod
    def current_quote(cls, okx_config: dict, symbol: str, session: requests.Session = None) -> Quote:
        resp = OkxRestApi.http_request(
            okx_config=okx_config,
            path=f'/api/v5/market/ticker?instId={symbol}',
            method='GET',
            session=session,
        )

        try:
            d: dict = resp.get('data', list())[0]
            pre_close = float(d.get('sodUtc0'))
            open_price = float(d.get('sodUtc0'))
            latest_price = float(d.get('last'))
            assert pre_close > 0.4
            assert open_price > 0.4
            assert latest_price > 0.4
            timestamp = int(d.get('ts')) / 1000
            us_date = TimeTools.from_timestamp(timestamp=timestamp, tz='US/Eastern')
        except Exception as e:
            raise QuoteFieldError(e)
        return Quote(
            symbol=symbol,
            open=open_price,
            pre_close=pre_close,
            latest_price=latest_price,
            status='NORMAL',
            time=us_date,
            broker_name=cls.BROKER_NAME,
            broker_display=cls.BROKER_DISPLAY,
        )

    @track_api
    def fetch_market_status(self) -> BrokerMarketStatusResult:
        result = BrokerMarketStatusResult()
        with self.MARKET_STATUS_BUCKET:
            resp = OkxRestApi.http_request(
                okx_config=self.broker_config,
                path='/api/v5/system/status',
                method='GET',
                session=self.http_session,
            )

        time_list: list[dict] = resp.get('data', list())
        time_list: list[tuple[int, int, str]] = [
            (int(item.get('begin')), int(item.get('end')), item.get('title'), )
            for item in time_list
        ]
        time_list: list[tuple[int, int, str]] = [
            (begin // 1000 - 8 * 60 * 60, end // 1000 - 8 * 60 * 60, title, )
            for begin, end, title in time_list
        ]
        now = TimeTools.utc_now().timestamp()
        unavailable = False
        reason = '--'
        for begin, end, title in time_list:
            if begin <= now <= end:
                unavailable = True
                reason = title
                break
        k = 'US'
        display = f'UNAVAILABLE: {reason}' if unavailable else self.MS_TRADING
        status = self.MS_CLOSED if unavailable else self.MS_TRADING
        result.append(BrokerTradeType.CRYPTO, [MarketStatusResult(region=k, status=status, display=display)])
        return result

    @track_api
    def fetch_quote(self) -> Quote:
        symbol = self.symbol
        with self.QUOTE_BUCKET:
            return self.current_quote(
                okx_config=self.broker_config,
                symbol=symbol,
                session=self.http_session,
            )

    @track_api
    def query_cash(self):
        okx_config = self.broker_config
        with self.ASSET_BUCKET:
            d = OkxRestApi.http_request(
                okx_config=okx_config,
                path='/api/v5/account/balance?ccy=USDT',
                method='GET',
                session=self.http_session,
            )
        amount = 0
        data = d.get('data', list())
        if data:
            details = data[0].get('details')
            if details:
                amount = float(details[0].get('availBal', 0.0))
        return amount

    @track_api
    def query_chips(self):
        okx_config = self.broker_config
        with self.ASSET_BUCKET:
            d = OkxRestApi.http_request(
                okx_config=okx_config,
                path='/api/v5/account/balance?ccy=BTC',
                method='GET',
                session=self.http_session,
            )
        qty = 0
        data = d.get('data', list())
        if data:
            details = data[0].get('details')
            if details:
                qty = int(details[0].get('availBal', 0.0))
        return qty


__all__ = ['OkxRestApi', ]
