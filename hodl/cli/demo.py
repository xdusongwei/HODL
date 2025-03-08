from textual.app import App, ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Header, Footer, Button, Markdown
from textual.binding import Binding
from textual.widgets._header import HeaderTitle
from hodl.unit_test import *
from hodl.tools import *
from hodl.cli.threads import html_writer
from hodl.storage import *
from hodl.cli.fix_screens.store_config_detail import *


class DemoStore(SimulationStore):
    STORE = None
    WRITER = None

    @classmethod
    def ci_config_path(cls):
        return LocateTools.locate_file('hodl/resources/demo.toml')

    @classmethod
    async def init_store(cls):
        var = cls.config()
        db = LocalDb(':memory:')
        env = var.jinja_env
        template = env.get_template("index.html")
        ticks = [
            Tick('25-03-10T09:30:00-04:00:00', pre_close=10.00, open=10.00, latest=10.00),
            Tick('25-03-10T09:30:01-04:00:00', pre_close=10.00, open=10.00, latest=10.00),
            Tick('25-03-10T09:30:02-04:00:00', pre_close=10.00, open=10.00, latest=10.00),
        ]
        DemoStore.STORE = SimulationBuilder.from_symbol(
            'FAKE', ticks=ticks, db=db, store_type=DemoStore
        )
        DemoStore.WRITER = html_writer.HtmlWriterThread(db, template)
        DemoStore.WRITER.write_html()

    @classmethod
    async def first_sell(cls):
        store = DemoStore.STORE
        ticks = [
            Tick('25-03-10T09:30:03-04:00:00', pre_close=10.00, open=10.00, latest=10.30),
        ]
        SimulationBuilder.resume(store, ticks=ticks)
        DemoStore.WRITER.write_html()

    @classmethod
    async def first_buy(cls):
        store = DemoStore.STORE
        ticks = [
            Tick('25-03-10T09:35:00-04:00:00', pre_close=10.00, open=10.00, latest=10.00),
            Tick('25-03-10T09:35:01-04:00:00', pre_close=10.00, open=10.00, latest=10.00),
            Tick('25-03-10T09:35:02-04:00:00', pre_close=10.00, open=10.00, latest=10.00),
        ]
        SimulationBuilder.resume(store, ticks=ticks)
        DemoStore.WRITER.write_html()


class DemoHeader(Header):
    def compose(self):
        title = HeaderTitle()
        title.text = 'demo'
        yield title


class DemoScreen(Screen):
    COUNTER = 0
    STEPS = [
        {
            'file': 'hodl/resources/demo/welcome.md',
            'action': DemoStore.init_store(),
        },
        {
            'file': 'hodl/resources/demo/ui.md',
        },
        {
            'file': 'hodl/resources/demo/firstsell.md',
            'action': DemoStore.first_sell(),
        },
        {
            'file': 'hodl/resources/demo/firstbuy.md',
            'action': DemoStore.first_buy(),
        },
    ]

    def compose(self) -> ComposeResult:
        yield DemoHeader(name='demo')
        with Container(id="container"):
            md = Markdown(id='md')
            yield md
            yield Button(id='next', label='开始')
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Event handler called when a button is pressed."""
        button_id = event.button.id
        if button_id != "next":
            return
        btn: Button = event.button
        btn.label = '继续'
        if DemoScreen.COUNTER == len(DemoScreen.STEPS) - 1:
            btn.label = '结束'
        if DemoScreen.COUNTER == len(DemoScreen.STEPS):
            self.app.exit()
            return
        try:
            node = DemoScreen.STEPS[DemoScreen.COUNTER]
            md_file = node.get('file')
            action = node.get('action')
            if md_file:
                md_path = LocateTools.locate_file(md_file)
                md: Markdown = self.query_one(Markdown)
                self.run_worker(md.load(md_path))
            if action:
                self.run_worker(action)
        finally:
            DemoScreen.COUNTER += 1


class Demo(App):
    CSS_PATH = "../../hodl/css/demo.css"

    SCREENS = {
        'DemoScreen': DemoScreen,
    }

    BINDINGS = [
        ("c", "view_config", "持仓配置"),
        Binding("q", "quit", "退出", priority=True),
    ]

    def on_mount(self) -> None:
        self.push_screen('DemoScreen')

    def compose(self) -> ComposeResult:
        yield DemoHeader(name='demo')
        yield Footer()

    def action_view_config(self):
        store: DemoStore = DemoStore.STORE
        if not store:
            return
        self.push_screen(StoreConfigIndexScreen(store.config().store_config_list()))


if __name__ == "__main__":
    app = Demo()
    app.run()
