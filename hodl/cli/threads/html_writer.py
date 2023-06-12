import time
import datetime
import dataclasses
import traceback
import pytz
from hodl.storage import *
from hodl.store import Store
from hodl.thread_mixin import *
from hodl.tools import *


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

    def __init__(self, variable: VariableTools, db: LocalDb, template):
        self.variable = variable
        self.db = db
        self.template = template
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

    @classmethod
    def _sort_stores(cls, stores: list[Store]):
        def _key(store: Store):
            sc, s, _ = store.args()
            return s.market_status != 'TRADING', sc.full_name

        stores.sort(key=_key)

    def write_html(self):
        variable = self.variable
        currency_list = ('USD', 'CNY', 'HKD',)
        new_hash = self.current_hash
        locks = list()
        try:
            html_file_path = variable.html_file_path
            html_manifest_path = variable.html_manifest_path
            html_monthly_earnings_currency = variable.html_monthly_earnings_currency
            template = self.template
            db = self.db
            stores: list[Store] = self.find_by_type(Store)
            self._sort_stores(stores)

            store_list: list[Store] = [store for store in stores if store.store_config.visible]
            for store in store_list:
                store.lock.acquire()
                locks.append(store.lock)
            new_hash = ','.join(f'{store.state.version}:{store.state.current}' for store in store_list)
            if self.current_hash != new_hash:
                if db:
                    create_time = TimeTools.timedelta(TimeTools.us_time_now(tz='Asia/Shanghai'), days=-365)
                    create_time = int(create_time.timestamp())
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
                html_manifest_path=html_manifest_path,
                auto_refresh_time=variable.html_auto_refresh_time,
                broker_icon_path=variable.broker_icon_path,
                monthly_earning_currency=FormatTool.json_dumps(html_monthly_earnings_currency),
            ).encode('utf8')
            LocateTools.write_file(html_file_path, html, mode='wb')
            self.total_write += len(html)
        except Exception:
            traceback.print_exc()
        finally:
            self.current_hash = new_hash
            for lock in locks:
                lock.release()

    def run(self):
        super(HtmlWriterThread, self).run()
        while True:
            time.sleep(24)
            if not self.variable.html_file_path:
                continue
            self.write_html()


__all__ = ['HtmlWriterThread', ]
