import re
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Header, Footer, ListView, ListItem, Label, Select, Input, Button
from textual.binding import Binding
from hodl.tools import *
from hodl.broker import BROKERS
from hodl.state import *


class Selected(Message):
    def __init__(self, elem_id: str) -> None:
        self.elem_id = elem_id
        super().__init__()


class OrderLinkScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Select(
            [(f'{broker_type.BROKER_DISPLAY}({broker_type.BROKER_NAME})', broker_type.BROKER_NAME, ) for broker_type in BROKERS],
            prompt='交易通道',
            id='brokerSelect',
            allow_blank=False,
        )
        yield Input(placeholder='标的代码', id='symbolInput')
        yield Input(placeholder='Level', id='levelInput')
        yield Input(placeholder='订单日期，格式为YYYY-mm-dd', id='dayInput')
        yield Select([('卖', 'SELL'), ('买', 'BUY'), ], prompt='交易方向', id='directionSelect', allow_blank=False)
        yield Input(placeholder='订单号/委托号/合同号', id='idInput')
        yield Input(placeholder='订单交易数量', id='qtyInput')
        yield Input(placeholder='(可选)订单已成交数量', id='filledInput')
        yield Input(placeholder='(可选)订单限价，不填写代表市价单', id='limitPriceInput')
        yield Input(placeholder='(可选)订单已成交均价', id='avgPriceInput')
        with Horizontal():
            yield Button.error(label='确认', disabled=True, id='confirmButton', classes='confirmButton')
            yield Button.error(label='确认2', disabled=True, id='confirmButton2', classes='confirmButton')
        yield Footer()

    def on_input_changed(self, message):
        button = self.query_one('#confirmButton')
        button.disabled = not self.check_form()

    def on_select_changed(self, message):
        button = self.query_one('#confirmButton')
        button.disabled = not self.check_form()

    def on_button_pressed(self, message: Button.Pressed):
        if message.button.id != 'confirmButton':
            return
        broker: Select = self.query_one('#brokerSelect')
        symbol: Input = self.query_one('#symbolInput')
        level: Input = self.query_one('#levelInput')
        day: Input = self.query_one('#dayInput')
        direction: Select = self.query_one('#directionSelect')
        order_id: Input = self.query_one('#idInput')
        qty: Input = self.query_one('#qtyInput')
        filled: Input = self.query_one('#filledInput')
        avg: Input = self.query_one('#avgPriceInput')
        limit: Input = self.query_one('#limitPriceInput')

        var = VariableTools()
        config = var.store_configs_by_group()[(broker.value, symbol.value, )]
        assert config

        level: int = int(level.value)
        order_day: str = str(day.value)
        direction: str = str(direction.value)
        qty: int = int(qty.value)
        order_id: int | str = str(order_id.value)

        if filled.value:
            filled_qty = int(filled.value)
        else:
            filled_qty = 0
        if avg.value:
            avg_price = float(avg.value)
        else:
            avg_price = 0
        if limit.value:
            limit_price = float(limit.value)
        else:
            limit_price = None

        for broker_type in BROKERS:
            if broker_type.BROKER_NAME != config.broker:
                continue
            order_id = broker_type.ORDER_ID_TYPE(order_id)

        order = Order.new_config_order(
            store_config=config,
            level=level,
            direction=direction,
            qty=qty,
            limit_price=limit_price,
            create_timestamp=FormatTool.adjust_precision(TimeTools.us_time_now().timestamp(), precision=3),
            order_day=order_day,
        )
        if order.is_buy:
            order.config_spread_rate = config.buy_spread_rate
        if order.is_sell:
            order.config_spread_rate = config.sell_spread_rate
        order.order_id = order_id
        order.filled_qty = filled_qty
        order.avg_price = avg_price

        state_file = config.state_file_path
        assert state_file

        with open(state_file, 'r', encoding='utf8') as f:
            text = f.read()
        state = FormatTool.json_loads(text)
        state = State(state)
        state.plan.append_order(order)

        config_text = FormatTool.json_dumps(state)
        with open(state_file, 'w', encoding='utf8') as f:
            f.write(config_text)

        self.app.exit(message=f'执行完成\n{config_text}')


    def check_form(self):
        broker: Select = self.query_one('#brokerSelect')
        symbol: Input = self.query_one('#symbolInput')
        level: Input = self.query_one('#levelInput')
        day: Input = self.query_one('#dayInput')
        direction: Select = self.query_one('#directionSelect')
        order_id: Input = self.query_one('#idInput')
        qty: Input = self.query_one('#qtyInput')
        filled: Input = self.query_one('#filledInput')
        avg: Input = self.query_one('#avgPriceInput')
        limit: Input = self.query_one('#limitPriceInput')
        if broker.value is None:
            return False
        if not symbol.value or not re.match(r'^[a-zA-Z0-9.-]+$', symbol.value):
            return False
        if not level.value or not re.match(r'^\d+$', level.value):
            return False
        if not day.value or not re.match(r'^\d{4}-\d{2}-\d{2}$', day.value):
            return False
        if direction.value is None:
            return False
        if not order_id.value or not re.match(r'^[a-zA-Z0-9.-]+$', order_id.value):
            return False
        if not qty.value or not re.match(r'^\d+$', qty.value):
            return False
        if filled.value and not re.match(r'^\d+$', filled.value):
            return False
        if avg.value and not re.match(r'^\d+(\.\d+)?$', avg.value):
            return False
        if limit.value and not re.match(r'^\d+(\.\d+)?$', limit.value):
            return False
        return True


class IndexScreen(Screen):
    BINDINGS = [
        Binding("1", "choose(1)", "选1"),
        Binding("2", "choose(2)", "选2"),
        Binding("3", "choose(3)", "选3"),
        Binding("4", "choose(4)", "选4"),
    ]

    def action_choose(self, i: int):
        self.query_one(ListView).index = i - 1

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        menu = ListView(
            ListItem(Label("1.补录订单信息", classes='indexLabel'), id='indexMenuOrderLink'),
            ListItem(Label("2.补录收益信息", classes='indexLabel'), id='indexMenuEarningLink'),
            ListItem(Label("3.刷新收益json文件", classes='indexLabel'), id='indexMenuRefreshEarnings'),
            ListItem(Label("4.弹射持仓", classes='indexLabel'), id='indexMenuShootOff'),
            initial_index=None,
            classes='indexListView',
        )
        yield menu
        yield Footer()

    def on_list_view_selected(self, message: ListView.Selected):
        if message.item:
            elem_id = message.item.id
            match elem_id:
                case 'indexMenuOrderLink':
                    pass
                    self.app.push_screen('OrderLinkScreen')
                case _:
                    pass


class HodlFixTools(App):
    CSS_PATH = "../../hodl/css/fix_tools.css"

    SCREENS = {
        "IndexScreen": IndexScreen(),
        "OrderLinkScreen": OrderLinkScreen(),
    }

    BINDINGS = [
        Binding("q", "quit", "退出"),
    ]

    def on_mount(self) -> None:
        self.push_screen('IndexScreen')

    def compose(self) -> ComposeResult:
        self.title = 'HODL - 修复工具'
        yield Header(show_clock=True)
        yield Footer()


if __name__ == "__main__":
    app = HodlFixTools()
    app.run()
