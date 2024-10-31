import dataclasses
import requests
from hodl.tools import *
from hodl.thread_mixin import *


@dataclasses.dataclass
class CurrencyNode:
    base_currency: str = dataclasses.field()
    target_currency: str = dataclasses.field()
    rate: float = dataclasses.field()

    @classmethod
    def from_dict(cls, data: dict) -> 'CurrencyNode':
        symbol = data.get('symbol', '')
        if len(symbol) == 6:
            base_currency = symbol[:3]
            target_currency = symbol[3:]
        else:
            raise ValueError(f'不正确的外汇交易对代码: {symbol}')
        rate = data.get('rate', None)
        assert isinstance(rate, float)
        assert rate > 0.0
        return CurrencyNode(
            base_currency=base_currency,
            target_currency=target_currency,
            rate=float(rate),
        )

    @property
    def currency_pair(self) -> str:
        return f'{self.base_currency}{self.target_currency}'

    def __hash__(self):
        return self.currency_pair.__hash__()

    def __eq__(self, other):
        if isinstance(other, CurrencyNode):
            return self.currency_pair == other.currency_pair
        return False


class CurrencyProxy(ThreadMixin):
    """
    汇率更新代理在使用之前需要配置一个 URL 地址,
    线程将循环 GET 请求这个地址, 以获取一个类似格式的 json 响应, 得到汇率信息.

    {
        "type": "currencyList",
        "currencyList": [
            {
                "symbol": "USDHKD",
                "rate": 7.77054
            },
            {
                "symbol": "USDCNY",
                "rate": 7.13455
            },
            {
                "symbol": "USDCNH",
                "rate": 7.13455
            }
        ]
    }

    汇率信息不是必要配置的部分, 除非需要操作的持仓属于非券商默认现金币种以外的货币.
    比如, 很多跨境券商, 默认币种是美元, 那么假如你需要控制的持仓是港股, 则这个持仓的运行依赖货币汇率,
    以便把账户美元现金转换为港币价值来维持系统的计算任务.
    """

    _CURRENCY: set[CurrencyNode] = set()

    def __init__(self):
        self.var = VariableTools()
        env = self.var.jinja_env
        template = env.get_template("currency_status.html")
        self.template = template
        self.ex: Exception | None = None

    @classmethod
    def pull_currency(cls):
        currency_nodes: list[CurrencyNode] = list()

        currency_config = HotReloadVariableTools.config().currency_config
        if not currency_config or not currency_config.url:
            return currency_nodes

        args = dict(
            method='GET',
            url=currency_config.url,
            timeout=currency_config.timeout,
            headers={
                'User-Agent': 'tradebot',
            },
        )
        try:
            resp = requests.request(**args)
            resp.raise_for_status()
            d: dict = resp.json()
            resp_type: str = d.get('type', '')
            assert resp_type == 'currencyList'
            currency_list = d.get('currencyList', list())
            currency_nodes = [CurrencyNode.from_dict(item) for item in currency_list]
            for node in currency_nodes:
                CurrencyProxy._CURRENCY.add(node)
            return currency_nodes
        except requests.JSONDecodeError:
            return currency_nodes

    def prepare(self):
        self.pull_currency()
        
    def run(self):
        super().run()
        while True:
            TimeTools.sleep(60.0)
            try:
                self.pull_currency()
                self.ex = None
            except Exception as e:
                self.ex = e

    def extra_html(self) -> None | str:
        template = self.template
        html = template.render(
            cl=sorted(list(CurrencyProxy._CURRENCY), key=lambda i: i.currency_pair),
            ex=self.ex,
        )
        return html

    @classmethod
    def convert_currency(
        cls,
        base_currency: str,
        target_currency: str,
        amount: float,
        precision: int = 2,
    ) -> float:
        currency_list = list(CurrencyProxy._CURRENCY)
        for currency in currency_list:
            if currency.base_currency != base_currency:
                continue
            if currency.target_currency != target_currency:
                continue
            rate = currency.rate
            converted_amount = amount * rate
            converted_amount = FormatTool.adjust_precision(converted_amount, precision=precision)
            return converted_amount
        raise ValueError(f'无法转换货币{base_currency}->{target_currency}')


__all__ = [
    'CurrencyNode',
    'CurrencyProxy',
]
