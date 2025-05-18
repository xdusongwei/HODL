import os
import time
from hodl.exception_tools import *
from hodl.store import Store
from hodl.thread_mixin import *
from hodl.proxy import *
from hodl.tools import *


class JsonWriterThread(ThreadMixin):
    def __init__(
            self,
            sleep_secs: int,
            ms_proxy: MarketStatusProxy,
    ):
        self.sleep_secs = sleep_secs
        self.total_write = 0
        self.market_status_proxy = ms_proxy

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
        stores: list[Store] = self.find_by_type(Store)
        pid = os.getpid()
        while True:
            time.sleep(4)
            path = VariableTools().manager_state_path
            if not path:
                return
            ms = self.market_status_proxy.all_status or dict()
            ms = {broker_type.BROKER_NAME: detail for broker_type, detail in ms.items()}
            items = list()
            for store in stores:
                if store.state and store.store_config.visible:
                    with store.lock:
                        items.append({
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
                                'cls': type(store).__name__,
                            },
                            'config': store.store_config.copy(),
                        })
            d = {
                'type': 'manager',
                'pid': pid,
                'time': FormatTool.adjust_precision(TimeTools.us_time_now().timestamp(), precision=3),
                'storeSleepSecs': sleep_secs,
                'marketStatus': ms,
                'items': items,
            }
            body = FormatTool.json_dumps(d, binary=True)
            LocateTools.write_file(path, body, mode='wb')
            self.total_write += len(body)


__all__ = ['JsonWriterThread', ]
