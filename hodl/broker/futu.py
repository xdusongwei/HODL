"""
接入富途证券的API文档
https://openapi.futunn.com/futu-api-doc/
"""
import re
from datetime import datetime
from futu import *
from hodl.broker.base import *
from hodl.quote import *
from hodl.tools import *
from hodl.exception_tools import *


class FutuApi(BrokerApiBase):
    BROKER_NAME = 'futu'
    BROKER_DISPLAY = '富途证券'
    META = [
        ApiMeta(
            trade_type=BrokerTradeType.STOCK,
            share_market_state=True,
            share_quote=True,
            market_status_regions={'US', 'HK', 'CN', },
            quote_regions={'HK', 'CN', },
            trade_regions=set(),
        ),
    ]

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

    def detect_plug_in(self):
        try:
            client = self.quote_client
            conn_id = client.get_sync_conn_id()
            return bool(conn_id)
        except Exception as e:
            return False

    def fetch_market_status(self) -> dict:
        client = self.quote_client
        with self.MARKET_STATUS_BUCKET:
            ret, data = client.get_global_state()
        if ret == RET_OK:
            market_map = {
                'market_sh': 'CN',
                'market_hk': 'HK',
                'market_us': 'US',
            }
            market_status_map = {
                'CLOSED': 'CLOSING',
                'AFTER_HOURS_END': 'CLOSING',
                'MORNING': 'TRADING',
                'AFTERNOON': 'TRADING',
            }
            result = dict()
            for k, v in data.items():
                if k not in market_map:
                    continue
                if v in market_status_map:
                    v = market_status_map[v]
                result[market_map[k]] = v
            return {
                BrokerTradeType.STOCK.value: result,
            }
        else:
            raise PrepareError(f'富途市场状态接口调用失败: {data}')

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
