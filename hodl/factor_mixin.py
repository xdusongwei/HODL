from abc import ABC
from hodl.store_hodl_base import *


class FactorMixin(StoreHodlBase, ABC):
    FACTORS_DICT = {
        'fear': [
            (1.0, 1.07, 1.04,),
            (1.0, 1.15, 1.07,),
            (1.0, 1.25, 1.11,),
            (2.0, 1.35, 1.15,),
            (2.0, 1.45, 1.22,),
            (3.0, 1.55, 1.31,),
            (2.0, 1.65, 1.35,),
            (2.0, 1.75, 1.38,),
            (2.0, 1.85, 1.42,),
            (3.0, 1.95, 1.49,),
            (3.0, 2.05, 1.55,),
        ],
        'neutral': [
            (01.0, 1.032, 1.010,),
            (01.0, 1.070, 1.025,),
            (01.2, 1.100, 1.050,),
            (01.2, 1.160, 1.070,),
            (01.2, 1.220, 1.100,),
            (03.4, 1.280, 1.140,),
            (01.0, 1.370, 1.160,),
            (02.0, 1.410, 1.170,),
            (02.0, 1.580, 1.220,),
            (04.0, 1.850, 1.340,),
            (04.0, 2.100, 1.460,),
        ],
        'greed': [  # 贪婪策略，可控最高涨幅110%。合计权重：22；10%以内波动，策略换手率14.5%。
            (01.0, 1.030, 1.000,),
            (01.0, 1.055, 1.015,),
            (01.2, 1.090, 1.030,),
            (01.2, 1.150, 1.050,),
            (01.2, 1.190, 1.070,),
            (03.4, 1.270, 1.140,),
            (01.0, 1.360, 1.150,),
            (02.0, 1.400, 1.160,),
            (02.0, 1.580, 1.210,),
            (04.0, 1.850, 1.330,),
            (04.0, 2.100, 1.450,),
        ],
    }

    def auto_select_factors(self) -> tuple[str, list[tuple[float, float, float]]]:
        sc, state, _ = self.args()
        fear_greed_type = 'neutral'
        if sc.cost_price is not None:
            # 需要动态选择因子表类型
            cost_price = sc.cost_price
            fear_rate = sc.factor_fear_rate_limit
            greed_rate = sc.factor_greed_rate_limit
            day_low = state.quote_low_price
            if isinstance(day_low, float) and isinstance(greed_rate, float) and isinstance(fear_rate, float):
                if day_low < cost_price * fear_rate:
                    fear_greed_type = 'fear'
                elif day_low < cost_price * greed_rate:
                    fear_greed_type = 'neutral'
                else:
                    fear_greed_type = 'greed'
        elif sc.factor_fear_and_greed in FactorMixin.FACTORS_DICT:
            # 按指定的设定选择因子表
            fear_greed_type = sc.factor_fear_and_greed
        factors = FactorMixin.FACTORS_DICT[fear_greed_type]
        return fear_greed_type, factors


__all__ = ['FactorMixin']
