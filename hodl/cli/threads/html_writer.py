import time
import datetime
import dataclasses
import traceback
from hodl.storage import *
from hodl.broker import *
from hodl.store import *
from hodl.store_hodl import *
from hodl.thread_mixin import *
from hodl.tools import *


class HtmlWriterThread(ThreadMixin):
    class _EnhancedJSONEncoder:
        @staticmethod
        def default(o):
            if dataclasses.is_dataclass(o):
                return dataclasses.asdict(o)
            raise TypeError

    @classmethod
    def _new_time(cls) -> str:
        return TimeTools.utc_now().strftime('%Y-%m-%dT%H:%M')

    def __init__(self, db: LocalDb, template):
        self.db = db
        self.template = template
        self.total_write = 0
        self.current_hash = ''
        self.current_time = self._new_time()
        self.recent_earnings = list()
        self.earning_list = list()
        self.earning_json = '{}'
        self.total_earning = list()
        self.order_times_ytd_json = '{}'

    @property
    def variable(self):
        return HotReloadVariableTools.config()

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
        setattr(earning, 'date', f'{day[2:4]}年{day[4:6]}月{day[6:]}日')
        return earning

    def _order_times_ytd(self):
        db = self.db
        world_latest = TimeTools.us_time_now(tz='Pacific/Auckland')
        this_year = world_latest.year
        utc_year = int(datetime.datetime(year=this_year, month=1, day=1, tzinfo=datetime.UTC).timestamp())
        orders = OrderRow.simple_items_after_create_time(db.conn, create_time=utc_year)
        d = dict()
        for order in orders:
            dt = TimeTools.from_timestamp(order.create_time, tz=TimeTools.region_to_tz(region=order.region))
            day = TimeTools.date_to_ymd(dt)
            if day in d:
                d[day] += 1
            else:
                d[day] = 1
        dt_count = datetime.datetime(year=this_year, month=1, day=1, tzinfo=datetime.UTC)
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
            if isinstance(store, StoreHodl) and plan.table_ready:
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
    def sort_stores(cls, stores: list[Store]):
        def _key(store: Store):
            sc = store.store_config
            state = store.state
            return state.market_status != 'TRADING', sc.full_name

        stores.sort(key=_key)

    def write_html(self):
        variable = self.variable
        total_earning_currency = variable.html_total_earning_currency
        html_asserts_currency = variable.html_assets_currency
        new_hash = self.current_hash
        new_time = self._new_time()
        try:
            html_file_path = variable.html_file_path
            html_manifest_path = variable.html_manifest_path
            html_monthly_earnings_currency = variable.html_monthly_earnings_currency
            template = self.template
            db = self.db
            stores: list[Store] = self.find_by_type(Store)
            self.sort_stores(stores)

            store_list: list[Store] = [store for store in stores if store.store_config.visible]
            new_hash = ','.join(f'{store.state.version}:{store.state.current}' for store in store_list)

            if self.current_hash != new_hash and self.current_time != new_time:
                self.current_time = new_time
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
                    for currency in total_earning_currency
                ]
                if db:
                    self.order_times_ytd_json = self._order_times_ytd()
            hodl_list, sell_list, earning_list = self.store_value(
                currency_list=html_asserts_currency,
                store_list=store_list,
            )

            html = template.render(
                order_times_ytd=self.order_times_ytd_json,
                store_list=store_list,
                FMT=FormatTool,
                ProfitRowTool=StoreHodl.ProfitRowTool,
                broker_types=BrokerApiBase.all_brokers_type(),
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

    def run(self):
        super(HtmlWriterThread, self).run()
        while True:
            time.sleep(24)
            if not self.variable.html_file_path:
                continue
            self.write_html()


__all__ = ['HtmlWriterThread', ]
