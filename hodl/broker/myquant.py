from urllib.parse import urljoin
import requests
from hodl.broker.base import *
from hodl.quote import *
from hodl.tools import *


@register_broker
class MyQuantApi(BrokerApiBase):
    BROKER_NAME = 'myquant'
    BROKER_DISPLAY = '掘金量化'
    ENABLE_BOOTING_CHECK = False
    
    QUOTE_BUCKET = LeakyBucket(120)

    @classmethod
    def http_request(
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
                'myquant-token': token,
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

    def _gm_action(self, uri: str, d: dict) -> dict:
        base_site = self.broker_config.get('url')
        timeout = self.broker_config.get('timeout', 20)
        token = self.broker_config.get('token', '')
        url = urljoin(base_site, uri)
        session = self.http_session
        d = MyQuantApi.http_request(
            method='POST',
            url=url,
            json=d,
            timeout=timeout,
            session=session,
            token=token,
            raise_for_status=False,
        )
        return d

    @track_api
    def fetch_quote(self) -> Quote:
        symbol = self.symbol
        args = {
            'symbol': symbol,
        }
        with self.QUOTE_BUCKET:
            d = self._gm_action(f'/api/myquant/quote', args)
        info_d: dict = d['info']
        quote_d: dict = d['quote']
        info_time = TimeTools.from_timestamp(info_d['tradeTimestamp'], tz='Asia/Shanghai')
        quote_time = TimeTools.from_timestamp(quote_d['createdAt'], tz='Asia/Shanghai')
        return Quote(
            symbol=self.symbol,
            open=quote_d['openPrice'],
            pre_close=info_d['preClose'],
            latest_price=quote_d['latestPrice'],
            time=max(info_time, quote_time),
            status='HALT' if info_d['isSuspended'] else 'NORMAL',
            day_low=quote_d['lowPrice'],
            day_high=quote_d['highPrice'],
            broker_name=self.BROKER_NAME,
            broker_display=self.BROKER_DISPLAY,
        )


__all__ = ['MyQuantApi', ]
