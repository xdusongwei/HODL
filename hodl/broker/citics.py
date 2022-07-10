from urllib.parse import urljoin
import requests
from hodl.broker.base import *
from hodl.exception_tools import *
from hodl.state import *
from hodl.tools import *


class CiticsRestApi(BrokerApiBase):
    BROKER_NAME = 'citics'
    META = [
        ApiMeta(
            trade_type=BrokerTradeType.STOCK,
            share_market_state=False,
            share_quote=False,
            market_status_regions=set(),
            quote_regions=set(),
            trade_regions={'CN', },
        ),
    ]

    @classmethod
    def http_request(
            cls,
            method: str,
            url: str,
            json=None,
            timeout=30,
            session: requests.Session = None,
    ):
        args = dict(
            method=method,
            url=url,
            timeout=timeout,
            json=json,
            headers={
                'User-Agent': 'tradebot',
            },
        )
        if session:
            resp = session.request(**args)
        else:
            resp = requests.request(**args)
        resp.raise_for_status()
        d: dict = resp.json()
        return d

    def _citics_fetch(self, uri: str) -> dict:
        base_site = self.broker_config.get('url')
        timeout = self.broker_config.get('timeout', 20)
        url = urljoin(base_site, uri)
        try:
            session = self.http_session
            d = CiticsRestApi.http_request(
                method='GET',
                url=url,
                timeout=timeout,
                session=session,
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
        url = urljoin(base_site, uri)
        session = self.http_session
        d = CiticsRestApi.http_request(
            method='POST',
            url=url,
            json=d,
            timeout=timeout,
            session=session,
        )
        return d

    def detect_plug_in(self):
        try:
            self._citics_fetch(f'/api/citics/state?ping=1&symbol={self.symbol}')
            return True
        except Exception as e:
            return False

    def query_cash(self):
        symbol = self.symbol
        citics_state = self._citics_fetch(f'/api/citics/state?symbol={symbol}')
        return citics_state['cashAvailable']

    def query_chips(self):
        symbol = self.symbol
        citics_state = self._citics_fetch(f'/api/citics/state?symbol={symbol}')
        positions = citics_state.get('positions', list())
        if positions:
            for p in positions:
                return p['持仓']
        return 0

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
