"""
接入盈透证券的API文档
https://ib-insync.readthedocs.io/readme.html
"""
import threading
import ib_insync
from ib_insync import IB, Stock, Contract, Ticker, LimitOrder, MarketOrder, Trade
from ib_insync.util import startLoop, UNSET_DOUBLE
from hodl.broker.base import *
from hodl.exception_tools import *
from hodl.quote import *
from hodl.state import *
from hodl.tools import *
from hodl.proxy import *


@register_broker
class InteractiveBrokersApi(BrokerApiBase):
    BROKER_NAME = 'interactiveBrokers'
    BROKER_DISPLAY = '盈透证券'
    ENABLE_BOOTING_CHECK = False
    CASH_CURRENCY = 'USD'

    LOCK = threading.RLock()
    GATEWAY_SOCKET: IB = None
    LOOP_STARTED: bool = False

    PLUGIN_BUCKET = LeakyBucket(60)
    ACCOUNT_BUCKET = LeakyBucket(60)
    ORDER_BUCKET = LeakyBucket(60)
    QUOTE_BUCKET = LeakyBucket(60)

    CONTRACTS: dict[str, Contract] = dict()
    TICKERS: dict[str, Ticker] = dict()

    def account_id(self) -> str:
        return self.broker_config.get('account_id')

    def ib_socket(self) -> IB:
        return InteractiveBrokersApi.GATEWAY_SOCKET
    
    def __post_init__(self):
        super().__post_init__()
        self.currency = 'USD'
        try:
            self._try_create_tws_client()
        except Exception as e:
            pass

    def on_init(self):
        try:
            self._try_create_tws_client()
        except Exception as e:
            pass

    def _try_create_tws_client(self):
        with InteractiveBrokersApi.LOCK:
            if not InteractiveBrokersApi.LOOP_STARTED:
                AsyncioProxyThread.call_from_sync(startLoop)
                InteractiveBrokersApi.LOOP_STARTED = True
            ib_socket = InteractiveBrokersApi.GATEWAY_SOCKET
            if ib_socket:
                try:
                    ib_dt = AsyncioProxyThread.call_coro_func(ib_socket.reqCurrentTimeAsync)
                    now = TimeTools.us_time_now(tz='UTC')
                    if TimeTools.timedelta(ib_dt, seconds=15) <= now:
                        raise TimeoutError
                    assert ib_socket.isConnected()
                    return
                except Exception as e:
                    print(f'InteractiveBrokersApi 测试连接失败: {e}')
            if ib_socket:
                AsyncioProxyThread.call_from_sync(ib_socket.disconnect)
                ib = ib_socket
            else:
                ib = ib_insync.IB()
            host = self.broker_config.get('host', '127.0.0.1')
            port = self.broker_config.get('port', 4001)
            client_id = self.broker_config.get('client_id', 0)
            timeout = self.broker_config.get('timeout', 8)
            account_id = self.account_id()
            AsyncioProxyThread.call(
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
            contract = Stock(symbol, 'SMART', currency=self.currency)
            InteractiveBrokersApi.CONTRACTS[symbol] = contract
            socket = self.ib_socket()
            AsyncioProxyThread.call_from_sync(socket.qualifyContracts, *[contract])
            ticker = AsyncioProxyThread.call_from_sync(socket.reqMktData, contract, '', False, False)
            assert ticker
            InteractiveBrokersApi.TICKERS[symbol] = ticker
            TimeTools.sleep(1.0)

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
                    if not socket:
                        raise PrepareError
                    l = AsyncioProxyThread.call(socket.accountSummaryAsync(account=self.account_id()))
                    d: dict[str, ib_insync.AccountValue] = {i.tag: i for i in l}
                    item = d['TotalCashValue']
                    assert item.currency == 'USD'
                    amount = float(item.value)
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
                    if not socket:
                        raise PrepareError
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
                    socket = self.ib_socket()
                    self._try_fill_contract()
                    contract = InteractiveBrokersApi.CONTRACTS[order.symbol]
                    if order.limit_price:
                        ib_order = LimitOrder(
                            action=order.direction,
                            totalQuantity=order.qty,
                            lmtPrice=order.limit_price,
                        )
                    else:
                        ib_order = MarketOrder(
                            action=order.direction,
                            totalQuantity=order.qty,
                        )
                    ib_order.tif = 'DAY'
                    ib_order.outsideRth = False
                    trade = AsyncioProxyThread.call_from_sync(socket.placeOrder, contract, ib_order)
                    TimeTools.sleep(2.0)
                    order_id = trade.order.permId
                    assert order_id
                    order.order_id = order_id
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
                        if ib_order.permId != order.order_id:
                            continue
                        AsyncioProxyThread.call_from_sync(socket.cancelOrder, ib_order)
                        return
                case _:
                    raise TradingError(f'撤单使用了不受支持的盈透证券交易连接通道')

    @classmethod
    def _reformat_float(cls, v):
        return 0.0 if v == UNSET_DOUBLE else v

    @classmethod
    def _total_fills(cls, trade: Trade) -> int:
        return int(trade.filled())

    @classmethod
    def _avg_price(cls, trade: Trade) -> float:
        total_fills = cls._total_fills(trade)
        if not total_fills:
            return 0
        cap = sum([fill.execution.shares * fill.execution.avgPrice for fill in trade.fills], 0.0)
        return FormatTool.adjust_precision(cap / total_fills, 5)

    @track_api
    def refresh_order(self, order: Order):
        with self.ORDER_BUCKET:
            match self.connection_type:
                case 'TWS':
                    socket = self.ib_socket()
                    self._try_fill_contract()
                    trades = socket.trades()
                    for ib_trade in trades:
                        ib_order = ib_trade.order
                        if ib_order.permId != order.order_id:
                            continue
                        qty = int(self._total_fills(ib_trade) + ib_trade.remaining())
                        filled_qty = self._total_fills(ib_trade)
                        qty = qty or filled_qty
                        assert qty >= filled_qty
                        avg_fill_price = self._avg_price(ib_trade)
                        reason = ''
                        if ib_trade.orderStatus.status == ib_insync.OrderStatus.Inactive:
                            reason = 'Inactive'

                        cancel_status = {ib_insync.OrderStatus.Cancelled, ib_insync.OrderStatus.ApiCancelled, }
                        is_cancelled = ib_trade.orderStatus.status in cancel_status
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
        # 盈透证券的开盘价, 日高日低价格不正确, 非必要不要与盈透行情混用多个行情源, 以免污染数据库或者持仓线程的状态跳变
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
