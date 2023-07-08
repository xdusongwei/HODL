from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, ListView, ListItem, Label
from textual.binding import Binding
from hodl.tools import *
from hodl.cli.fix_screens.order_link import *
from hodl.cli.fix_screens.store_config_detail import *


class IndexScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        menu = ListView(
            ListItem(Label("1.补录订单信息", classes='indexLabel'), id='indexMenuOrderLink'),
            ListItem(Label("2.补录收益信息", classes='indexLabel'), id='indexMenuEarningLink'),
            ListItem(Label("3.刷新收益json文件", classes='indexLabel'), id='indexMenuRefreshEarnings'),
            ListItem(Label("4.弹射持仓", classes='indexLabel'), id='indexMenuShootOff'),
            ListItem(Label("0.持仓设定", classes='indexLabel'), id='indexMenuStoreConfig'),
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
                case _:
                    pass


class HodlFixTools(App):
    CSS_PATH = "../../hodl/css/fix_tools.css"

    SCREENS = {
        "IndexScreen": IndexScreen(),
        "OrderLinkScreen": OrderLinkScreen(),
        "StoreConfigIndexScreen": StoreConfigIndexScreen(),
        "StoreConfigScreen": StoreConfigScreen(),
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
