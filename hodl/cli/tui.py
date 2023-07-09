import sys
import asyncio
import threading
import httpx
from rich.align import Align
from rich.console import Group
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Vertical, Container, Grid
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Header, Footer, DataTable, Static
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets._header import HeaderClock, HeaderTitle, HeaderClockSpace
from hodl.store import *
from hodl.tools import *
from hodl.state import *
from hodl.store_base import *
from hodl.cli.fix_screens.store_config_detail import *


PAIRS_LIST: list[tuple[dict, dict, StoreConfig, State]] = list()
RECENT_EARNINGS_LIST: list[dict] = list()


def default_style(state: State):
    return 'white' if state.market_status == 'TRADING' else 'grey50'


class HodlHeaderClock(HeaderClock):
    DEFAULT_CSS = """
        HodlHeaderClock {
            width: 26;
            opacity: 90%;
        }
        """

    def render(self):
        cst_time = TimeTools.us_time_now(tz='Asia/Shanghai')
        if 9 <= cst_time.hour <= 15:
            tz_name = 'CST'
            time = cst_time
        else:
            tz_name = 'EDT'
            time = TimeTools.us_time_now()
        time = time.isoformat(timespec='milliseconds')
        time = time[:-10]
        return Text(f'{tz_name}: {time}', style="bright_green")


class HodlHeaderTitle(HeaderTitle):
    DEFAULT_CSS = """
    HodlHeaderTitle {
        content-align: left middle;
        text-opacity: 75%;
        padding: 0 1;
    }
    """


class HodlHeader(Header):
    def compose(self):
        yield HodlHeaderTitle()
        yield HodlHeaderClock() if self._show_clock else HeaderClockSpace()


class StorePanel(Widget):
    pairs_list: reactive[list[tuple[dict, dict, StoreConfig, State]]] = reactive(list)

    def render(self):
        parts = list()
        for item in self.pairs_list:
            item: tuple[dict, dict, StoreConfig, State] = item
            thread, store, config, state = item
            default_color = default_style(state)
            text = Text(style=default_color)
            text.append(f'[{state.trade_broker_display}]{config.symbol} {config.name}\n')

            tags = list()
            prudent = '惜售' if state.plan.prudent else '超卖'
            tags.append(prudent)
            args = list()
            args.append('昨收')
            args.append('开盘')
            if config.base_price_last_buy:
                args.append('买回')
            if config.base_price_day_low:
                args.append('日低')
            tags.append(f'{state.bp_function}({",".join(args)})')
            text.append(f'策略: {"|".join(tags)}\n')
            state_bar = StoreBase.state_bar(
                thread_alive=not thread.get('dead'),
                config=config,
                state=state,
            )
            text.append(' '.join(elem.content for elem in state_bar) + '\n')
            parts.append(text)
        return Align.left(Group(*parts))


class StatusPanel(Widget):
    pairs_list: reactive[list[tuple[dict, dict, StoreConfig, State]]] = reactive(list)

    def render(self):
        parts = list()
        for item in self.pairs_list:
            item: tuple[dict, dict, StoreConfig, State] = item
            thread, store, config, state = item
            default_color = default_style(state)
            dt = f'{FormatTool.pretty_dt(state.quote_time, region=config.region, with_year=FormatTool)[:-10]}'
            latest = FormatTool.pretty_price(state.quote_latest_price, config=config)
            rate = FormatTool.factor_to_percent(state.quote_rate, fmt='{:+.2%}')

            color = 'green'
            if state.quote_latest_price and state.quote_pre_close:
                if state.quote_latest_price < state.quote_pre_close:
                    color = 'red'
            text = Text(style=default_color)
            text.append(f'[{config.region}]{config.symbol} {dt}\n')
            text.append(f'报价: ')
            text.append(f'{latest} {rate}\n', style=color)
            buff_bar = StoreBase.buff_bar(
                config=config,
                state=state,
                process_time=store.get('processTime'),
            )
            text.append('状态: ' + ''.join(elem.content for elem in buff_bar) + '\n')
            parts.append(text)
        return Align.left(Group(*parts))


class PlanPanel(Widget):
    pairs_list: reactive[list[tuple[dict, dict, StoreConfig, State]]] = reactive(list)

    @classmethod
    def cash_to_emoji(cls, n: int):
        icon = '🪙'
        if n >= 500:
            icon = '💰'
        if n >= 1000:
            icon = '💵'
        if n >= 2000:
            icon = '💎'
        return icon

    def render(self):
        parts = list()
        for item in self.pairs_list:
            item: tuple[dict, dict, StoreConfig, State] = item
            thread, store, config, state = item
            default_color = default_style(state)
            base_price = FormatTool.pretty_price(state.plan.base_price, config=config)
            profit_tool = Store.ProfitRowTool(config=config, state=state)
            text = Text(style=default_color)
            id_title = f'[{config.region}]{config.symbol}'
            if profit_tool.has_table and profit_tool.filled_level:
                total_rate = profit_tool.rows.row_by_level(profit_tool.filled_level).total_rate
                earning = profit_tool.earning_forecast(rate=total_rate)
                earning_text = FormatTool.pretty_price(earning, config=config, only_int=True)
                level = f'{profit_tool.filled_level}/{len(profit_tool.rows)}'
                text.append(f'{id_title}#{level} ')
                icon = self.cash_to_emoji(earning)
                text.append(f'预计{icon}{earning_text}\n', style='bright_green')
            else:
                text.append(id_title)
                if earning := state.plan.earning:
                    icon = self.cash_to_emoji(earning)
                    earning_text = FormatTool.pretty_price(earning, config=config, only_int=True)
                    earning_text = f' 套利{icon}{earning_text}'
                    text.append(f'{earning_text}', style='bright_green')
                    if rework_price := state.plan.rework_price:
                        rework_price = FormatTool.pretty_price(rework_price, config=config)
                        text.append(f' 🔁{rework_price}')
                    text.append(f'\n')
                else:
                    tp_text = ''
                    if state.ta_tumble_protect_flag:
                        tp_text += '⚠️MA'
                    if state.ta_tumble_protect_rsi:
                        tp_text += '🚫RSI'
                    text.append(f'{id_title} ⚓️{base_price}{tp_text}\n')

            sell_at = sell_percent = buy_at = buy_percent = None
            sell_percent_color = buy_percent_color = 'red'
            if profit_tool.has_table:
                sell_at = profit_tool.sell_at
                sell_percent = profit_tool.sell_percent
                if sell_percent is not None:
                    if sell_percent < 0.05:
                        sell_percent_color = 'yellow1'
                    if sell_percent < 0.01:
                        sell_percent_color = 'bright_green'
                buy_at = profit_tool.buy_at
                buy_percent = profit_tool.buy_percent
                if buy_percent is not None:
                    if buy_percent < 0.05:
                        buy_percent_color = 'yellow1'
                    if buy_percent < 0.01:
                        buy_percent_color = 'bright_green'
            sell_percent = FormatTool.factor_to_percent(sell_percent, fmt='{:.1%}')
            buy_percent = FormatTool.factor_to_percent(buy_percent, fmt='{:.1%}')
            text.append(f'卖出价: {FormatTool.pretty_price(sell_at, config=config)}')
            if profit_tool.sell_percent is not None:
                text.append(f' 距离')
                text.append(sell_percent, style=sell_percent_color)
            text.append('\n')
            text.append(f'买回价: {FormatTool.pretty_price(buy_at, config=config)}')
            if profit_tool.buy_percent is not None:
                text.append(f' 距离')
                text.append(buy_percent, style=buy_percent_color)
            text.append('\n')

            parts.append(text)
        return Align.left(Group(*parts))


class StoreScreen(Screen):
    def on_screen_resume(self):
        global PAIRS_LIST
        self.query_one(StorePanel).pairs_list = PAIRS_LIST
        self.query_one(StatusPanel).pairs_list = PAIRS_LIST
        self.query_one(PlanPanel).pairs_list = PAIRS_LIST

    def compose(self) -> ComposeResult:
        yield HodlHeader(name='HODL', show_clock=True)
        store = Vertical(classes="hPanel", id='ssStore')
        store.border_title = '持仓'
        store.mount(StorePanel())
        quote = Vertical(classes="hPanel", id='ssQuote')
        quote.border_title = '状态'
        quote.mount(StatusPanel())
        plan = Vertical(classes="hPanel", id='ssPlan')
        plan.border_title = '计划'
        plan.mount(PlanPanel())
        yield store
        yield quote
        yield plan
        yield Footer()


class OrderScreen(Screen):
    pairs_list: reactive[list[tuple[dict, dict, StoreConfig, State]]] = reactive(list)

    def on_screen_resume(self):
        global PAIRS_LIST
        self.pairs_list = PAIRS_LIST

    def watch_pairs_list(self, pairs: list[tuple[dict, dict, StoreConfig, State]]):
        orders: list[tuple[Order, State]] = list()
        try:
            table = self.query_one(DataTable)

            for thread, store, config, state in pairs:
                items = [(order, state,) for order in state.plan.orders]
                orders.extend(items)
            orders.sort(key=lambda i: i[0].create_timestamp, reverse=True)

            table.clear()
            for idx, item in enumerate(orders):
                order, state = item
                tz = TimeTools.region_to_tz(order.region)
                time = TimeTools.from_timestamp(order.create_timestamp, tz=tz)
                date = TimeTools.us_time_now(tz=tz)
                day = date.strftime('%Y-%m-%d')
                is_today = day == order.order_day
                style = 'white'
                if not is_today:
                    style = 'grey50'
                limit_price = '市价'
                if order.limit_price:
                    limit_price = FormatTool.pretty_usd(
                        order.limit_price,
                        currency=order.currency,
                        precision=order.precision,
                    )
                table.add_row(
                    Text(order.order_emoji, style=style),
                    Text(f'{time.strftime("%y-%m-%d")}T{time.strftime("%H:%M:%S")}', style=style),
                    Text(state.trade_broker_display, justify="left", style=style),
                    Text(state.name, justify="center", style=style),
                    Text(f'[{order.region}]{order.symbol}', justify="left", style=style),
                    Text(f'{order.direction}#{order.level}', justify="left", style=style),
                    Text(f'{limit_price}', justify="right", style=style),
                    Text(FormatTool.pretty_number(order.qty), justify="right", style=style),
                    Text(
                        f'{FormatTool.pretty_usd(order.avg_price, currency=order.currency, precision=order.precision)}',
                        justify="right", style=style),
                    Text(f'{FormatTool.pretty_number(order.filled_qty)}', justify="right", style=style),
                    height=1,
                )
            table.refresh()
        except NoMatches as ex:
            pass

    def compose(self) -> ComposeResult:
        yield HodlHeader(name='HODL', show_clock=True)
        table = DataTable(name='订单', zebra_stripes=True, show_cursor=False)
        table.add_columns(
            Text('#', style='grey66'),
            Text('时间', style='grey66'),
            Text('通道', style='grey66'),
            Text('名称', style='grey66'),
            Text('标的', style='grey66'),
            Text('方向', style='grey66'),
            Text('订单价', style='grey66'),
            Text('订单量', style='grey66'),
            Text('成交价', style='grey66'),
            Text('成交量', style='grey66'),
        )
        yield table
        yield Footer()


class EarningItem(Static):
    d: reactive[dict] = reactive(dict)

    def render(self):
        currency = self.d.get('currency', None)
        earning = self.d.get('earning', None)
        symbol = self.d.get('symbol', None)
        region = self.d.get('region', None)
        day = self.d.get('day', None)
        name = self.d.get('name', None)
        text = Text()
        text.append(f'{FormatTool.pretty_usd(earning, currency=currency, only_int=True)}\n', style='green')
        if region and symbol:
            text.append(f'[{region}]{symbol}\n')
        else:
            text.append(f'{name}{currency}\n')
        text.append(f'完成日期: {day}')
        return text


class EarningScreen(Screen):
    recent_earnings_list: reactive[list[dict]] = reactive(list)

    def compose(self) -> ComposeResult:
        global RECENT_EARNINGS_LIST
        yield HodlHeader(name='HODL', show_clock=True)
        with Container():
            with Grid(classes='earningGrid'):
                for d in RECENT_EARNINGS_LIST:
                    widget = EarningItem(classes='earningItem')
                    widget.d = d
                    yield widget
        yield Footer()

    def render(self):
        global RECENT_EARNINGS_LIST
        return f'{len(RECENT_EARNINGS_LIST)}'


class HODL(App):
    CSS_PATH = "../../hodl/css/tui.css"
    SCREENS = {
        "StoreScreen": StoreScreen(),
        "OrderScreen": OrderScreen(),
        "EarningScreen": EarningScreen(),
    }
    BINDINGS = [
        ("h", "home_page", "持仓"),
        ("o", "order_page", "订单"),
        ("e", "earning_page", "收益"),
        ("a", "auto_play", "滚动模式"),
        ("c", "view_config", "持仓配置"),
        Binding("q", "quit", "退出", priority=True),
    ]
    order_filled_dict: dict[str, bool] = dict()
    windows_notification_client = None
    auto_play_on = False

    def _notify_filled_msg(self, order: Order, state: State):
        try:
            if sys.platform != 'win32':
                return
            if self.windows_notification_client is None:
                from win10toast import ToastNotifier
                self.windows_notification_client = ToastNotifier()
            direction = order.direction
            price = FormatTool.pretty_usd(order.avg_price, currency=order.currency, precision=order.precision)
            qty = FormatTool.pretty_number(order.filled_qty)
            msg = f'🎉{state.full_name} {direction} {price}@{qty}已成交'
            args = dict(
                title='HODL',
                msg=msg,
                duration=8,
                threaded=False,
            )
            thread = threading.Thread(
                name=f'orderFilled:{order.unique_id}',
                daemon=True,
                target=self.windows_notification_client.show_toast,
                kwargs=args,
            )
            thread.start()
        except Exception as ex:
            pass

    def action_view_config(self):
        global PAIRS_LIST
        config_list = [item[2] for item in PAIRS_LIST]
        self.auto_play_on = False
        self.push_screen(StoreConfigIndexScreen(config_list))

    def action_home_page(self, switch=True):
        global PAIRS_LIST
        try:
            if switch:
                self.switch_screen('StoreScreen')
            else:
                self.query_one(StorePanel).pairs_list = PAIRS_LIST
                self.query_one(StatusPanel).pairs_list = PAIRS_LIST
                self.query_one(PlanPanel).pairs_list = PAIRS_LIST
        except NoMatches as ex:
            pass

    def action_order_page(self, switch=True):
        global PAIRS_LIST
        try:
            if switch:
                self.switch_screen('OrderScreen')
            else:
                screen = self.query_one(OrderScreen)
                screen.pairs_list = PAIRS_LIST
        except NoMatches as ex:
            pass

    def action_earning_page(self, switch=True):
        global RECENT_EARNINGS_LIST
        try:
            if switch:
                self.switch_screen('EarningScreen')
            else:
                screen = self.query_one(EarningScreen)
                screen.recent_earnings_list = RECENT_EARNINGS_LIST
        except NoMatches as ex:
            pass

    def action_auto_play(self):
        self.auto_play_on = not self.auto_play_on

    def on_mount(self) -> None:
        self.push_screen('StoreScreen')
        self.run_worker(self.state_worker())
        self.run_worker(self.earning_worker())
        self.run_worker(self.auto_play_worker())

    def compose(self) -> ComposeResult:
        yield HodlHeader(name='HODL', show_clock=True)
        yield Footer()

    async def state_worker(self):
        global PAIRS_LIST
        var = VariableTools()
        tui_config = var.tui_config
        session = httpx.AsyncClient(timeout=tui_config.period_seconds, http2=True, trust_env=False)
        while True:
            try:
                url = tui_config.manager_url
                if not url:
                    continue
                response = await session.get(url)
                d = response.json()
                resp_items = d.get('items', list())
                store_items = [item.get('store') for item in resp_items]
                thread_list = [StoreConfig(item.get('thread', dict())) for item in resp_items]
                config_list = [StoreConfig(item.get('config', dict())) for item in resp_items]
                status_list = [State(item.get('state', dict())) for item in store_items]
                pairs_list = list(zip(thread_list, store_items, config_list, status_list))
                PAIRS_LIST = pairs_list

                self.action_home_page(switch=False)
                self.action_order_page(switch=False)

                orders: list[tuple[Order, State]] = list()
                for thread, store, config, state in pairs_list:
                    items = [(order, state,) for order in state.plan.orders]
                    orders.extend(items)
                for item in orders:
                    order, state = item
                    if order.unique_id not in self.order_filled_dict:
                        self.order_filled_dict[order.unique_id] = order.is_filled
                    if order.is_filled and not self.order_filled_dict.get(order.unique_id):
                        self.order_filled_dict[order.unique_id] = order.is_filled
                        self._notify_filled_msg(order=order, state=state)
                if self.query(HodlHeaderTitle):
                    header_widget = self.query_one(HodlHeaderTitle)
                    header_widget.sub_text = ''
            except Exception as ex:
                if self.query(HodlHeaderTitle):
                    header_widget = self.query_one(HodlHeaderTitle)
                    header_widget.sub_text = '无连接'
            finally:
                await asyncio.sleep(tui_config.period_seconds)

    async def earning_worker(self):
        global RECENT_EARNINGS_LIST
        var = VariableTools()
        tui_config = var.tui_config
        session = httpx.AsyncClient(timeout=tui_config.period_seconds, http2=True, trust_env=False)
        while True:
            try:
                url = tui_config.earning_url
                if not url:
                    continue
                response = await session.get(url)
                d = response.json()
                recent_earnings: list[dict] = d.get('recentEarnings', list())
                RECENT_EARNINGS_LIST = recent_earnings
                self.action_earning_page(switch=False)
            except Exception as ex:
                pass
            finally:
                await asyncio.sleep(tui_config.period_seconds * 4)

    async def auto_play_worker(self):
        actions = [
            self.action_home_page,
            self.action_order_page,
            self.action_earning_page,
        ]
        idx = 0
        assert actions
        while True:
            if self.auto_play_on:
                func = actions[idx]
                func()
            await asyncio.sleep(16)
            idx += 1
            idx %= len(actions)


if __name__ == "__main__":
    StoreConfig.READONLY = True
    app = HODL()
    app.run()
