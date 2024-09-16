"""
接入富途证券的API文档
https://openapi.futunn.com/futu-api-doc/
"""
import re
from futu import *
from hodl.broker.base import *
from hodl.quote import *
from hodl.tools import *
from hodl.exception_tools import *
from hodl.state import *


class FutuApi(BrokerApiBase):
    BROKER_NAME = 'futu'
    BROKER_DISPLAY = '富途证券'
    ENABLE_BOOTING_CHECK = True

    QUOTE_CLIENT: OpenQuoteContext = None
    TRADE_CLIENT: OpenSecTradeContext = None
    MARKET_STATUS_BUCKET = LeakyBucket(10)
    SNAPSHOT_BUCKET = LeakyBucket(120)
    ASSET_BUCKET = LeakyBucket(20)
    POSITION_BUCKET = LeakyBucket(20)
    UNLOCK_BUCKET = LeakyBucket(20)
    PLACE_ORDER_BUCKET = LeakyBucket(30)
    CANCEL_ORDER_BUCKET = LeakyBucket(30)
    REFRESH_ORDER_BUCKET = LeakyBucket(20)

    def on_init(self):
        config_dict = self.broker_config
        pk_path = config_dict.get('pk_path', '')
        self.unlock_pin = config_dict.get('unlock_pin', '')
        if pk_path:
            SysConfig.enable_proto_encrypt(is_encrypt=True)
            SysConfig.set_init_rsa_file(pk_path)
        if FutuApi.TRADE_CLIENT is None:
            SysConfig.set_all_thread_daemon(True)
            config_dict = self.broker_config
            host = config_dict.get('host', '127.0.0.1')
            port = config_dict.get('port', 11111)
            trade_ctx = OpenSecTradeContext(
                filter_trdmarket=TrdMarket.US,
                host=host,
                port=port,
                security_firm=SecurityFirm.FUTUSECURITIES,
            )
            trade_ctx.set_sync_query_connect_timeout(6.0)
            FutuApi.TRADE_CLIENT = trade_ctx
        self.trade_client = FutuApi.TRADE_CLIENT

    def __post_init__(self):
        config_dict = self.broker_config
        pk_path = config_dict.get('pk_path', '')
        if pk_path:
            SysConfig.enable_proto_encrypt(is_encrypt=True)
            SysConfig.set_init_rsa_file(pk_path)
        if FutuApi.QUOTE_CLIENT is None:
            SysConfig.set_all_thread_daemon(True)
            host = config_dict.get('host', '127.0.0.1')
            port = config_dict.get('port', 11111)
            quote_ctx = OpenQuoteContext(host=host, port=port)
            quote_ctx.set_sync_query_connect_timeout(6.0)
            FutuApi.QUOTE_CLIENT = quote_ctx
        self.quote_client = FutuApi.QUOTE_CLIENT

    @track_api
    def detect_plug_in(self):
        try:
            client = self.trade_client
            conn_id = client.get_sync_conn_id()
            return bool(conn_id)
        except Exception as e:
            return False

    @track_api
    def fetch_market_status(self) -> BrokerMarketStatusResult:
        result = BrokerMarketStatusResult()
        client = self.quote_client
        with self.MARKET_STATUS_BUCKET:
            ret, data = client.get_global_state()
        if ret == RET_OK:
            rl: list[MarketStatusResult] = list()
            for k, v in data.items():
                if k not in self.MS_REGION_TABLE:
                    continue
                region = self.MS_REGION_TABLE[k]
                status = v
                rl.append(MarketStatusResult(region=region, status=status))

            result.append(BrokerTradeType.STOCK, rl)
            return result
        else:
            raise PrepareError(f'富途市场状态接口调用失败: {data}')

    @classmethod
    def to_futu_symbol(cls, symbol: str) -> str:
        if re.match(r'^[56]\d{5}$', symbol):
            symbol = f'SH.{symbol}'
        elif re.match(r'^[013]\d{5}$', symbol):
            symbol = f'SZ.{symbol}'
        elif re.match(r'^\d{5}$', symbol):
            symbol = f'HK.{symbol}'
        else:
            symbol = f'US.{symbol}'
        return symbol

    @classmethod
    def to_tz(cls, symbol: str) -> str:
        if re.match(r'^[56]\d{5}$', symbol):
            tz_offset = '+08:00'
        elif re.match(r'^[013]\d{5}$', symbol):
            tz_offset = '+08:00'
        elif re.match(r'^\d{5}$', symbol):
            tz_offset = '+08:00'
        else:
            raise PrepareError(f'不能转换{symbol}为任何富途证券的时区信息')
        return tz_offset

    @track_api
    def fetch_quote(self) -> Quote:
        symbol = self.symbol
        client = self.quote_client
        with self.SNAPSHOT_BUCKET:
            tz_offset = self.to_tz(symbol)
            futu_symbol = self.to_futu_symbol(symbol)
            ret, data = client.get_market_snapshot([futu_symbol, ])
        if ret == RET_OK:
            table = FormatTool.dataframe_to_list(data)
            for d in table:
                update_time: str = d['update_time']
                update_time = f"{update_time.replace(' ', 'T')}{tz_offset}"
                date = datetime.fromisoformat(update_time)
                return Quote(
                    symbol=self.symbol,
                    open=d['open_price'],
                    pre_close=d['prev_close_price'],
                    latest_price=d['last_price'],
                    time=date,
                    status=d['sec_status'],
                    day_low=d['low_price'],
                    day_high=d['high_price'],
                    broker_name=self.BROKER_NAME,
                    broker_display=self.BROKER_DISPLAY,
                )
        else:
            raise PrepareError(f'富途快照接口调用失败: {data}')

    @track_api
    def query_cash(self):
        try:
            with self.ASSET_BUCKET:
                resp, data = self.trade_client.accinfo_query(
                    refresh_cache=True,
                    currency=Currency.USD,
                )
            if resp == RET_OK and len(FormatTool.dataframe_to_list(data)) == 1:
                return float(FormatTool.dataframe_to_list(data)[0]['cash'])
            else:
                raise PrepareError(f'富途证券可用资金信息获取失败: {data}')
        except Exception as e:
            raise PrepareError(f'富途证券资金接口调用失败: {e}')

    @track_api
    def query_chips(self):
        symbol = self.symbol
        try:
            with self.POSITION_BUCKET:
                resp, data = self.trade_client.position_list_query(
                    code=self.to_futu_symbol(symbol),
                    refresh_cache=True,
                )
                if resp == RET_OK:
                    for d in FormatTool.dataframe_to_list(data):
                        return int(d['qty'])
                    return 0
                else:
                    raise PrepareError(f'富途证券持仓获取失败: {data}')
        except Exception as e:
            raise PrepareError(f'富途证券持仓接口调用失败: {e}')

    def try_unlock(self):
        if not self.unlock_pin:
            return
        with self.UNLOCK_BUCKET:
            ret, data = self.trade_client.unlock_trade(password_md5=self.unlock_pin)
        if ret != RET_OK:
            raise Exception(f'富途证券解锁交易失败: {data}')

    @track_api
    def place_order(self, order: Order):
        self.try_unlock()
        with self.PLACE_ORDER_BUCKET:
            ret, data = self.trade_client.place_order(
                code=self.to_futu_symbol(order.symbol),
                price=order.limit_price or 1.0,
                qty=order.qty,
                trd_side=TrdSide.BUY if order.is_buy else TrdSide.SELL,
                order_type=OrderType.NORMAL if order.limit_price else OrderType.MARKET,
                time_in_force=TimeInForce.DAY,
                fill_outside_rth=False,
            )
        if ret != RET_OK:
            raise Exception(f'富途证券下单失败: {data}')
        orders = FormatTool.dataframe_to_list(data)
        assert len(orders) == 1
        order_id = orders[0]['order_id']
        assert order_id
        order.order_id = order_id

    @track_api
    def cancel_order(self, order: Order):
        self.try_unlock()
        with self.CANCEL_ORDER_BUCKET:
            ret, data = self.trade_client.modify_order(
                modify_order_op=ModifyOrderOp.CANCEL,
                order_id=order.order_id,
                qty=order.qty,
                price=order.limit_price,
            )
        if ret != RET_OK:
            raise Exception(f'富途证券撤单失败, 订单: {order}, 原因: {data}')

    @track_api
    def refresh_order(self, order: Order):
        with self.REFRESH_ORDER_BUCKET:
            ret, data = self.trade_client.order_list_query(
                order_id=order.order_id,
                refresh_cache=True,
            )
            if ret != RET_OK:
                raise OrderRefreshError(f'富途证券刷新失败, 订单: {order}')
            orders = FormatTool.dataframe_to_list(data)
            assert len(orders) == 1
            futu_order = orders[0]
            reason = ''
            if futu_order['order_status'] == OrderStatus.FAILED:
                reason = 'FAILED'
            if futu_order['order_status'] == OrderStatus.DISABLED:
                reason = 'DISABLED'
            if futu_order['order_status'] == OrderStatus.DELETED:
                reason = 'DELETED'
            self.modify_order_fields(
                order=order,
                qty=order.qty,
                filled_qty=int(futu_order['dealt_qty']),
                avg_fill_price=float(futu_order['dealt_avg_price']) or 0.0,
                trade_timestamp=None,
                reason=reason,
                is_cancelled=futu_order['order_status'] in {OrderStatus.CANCELLED_PART, OrderStatus.CANCELLED_ALL, },
            )


__all__ = ['FutuApi', ]
