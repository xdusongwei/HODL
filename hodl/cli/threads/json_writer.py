import os
import time
import threading
from hodl.store import Store
from hodl.thread_mixin import *
from hodl.broker.broker_proxy import *
from hodl.tools import *


class JsonWriterThread(ThreadMixin):
    def __init__(
            self,
            sleep_secs: int,
            stores: list[Store], ms_proxy: MarketStatusProxy,
            html_thread: threading.Thread,
            ms_thread: threading.Thread,
    ):
        self.sleep_secs = sleep_secs
        self.stores = stores
        self.total_write = 0
        self.market_status_proxy = ms_proxy
        self.html_thread = html_thread
        self.ms_thread = ms_thread

    def primary_bar(self) -> list[BarElementDesc]:
        bar = [
            BarElementDesc(
                content=f'🎞️{FormatTool.number_to_size(self.total_write)}',
                tooltip=f'累计写入量',
            )
        ]
        return bar

    def run(self):
        super(JsonWriterThread, self).run()
        sleep_secs = self.sleep_secs
        stores = self.stores
        pid = os.getpid()
        while True:
            time.sleep(4)
            path = VariableTools().manager_state_path
            if not path:
                return
            ms = self.market_status_proxy.all_status or dict()
            ms = {broker_type.BROKER_NAME: detail for broker_type, detail in ms.items()}
            d = {
                'type': 'manager',
                'pid': pid,
                'time': TimeTools.us_time_now().timestamp(),
                'storeSleepSecs': sleep_secs,
                'marketStatus': ms,
                'marketStatusThread': {
                    'name': self.ms_thread.name,
                    'id': self.ms_thread.native_id,
                    'dead': not self.ms_thread.is_alive(),
                } if self.ms_thread else {},
                'htmlWriterThread': {
                    'name': self.html_thread.name,
                    'id': self.html_thread.native_id,
                    'dead': not self.html_thread.is_alive(),
                } if self.html_thread else {},
                'items': [
                    {
                        'symbol': store.store_config.symbol,
                        'thread': {
                            'name': store.current_thread.name,
                            'id': store.current_thread.native_id,
                            'dead': not store.current_thread.is_alive(),
                        },
                        'store': {
                            'state': store.state,
                            'exception': str(store.exception or ''),
                            'hasDb': bool(store.db),
                            'hasAlertBot': store.bot.is_alive,
                            'processTime': store.process_time,
                        },
                        'config': {
                            'name': store.store_config.name,
                            'symbol': store.store_config.symbol,
                            'maxShares': store.store_config.max_shares,
                            'enable': store.store_config.enable,
                            'prudent': store.store_config.prudent,
                            'broker': store.store_config.broker,
                            'tradeType': store.store_config.trade_type,
                            'region': store.store_config.region,
                            'precision': store.store_config.precision,
                            'lockPosition': store.store_config.lock_position,
                            'basePriceLastBuy': store.store_config.base_price_last_buy,
                            'basePriceDayLow': store.store_config.base_price_day_low,
                            'currency': store.store_config.currency,
                            'reworkLevel': store.store_config.rework_level,
                            'marketPriceRate': store.store_config.market_price_rate,
                        },
                        'broker': {
                            'tradeBroker': str(store.broker_proxy.trade_broker),
                        } if store.broker_proxy else {},
                    }
                    for store in stores if store.state],
            }
            body = FormatTool.json_dumps(d, binary=True)
            with open(path, 'wb') as f:
                f.write(body)
            self.total_write += len(body)


__all__ = ['JsonWriterThread', ]
