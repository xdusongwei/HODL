from typing import Type
from collections import defaultdict
from hodl.thread_mixin import *
from hodl.broker.base import *
from hodl.broker.broker_proxy import *
from hodl.state import *
from hodl.tools import *


class MarketStatusThread(ThreadMixin):
    def __init__(self, ms_proxy: MarketStatusProxy, var: VariableTools):
        env = var.jinja_env
        template = env.get_template("market_status.html")
        self.template = template
        self.ms_proxy = ms_proxy
        self.ok_counter = defaultdict(int)
        self.error_counter = defaultdict(int)
        self.latest_time = dict()
        self.vix_info = dict()
        self.broker_names = set()

    def prepare(self):
        print(f'开启异步线程拉取市场状态')
        self.ms_proxy.pull_market_status()
        print(f'预拉取市场状态结束')

    def run(self):
        super(MarketStatusThread, self).run()
        while True:
            ms = self.ms_proxy.pull_market_status()
            if not ms:
                break
            for t_broker, d in ms.items():
                broker_name = t_broker.BROKER_NAME
                self.broker_names.add(broker_name)
                if d.has_error:
                    self.error_counter[broker_name] += 1
                else:
                    self.ok_counter[broker_name] += 1
                    self.latest_time[broker_name] = TimeTools.us_time_now(tz='UTC')
                    if vix := d.vix:
                        latest_vix = vix
                        self.vix_info[broker_name] = latest_vix.copy()
                    else:
                        self.vix_info[broker_name] = None

    def primary_bar(self) -> list[BarElementDesc]:
        bar = list()
        for name in sorted(self.broker_names):
            tooltip = f'上次成功时间: {FormatTool.pretty_dt(self.latest_time.get(name))}'
            elem = BarElementDesc(
                content=f'{name}:✅{self.ok_counter.get(name, 0)}❌{self.error_counter.get(name, 0)}',
                tooltip=tooltip,
            )
            bar.append(elem)
        return bar

    @classmethod
    def _extra_html(cls, template, ms: dict[Type[BrokerApiBase], BrokerMarketStatusResult]):
        html = template.render(
            ms=ms,
            FMT=FormatTool,
            TT=TimeTools,
        )
        return html

    def extra_html(self) -> None | str:
        template = self.template
        ms = self.ms_proxy.all_status
        return self._extra_html(template, ms)


__all__ = ['MarketStatusThread', ]
