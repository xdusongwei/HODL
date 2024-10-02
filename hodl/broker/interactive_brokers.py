"""
接入盈透证券的API文档
https://ib-insync.readthedocs.io/readme.html
"""
import threading
import ib_insync
from ib_insync import Stock, Contract, Ticker
from ib_insync.util import startLoop
from hodl.broker.base import *
from hodl.exception_tools import *
from hodl.quote import *
from hodl.state import *
from hodl.tools import *
from hodl.async_proxy import *


class InteractiveBrokersApi(BrokerApiBase):
    BROKER_NAME = 'interactiveBrokers'
    BROKER_DISPLAY = '盈透证券'
    ENABLE_BOOTING_CHECK = True

    LOCK = threading.RLock()
    GATEWAY_SOCKET: ib_insync.IB = None
    LOOP_STARTED: bool = False

    PLUGIN_BUCKET = LeakyBucket(60)
    ACCOUNT_BUCKET = LeakyBucket(60)
    ORDER_BUCKET = LeakyBucket(60)
    QUOTE_BUCKET = LeakyBucket(60)

    CONTRACTS: dict[str, Contract] = {}
    TICKERS: dict[str, Ticker] = {}

    def account_id(self) -> str:
        return self.broker_config.get('account_id')

    def ib_socket(self) -> ib_insync.IB:
        return InteractiveBrokersApi.GATEWAY_SOCKET
    
    def __post_init__(self):
        super().__post_init__()
        try:
            self._try_create_tws_client()
        except Exception as e:
            pass

    def _try_create_tws_client(self):
        with InteractiveBrokersApi.LOCK:
            if not InteractiveBrokersApi.LOOP_STARTED:
                AsyncProxyThread.call_from_sync(startLoop)
                InteractiveBrokersApi.LOOP_STARTED = True
            ib_socket = InteractiveBrokersApi.GATEWAY_SOCKET
            if ib_socket:
                try:
                    ib_dt = AsyncProxyThread.call_coro_func(ib_socket.reqCurrentTimeAsync)
                    now = TimeTools.us_time_now(tz='UTC')
                    if TimeTools.timedelta(ib_dt, seconds=15) <= now:
                        raise TimeoutError
                    assert ib_socket.isConnected()
                    return
                except Exception as e:
                    print(f'has error {e}')
            if ib_socket:
                AsyncProxyThread.call_from_sync(ib_socket.disconnect)
                ib = ib_socket
            else:
                ib = ib_insync.IB()
            host = self.broker_config.get('host', '127.0.0.1')
            port = self.broker_config.get('port', 4001)
            client_id = self.broker_config.get('client_id', 0)
            timeout = self.broker_config.get('timeout', 8)
            account_id = self.account_id()
            AsyncProxyThread.call(
                ib.connectAsync(
                    host=host,
                    port=port,
                    clientId=client_id,
                    timeout=timeout,
                    account=account_id,
                )
            )
            InteractiveBrokersApi.GATEWAY_SOCKET = ib

    def _try_fill_contract(self):
        symbol = self.symbol
        with InteractiveBrokersApi.LOCK:
            if symbol in InteractiveBrokersApi.CONTRACTS:
                return
            contract = Stock(symbol, 'SMART', currency='USD')
            InteractiveBrokersApi.CONTRACTS[symbol] = contract
            socket = self.ib_socket()
            AsyncProxyThread.call_from_sync(socket.qualifyContracts, *[contract])
            ticker = AsyncProxyThread.call_from_sync(socket.reqMktData, contract, '', False, False)
            assert ticker
            InteractiveBrokersApi.TICKERS[symbol] = ticker

    @property
    def connection_type(self) -> str:
        """
        盈透证券可试用多种方式接入证券交易，
        有ClientPortalAPI和IB Gateway，
        前者接入方式盘中时段会频繁主动掉线，如果需要使用，需要人工一个交易日内登陆多次，登录时机亦须掌握清楚。
        """
        connection_type = self.broker_config.get('connection_type', 'ClientPortalAPI')
        assert connection_type in {'ClientPortalAPI', 'TWS', }
        return connection_type

    @track_api
    def detect_plug_in(self):
        with self.PLUGIN_BUCKET:
            match self.connection_type:
                case 'TWS':
                    try:
                        self._try_create_tws_client()
                        return True
                    except Exception as e:
                        return False
                case _:
                    return False

    @track_api
    def query_cash(self) -> float:
        with self.ACCOUNT_BUCKET:
            match self.connection_type:
                case 'TWS':
                    socket = self.ib_socket()
                    l = AsyncProxyThread.call(socket.accountSummaryAsync(account=self.account_id()))
                    d: dict[str, ib_insync.AccountValue] = {i.tag: i for i in l}
                    item = d['TotalCashValue']
                    assert item.currency == 'USD'
                    amount = float(item.value)
                    assert amount >= 0
                    return amount
                case _:
                    return 0.0

    @track_api
    def query_chips(self) -> int:
        """
        返回 self.symbol 获取实际持仓数量。
        """
        with self.ACCOUNT_BUCKET:
            match self.connection_type:
                case 'TWS':
                    socket = self.ib_socket()
                    l = socket.positions(account=self.account_id())
                    for position in l:
                        contract = position.contract
                        if contract.symbol != self.symbol:
                            continue
                        return int(position.position)
                    return 0
                case _:
                    return 0

    @track_api
    def place_order(self, order: Order):
        with self.ORDER_BUCKET:
            match self.connection_type:
                case 'TWS':
                    raise TradingError(f'下单使用了不受支持的盈透证券交易连接通道')
                case _:
                    raise TradingError(f'下单使用了不受支持的盈透证券交易连接通道')

    @track_api
    def cancel_order(self, order: Order):
        with self.ORDER_BUCKET:
            match self.connection_type:
                case 'TWS':
                    socket = self.ib_socket()
                    trades = socket.trades()
                    for ib_trade in trades:
                        ib_order = ib_trade.order
                        if ib_order.orderId != order.order_id:
                            continue
                        socket.cancelOrder(order=ib_order)
                        return
                    raise TradingError(f'没有找到有效订单用于撤单')
                case _:
                    raise TradingError(f'撤单使用了不受支持的盈透证券交易连接通道')

    @track_api
    def refresh_order(self, order: Order):
        with self.ORDER_BUCKET:
            match self.connection_type:
                case 'TWS':
                    socket = self.ib_socket()
                    trades = socket.trades()
                    for ib_trade in trades:
                        ib_order = ib_trade.order
                        if ib_order.orderId != order.order_id:
                            continue
                        qty = int(ib_order.totalQuantity)
                        filled_qty = int(ib_trade.orderStatus.filled)
                        avg_fill_price = ib_trade.orderStatus.avgFillPrice
                        reason = ''
                        if ib_trade.orderStatus.status == ib_insync.OrderStatus.Inactive:
                            reason = 'Inactive'

                        is_cancelled = ib_trade.orderStatus.status == ib_insync.OrderStatus.Cancelled
                        self.modify_order_fields(
                            order=order,
                            qty=qty,
                            filled_qty=filled_qty,
                            avg_fill_price=avg_fill_price,
                            trade_timestamp=None,
                            reason=reason,
                            is_cancelled=is_cancelled,
                        )
                    return 0
                case _:
                    return 0

    @track_api
    def fetch_quote(self) -> Quote:
        # 盈透证券的开盘价, 日高日低价格不正确, 非必要不要与盈透行情混用多个行情源, 以免污染数据库或者持仓线程的状态
        with self.QUOTE_BUCKET:
            symbol = self.symbol
            self._try_fill_contract()
            ticker = InteractiveBrokersApi.TICKERS.get(symbol)
            if not ticker:
                raise PrepareError
        quote_time = ticker.time
        if not quote_time:
            raise PrepareError
        return Quote(
            symbol=self.symbol,
            open=ticker.open,
            pre_close=ticker.close,
            latest_price=ticker.marketPrice(),
            time=quote_time,
            status='HALT' if ticker.halted != 0 else 'NORMAL',
            day_low=ticker.low,
            day_high=ticker.high,
            broker_name=self.BROKER_NAME,
            broker_display=self.BROKER_DISPLAY,
        )


__all__ = ['InteractiveBrokersApi', ]
