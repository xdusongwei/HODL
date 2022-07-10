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
    #
    profit_rate: float
    # 调仓过的部分自身的获利比例
    float_rate: float
    # 调仓过的部分占全部仓位的获利比例
    total_rate: float
    # 卖出价格
    sell_at: float
    # 买入价格
    buy_at: float
    # 点差
    buy_spread: float
    sell_spread: float
    # 卖出股数
    shares: int

    def __str__(self):
        return f'<Level{self.level} sell@{FMT.pretty_usd(self.sell_at)} buy@{FMT.pretty_usd(self.buy_at)} ' \
               f'shares:{self.shares:,}>'

    def __repr__(self):
        return self.__str__()


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
        if prudent:
            # 22
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
            # 24
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
        sell_percent = list(self.sell_rate)
        buy_percent = list(self.buy_rate)
        result = ProfitTable()
        result.table_row = self.table_size
        for i in range(self.table_size):
            range_weight = weight[0:i + 1]

            sell_value = sum(weight[j] * sell_percent[j] for j in range(i + 1))
            buy_value = sum(range_weight) * buy_percent[i]

            profit = sell_value - buy_value
            float_rate = profit / sum(range_weight)
            total_rate = profit / sum(weight)
            profit_rate = base_asset * total_rate
            sell_at = base_price * sell_percent[i] + sell_spread
            buy_at = base_price * buy_percent[i] - buy_spread
            shares = int(max_shares * weight[i] / sum(weight))
            shares = (shares // shares_per_unit) * shares_per_unit
            if shares <= 0:
                return ProfitTable()
            row = ProfitRow(
                level=i+1,
                profit_rate=FMT.adjust_precision(profit_rate, precision),
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
