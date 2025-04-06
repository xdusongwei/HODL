"""
可以通过命令启动这个管理模块, 来补录订单和收益.
"""
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, ListView, ListItem, Label
from textual.binding import Binding
from hodl.bot import *
from hodl.tools import *
from hodl.cli.fix_screens.order_link import *
from hodl.cli.fix_screens.store_config_detail import *
from hodl.cli.fix_screens.earning_link import *


class IndexScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        menu = ListView(
            ListItem(Label("1.补录订单信息", classes='indexLabel'), id='indexMenuOrderLink'),
            ListItem(Label("2.补录收益信息", classes='indexLabel'), id='indexMenuEarningLink'),
            ListItem(Label("3.生成电报机器人指令列表", classes='indexLabel'), id='indexPrintTgCmdList'),
            ListItem(Label("0.查看持仓设定", classes='indexLabel'), id='indexMenuStoreConfig'),
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
                    self.app.push_screen(OrderLinkScreen())
                case 'indexMenuStoreConfig':
                    self.app.push_screen(StoreConfigIndexScreen())
                case 'indexMenuEarningLink':
                    self.app.push_screen(EarningLinkScreen())
                case 'indexPrintTgCmdList':
                    self.print_tg_cmd_list()
                case _:
                    pass

    def print_tg_cmd_list(self):
        conversation_types = TelegramConversationBase.all_conversation_type()
        lines = list()
        for t in conversation_types:
            line = f'{t.COMMAND_NAME.lower()} - {t.COMMAND_TITLE}'
            lines.append(line)
        self.app.exit(message=f'在 @BotFather 中使用 /setcommands 回应命令菜单项:\n{"\n".join(lines)}')


class HodlFixTools(App):
    CSS_PATH = "../../hodl/css/fix_tools.css"

    SCREENS = {
        "IndexScreen": IndexScreen,
        "OrderLinkScreen": OrderLinkScreen,
        "StoreConfigIndexScreen": StoreConfigIndexScreen,
        "StoreConfigScreen": StoreConfigScreen,
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
    StoreConfig.READONLY = True
    app = HodlFixTools()
    app.run()
