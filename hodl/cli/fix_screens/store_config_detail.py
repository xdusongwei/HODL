from rich.text import Text
from textual.reactive import reactive
from textual.app import ComposeResult
from textual.containers import VerticalScroll, Container
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Header, Footer, ListView, ListItem, Label, Input, Button, Checkbox, ContentSwitcher, \
    TabbedContent, TabPane
from textual.binding import Binding
from hodl.tools import *


class FormItem(Widget):
    DEFAULT_CSS = """
        FormItem {
            layout: vertical;
            min-width: 24;
            height: auto;
        }

        .formField {
            layout: horizontal;
            height: 3;
            min-width: 24;
        }

        .formLabel {
            content-align: right middle;
            padding: 1 1;
            width: 25%;
        }

        .formValue {
            width: 55%;
        }
        """

    def __init__(self, label: str, widget: Widget, desc: str = None):
        super().__init__()
        text = Text(label)
        if desc:
            text.append('\n')
            text.append(desc, style='gray50')
        self.label = Label(text, classes='formLabel')
        self.widget = widget

    def compose(self) -> ComposeResult:
        with Container(classes='formField'):
            yield self.label
            yield Container(self.widget, classes='formValue')


class StoreConfigScreen(Screen):
    config = reactive[StoreConfig](None)

    BINDINGS = [
        Binding("b", "back", "返回"),
    ]

    def action_back(self):
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.query_one(ContentSwitcher).current = event.button.id

    def compose(self) -> ComposeResult:
        config: StoreConfig = self.config
        yield Header(show_clock=True)
        yield Footer()
        with VerticalScroll():
            with TabbedContent():
                with TabPane("基本"):
                    yield FormItem(
                        'group',
                        Input(value=config.group, disabled=True),
                        desc='分组编号',
                    )
                    yield FormItem(
                        'broker',
                        Input(value=config.broker, disabled=True),
                        desc='券商通道',
                    )
                    yield FormItem(
                        'region',
                        Input(value=config.region, disabled=True),
                        desc='标的地区',
                    )
                    yield FormItem(
                        'symbol',
                        Input(value=config.symbol, disabled=True),
                        desc='标的',
                    )
                    yield FormItem(
                        'name',
                        Input(value=config.name, disabled=True),
                        desc='自定义名称',
                    )
                    yield FormItem(
                        'trade_type',
                        Input(value=config.trade_type, disabled=True),
                        desc='交易品种',
                    )
                    yield FormItem(
                        'currency',
                        Input(value=config.currency, disabled=True),
                        desc='交易币种',
                    )
                    yield FormItem(
                        'enable',
                        Checkbox('', config.enable, disabled=True),
                        desc='使能开关',
                    )
                    yield FormItem(
                        'visible',
                        Checkbox('', config.visible, disabled=True),
                        desc='可见',
                    )
                    yield FormItem(
                        'lock_position',
                        Checkbox('', config.lock_position, disabled=True),
                        desc='严格核算持仓股数',
                    )
                    yield FormItem(
                        'max_shares',
                        Input(value=f'{config.max_shares}股', disabled=True),
                        desc='可操作股数',
                    )

                    yield FormItem(
                        'sleep_mode',
                        Checkbox('', config.sleep_mode, disabled=True),
                        desc='非交易时段减少工作量',
                    )
                with TabPane("格式"):
                    yield FormItem(
                        'precision',
                        Input(value=f'{config.precision}位', disabled=True),
                        desc='股价小数精度',
                    )
                    yield FormItem(
                        'shares_per_unit',
                        Input(value=f'一手{config.shares_per_unit}股', disabled=True),
                        desc='一手股数',
                    )
                    yield FormItem(
                        'legal_rate_daily',
                        Input(value=f'{FormatTool.factor_to_percent(config.legal_rate_daily)}', disabled=True),
                        desc='标的每日涨跌幅限制',
                    )
                    yield FormItem(
                        'buy_spread_rate',
                        Input(value=f'{FormatTool.factor_to_percent(config.buy_spread_rate, fmt="{:.2%}")}',
                              disabled=True),
                        desc='买入需要的点差,按成交价比例扣除',
                    )
                    yield FormItem(
                        'sell_spread_rate',
                        Input(value=f'{FormatTool.factor_to_percent(config.sell_spread_rate, fmt="{:.2%}")}',
                              disabled=True),
                        desc='卖出需要的点差,按成交价比例扣除',
                    )
                with TabPane("策略"):
                    yield FormItem(
                        'trade_strategy',
                        Input(value=config.trade_strategy, disabled=True),
                        desc='交易策略',
                    )
                    yield FormItem(
                        'factor_fear_and_greed',
                        Input(value=config.factor_fear_and_greed, disabled=True),
                        desc='指定专门的恐贪因子类型',
                    )
                    yield FormItem(
                        'cost_price',
                        Input(value=f'{FormatTool.pretty_price(config.cost_price, config=config)}',
                              disabled=True),
                        desc='自动选择恐贪因子类型的成本价格',
                    )
                    yield FormItem(
                        'factor_fear_rate_limit',
                        Input(value=f'{FormatTool.factor_to_percent(config.factor_fear_rate_limit)}',
                              disabled=True),
                        desc='自动恐贪因子中恐慌幅度阈值',
                    )
                    yield FormItem(
                        'factor_greed_rate_limit',
                        Input(value=f'{FormatTool.factor_to_percent(config.factor_greed_rate_limit)}',
                              disabled=True),
                        desc='自动恐贪因子中贪婪幅度阈值',
                    )
                    yield FormItem(
                        'price_rate',
                        Input(value=f'{FormatTool.factor_to_percent(config.price_rate)}', disabled=True),
                        desc='控制因子表的幅度',
                    )
                    yield FormItem(
                        'rework_level',
                        Input(value=f'{config.rework_level}', disabled=True),
                        desc='当日套利后,重新工作需要的计划等级',
                    )
                    yield FormItem(
                        'market_price_rate',
                        Input(value=f'{FormatTool.factor_to_percent(config.market_price_rate, fmt="{:.2%}")}',
                              disabled=True),
                        desc='触发市价单需要的报价偏离幅度',
                    )
                    yield FormItem(
                        'buy_order_rate',
                        Input(value=f'{FormatTool.factor_to_percent(config.buy_order_rate, fmt="{:.2%}")}',
                              disabled=True),
                        desc='下达买入订单需要的价格接近幅度',
                    )
                    yield FormItem(
                        'sell_order_rate',
                        Input(value=f'{FormatTool.factor_to_percent(config.sell_order_rate, fmt="{:.2%}")}',
                              disabled=True),
                        desc='下达卖出订单需要的价格接近幅度',
                    )
                    yield FormItem(
                        'base_price_last_buy',
                        Checkbox('', config.base_price_last_buy, disabled=True),
                        desc='上次买回价作为基准价格',
                    )
                    yield FormItem(
                        'base_price_using_broker',
                        Checkbox('', config.base_price_isolated, disabled=True),
                        desc='是否只使用单独的买回参考价格',
                    )
                    yield FormItem(
                        'base_price_last_buy_days',
                        Input(value=f'{config.base_price_last_buy_days}天', disabled=True),
                        desc='上次买回价可作用的自然天数',
                    )
                    yield FormItem(
                        'base_price_day_low',
                        Checkbox('', config.base_price_day_low, disabled=True),
                        desc='当日最低价作为基准价格',
                    )
                with TabPane("保护"):
                    yield FormItem(
                        'base_price_tumble_protect',
                        Checkbox('', config.base_price_tumble_protect, disabled=True),
                        desc='MA暴跌保护开关',
                    )
                    yield FormItem(
                        'tumble_protect_day_range',
                        Input(value=f'{config.tumble_protect_day_range}天', disabled=True),
                        desc='MA暴跌保护监控的近几天历史报价',
                    )
                    yield FormItem(
                        'tumble_protect_day_range',
                        Input(value=f'{config.tumble_protect_sample_range}天', disabled=True),
                        desc='MA暴跌保护历史最低价的样本范围',
                    )
                    yield FormItem(
                        'vix_tumble_protect',
                        Input(value=f'{FormatTool.pretty_number(config.vix_tumble_protect)}', disabled=True),
                        desc='VIX暴跌保护触发的上限值',
                    )
                    yield FormItem(
                        'tumble_protect_rsi',
                        Checkbox('', config.tumble_protect_rsi, disabled=True),
                        desc='RSI暴跌保护开关',
                    )
                    yield FormItem(
                        'tumble_protect_rsi_period',
                        Input(value=f'{config.tumble_protect_rsi_period}天', disabled=True),
                        desc='RSI计算周期',
                    )
                    yield FormItem(
                        'tumble_protect_rsi_lock_limit',
                        Input(value=f'{FormatTool.pretty_number(config.tumble_protect_rsi_lock_limit)}', disabled=True),
                        desc='RSI暴跌保护触发的RSI下限值',
                    )
                    yield FormItem(
                        'tumble_protect_rsi_unlock_limit',
                        Input(value=f'{FormatTool.pretty_number(config.tumble_protect_rsi_unlock_limit)}',
                              disabled=True),
                        desc='RSI暴跌保护触发后的RSI解锁上限值',
                    )
                    yield FormItem(
                        'tumble_protect_rsi_warning_limit',
                        Input(value=f'{FormatTool.pretty_number(config.tumble_protect_rsi_warning_limit)}',
                              disabled=True),
                        desc='RSI预警的下限值',
                    )
                with TabPane("文件"):
                    yield FormItem(
                        'state_file_path',
                        Input(value=config.state_file_path, disabled=True),
                        desc='状态文件的位置',
                    )
                    yield FormItem(
                        'state_archive_folder',
                        Input(value=config.state_archive_folder, disabled=True),
                        desc='按天归档备份的状态文件目录',
                    )


class StoreConfigIndexScreen(Screen):
    DEFAULT_CSS = """
            StoreConfigIndexScreen {
                align: center middle;
            }
            
            .indexListView {
                width: 45;
                height: auto;
                margin: 2 2;
            }
            
            .indexLabel {
                padding: 1 2;
                width: 100%;
            }
            """

    BINDINGS = [
        Binding("b", "back", "返回"),
    ]

    def __init__(self, config_list: list[StoreConfig] = None):
        super().__init__()
        self.config_list = config_list

    def action_back(self):
        self.app.pop_screen()

    class ConfigListItem(ListItem):
        config = reactive[StoreConfig](None)

    def compose(self) -> ComposeResult:
        if self.config_list is None:
            var = VariableTools()
            config_list = var.store_config_list()
        else:
            config_list = self.config_list

        yield Header(show_clock=True)

        items = [
            StoreConfigIndexScreen.ConfigListItem(
                Label(
                    f'{config.full_name}',
                    classes='indexLabel',
                ),
            ) for idx, config in enumerate(config_list)
        ]
        for idx, config in enumerate(config_list):
            items[idx].config = config

        menu = ListView(
            *items,
            initial_index=None,
            classes='indexListView',
        )
        yield menu
        yield Footer()

    def on_list_view_selected(self, message: ListView.Selected):
        if message.item is None:
            return
        elem: StoreConfigIndexScreen.ConfigListItem = message.item
        screen = StoreConfigScreen()
        screen.config = elem.config
        self.app.push_screen(screen)


__all__ = ['StoreConfigScreen', 'StoreConfigIndexScreen', ]
