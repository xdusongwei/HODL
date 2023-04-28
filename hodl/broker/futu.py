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

    QUOTE_CLIENT: OpenQuoteContext = None
    MARKET_STATUS_BUCKET = LeakyBucket(10)
    SNAPSHOT_BUCKET = LeakyBucket(120)

    def __post_init__(self):
        if FutuApi.QUOTE_CLIENT is None:
            SysConfig.set_all_thread_daemon(True)
            config_dict = self.broker_config
            host = config_dict.get('host', '127.0.0.1')
            port = config_dict.get('port', 11111)
            quote_ctx = OpenQuoteContext(host=host, port=port)
            FutuApi.QUOTE_CLIENT = quote_ctx
        self.quote_client = FutuApi.QUOTE_CLIENT

    @track_api
    def detect_plug_in(self):
        try:
            client = self.quote_client
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

    @track_api
    def fetch_quote(self) -> Quote:
        symbol = self.symbol
        client = self.quote_client
        with self.SNAPSHOT_BUCKET:
            tz_offset = None
            if re.match(r'^[56]\d{5}$', symbol):
                symbol = f'SH.{symbol}'
                tz_offset = '+08:00'
            if re.match(r'^[013]\d{5}$', symbol):
                symbol = f'SZ.{symbol}'
                tz_offset = '+08:00'
            if re.match(r'^\d{5}$', symbol):
                symbol = f'HK.{symbol}'
                tz_offset = '+08:00'
            if tz_offset is None:
                raise PrepareError(f'富途快照接口不能确定{self.symbol}的时区')
            ret, data = client.get_market_snapshot([symbol, ])
        if ret == RET_OK:
            table = data.to_dict(orient='records')
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


__all__ = ['FutuApi', ]
