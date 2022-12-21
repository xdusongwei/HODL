import os
import time
import datetime
import dataclasses
import platform
import traceback
from threading import Thread
from collections import defaultdict
import pytz
import psutil
from hodl.bot import AlertBot, ConversationBot
from hodl.storage import *
from hodl.store import Store
from hodl.quote_mixin import QuoteMixin
from hodl.thread_mixin import *
from hodl.broker.broker_proxy import *
from hodl.tools import *


class MarketStatusThread(ThreadMixin):
    def __init__(self, broker_proxy: BrokerProxy):
        self.broker_proxy = broker_proxy
        self.ok_counter = defaultdict(int)
        self.error_counter = defaultdict(int)
        self.latest_time = dict()
        self.vix_info = dict()
        self.broker_names = set()

    def prepare(self):
        print(f'开启异步线程拉取市场状态')
        self.broker_proxy.pull_market_status()
        print(f'预拉取市场状态结束')

    def run(self):
        super(MarketStatusThread, self).run()
        while True:
            ms = self.broker_proxy.pull_market_status()
            if not ms:
                continue
            for t_broker, d in ms.items():
                broker_name = t_broker.BROKER_NAME
                self.broker_names.add(broker_name)
                if '_marketStatusException' in d or '_vixException' in d:
                    self.error_counter[broker_name] += 1
                else:
                    self.ok_counter[broker_name] += 1
                    self.latest_time[broker_name] = TimeTools.us_time_now(tz='UTC')
                    if 'vix' in d:
                        latest_vix = d.get('vix', dict())
                        self.vix_info[broker_name] = latest_vix.copy()
                    else:
                        self.vix_info[broker_name] = None

    def primary_bar(self) -> list[BarElementDesc]:
        bar = list()
        for name in sorted(self.broker_names):
            tooltip = f'上次成功时间: {FormatTool.pretty_dt(self.latest_time.get(name))}\n'
            if vix_info := self.vix_info.get(name, None):
                vix_latest = vix_info.get('latest')
                vix_time = vix_info.get('time')
                vix_date = TimeTools.from_timestamp(vix_time)
                tooltip += f'VIX:{FormatTool.pretty_usd(vix_latest, precision=2)}@{FormatTool.pretty_dt(vix_date)}'
            elem = BarElementDesc(
                content=f'{name}:✅{self.ok_counter.get(name, 0)}❌{self.error_counter.get(name, 0)}',
                tooltip=tooltip,
            )
            bar.append(elem)
        return bar


class PsUtilThread(ThreadMixin):
    BUFF_BAR = list()

    def secondary_bar(self) -> list[BarElementDesc]:
        return PsUtilThread.BUFF_BAR

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
        new_bar.append(BarElementDesc(content=f'start: {running_time}'))
        new_bar.append(BarElementDesc(content=f'cpu: {cpu_percent}'))
        new_bar.append(BarElementDesc(content=f'memory: {memory_usage}'))
        new_bar.append(BarElementDesc(content=f'threads: {process.num_threads()}'))
        new_bar.append(BarElementDesc(content=f'fds: {process.num_fds()}'))
        new_bar.append(BarElementDesc(content=f'read: {total_read}'))
        new_bar.append(BarElementDesc(content=f'write: {total_write}'))
        return new_bar

    def run(self):
        super(PsUtilThread, self).run()
        while True:
            try:
                PsUtilThread.BUFF_BAR = self.collect()
            except Exception as e:
                traceback.print_exc()
                time.sleep(10)


class HtmlWriterThread(ThreadMixin):
    class _ProfitRowTool:
        def __init__(self, store: Store):
            self.price = store.state.quote_latest_price
            self.store_config = store.store_config
            self.plan = store.state.plan
            self.filled_level = 0
            self.rows = list()
            self.buy_percent = None
            self.sell_percent = None
            self.has_table = self.plan.table_ready
            if self.has_table:
                self.filled_level = self.plan.current_sell_level_filled()
                self.rows = Store.build_table(store_config=self.store_config, plan=self.plan)
            if self.filled_level and self.price:
                idx = self.filled_level - 1
                rate = abs(self.price - self.rows[idx].buy_at) / self.price
                self.buy_percent = rate
            if self.filled_level < len(self.rows):
                idx = self.filled_level
                rate = abs(self.price - self.rows[idx].sell_at) / self.price
                self.sell_percent = rate

        def earning_forecast(self, rate: float) -> int:
            base_value = (self.plan.total_chips or 0) * (self.plan.base_price or 0.0)
            return int(base_value * (rate - 1))

    class _EnhancedJSONEncoder:
        @staticmethod
        def default(o):
            if dataclasses.is_dataclass(o):
                return dataclasses.asdict(o)
            raise TypeError

    def __init__(self, variable: VariableTools, db: LocalDb, template, stores: list[Store]):
        self.variable = variable
        self. db = db
        self.template = template
        self.stores = stores
        self.total_write = 0
        self.current_hash = ''
        self.recent_earnings = list()
        self.earning_list = list()
        self.earning_json = '{}'
        self.total_earning = list()
        self.order_times_ytd_json = '{}'

    def primary_bar(self) -> list[BarElementDesc]:
        bar = [
            BarElementDesc(
                content=f'🎞️{FormatTool.number_to_size(self.total_write)}',
                tooltip=f'累计写入量',
            )
        ]
        return bar

    @classmethod
    def _earning_style(cls, earning: EarningRow):
        match earning.currency:
            case 'USD':
                setattr(earning, 'style', 'text-success')
            case 'CNY':
                setattr(earning, 'style', 'text-danger')
            case 'HKD':
                setattr(earning, 'style', 'text-danger')
            case _:
                setattr(earning, 'style', 'text-success')
        day = str(earning.day)
        setattr(earning, 'date', f'{day[:4]}年{day[4:6]}月{day[6:]}日')
        return earning

    def _order_times_ytd(self):
        db = self.db
        world_latest = TimeTools.us_time_now(tz='Pacific/Auckland')
        this_year = world_latest.year
        utc_year = int(datetime.datetime(year=this_year, month=1, day=1, tzinfo=pytz.timezone('UTC')).timestamp())
        orders = OrderRow.simple_items_after_create_time(db.conn, create_time=utc_year)
        d = dict()
        for order in orders:
            dt = TimeTools.from_timestamp(order.create_time, tz=TimeTools.region_to_tz(region=order.region))
            day = TimeTools.date_to_ymd(dt)
            if day in d:
                d[day] += 1
            else:
                d[day] = 1
        dt_count = datetime.datetime(year=this_year, month=1, day=1, tzinfo=pytz.timezone('UTC'))
        while dt_count.year == this_year:
            day = TimeTools.date_to_ymd(dt_count)
            if day not in d:
                d[day] = 0
            dt_count += datetime.timedelta(days=1)

        order_times_ytd = [dict(date=k, v=v) for k, v in d.items()]
        order_times_ytd.sort(key=lambda i: i['date'])
        return FormatTool.json_dumps(order_times_ytd)

    @classmethod
    def store_value(cls, currency_list, store_list: list[Store]):
        hodl_dict = {currency: 0.0 for currency in currency_list}
        sell_dict = {currency: 0.0 for currency in currency_list}
        earning_dict = {currency: 0.0 for currency in currency_list}
        for store in store_list:
            currency = store.store_config.currency
            price = store.state.quote_latest_price
            plan = store.state.plan
            total_chips = plan.total_chips
            sell_volume = plan.total_volume_not_active(assert_zero=False)
            max_level = plan.current_sell_level_filled()
            orders = plan.orders
            if currency not in currency_list:
                continue
            if not price:
                continue
            if total_chips < sell_volume:
                continue
            hodl_cost = (total_chips - sell_volume) * price
            hodl_dict[currency] += hodl_cost
            if sell_volume:
                sell_cost = sum(order.filled_value for order in orders if order.is_sell)
                sell_dict[currency] += sell_cost
            forecast_earning = 0.0
            if plan.table_ready:
                rows = store.current_table()
            else:
                rows = list()
            for idx, row in enumerate(rows):
                level = idx + 1
                if max_level >= level:
                    base_value = (plan.total_chips or 0) * (plan.base_price or 0.0)
                    forecast_earning = (row.total_rate - 1) * base_value
            earning_dict[currency] += forecast_earning
        hodl_list = [(k, v,) for k, v in hodl_dict.items()]
        sell_list = [(k, v,) for k, v in sell_dict.items()]
        earning_list = [(k, v,) for k, v in earning_dict.items()]
        return hodl_list, sell_list, earning_list

    def write_html(self):
        currency_list = ('USD', 'CNY', 'HKD',)
        new_hash = self.current_hash
        try:
            html_file_path = self.variable.html_file_path
            template = self.template
            db = self.db
            store_list: list[Store] = self.stores.copy()
            new_hash = ','.join(f'{store.state.version}:{store.state.current}' for store in store_list)
            if self.current_hash != new_hash:
                if db:
                    create_time = (TimeTools.us_time_now(tz='Asia/Shanghai') - datetime.timedelta(days=365)).timestamp()
                    create_time = int(create_time)
                    self.recent_earnings = list(EarningRow.items_after_time(con=db.conn, create_time=create_time))
                else:
                    self.recent_earnings = list()
                self.earning_list = [self._earning_style(earning) for earning in self.recent_earnings[:20]]
                self.earning_json = FormatTool.json_dumps(
                    self.recent_earnings,
                    default=HtmlWriterThread._EnhancedJSONEncoder.default,
                )
                create_time = int(TimeTools.us_time_now().timestamp())
                self.total_earning = [
                    (currency, EarningRow.total_amount_before_time(db.conn, create_time=create_time, currency=currency))
                    for currency in currency_list
                ]
                if db:
                    self.order_times_ytd_json = self._order_times_ytd()
            hodl_list, sell_list, earning_list = self.store_value(currency_list=currency_list, store_list=store_list)

            html = template.render(
                order_times_ytd=self.order_times_ytd_json,
                store_list=store_list,
                FMT=FormatTool,
                ProfitRowTool=self._ProfitRowTool,
                earning_list=self.earning_list,
                earning_json=self.earning_json,
                threads=ThreadMixin.threads(),
                total_earning=self.total_earning,
                hodl_value=hodl_list,
                sell_value=sell_list,
                earning_value=earning_list,
            ).encode('utf8')
            with open(html_file_path, "wb") as f:
                f.write(html)
            self.total_write += len(html)
        except Exception:
            traceback.print_exc()
        finally:
            self.current_hash = new_hash

    def run(self):
        super(HtmlWriterThread, self).run()
        while True:
            time.sleep(24)
            if not self.variable.html_file_path:
                continue
            self.write_html()


class JsonWriterThread(ThreadMixin):
    def __init__(self, sleep_secs: int, stores: list[Store]):
        self.sleep_secs = sleep_secs
        self.stores = stores
        self.total_write = 0

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
        while True:
            time.sleep(4)
            path = VariableTools().manager_state_path
            if not path:
                return
            ms = BrokerProxy.MARKET_STATUS or dict()
            ms = {broker_type.BROKER_NAME: detail for broker_type, detail in ms.items()}
            d = {
                'type': 'manager',
                'pid': os.getpid(),
                'time': TimeTools.us_time_now().timestamp(),
                'storeSleepSecs': sleep_secs,
                'marketStatus': ms,
                'marketStatusThread': {
                    'name': Manager.MARKET_STATUS_THREAD.name,
                    'id': Manager.MARKET_STATUS_THREAD.native_id,
                    'dead': not Manager.MARKET_STATUS_THREAD.is_alive(),
                } if Manager.MARKET_STATUS_THREAD else {},
                'htmlWriterThread': {
                    'name': Manager.HTML_THREAD.name,
                    'id': Manager.HTML_THREAD.native_id,
                    'dead': not Manager.HTML_THREAD.is_alive(),
                } if Manager.HTML_THREAD else {},
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


class Manager(ThreadMixin):
    DB: LocalDb = None
    CONVERSATION_BOT: ConversationBot = None
    MARKET_STATUS_THREAD: Thread = None
    HTML_THREAD: Thread = None
    JSON_THREAD: Thread = None
    PSUTIL_THREAD: Thread = None

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
        bar.append(BarElementDesc(content=f'os: {platform.system()}'))
        bar.append(BarElementDesc(content=f'arch: {platform.machine()}'))
        bar.append(BarElementDesc(content=f'python: {platform.python_version()}'))
        return bar

    def run(self):
        super(Manager, self).run()
        var = VariableTools()
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

        if var.async_market_status:
            mkt_thread = MarketStatusThread(broker_proxy=stores[0].broker_proxy)
            mkt_thread.prepare()

            Manager.MARKET_STATUS_THREAD = mkt_thread.start(
                name='marketStatusPuller',
            )

        env = var.jinja_env
        template = env.get_template("index.html")
        Manager.HTML_THREAD = HtmlWriterThread(
            variable=var,
            db=db,
            template=template,
            stores=stores,
        ).start(
            name='htmlWriter',
        )
        print(f'HTML刷新线程已启动')

        Manager.JSON_THREAD = JsonWriterThread(
            sleep_secs=var.sleep_limit,
            stores=stores,
        ).start(
            name='jsonWriter',
        )
        print(f'json刷新线程已启动')

        Manager.PSUTIL_THREAD = PsUtilThread().start(name='psutil')

        while True:
            try:
                time.sleep(4)
                variable = VariableTools()
                sleep_secs = variable.sleep_limit
                store_configs = variable.store_configs
                if len(store_configs) != len(stores):
                    print(f'运行中的持仓对象数量和配置文件中的持仓配置数量不一致')
                    return
                for store in stores:
                    symbol = store.store_config.symbol
                    new_config = store_configs.get(symbol)
                    if new_config:
                        with store.thread_lock():
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


instance = Manager()
instance.run()
