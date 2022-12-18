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


class ProfitTable(list):
    def __init__(self, *args, **kwargs):
        super(ProfitTable, self).__init__()
        self.table_row = None

    def row_by_level(self, level: int) -> ProfitRow:
        assert 0 < level <= self.table_row
        return self[level-1]

    @property
    def size(self) -> int:
        return len(self)


class PlanCalc:
    def __init__(
            self,
            weight=None,
            sell_rate=None,
            buy_rate=None,
            prudent=True,
            price_rate=1.0,
    ):
        if weight is None or sell_rate is None or buy_rate is None:
            factors = self._build_argument(prudent=prudent, price_rate=price_rate)
            weight = factors.weight
            sell_rate = factors.sell_rate
            buy_rate = factors.buy_rate

        self.weight = weight
        self.sell_rate = sell_rate
        self.buy_rate = buy_rate

    @classmethod
    def _build_argument(cls, prudent=True, price_rate=1.0) -> _Argument:
        """
        构建默认的买卖价位的因子列表。
        大多数情形下，持仓套利主要集中在3%~10%以内的波动区间。
        但是考虑到股价存在大幅波动的可能，绝大部分持仓需要分段在更高的价位上卖出。
        列表项是一个三元组，分别代表了买入价位比例因子，卖出价位比例因子，卖出的仓位权重。
        """
        if prudent:
            # 惜售策略，可控最高涨幅100%。合计权重：22；10%以内波动，策略换手率14.5%。
            factors = [
                (01.0, 1.030, 1.000,),
                (01.0, 1.055, 1.015,),
                (01.2, 1.090, 1.030,),
                (01.2, 1.150, 1.050,),

                (01.2, 1.190, 1.070,),
                (03.4, 1.270, 1.140,),
                (01.0, 1.360, 1.150,),

                (02.0 + 00.0, 1.400, 1.160,),

                (02.0 + 00.0, 1.580, 1.210,),
                (02.0 + 02.0, 1.850, 1.330,),

                (02.0 + 02.0, 2.100, 1.450,),
            ]
            weight = [factor[0] for factor in factors]
            sell_rate = [factor[1] for factor in factors]
            buy_rate = [factor[2] for factor in factors]
        else:
            # 超卖策略，可控最高涨幅50%。合计权重：24；10%以内波动，策略换手率12.5%。
            factors = [
                (01.0, 1.030, 1.000,),
                (01.0, 1.050, 1.015,),
                (01.0, 1.080, 1.030,),
                (02.0, 1.120, 1.050,),

                (01.0, 1.190, 1.060,),
                (02.0, 1.210, 1.080,),
                (01.0, 1.240, 1.090,),

                (03.0, 1.300, 1.120,),
                (02.0, 1.330, 1.130,),

                (04.0, 1.390, 1.180,),
                (02.0, 1.420, 1.190,),

                (04.0, 1.550, 1.240,),
            ]
            weight = [factor[0] for factor in factors]
            sell_rate = [factor[1] for factor in factors]
            buy_rate = [factor[2] for factor in factors]

        sell_rate = [FMT.adjust_precision((r - 1.0) * price_rate + 1.0, 5) for r in sell_rate]
        buy_rate = [FMT.adjust_precision((r - 1.0) * price_rate + 1.0, 5) for r in buy_rate]

        return _Argument(
            weight=weight,
            sell_rate=sell_rate,
            buy_rate=buy_rate,
        )

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
            buy_spread=0.01,
            sell_spread=0.01,
            precision=2,
            shares_per_unit=1,
    ) -> ProfitTable[ProfitRow]:
        buy_spread = abs(buy_spread)
        sell_spread = abs(sell_spread)
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
            sell_at = base_price * sell_rate[i] + sell_spread
            buy_at = base_price * buy_rate[i] - buy_spread

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
                buy_spread=buy_spread,
                sell_spread=sell_spread,
                shares=shares,
            )
            result.append(row)
        return result


__all__ = ['PlanCalc', 'ProfitTable', 'ProfitRow', ]
