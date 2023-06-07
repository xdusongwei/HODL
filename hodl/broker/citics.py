from urllib.parse import urljoin
import requests
from hodl.broker.base import *
from hodl.exception_tools import *
from hodl.quote import *
from hodl.state import *
from hodl.tools import *


class CiticsRestApi(BrokerApiBase):
    BROKER_NAME = 'citics'
    BROKER_DISPLAY = '中信证券'
    ENABLE_BOOTING_CHECK = False

    @classmethod
    def http_request(
            cls,
            method: str,
            url: str,
            json=None,
            timeout=30,
            session: requests.Session = None,
            token: str = '',
            raise_for_status = False,
    ):
        args = dict(
            method=method,
            url=url,
            timeout=timeout,
            json=json,
            headers={
                'User-Agent': 'tradebot',
                'Citics-Token': token,
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

    def _citics_fetch(self, uri: str) -> dict:
        base_site = self.broker_config.get('url')
        timeout = self.broker_config.get('timeout', 20)
        token = self.broker_config.get('token', '')
        url = urljoin(base_site, uri)
        try:
            session = self.http_session
            d = CiticsRestApi.http_request(
                method='GET',
                url=url,
                timeout=timeout,
                session=session,
                token=token,
                raise_for_status=True,
            )
            citics_state = d.get('state', dict())
            citics_current = citics_state.get('current')
            assert citics_current == '就绪'
            return citics_state
        except Exception as e:
            raise e

    def _citics_action(self, uri: str, d: dict) -> dict:
        base_site = self.broker_config.get('url')
        timeout = self.broker_config.get('timeout', 20)
        token = self.broker_config.get('token', '')
        url = urljoin(base_site, uri)
        session = self.http_session
        d = CiticsRestApi.http_request(
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
    def detect_plug_in(self):
        try:
            self._citics_fetch(f'/api/citics/state?ping=1&symbol={self.symbol}')
            return True
        except Exception as e:
            return False

    @track_api
    def fetch_quote(self) -> Quote:
        symbol = self.symbol
        citics_state = self._citics_fetch(f'/api/citics/state')
        quote_list = citics_state['quoteList']
        for quote in quote_list:
            qd: dict = quote
            if qd.get('symbol') != symbol:
                continue
            return Quote(
                symbol=qd['symbol'],
                open=FormatTool.adjust_precision(qd['open_price'], 3),
                pre_close=FormatTool.adjust_precision(qd['pre_close'], 3),
                latest_price=FormatTool.adjust_precision(qd['latest_price'], 3),
                time=TimeTools.from_timestamp(qd['time']),
                status='NORMAL' if qd['status'] else '--',
                day_low=FormatTool.adjust_precision(qd['low_price'], 3),
                day_high=FormatTool.adjust_precision(qd['high_price'], 3),
                broker_name=self.BROKER_NAME,
                broker_display=self.BROKER_DISPLAY,
            )
        raise PrepareError(f'中信证券找不到指定的行情:{symbol}')

    @track_api
    def query_cash(self):
        symbol = self.symbol
        citics_state = self._citics_fetch(f'/api/citics/state?symbol={symbol}')
        return citics_state['cashAvailable']

    @track_api
    def query_chips(self):
        symbol = self.symbol
        citics_state = self._citics_fetch(f'/api/citics/state?symbol={symbol}')
        positions = citics_state.get('positions', list())
        if positions:
            for p in positions:
                return p['持仓']
        return 0

    @track_api
    def place_order(self, order: Order):
        args = {
            'symbol': order.symbol,
            'direction': order.direction,
            'qty': order.qty,
            'limitPrice': order.limit_price,
            'name': self.name,
        }
        d = self._citics_action(f'/api/citics/order/place', args)
        contract_id = d.get('contractId')
        reason = d.get('reason')
        is_submit = d.get('isSubmit', True)
        if not contract_id:
            err = CiticsError(reason)
            err.thread_killer = is_submit
            raise err
        order.order_id = contract_id

    @track_api
    def cancel_order(self, order: Order):
        args = {
            'contractId': order.order_id,
        }
        d = self._citics_action(f'/api/citics/order/cancel', args)
        is_ok = d.get('isOk')
        reason = d.get('reason')
        is_submit = d.get('isSubmit', True)
        if not is_ok:
            err = CiticsError(reason)
            err.thread_killer = is_submit
            raise err

    @track_api
    def refresh_order(self, order: Order):
        symbol = self.symbol
        citics_state = self._citics_fetch(f'/api/citics/state?symbol={symbol}')
        orders: list[dict] = citics_state.get('orders', list())
        for o in orders:
            if o['合同编号'] != order.order_id:
                continue
            self.modify_order_fields(
                order=order,
                qty=o['委托数量'],
                filled_qty=o['成交数量'],
                avg_fill_price=o['成交价格'],
                trade_timestamp=None,
                reason=o['废单原因'],
                is_cancelled=o['委托状态'] == '已撤',
            )
            break
        else:
            # 中信证券晚上会把当日委托清空， 后面时间如果找不到委托则忽略
            if TimeTools.us_time_now().strftime('%H:%M') < "16:00":
                raise CiticsError(f'中信证券找不到{symbol}委托: [{type(order.order_id).__name__}]{order.order_id}')


__all__ = ['CiticsRestApi', ]
