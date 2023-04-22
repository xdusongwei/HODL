"""
接入盈透证券的API文档
https://interactivebrokers.github.io/cpwebapi/
"""
import requests
from urllib.parse import urljoin, urlencode
from hodl.broker.base import *
from hodl.exception_tools import *
from hodl.quote import *


class InteractiveBrokers(BrokerApiBase):
    BROKER_NAME = 'interactiveBrokers'
    BROKER_DISPLAY = '盈透证券'
    META = [
        ApiMeta(
            trade_type=BrokerTradeType.STOCK,
            share_market_state=False,
            share_quote=True,
            market_status_regions=set(),
            quote_regions={'US', 'HK', },
            trade_regions={'US', 'HK', },
            need_conid=True,
        ),
    ]

    @classmethod
    def http_request(
            cls,
            ib_config: dict,
            path: str,
            method: str,
            params: dict | None = None,
            session: requests.Session = None,
    ) -> dict:
        timeout = ib_config.get('timeout', 16)
        site = ib_config.get('site')
        url = urljoin(site, path)
        args = dict(
            method=method,
            url=url,
            params=params,
            verify=False,
            timeout=timeout,
        )
        if session:
            resp = session.request(**args)
        else:
            resp = requests.request(**args)
        resp.raise_for_status()
        return resp.json()

    def detect_plug_in(self):
        try:
            d = self.http_request(
                ib_config=self.broker_config,
                path='/tickle',
                method='POST',
                session=self.http_session,
            )
            authenticated = d.get('iserver', dict()).get('authStatus', dict()).get('authenticated', False)
            return authenticated
        except Exception as e:
            return False

    def fetch_quote(self) -> Quote:
        d = self.http_request(
            ib_config=self.broker_config,
            path='/md/snapshot',
            method='GET',
            params=dict(conids=self.conid, fields='31,70,71,82,6509,7295,'),
            session=self.http_session,
        )
        if not d:
            raise PrepareError(f'盈透快照接口调用失败, symbol:{self.symbol}, conid:{self.conid}')
        item = d[0]
        raise NotImplementedError


__all__ = ['InteractiveBrokers', ]
