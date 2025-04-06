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


class DemoHtmlWriter(html_writer.HtmlWriterThread):
    pass


class DemoStore(SimulationStore):
    CONFIG_PATH: str = ''
    STORE_LIST: list[SimulationStore] = list()
    STORE = None
    WRITER = None

    TP_TICKS = [
        Tick('25-03-10T16:00:00-04:00:00', ms='CLOSING', pre_close=10.0, open=10.0, latest=10.0, high=10.0, low=10.0),
        Tick('25-03-11T09:30:00-04:00:00', pre_close=10.00, open=10.00, latest=9.00, high=9.00, low=9.00),
        Tick('25-03-11T16:00:00-04:00:00', ms='CLOSING', pre_close=9.00, open=9.00, latest=9.00, high=9.00, low=9.00),
        Tick('25-03-12T09:30:00-04:00:00', pre_close=9.00, open=9.00, latest=8.00, high=8.00, low=8.00),
        Tick('25-03-12T16:00:00-04:00:00', ms='CLOSING', pre_close=9.00, open=9.00, latest=8.00, high=8.00, low=8.00),
        Tick('25-03-13T09:30:00-04:00:00', pre_close=8.00, open=8.00, latest=7.00, high=7.00, low=7.00),
        Tick('25-03-13T16:00:00-04:00:00', ms='CLOSING', pre_close=8.00, open=8.00, latest=7.00, high=7.00, low=7.00),
        Tick('25-03-14T09:30:00-04:00:00', pre_close=7.00, open=7.00, latest=6.50, high=6.50, low=6.50),
        Tick('25-03-14T16:00:00-04:00:00', ms='CLOSING', pre_close=7.00, open=7.00, latest=6.50, high=6.50, low=6.50),
        Tick('25-03-15T09:30:00-04:00:00', pre_close=6.50, open=6.50, latest=6.00, high=6.00, low=6.00),
        Tick('25-03-15T16:00:00-04:00:00', ms='CLOSING', pre_close=6.50, open=6.50, latest=6.00, high=6.00, low=6.00),
        Tick('25-03-16T09:30:00-04:00:00', pre_close=6.00, open=6.00, latest=5.00, high=5.00, low=5.00),
        Tick('25-03-16T16:00:00-04:00:00', ms='CLOSING', pre_close=6.00, open=6.00, latest=5.00, high=5.00, low=5.00),
        Tick('25-03-17T09:30:00-04:00:00', pre_close=5.00, open=5.00, latest=5.00, high=5.00, low=5.00),
    ]

    @classmethod
    def ci_config_path(cls):
        return LocateTools.locate_file(cls.CONFIG_PATH)

    @classmethod
    async def init_stores(cls, cfg_path: str, expand_ticks: list[Tick] = None) -> None:
        for store in DemoStore.STORE_LIST:
            store.unmount()
        DemoStore.STORE_LIST = list()

        cls.CONFIG_PATH = cfg_path
        var = cls.config()
        db = LocalDb(':memory:')
        env = var.jinja_env
        template = env.get_template("index.html")
        ticks = [
            Tick('25-03-10T09:30:00-04:00:00', pre_close=10.00, open=10.00, latest=10.00),
            Tick('25-03-10T09:30:01-04:00:00', pre_close=10.00, open=10.00, latest=10.00),
            Tick('25-03-10T09:30:02-04:00:00', pre_close=10.00, open=10.00, latest=10.00),
        ]
        DemoStore.STORE_LIST = [
            SimulationBuilder.from_config(sc, ticks=ticks, db=db, store_type=DemoStore)
            for sc in var.store_config_list()
        ]
        if expand_ticks:
            DemoStore.STORE_LIST = [
                SimulationBuilder.resume(store, ticks=expand_ticks)
                for store in DemoStore.STORE_LIST
            ]
        DemoStore.WRITER = DemoHtmlWriter(db, template)
        DemoStore.WRITER.write_html()

    @classmethod
    async def resume(cls, ticks: list[Tick]) -> None:
        for store in cls.STORE_LIST:
            SimulationBuilder.resume(store, ticks=ticks)
        if DemoStore.WRITER:
            DemoStore.WRITER.write_html()

    @classmethod
    async def first_sell(cls):
        ticks = [
            Tick('25-03-10T09:30:03-04:00:00', pre_close=10.00, open=10.00, latest=10.30),
        ]
        await cls.resume(ticks)

    @classmethod
    async def first_buy(cls):
        ticks = [
            Tick('25-03-10T09:35:00-04:00:00', pre_close=10.00, open=10.00, latest=10.00),
            Tick('25-03-10T09:35:01-04:00:00', pre_close=10.00, open=10.00, latest=10.00),
            Tick('25-03-10T09:35:02-04:00:00', pre_close=10.00, open=10.00, latest=10.00),
        ]
        await cls.resume(ticks)

    @classmethod
    async def tp_effect(cls):
        ticks = [
            Tick('25-03-17T09:30:03-04:00:00', pre_close=5.0, open=5.0, latest=6.0, high=6.0, low=6.0),
            Tick('25-03-17T16:00:00-04:00:00', ms='CLOSING', pre_close=5.0, open=5.0, latest=6.0, high=6.0, low=6.0),
            Tick('25-03-18T09:30:03-04:00:00', pre_close=6.0, open=6.0, latest=7.0, high=7.0, low=7.0),
            Tick('25-03-18T16:00:00-04:00:00', ms='CLOSING', pre_close=6.0, open=6.0, latest=7.0, high=7.0, low=7.0),
            Tick('25-03-19T09:30:03-04:00:00', pre_close=7.0, open=7.0, latest=8.0, high=8.0, low=8.0),
            Tick('25-03-19T16:00:00-04:00:00', ms='CLOSING', pre_close=7.0, open=7.0, latest=8.0, high=8.0, low=8.0),
            Tick('25-03-20T09:30:03-04:00:00', pre_close=8.0, open=8.0, latest=9.0, high=9.0, low=9.0),
            Tick('25-03-20T16:00:00-04:00:00', ms='CLOSING', pre_close=8.0, open=9.0, latest=9.0, high=9.0, low=9.0),
            Tick('25-03-21T09:30:03-04:00:00', pre_close=9.0, open=9.0, latest=10.0, high=10.0, low=10.0),
            Tick('25-03-21T16:00:00-04:00:00', ms='CLOSING', pre_close=9.0, open=9.0, latest=10.0, high=10.0, low=10.0),
        ]
        await cls.resume(ticks)


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
            'action': DemoStore.init_stores('hodl/resources/demo.toml'),
        },
        {
            'file': 'hodl/resources/demo/store.md',
        },
        {
            'file': 'hodl/resources/demo/firstsell.md',
            'action': DemoStore.first_sell(),
        },
        {
            'file': 'hodl/resources/demo/firstbuy.md',
            'action': DemoStore.first_buy(),
        },
        {
            'file': 'hodl/resources/demo/factors.md',
            'action': DemoStore.init_stores('hodl/resources/demo_factors.toml'),
        },
        {
            'file': 'hodl/resources/demo/tumble_protect.md',
            'action': DemoStore.init_stores('hodl/resources/demo_tumble_protect.toml', DemoStore.TP_TICKS),
        },
        {
            'file': 'hodl/resources/demo/tumble_protect_effect.md',
            'action': DemoStore.tp_effect(),
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
    CSS_PATH = "../../hodl/resources/css/demo.css"

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
        stores = DemoStore.STORE_LIST
        if not stores:
            return
        self.push_screen(StoreConfigIndexScreen(DemoStore.config().store_config_list()))


if __name__ == "__main__":
    app = Demo()
    app.run()
