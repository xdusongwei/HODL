import random
import dataclasses
from functools import reduce
from operator import mul
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

    @property
    def unique_pair(self) -> str:
        return ''.join(sorted([self.base_currency, self.target_currency, ]))

    def __hash__(self):
        return self.unique_pair.__hash__()

    def __eq__(self, other):
        if isinstance(other, CurrencyNode):
            return self.unique_pair == other.unique_pair
        return False


@dataclasses.dataclass
class DfsSearchState:
    base_currency: str
    target_currency: str
    edges: list[CurrencyNode]
    current_path: list[CurrencyNode] = dataclasses.field(default_factory=list)
    tail_currency: str = None
    best_distance: int = 100


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
    比如, 很多跨境券商, 默认现金币种是美元, 那么假如你需要控制的持仓是港股, 则这个持仓的运行依赖货币汇率,
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

        new_set = CurrencyProxy._CURRENCY.copy()
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
                if node in new_set:
                    new_set.remove(node)
                new_set.add(node)
            return currency_nodes
        except requests.JSONDecodeError:
            return currency_nodes
        finally:
            CurrencyProxy._CURRENCY = new_set

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
    def _search_dfs(cls, state: DfsSearchState) -> list[CurrencyNode]:
        current_path = state.current_path
        edges = state.edges
        base_currency = state.base_currency
        target_currency = state.target_currency
        tail_currency = state.tail_currency
        if len(current_path) > len(edges):
            raise ValueError(f'搜索货币对的路径栈大小超出了容量')
        if len(current_path) >= state.best_distance:
            return list()
        best_result = list()
        for edge in edges:
            if edge.base_currency == edge.target_currency:
                continue
            if edge in current_path:
                continue
            if len(current_path) == 0:
                if edge.base_currency != base_currency and edge.target_currency != base_currency:
                    continue
                tail_currency = base_currency
            else:
                if tail_currency not in {edge.base_currency, edge.target_currency, }:
                    continue
            new_tail_currency = edge.target_currency if edge.base_currency == tail_currency else edge.base_currency
            state.current_path = new_current_path = current_path.copy()
            state.tail_currency = new_tail_currency
            new_current_path.append(edge)
            if edge.target_currency == target_currency or edge.base_currency == target_currency:
                if len(new_current_path) < state.best_distance:
                    state.best_distance = len(new_current_path)
                    return new_current_path
            else:
                result = cls._search_dfs(state)
                if result:
                    if not best_result:
                        best_result = result
                    elif len(result) < len(best_result):
                        best_result = result
        return best_result

    @classmethod
    def search_rate(
        cls,
        base_currency: str,
        target_currency: str,
    ):
        currency_edges = list(CurrencyProxy._CURRENCY)
        random.shuffle(currency_edges)
        state = DfsSearchState(
            base_currency=base_currency,
            target_currency=target_currency,
            edges=currency_edges,
        )
        path = cls._search_dfs(state)
        if not path:
            raise ValueError(f'无法搜索到{base_currency}->{target_currency}货币兑换方式.')
        rate_link = list()
        currency_tail = base_currency
        for node in path:
            if node.base_currency == currency_tail:
                rate_link.append(node.rate)
                currency_tail = node.target_currency
            else:
                rate_link.append(1.0 / node.rate)
                currency_tail = node.base_currency
        rate = reduce(mul, rate_link)
        return rate

    @classmethod
    def convert_currency(
        cls,
        base_currency: str,
        target_currency: str,
        amount: float,
        precision: int = 2,
    ) -> float:
        rate = cls.search_rate(base_currency, target_currency)
        converted_amount = amount * rate
        converted_amount = FormatTool.adjust_precision(converted_amount, precision=precision)
        return converted_amount


__all__ = [
    'CurrencyNode',
    'CurrencyProxy',
]
