import asyncio
import httpx
from rich.align import Align
from rich.console import Group
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Header, Footer, DataTable, Static
from textual.binding import Binding
from hodl.store import *
from hodl.tools import *
from hodl.state import *
from hodl.store_base import *


PAIRS_LIST: list[tuple[dict, dict, StoreConfig, State]] = list()


def default_style(state: State):
    return 'white' if state.market_status == 'TRADING' else 'grey50'


class StorePanel(Widget):
    def render(self):
        parts = list()
        for thread, store, config, state in PAIRS_LIST:
            default_color = default_style(state)
            text = Text(style=default_color)
            text.append(f'[{state.trade_broker_display}]{config.symbol} {config.name}\n')

            tags = list()
            prudent = '惜售' if state.plan.prudent else '超卖'
            tags.append(prudent)
            tags.append('昨收')
            if config.get('basePriceLastBuy'):
                tags.append('买回')
            if config.get('basePriceDayLow'):
                tags.append('日低')
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
    def render(self):
        parts = list()
        for thread, store, config, state in PAIRS_LIST:
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
            text.append(f'{latest}({rate})\n', style=color)
            buff_bar = StoreBase.buff_bar(
                config=config,
                state=state,
                process_time=store.get('processTime'),
            )
            text.append('状态: ' + ''.join(elem.content for elem in buff_bar) + '\n')
            parts.append(text)
        return Align.left(Group(*parts))


class PlanPanel(Widget):
    def render(self):
        parts = list()
        for thread, store, config, state in PAIRS_LIST:
            default_color = default_style(state)
            base_price = FormatTool.pretty_price(state.plan.base_price, config=config)
            profit_tool = Store.ProfitRowTool(config=config, state=state)
            text = Text(style=default_color)
            if profit_tool.has_table and profit_tool.filled_level:
                total_rate = profit_tool.rows.row_by_level(profit_tool.filled_level).total_rate
                earning = profit_tool.earning_forecast(rate=total_rate)
                earning = FormatTool.pretty_price(earning, config=config, only_int=True)
                id_title = f'[{config.region}]{config.symbol}'
                level = f'{profit_tool.filled_level}/{len(profit_tool.rows)}'
                text.append(f'{id_title}#{level} 💰{earning}\n')
            else:
                text.append(f'[{config.region}]{config.symbol} ⚓️{base_price}\n')

            sell_at = sell_percent = buy_at = buy_percent = None
            if profit_tool.has_table:
                sell_at = profit_tool.sell_at
                sell_percent = profit_tool.sell_percent
                buy_at = profit_tool.buy_at
                buy_percent = profit_tool.buy_percent
            sell_percent = FormatTool.factor_to_percent(sell_percent, fmt='{:.1%}')
            buy_percent = FormatTool.factor_to_percent(buy_percent, fmt='{:.1%}')
            text.append(f'卖出价: {FormatTool.pretty_price(sell_at, config=config)}')
            if profit_tool.sell_percent is not None:
                text.append(f'(距离{sell_percent})')
            text.append('\n')
            text.append(f'买回价: {FormatTool.pretty_price(buy_at, config=config)}')
            if profit_tool.buy_percent is not None:
                text.append(f'(距离{buy_percent})')
            text.append('\n')

            parts.append(text)
        return Align.left(Group(*parts))


class StoreScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(name='HODL', show_clock=True)
        store = Vertical(classes="box", id='ssStore')
        store.border_title = '持仓'
        store.mount(StorePanel())
        quote = Vertical(classes="box", id='ssQuote')
        quote.border_title = '状态'
        quote.mount(StatusPanel())
        plan = Vertical(classes="box", id='ssPlan')
        plan.border_title = '计划'
        plan.mount(PlanPanel())
        yield store
        yield quote
        yield plan
        yield Footer()


class OrderScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(name='HODL', show_clock=True)
        table = DataTable(name='订单')
        table.add_columns(
            '#',
            '时间',
            '通道',
            '标的',
            '方向',
            '订单价',
            '订单量',
            '成交价',
            '成交量',
        )
        table.zebra_stripes = True
        table.cursor_type = 'row'
        yield table
        yield Footer()


class EarningScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(name='HODL', show_clock=True)
        earning = Static("收益", classes="box")
        yield earning
        yield Footer()


class HODL(App):
    CSS_PATH = "../../hodl/css/tui.css"
    SCREENS = {
        "StoreScreen": StoreScreen(),
        "OrderScreen": OrderScreen(),
        "EarningScreen": EarningScreen(),
    }
    BINDINGS = [
        ("h", "home_page()", "持仓"),
        ("o", "order_page()", "订单"),
        ("e", "earning_page()", "收益"),
        ("a", "auto_play", "滚动模式"),
        Binding("q", "quit", "退出", priority=True),
    ]

    def action_home_page(self, switch=True):
        try:
            if switch:
                self.switch_screen('StoreScreen')
            self.query_one(StorePanel).refresh(layout=True)
            self.query_one(StatusPanel).refresh(layout=True)
            self.query_one(PlanPanel).refresh(layout=True)
        except NoMatches as ex:
            pass

    def action_order_page(self, switch=True):
        global PAIRS_LIST
        if switch:
            self.switch_screen('OrderScreen')
        orders = list()
        try:
            screen: OrderScreen = self.SCREENS['OrderScreen']
            table = screen.query_one(DataTable)

            for thread, store, config, state in PAIRS_LIST:
                orders.extend(state.plan.orders)
            orders.sort(key=lambda i: i.create_timestamp, reverse=True)

            table.clear()
            for idx, order in enumerate(orders):
                tz = TimeTools.region_to_tz(order.region)
                time = TimeTools.from_timestamp(order.create_timestamp, tz=tz)
                limit_price = '市价'
                if order.limit_price:
                    limit_price = FormatTool.pretty_usd(
                        order.limit_price,
                        currency=order.currency,
                        precision=order.precision,
                    )
                table.add_row(
                    Text(order.order_emoji),
                    Text(f'{time.strftime("%y-%m-%d")}T{time.strftime("%H:%M:%S")}'),
                    Text(order.broker, justify="left"),
                    Text(f'[{order.region}]{order.symbol}', justify="left"),
                    Text(f'{order.direction}#{order.level}', justify="left"),
                    Text(f'{limit_price}', justify="right"),
                    Text(FormatTool.pretty_number(order.qty), justify="right"),
                    Text(
                        f'{FormatTool.pretty_usd(order.avg_price, currency=order.currency, precision=order.precision)}',
                        justify="right"),
                    Text(f'{FormatTool.pretty_number(order.filled_qty)}', justify="right"),
                )
            table.refresh(layout=True)
        except NoMatches as ex:
            pass

    def action_earning_page(self, switch=True):
        if switch:
            self.switch_screen('EarningScreen')

    def action_auto_play(self):
        pass

    def on_mount(self) -> None:
        self.push_screen('StoreScreen')
        self.run_worker(self.worker(), exclusive=True)

    def compose(self) -> ComposeResult:
        yield Header(name='HODL', show_clock=True)
        yield Footer()

    async def worker(self):
        global PAIRS_LIST
        var = VariableTools()
        tui_config = var.tui_config
        session = httpx.AsyncClient(timeout=tui_config.period_seconds, http2=True, trust_env=False)
        while True:
            try:
                url = tui_config.manager_url
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
            except Exception as ex:
                pass
            await asyncio.sleep(tui_config.period_seconds)


if __name__ == "__main__":
    app = HODL()
    app.run()
