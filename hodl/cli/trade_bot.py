import os
import time
import platform
from threading import Thread
from hodl.bot import AlertBot, ConversationBot
from hodl.storage import *
from hodl.store import Store
from hodl.quote_mixin import QuoteMixin
from hodl.thread_mixin import *
from hodl.broker.base import *
from hodl.broker.broker_proxy import *
from hodl.tools import *
from hodl.exception_tools import *
from hodl.cli.threads.market_status import *
from hodl.cli.threads.ps_util import *
from hodl.cli.threads.html_writer import *
from hodl.cli.threads.json_writer import *


class Manager(ThreadMixin):
    DB: LocalDb = None
    CONVERSATION_BOT: ConversationBot = None
    MARKET_STATUS_THREAD: Thread = None
    HTML_THREAD: Thread = None
    JSON_THREAD: Thread = None
    PSUTIL_THREAD: Thread = None
    PACKAGE_LIST: list[dict] = list()

    def __init__(self):
        self.var = VariableTools()
        env = self.var.jinja_env
        template = env.get_template("api_status.html")
        self.template = template
        BrokerApiBase.set_up_var(var=self.var)

    @classmethod
    def monitor_alert(cls, stores: list[Store]):
        for store in stores:
            thread = store.current_thread
            if thread.is_alive():
                continue
            text = f'💀线程[{thread.name}]已崩溃。\n'
            if detail := store.state.risk_control_detail:
                text += f'风控错误:{detail}\n'
            if e := store.exception:
                text += f'异常原因:{e}\n'
            store.bot.set_alarm(AlertBot.K_THREAD_DEAD, text=text)

    @classmethod
    def rework_store(cls, stores: list[Store]):
        for store in stores:
            if not store.store_config.enable:
                continue
            thread = store.current_thread
            with store.thread_lock():
                state = store.state
                plan = state.plan
                tz = store.runtime_state.tz_name
                state_path = store.store_config.state_file_path
                if not state_path:
                    continue
                if not state.is_today_get_off(tz=tz):
                    continue
                if not plan.rework_price:
                    continue
                latest_price = state.quote_latest_price
                if not latest_price:
                    continue
                if plan.rework_price > latest_price:
                    continue
                if not os.path.exists(state_path):
                    continue
                try:
                    os.remove(state_path)
                    rework_price = FormatTool.pretty_price(plan.rework_price, config=store.store_config)
                    store.bot.send_text(f'{thread.name}套利后价格达到{rework_price}, 持仓状态数据被重置')
                except FileNotFoundError:
                    pass
                except Exception as e:
                    store.bot.send_text(f'{thread.name}套利后价格达到条件, 持仓状态数据被重置失败: {e}')

    def primary_bar(self) -> list[BarElementDesc]:
        bar = []
        if Manager.CONVERSATION_BOT.bot:
            bar.append(BarElementDesc(content=f'🤖Telegram', tooltip=f'机器人可以对话或者报警'))
        if Manager.DB:
            bar.append(BarElementDesc(content=f'📼sqlite', tooltip=f'已启用数据库'))
        return bar

    def secondary_bar(self) -> list[BarElementDesc]:
        bar = list()
        bar.append(BarElementDesc(content=f'🖥os: {platform.system()}'))
        bar.append(BarElementDesc(content=f'🏗️arch: {platform.machine()}'))
        bar.append(BarElementDesc(content=f'🐍python: {platform.python_version()}'))
        for d in Manager.PACKAGE_LIST:
            name = d['name']
            version = d['version']
            bar.append(BarElementDesc(content=f'📦{name}({version})'))
        return bar

    @classmethod
    def _extra_html(cls, template, rl):
        html = template.render(
            rl=rl,
            FMT=FormatTool,
            TT=TimeTools,
        )
        return html

    def extra_html(self) -> None | str:
        template = self.template
        rl = track_api_report()
        return self._extra_html(template, rl)

    def run(self):
        super(Manager, self).run()
        var = self.var
        store_configs = var.store_configs
        if not store_configs:
            print('没有任何持仓配置')
            return

        db = None
        if path := var.db_path:
            db = LocalDb(db_path=path)
            Manager.DB = db
        try:
            Manager.CONVERSATION_BOT = ConversationBot(updater=var.telegram_updater(), db=db)
            stores = [Store(store_config=config, db=db) for config in store_configs.values()]
            for store in stores:
                store.prepare()
            threads = [
                store.start(
                    name=f'Store([{store.store_config.region}]{store.store_config.symbol})',
                )
                for store in stores
            ]
        except Exception as e:
            if db:
                db.conn.close()
            raise e

        ms_proxy = MarketStatusProxy(
            var=var,
            session=Store.SESSION,
        )
        if var.async_market_status:
            mkt_thread = MarketStatusThread(ms_proxy=ms_proxy, var=var)
            mkt_thread.prepare()

            Manager.MARKET_STATUS_THREAD = mkt_thread.start(
                name='marketStatusPuller',
            )

        env = var.jinja_env
        template = env.get_template("index.html")
        html_thread = HtmlWriterThread(
            variable=var,
            db=db,
            template=template,
        )
        Manager.HTML_THREAD = html_thread.start(
            name='htmlWriter',
        )
        print(f'HTML刷新线程已启动')

        Manager.JSON_THREAD = JsonWriterThread(
            sleep_secs=var.sleep_limit,
            ms_proxy=ms_proxy,
            ms_thread=Manager.MARKET_STATUS_THREAD,
            html_thread=Manager.HTML_THREAD,
        ).start(
            name='jsonWriter',
        )
        print(f'json刷新线程已启动')

        Manager.PSUTIL_THREAD = PsUtilThread().start(name='psutil')

        while True:
            try:
                time.sleep(4)
                try:
                    variable = VariableTools()
                except Exception as e:
                    raise ConfigReadError(e)
                sleep_secs = variable.sleep_limit
                store_configs = variable.store_configs
                if len(store_configs) != len(stores):
                    print(f'运行中的持仓对象数量和配置文件中的持仓配置数量不一致')
                    return
                BrokerApiBase.set_up_var(var=variable)
                html_thread.variable = variable
                for store in stores:
                    symbol = store.store_config.symbol
                    new_config = store_configs.get(symbol)
                    if new_config:
                        with store.thread_lock():
                            current_config = store.runtime_state.store_config
                            if current_config != new_config:
                                store.runtime_state.store_config = new_config
                            store.runtime_state.variable = variable
                    else:
                        print(f'找不到标的{symbol}的持仓配置信息')
                        return
                    store.runtime_state.sleep_secs = sleep_secs
                    QuoteMixin.change_cache_ttl(sleep_secs)
                self.monitor_alert(stores=stores)
                self.rework_store(stores=stores)
            except KeyboardInterrupt:
                for thread in threads:
                    if thread.is_alive():
                        thread.join()
                if db:
                    db.conn.close()

                if updater := Manager.CONVERSATION_BOT.updater:
                    updater.stop()
                return
            except ConfigReadError as e:
                print(f'读取配置文件出错: {e}')


if __name__ == '__main__':
    try:
        import subprocess
        j = subprocess.run(['pdm', 'list', '--json'], capture_output=True).stdout
        Manager.PACKAGE_LIST = sorted(FormatTool.json_loads(j), key=lambda i: i['name'].lower())
    finally:
        instance = Manager()
        instance.run()
