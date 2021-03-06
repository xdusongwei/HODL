from os import environ
import asyncio
from collections import defaultdict
import httpx
environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
from pygame import mixer
from rich import box
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.console import Group
from rich.emoji import Emoji
from rich.columns import Columns
from rich.table import Table
from textual.app import App
from textual import events
from textual.widgets import Placeholder
from hodl.tools import *
from hodl.state import *
from hodl.store_base import StoreBase
from hodl.tools import FormatTool as FMT


class ConfigMixin:
    CONFIGS = VariableTools().tui_configs

    @classmethod
    def config(cls):
        timestamp = int(TimeTools.utc_now().timestamp())
        configs = ConfigMixin.CONFIGS
        offset = (timestamp // 16) % len(configs)
        config = configs[offset]
        return config


class DataMixin:
    STORE_ITEMS: dict = defaultdict(list)
    CONFIG_ITEMS: dict = defaultdict(list)
    THREAD_ITEMS: dict = defaultdict(list)
    PROFIT: dict = defaultdict(list)


class PlaceholderBase(Placeholder, ConfigMixin, DataMixin):
    pass


class StatusWidget(PlaceholderBase):
    def render(self):
        tui_config = self.config()
        border_style = tui_config.border_style
        store_items = self.STORE_ITEMS[id(tui_config)]
        config_items = self.CONFIG_ITEMS[id(tui_config)]
        thread_items = self.THREAD_ITEMS[id(tui_config)]
        cst_time = TimeTools.us_time_now(tz='Asia/Shanghai')
        if 9 <= cst_time.hour <= 15:
            tz_name = 'CST'
            time = cst_time
        else:
            tz_name = 'EDT'
            time = TimeTools.us_time_now()
        time = time.isoformat(timespec='milliseconds')
        time = time[2:-10]
        container = list()
        dt = Text(f"持仓(")
        dt.append(Text(f'{tz_name}: {time}', style="green"))
        dt.append(')')
        cross_mark = Emoji('cross_mark')
        check = Emoji('white_heavy_check_mark')
        no_entry = Emoji('no_entry')
        skull = Emoji('skull')
        plug = Emoji('electric_plug')
        money_bag = Emoji('money_bag')
        for store_dict, config_dict, thread_dict in zip(store_items, config_items, thread_items):
            state = store_dict.get('state')
            e = store_dict.get('exception')
            state = State(state)
            plan: Plan = state.plan
            config = StoreConfig(config_dict)
            symbol = config.symbol
            region = config.region

            default_style = 'white' if state.market_status == 'TRADING' else 'grey50'

            name = f' {state.name}' if state.name else ''
            title = f'[{region}]{symbol}{name}'
            text = Text(style=default_style)
            tags = list()
            prudent = '惜售' if plan.prudent else '超卖'
            if plan.price_rate != 1.0:
                prudent += f'({int(plan.price_rate * 100)}%)'
            tags.append(prudent)
            tags.append('昨收')
            if config.get('basePriceLastBuy'):
                tags.append('买回')
            if config.get('basePriceDayLow'):
                tags.append('日低')
            text.append(Text(f'策略: {"|".join(tags)}\n'))
            if config.enable:
                if thread_dict.get('dead'):
                    system_status = skull
                elif state.current == StoreBase.STATE_GET_OFF:
                    system_status = money_bag
                elif not state.is_plug_in:
                    system_status = plug
                elif state.current == StoreBase.STATE_TRADE:
                    system_status = check
                else:
                    system_status = cross_mark
            else:
                system_status = no_entry
            market_status = check if state.market_status == 'TRADING' else cross_mark
            text.append(Text(
                f'{system_status}系统  '
                f'{market_status}市场  '
                f'{check if state.quote_enable_trade else cross_mark}标的  '
                f'{cross_mark if state.risk_control_break else check}风控'
                f'\n'))
            if state.risk_control_break:
                text.append(Text(f'风控异常: {state.risk_control_detail}\n', style='red'))
            if e and e != state.risk_control_detail:
                text.append(Text(f'执行异常: {e}\n', style='red'))
            container.append(Text(title, style=default_style))
            container.append(text)

        return Panel(
            Align.left(Group(*container)),
            title=dt,
            border_style=border_style,
            box=box.ROUNDED,
            style=self.style,
            height=self.height,
        )


class QuoteWidget(PlaceholderBase):
    FLASH = False

    @classmethod
    def _color(cls, current, base):
        if current and base:
            return 'green' if current >= base else 'red'

    def render(self):
        tui_config = self.config()
        self.FLASH = TimeTools.us_time_now().second % 4
        config = self.config()
        border_style = config.border_style
        store_items = self.STORE_ITEMS[id(config)]
        config_items = self.CONFIG_ITEMS[id(config)]
        container = list()
        for store_dict, config_dict in zip(store_items, config_items):
            state = store_dict.get('state')
            state = State(state)
            plan: Plan = state.plan
            config = StoreConfig(config_dict)
            symbol = config.symbol
            latest_price = state.quote_latest_price
            region = config.region

            lock_position = ''
            if config.get('lockPosition'):
                lock_position = '🔒'

            rework_set = ''
            if state.plan.rework_price:
                rework_set = '🔁'

            battery = '🔋'
            chips = plan.total_chips
            diff = plan.total_volume_not_active(assert_zero=False)
            if chips and (chips - diff) >= 0:
                remain = chips - diff
                percent = int(remain / chips * 100)
                battery += f'{percent}%'
            else:
                battery += f'--'
            if not tui_config.display_chip_rate:
                battery = ''

            process_time_text = ''
            process_time = store_dict.get('processTime')
            if process_time:
                process_time = f'{int(process_time * 1000)}'
            else:
                process_time = '--'
            if tui_config.display_process_time:
                process_time_text = f'📶{process_time}ms'

            default_style = 'white' if state.market_status == 'TRADING' else 'grey50'

            title = f'[{region}]{symbol} {FMT.pretty_dt(state.quote_time, region=region, with_year=False)[:-10]}'
            rate = 0.0
            if state.quote_pre_close and latest_price:
                rate = round(latest_price / state.quote_pre_close * 100 - 100, 2)
            text = Text(style=default_style)
            text.append(
                '最新: '
            )
            text.append(
                f'{FMT.pretty_price(latest_price, config=config)}({rate:+.2f}%)\n',
                style=self._color(latest_price, state.quote_pre_close),
            )
            text.append(
                f'状态: {rework_set}{lock_position}{battery}{process_time_text}\n',
            )
            container.append(Text(title, style=default_style))
            container.append(text)
        return Panel(
            Align.left(Group(*container)),
            title=f'状态({len(store_items)})',
            border_style=border_style,
            box=box.ROUNDED,
            style=self.style,
            height=self.height,
        )


class OrderWidget(PlaceholderBase):
    def render(self):
        config = self.config()
        border_style = config.border_style
        items = self.STORE_ITEMS[id(config)]
        orders = list()
        for store_dict in items:
            state = store_dict.get('state')
            state = State(state)
            orders.extend(state.plan.orders)
        orders = sorted(orders, key=lambda order: order.create_timestamp, reverse=True)

        table = Table(padding=(0, 1, 0, 1,), border_style=border_style)

        table.add_column(f'{len(orders)}', justify="right", style="grey66", no_wrap=True, width=2)
        table.add_column("时间", justify="right", style="grey66", no_wrap=True)
        table.add_column("标的", justify="left")
        table.add_column("方向", justify="left", style="grey66")
        table.add_column("订单价", justify="right", style="green")
        table.add_column("订单量", justify="right", style="grey66")
        table.add_column("成交价", justify="right", style="green")
        table.add_column("成交量", justify="right", style="grey66")
        table.add_column("标志", justify="right", style="red")

        waiting = Emoji('hourglass_not_done')
        error = Emoji('cross_mark')
        check = Emoji('white_heavy_check_mark')
        saved = Emoji('floppy_disk')

        for order in orders:
            flags = '{}{}'.format(
                '止' if order.has_error else '',
                '撤' if order.is_canceled else '',
            )
            tz = TimeTools.region_to_tz(region=order.region)
            date = TimeTools.us_time_now(tz=tz)
            day = date.strftime('%Y-%m-%d')
            time = TimeTools.from_timestamp(order.create_timestamp, tz=tz)
            is_today = day == order.order_day
            style = 'grey66'
            if not is_today:
                icon = saved
                style = 'grey50'
            elif order.is_filled:
                icon = check
            elif order.is_waiting_filling:
                icon = waiting
            elif flags:
                icon = error
            else:
                icon = check

            symbol = order.symbol
            table.add_row(
                Text(text=f'{icon}'),
                Text(text=f'{time.strftime("%y-%m-%d")}\n{time.strftime("%H:%M:%S")}', style=style),
                Text(text=f'[{order.region}]{symbol}', style=style),
                Text(text=f'{order.direction}.{order.level}', style=style),
                Text(text=FMT.pretty_usd(order.limit_price, currency=order.currency, region=order.region)),
                Text(text=FMT.pretty_number(order.qty), style=style),
                Text(text=FMT.pretty_usd(order.avg_price, currency=order.currency, region=order.region)),
                Text(text=FMT.pretty_number(order.filled_qty), style=style),
                Text(text=flags),
            )
        return table


class ProfitWidget(PlaceholderBase):
    def render(self):
        config = self.config()
        items = self.PROFIT[id(config)]
        icons = {
            'little': '🪙',
            'notBad': Emoji('dollar_banknote'),
            'huge': Emoji('money_bag'),
            'super': Emoji('gem_stone'),
        }
        lines = list()
        for item in items:
            day, symbol, earning, region = item
            earning = int(earning)
            if earning >= 8000:
                icon = icons['super']
            elif earning >= 4000:
                icon = icons['huge']
            elif earning > 1000:
                icon = icons['notBad']
            else:
                icon = icons['little']
            text = Text(
                f'{icon} {day[2:]} {FMT.pretty_usd(earning, only_int=True, region=region)}@{symbol}',
                style='green',
            )
            lines.append(text)
        total_earning_usd = FMT.pretty_usd(sum(item[2] for item in items if item[3] == 'US'), only_int=True, unit='$')
        total_earning_cny = FMT.pretty_usd(sum(item[2] for item in items if item[3] == 'CN'), only_int=True, unit='¥')
        return Panel(
            Columns(lines, column_first=False, width=config.profit_width, padding=(0, 0, 0, 3, )),
            title=f'{config.name}({total_earning_usd}, {total_earning_cny})',
            border_style=config.border_style,
            box=box.ROUNDED,
            style=self.style,
            height=self.height,
        )


class GridApp(App, ConfigMixin, DataMixin):
    SESSION: httpx.AsyncClient = None
    MARKET_STATUS = 'UNKNOWN'
    ENABLE_AUDIO = False

    @classmethod
    def _init_bgm(cls):
        try:
            mixer.init()
            GridApp.ENABLE_AUDIO = True
            mixer.music.set_volume(0.5)
        except Exception:
            GridApp.ENABLE_AUDIO = False

    @classmethod
    def _set_up_bgm(cls, path):
        if not cls.ENABLE_AUDIO:
            return
        if path:
            path = LocateTools.locate_file(path)
            mixer.music.load(path)
            mixer.music.play(loops=-1)
        else:
            mixer.music.unload()

    @classmethod
    async def request_manager_api(cls, config: TuiConfig):
        try:
            url = config.manager_url
            response = await cls.SESSION.get(url)
            d = response.json()
            resp_items = d.get('items', list())
            store_items = [item.get('store') for item in resp_items]
            cls.STORE_ITEMS[id(config)] = store_items
            cls.CONFIG_ITEMS[id(config)] = [item.get('config', dict()) for item in resp_items]
            cls.THREAD_ITEMS[id(config)] = [item.get('thread', dict()) for item in resp_items]
            status_list = [State(item.get('state', dict())) for item in store_items]
            if any(1 for state in status_list
                   if state.market_status == 'TRADING' and state.current != StoreBase.STATE_GET_OFF):
                new_market_status = 'CASINO'
            else:
                new_market_status = 'SLEEP'
            if cls.MARKET_STATUS != new_market_status:
                cls.MARKET_STATUS = new_market_status
                if new_market_status == 'CASINO':
                    cls._set_up_bgm(path=config.trading_sound)
                else:
                    cls._set_up_bgm(path=config.sleep_sound)
        except Exception:
            pass

    @classmethod
    async def request_profit_api(cls, config: TuiConfig):
        profit = list()
        try:
            url = config.profit_url
            response = await cls.SESSION.get(url)
            text = response.text
            lines = text.split('\n')
            for line in lines:
                if not line:
                    continue
                parts = line.split(',')
                day, symbol, earning, region = parts
                day: str = day.strip('" ')
                symbol: str = symbol.strip('" ')
                earning: str = earning.strip('" ')
                region: str = region.strip('" ')
                profit.append((day, symbol, int(earning), region))
            cls.PROFIT[id(config)] = profit
        except Exception:
            pass

    @classmethod
    async def fetch_state(cls):
        if not cls.SESSION:
            cls.SESSION = httpx.AsyncClient(timeout=4, http2=True, trust_env=False)
        for config in cls.CONFIGS:
            asyncio.create_task(cls.request_manager_api(config))

    @classmethod
    async def fetch_earning(cls):
        if not cls.SESSION:
            cls.SESSION = httpx.AsyncClient(timeout=4, http2=True, trust_env=False)
        for config in cls.CONFIGS:
            asyncio.create_task(cls.request_profit_api(config))

    async def on_load(self, event: events.Load) -> None:
        await self.bind("q", "quit", "Quit")
        await self.bind("m", "mute", "Mute")

    async def action_mute(self) -> None:
        if not GridApp.ENABLE_AUDIO:
            return
        volume = mixer.music.get_volume()
        if volume:
            mixer.music.set_volume(0.0)
        else:
            mixer.music.set_volume(0.5)

    async def on_shutdown_request(self, event: events.ShutdownRequest) -> None:
        if GridApp.SESSION:
            await GridApp.SESSION.aclose()
            GridApp.SESSION = None

    async def on_mount(self) -> None:
        """Make a simple grid arrangement."""

        grid = await self.view.dock_grid(edge="left", name="left")

        grid.add_column(fraction=3, name="left", min_size=20)
        grid.add_column(fraction=3, name="center")
        grid.add_column(fraction=6, name="right")

        grid.add_row(fraction=1, name="top", min_size=2)
        grid.add_row(fraction=1, name="middle")
        grid.add_row(fraction=1, name="bottom")

        grid.add_areas(
            area1="left,top-start|middle-end",
            area2="center,top-start|middle-end",
            area3="right,top-start|bottom-end",
            area4="left-start|center-end,bottom",
        )

        status_widget = StatusWidget(name="状态")
        quote_widget = QuoteWidget(name="行情")
        order_widget = OrderWidget(name="订单")
        profit_widget = ProfitWidget(name="历史收益")

        grid.place(
            area1=status_widget,
            area2=quote_widget,
            area3=order_widget,
            area4=profit_widget,
        )
        self.set_interval(4, self.fetch_state, name='fetch_state')
        self.set_interval(15, self.fetch_earning, name='fetch_earning')
        self.set_interval(0.5, status_widget.refresh)
        self.set_interval(2, quote_widget.refresh)
        self.set_interval(2, order_widget.refresh)
        self.set_interval(2, profit_widget.refresh)
        self._init_bgm()


GridApp.run(title="TUI")
