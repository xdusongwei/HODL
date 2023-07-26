from dataclasses import dataclass
from hodl.tools import FormatTool as FMT


@dataclass
class _Argument:
    weight: list[float]
    sell_rate: list[float]
    buy_rate: list[float]


@dataclass
class ProfitRow:
    level: int
    # 计算出新市值，目前没什么用途
    value: float
    # 调仓过的部分自身的获利比例
    float_rate: float
    # 调仓过的部分占全部仓位的获利比例
    total_rate: float
    # 卖出价格
    sell_at: float
    # 买入价格
    buy_at: float
    # 点差，买卖价格已经把点差算进去了，如果需要还原期望价格，从这里扣除
    buy_spread: float
    sell_spread: float
    # 卖出股数
    shares: int

    def __str__(self):
        return f'<' \
               f'Level{self.level} ' \
               f'sell@{FMT.pretty_usd(self.sell_at, unit="")} ' \
               f'buy@{FMT.pretty_usd(self.buy_at, unit="")} ' \
               f'shares:{self.shares:,}>'

    def __repr__(self):
        return self.__str__()

    def full_report(self):
        return f'<' \
               f'Level{self.level} ' \
               f'sell@{FMT.pretty_usd(self.sell_at, unit="")} ' \
               f'buy@{FMT.pretty_usd(self.buy_at, unit="")} ' \
               f'float rate: {FMT.factor_to_percent(self.float_rate, fmt="{:.2%}", base_100=False)} ' \
               f'total rate: {FMT.factor_to_percent(self.total_rate, fmt="{:.2%}", base_100=False)} ' \
               f'shares:{self.shares:,}>'


class ProfitTable(list[ProfitRow]):
    def __init__(self, *args, **kwargs):
        super(ProfitTable, self).__init__()
        self.table_row = None

    def row_by_level(self, level: int) -> ProfitRow:
        assert 0 < level <= self.table_row
        return self[level-1]

    @property
    def size(self) -> int:
        return len(self)

    def check_factors(self):
        assert len(self) > 0
        for row in self:
            assert row.total_rate >= 1.0


class PlanCalc:
    def __init__(
            self,
            weight=None,
            sell_rate=None,
            buy_rate=None,
    ):
        if weight is None or sell_rate is None or buy_rate is None:
            raise ValueError(f'没有传入有效因子')

        self.weight = weight
        self.sell_rate = sell_rate
        self.buy_rate = buy_rate

    @property
    def table_size(self) -> int:
        assert len(self.weight) == len(self.sell_rate)
        assert len(self.weight) == len(self.buy_rate)
        return len(self.weight)

    def profit_rows(
            self,
            base_price: float,
            max_shares: int,
            base_asset=1.0,
            buy_spread=None,
            sell_spread=None,
            precision=2,
            shares_per_unit=1,
            buy_spread_rate=None,
            sell_spread_rate=None,
    ) -> ProfitTable[ProfitRow]:
        weight = list(self.weight)
        sell_rate = list(self.sell_rate)
        buy_rate = list(self.buy_rate)
        result = ProfitTable()
        result.table_row = self.table_size
        sum_shares = 0
        for i in range(self.table_size):
            range_weight = weight[0:i + 1]

            # 平均卖出和买入的重心centre-of-gravity
            sell_cog = sum(weight[j] * sell_rate[j] for j in range(i + 1))
            buy_cog = sum(range_weight) * buy_rate[i]

            cog_diff = sell_cog - buy_cog
            float_rate = cog_diff / sum(range_weight)
            total_rate = cog_diff / sum(weight)
            value = base_asset * total_rate
            sell_spread_points = FMT.spread(
                price=base_price * sell_rate[i],
                precision=precision,
                spread=sell_spread,
                spread_rate=sell_spread_rate,
            )
            buy_spread_points = FMT.spread(
                price=base_price * buy_rate[i],
                precision=precision,
                spread=buy_spread,
                spread_rate=buy_spread_rate,
            )
            sell_at = base_price * sell_rate[i] + sell_spread_points
            buy_at = base_price * buy_rate[i] - buy_spread_points

            # 由于权重不能把全部股数整除的原因，下一档的股数要补上之前档位股数的余下部分，减少因为除不尽导致不能流动的股票份额
            range_shares = int(max_shares * sum(range_weight) / sum(weight))
            shares = range_shares - sum_shares
            shares = (shares // shares_per_unit) * shares_per_unit
            sum_shares += shares
            if shares <= 0:
                return ProfitTable()
            row = ProfitRow(
                level=i+1,
                value=FMT.adjust_precision(value, precision),
                float_rate=FMT.adjust_precision(float_rate + 1, 4),
                total_rate=FMT.adjust_precision(total_rate + 1, 4),
                sell_at=FMT.adjust_precision(sell_at, precision),
                buy_at=FMT.adjust_precision(buy_at, precision),
                buy_spread=buy_spread_points,
                sell_spread=sell_spread_points,
                shares=shares,
            )
            result.append(row)
        return result


__all__ = ['PlanCalc', 'ProfitTable', 'ProfitRow', ]
