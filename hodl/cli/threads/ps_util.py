import os
import time
import traceback
import psutil
from hodl.thread_mixin import *
from hodl.tools import *


class PsUtilThread(ThreadMixin):
    def __init__(self):
        super().__init__()
        self.bar_items = list()

    def secondary_bar(self) -> list[BarElementDesc]:
        return self.bar_items

    @classmethod
    def collect(cls):
        new_bar = list()
        pid = os.getpid()
        process = psutil.Process(pid)
        cpu_factor = process.cpu_percent(interval=30) / 100.0
        cpu_percent = FormatTool.factor_to_percent(cpu_factor, fmt='{:.1%}')
        memory_usage = FormatTool.number_to_size(process.memory_info().rss)
        create_time = process.create_time()
        running_secs = TimeTools.us_time_now().timestamp() - create_time
        running_time = TimeTools.precisedelta(running_secs, minimum_unit="minutes", format='%0.0f')
        io_counter = process.io_counters()
        total_read = FormatTool.number_to_size(io_counter.read_bytes)
        total_write = FormatTool.number_to_size(io_counter.write_bytes)
        new_bar.append(BarElementDesc(content=f'time: {running_time}'))
        new_bar.append(BarElementDesc(content=f'cpu: {cpu_percent}'))
        new_bar.append(BarElementDesc(content=f'memory: {memory_usage}'))
        new_bar.append(BarElementDesc(content=f'threads: {process.num_threads()}'))
        try:
            new_bar.append(BarElementDesc(content=f'fds: {process.num_fds()}'))
        except Exception as e:
            # POSIX 不支持
            new_bar.append(BarElementDesc(content=f'fds: --'))
        new_bar.append(BarElementDesc(content=f'read: {total_read}'))
        new_bar.append(BarElementDesc(content=f'write: {total_write}'))
        return new_bar

    def run(self):
        super(PsUtilThread, self).run()
        while True:
            try:
                self.bar_items = self.collect()
            except Exception as e:
                traceback.print_exc()
                time.sleep(10)


__all__ = ['PsUtilThread', ]
