"""
接入盈透证券的API文档
https://interactivebrokers.github.io/cpwebapi/
"""
import requests
from urllib.parse import urljoin
from hodl.broker.base import *
from hodl.exception_tools import *
from hodl.quote import *
from hodl.state import *
from hodl.tools import *


class InteractiveBrokers(BrokerApiBase):
    CONID_TABLE: dict = dict()
    CONID_MATCH_TABLE: dict[str, list[dict]] = dict()

    BROKER_NAME = 'interactiveBrokers'
    BROKER_DISPLAY = '盈透证券'
    ENABLE_BOOTING_CHECK = False

    PLUGIN_BUCKET = LeakyBucket(60)
    ACCOUNT_BUCKET = LeakyBucket(60)
    ORDER_BUCKET = LeakyBucket(120)

    LATEST_REAUTH_TIME: int = 0

    @classmethod
    def http_request(
            cls,
            ib_config: dict,
            path: str,
            method: str,
            params: dict | None = None,
            json: dict | None = None,
            session: requests.Session = None,
    ) -> dict:
        timeout = ib_config.get('timeout', 16)
        site = ib_config.get('site')
        url = urljoin(site, path)
        args = dict(
            method=method,
            url=url,
            params=params,
            json=json,
            verify=False,
            timeout=timeout,
        )
        if session:
            resp = session.request(**args)
        else:
            resp = requests.request(**args)
        resp.raise_for_status()
        return resp.json()

    def account_id(self) -> str:
        return self.broker_config.get('account_id')

    def reauthenticate(self) -> bool:
        try:
            d = self.http_request(
                ib_config=self.broker_config,
                path='/v1/api/iserver/reauthenticate',
                method='POST',
                session=self.http_session,
            )
            message = d.get('message', '')
            return message == 'triggered'
        except Exception as e:
            return False

    def tickle(self):
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
    def detect_plug_in(self):
        with self.PLUGIN_BUCKET:
            now_ts = int(TimeTools.utc_now().timestamp())
            if InteractiveBrokers.LATEST_REAUTH_TIME + 3600 < now_ts:
                InteractiveBrokers.LATEST_REAUTH_TIME = now_ts
                self.reauthenticate()
            return self.tickle()

    @track_api
    def query_cash(self) -> float:
        with self.ACCOUNT_BUCKET:
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
    def query_chips(self) -> int:
        """
        返回 self.symbol 获取实际持仓数量。
        """
        with self.ACCOUNT_BUCKET:
            account_id = self.broker_config.get('account_id')
            conid = self.query_conid()
            d = self.http_request(
                ib_config=self.broker_config,
                path=f'/v1/api/portfolio/{account_id}/position/{conid}',
                method='GET',
                session=self.http_session,
            )
            if d:
                position = d[0].get('position', 0)
                position = int(position)
                return position
            else:
                return 0

    @track_api
    def place_order(self, order: Order):
        with self.ORDER_BUCKET:
            account_id = self.account_id()
            conid = self.query_conid()
            args = {
                'orders': [
                    {
                        'conid': conid,
                        'orderType': 'MKT' if order.limit_price is None else 'LMT',
                        'price': order.limit_price,
                        'side': order.direction,
                        'tif': 'DAY',
                        'quantity': order.qty,
                    },
                ],
            }
            d = self.http_request(
                ib_config=self.broker_config,
                path=f'/v1/api/iserver/account/{account_id}/orders',
                method='POST',
                json=args,
                session=self.http_session,
            )
            if not d:
                raise TradingError(f'盈透证券下单接口返回了空数据')
            order_resp: dict = d[0]
            reply_id = order_resp.get('id')
            message = order_resp.get('message')
            is_suppressed = order_resp.get('isSuppressed', True)
            if message and not is_suppressed:
                args = {
                    'confirmed': True,
                }
                d = self.http_request(
                    ib_config=self.broker_config,
                    path=f'/v1/api/iserver/reply/{reply_id}',
                    method='POST',
                    json=args,
                    session=self.http_session,
                )
                if not d:
                    raise TradingError(f'盈透证券确认下单接口返回了空数据')
                reply_resp: dict = d[0]
                order_id = reply_resp.get('order_id')
                error = reply_resp.get('error')
                if order_id:
                    order.order_id = order_id
                else:
                    order.error_reason = error
                    raise TradingError(f'盈透证券确认下单接口返回失败原因:{error}')
            else:
                raise TradingError(f'盈透证券确认下单接口没有给出确认信息')

    @track_api
    def cancel_order(self, order: Order):
        with self.ORDER_BUCKET:
            account_id = self.account_id()
            d: dict = self.http_request(
                ib_config=self.broker_config,
                path=f'/v1/api/iserver/account/{account_id}/order/{order.order_id}',
                method='DELETE',
                session=self.http_session,
            )
            if not d:
                raise TradingError(f'盈透证券确认撤单接口返回了空数据')

    @track_api
    def refresh_order(self, order: Order):
        with self.ORDER_BUCKET:
            try:
                d: dict = self.http_request(
                    ib_config=self.broker_config,
                    path=f'/v1/api/iserver/account/order/status/{order.order_id}',
                    method='GET',
                    session=self.http_session,
                )
                order_status = d.get('order_status', '')
                qty = int(float(d.get('size')))
                filled_qty = int(float(d.get('cum_fill')))
                avg_fill_price = float(d.get('average_price', 0.0))
                self.modify_order_fields(
                    order=order,
                    qty=qty,
                    filled_qty=filled_qty,
                    avg_fill_price=avg_fill_price,
                    trade_timestamp=None,
                    reason='',
                    is_cancelled=order_status=='Cancelled',
                )
            except Exception as e:
                raise OrderRefreshError(f'更新盈透证券订单{order.order_id}失败: {e}')

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
