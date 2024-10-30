from urllib.parse import urljoin
import requests
from hodl.broker.base import *
from hodl.exception_tools import *
from hodl.state import *
from hodl.tools import *


@register_broker
class CiticsRestApi(BrokerApiBase):
    BROKER_NAME = 'citics'
    BROKER_DISPLAY = '中信证券'
    ENABLE_BOOTING_CHECK = False
    CASH_CURRENCY = 'CNY'

    FILE_LOCK = None

    def on_init(self):
        if CiticsRestApi.FILE_LOCK is None:
            order_lock_file = self.broker_config.get('order_lock_file', None)
            CiticsRestApi.FILE_LOCK = Filelock(order_lock_file)

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

    def _citics_fetch(self, uri: str, timeout: int = None) -> dict:
        base_site = self.broker_config.get('url')
        if timeout is None:
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
            if 'current' in citics_state:
                citics_current = citics_state.get('current')
                assert citics_current == '就绪'
            elif 'isReady' in citics_state:
                citics_current = citics_state.get('isReady')
                assert citics_current
            else:
                raise ValueError(f'中信证券接口响应中不存在任何指示系统状态的字段')
            return citics_state
        except Exception as e:
            raise e

    def _citics_action(self, uri: str, d: dict) -> dict:
        base_site = self.broker_config.get('url')
        timeout = self.broker_config.get('timeout', 20)
        token = self.broker_config.get('token', '')
        url = urljoin(base_site, uri)
        session = self.http_session
        with CiticsRestApi.FILE_LOCK:
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
            self._citics_fetch(f'/api/citics/state?ping=1&symbol={self.symbol}', timeout=5)
            return True
        except Exception as e:
            return False

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
                if '持仓' in p:
                    return p['持仓']
                if '参考持股' in p:
                    return p['参考持股']
        return 0

    @track_api
    def place_order(self, order: Order):
        args = {
            'symbol': order.symbol,
            'direction': order.direction,
            'qty': order.qty,
            'limitPrice': order.limit_price,
            'name': self.name,
            'protectPrice': order.protect_price,
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
            if '合同编号' in o:
                oid = o['合同编号']
            elif '委托编号' in o:
                oid = o['委托编号']
            else:
                continue
            if oid != order.order_id:
                continue
            reason = ''
            if '废单原因' in o:
                reason = o['废单原因']
            if '返回信息' in o:
                reason = o['返回信息']
            self.modify_order_fields(
                order=order,
                qty=o['委托数量'],
                filled_qty=o['成交数量'],
                avg_fill_price=o['成交价格'],
                trade_timestamp=None,
                reason=reason,
                is_cancelled=o['委托状态'] == '已撤',
            )
            break
        else:
            # 中信证券晚上会把当日委托清空， 后面时间如果找不到委托则忽略
            if TimeTools.us_time_now().strftime('%H:%M') < "16:00":
                raise CiticsError(f'中信证券找不到{symbol}委托: [{type(order.order_id).__name__}]{order.order_id}')


__all__ = ['CiticsRestApi', ]
