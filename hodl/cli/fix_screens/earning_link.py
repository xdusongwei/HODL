import re
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Header, Footer, Select, Input, Button
from hodl.tools import *
from hodl.broker import *
from hodl.storage import *


class Selected(Message):
    def __init__(self, elem_id: str) -> None:
        self.elem_id = elem_id
        super().__init__()


class EarningLinkScreen(Screen):
    BINDINGS = [
        Binding("b", "back", "返回"),
    ]

    @classmethod
    def all_broker_types(cls):
        return BrokerApiBase.all_brokers_type()

    def action_back(self):
        self.app.pop_screen()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Select(
            [
                (f'{broker_type.BROKER_DISPLAY}({broker_type.BROKER_NAME})', broker_type.BROKER_NAME, )
                for broker_type in self.all_broker_types()
            ],
            prompt='交易通道',
            id='brokerSelect',
            allow_blank=False,
        )
        yield Input(placeholder='标的代码', id='symbolInput')
        yield Select(
            [
                ('US', 'US'),
                ('HK', 'HK'),
                ('CN', 'CN'),
            ],
            prompt='所属地区',
            id='regionSelect',
            allow_blank=False,
        )
        yield Input(placeholder='套利日期，格式为YYYY-mm-dd', id='dayInput')
        yield Input(placeholder='获利币种，例如USD, CNY, HKD', id='currencyInput')
        yield Input(placeholder='套利金额', id='amountInput')
        with Center():
            yield Button.error(label='确认', disabled=True, id='confirmButton', classes='confirmButton')
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
        region: Select = self.query_one('#regionSelect')
        day: Input = self.query_one('#dayInput')
        currency_input: Select = self.query_one('#currencyInput')
        amount_input: Input = self.query_one('#amountInput')

        var = VariableTools()
        if not var.db_path:
            self.app.exit(message=f'没有配置数据库, 不能补录收益信息')
            return
        db = LocalDb(var.db_path)

        currency: str = str(currency_input.value)
        order_day: int = int(day.value.replace('-', ''))
        amount: int = int(amount_input.value)
        unit = FormatTool.currency_to_unit(currency=currency)
        create_time = int(TimeTools.us_time_now().timestamp())

        earning = EarningRow(
            day=order_day,
            symbol=symbol.value,
            currency=currency,
            days=None,
            amount=amount,
            unit=unit,
            region=region.value,
            broker=broker.value,
            buyback_price=None,
            max_level=0,
            state_version=None,
            create_time=create_time,
        )
        earning.save(con=db.conn)

        earning_detail = (f'\n\n代码:{symbol.value}\n通道:{broker.value}\n区域:{region.value}\n日期:{order_day}\n'
                          f'币种:{currency}\n金额:{amount}\n单位:{unit}\n创建时间:{create_time}\n')
        self.app.exit(message=f'执行完成:\n{earning_detail}')

    def check_form(self):
        broker: Select = self.query_one('#brokerSelect')
        symbol: Input = self.query_one('#symbolInput')
        region: Select = self.query_one('#regionSelect')
        day: Input = self.query_one('#dayInput')
        currency_input: Select = self.query_one('#currencyInput')
        amount_input: Input = self.query_one('#amountInput')
        if broker.value is None:
            return False
        if not symbol.value or not re.match(r'^[a-zA-Z0-9.-]+$', symbol.value):
            return False
        if not day.value or not re.match(r'^\d{4}-\d{2}-\d{2}$', day.value):
            return False
        if region.value is None:
            return False
        if currency_input.value is None:
            return False
        if not amount_input.value or not re.match(r'^\d+$', amount_input.value):
            return False
        return True


__all__ = ['EarningLinkScreen', ]
