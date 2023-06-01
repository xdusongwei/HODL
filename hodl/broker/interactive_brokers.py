"""
接入盈透证券的API文档
https://interactivebrokers.github.io/cpwebapi/
"""
import requests
from urllib.parse import urljoin
from hodl.broker.base import *
from hodl.exception_tools import *
from hodl.quote import *
from hodl.tools import *


class InteractiveBrokers(BrokerApiBase):
    CONID_TABLE: dict = dict()
    CONID_MATCH_TABLE: dict[str, list[dict]] = dict()

    BROKER_NAME = 'interactiveBrokers'
    BROKER_DISPLAY = '盈透证券'

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

    @track_api
    def detect_plug_in(self):
        try:
            d = self.http_request(
                ib_config=self.broker_config,
                path='/v1/api/tickle',
                method='POST',
                session=self.http_session,
            )
            authenticated = d.get('iserver', dict()).get('authStatus', dict()).get('authenticated', False)
            return authenticated
        except Exception as e:
            return False

    @track_api
    def query_cash(self) -> float:
        account_id = self.broker_config.get('account_id')
        d = self.http_request(
            ib_config=self.broker_config,
            path=f'/v1/api/portfolio/{account_id}/summary',
            method='GET',
            session=self.http_session,
        )
        available_funds = d.get('availablefunds', dict())
        amount = available_funds.get('amount', 0.0)
        return amount

    def query_conid(self):
        symbol = self.symbol
        conid = InteractiveBrokers.CONID_TABLE.get(symbol, None)
        if conid is None:
            conid = None
            d = self.http_request(
                ib_config=self.broker_config,
                path='/v1/api/trsrv/stocks',
                method='GET',
                params=dict(symbols=symbol),
                session=self.http_session,
            )
            match_list: list[dict] = d[symbol]
            for item in match_list:
                asset_class = item.get('assetClass')
                if asset_class != 'STK':
                    continue
                contracts: list[dict] = item.get('contracts')
                for contract in contracts:
                    is_us = contract.get('isUS')
                    if not is_us:
                        continue
                    conid = contract.get('conid')
                    break
            if conid:
                InteractiveBrokers.CONID_TABLE[symbol] = conid
                InteractiveBrokers.CONID_MATCH_TABLE[symbol] = match_list
            else:
                raise IbkrConidMissingError(f'{symbol}找不到对应的conid')
        return conid

    @track_api
    def fetch_quote(self) -> Quote:
        conid = self.query_conid()
        d = self.http_request(
            ib_config=self.broker_config,
            path='/v1/api/md/snapshot',
            method='GET',
            params=dict(conids=conid, fields='31,70,71,82,6509,7295,7741,6508,HasDelayed'),
            session=self.http_session,
        )
        if not d:
            raise PrepareError(f'盈透快照接口调用失败, symbol:{self.symbol}, conid:{conid}')
        item = d[0]
        availability: str = item.get('6509', '')
        if not availability.startswith('R'):
            raise QuoteFieldError(f'盈透快照接口可用性不匹配:{availability}, symbol:{self.symbol}, conid:{conid}')
        latest_price = float(item['31'])
        open_price = float(item['7295'])
        day_high = float(item['70'])
        day_low = float(item['71'])
        pre_close = latest_price - float(item['82'])
        return Quote(
            symbol=self.symbol,
            open=open_price,
            pre_close=pre_close,
            latest_price=latest_price,
            time=TimeTools.utc_now(),
            status='NORMAL',
            day_low=day_low,
            day_high=day_high,
            broker_name=self.BROKER_NAME,
            broker_display=self.BROKER_DISPLAY,
        )


__all__ = ['InteractiveBrokers', ]
