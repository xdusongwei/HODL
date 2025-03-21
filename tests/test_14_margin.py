import pytest
from hodl.exception_tools import *
from hodl.unit_test import *


class MarginTestCase(HodlTestCase):
    def test_margin(self):
        """
        限制可用资金为 0, 保证金上限为 45450, 第一天卖出一档, 第二天买回, 应通过.
        第一档卖出 4545 股, 买入价格为 10.00, 那么 (可用资金 + 保证金上限) 刚好可以购回剩余股票
        """
        var = self.config()
        store_config = var.store_configs['TEST']

        pc = 10.0
        p_sell = pc * 1.03
        p_buy = pc * 1.0
        ticks = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Tick(time='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Tick(time='23-04-10T20:00:00-04:00:00', ms='CLOSING', pre_close=pc, open=p_sell, latest=p_sell, ),
            Tick(time='23-04-11T09:31:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
            Tick(time='23-04-11T09:32:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
            Tick(time='23-04-11T09:33:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
        ]
        store = SimulationBuilder.from_config(
            store_config=store_config,
            ticks=ticks,
            cash_amount=0.0,
            margin_amount=45450.0,
        )
        plan = store.state.plan
        assert plan.earning

    def test_margin_buy_error(self):
        """
        限制可用资金为 0, 保证金上限为 45449, 第一天卖出一档, 第二天买回, 不应通过.
        第一档卖出 4545 股, 买入价格为 10.00, 那么 (可用资金 + 保证金上限) 差一块钱可以购回剩余股票
        """
        var = self.config()
        store_config = var.store_configs['TEST']

        pc = 10.0
        p_sell = pc * 1.03
        p_buy = pc * 1.0
        ticks = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Tick(time='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Tick(time='23-04-10T20:00:00-04:00:00', ms='CLOSING', pre_close=pc, open=p_sell, latest=p_sell, ),
            Tick(time='23-04-11T09:31:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
            Tick(time='23-04-11T09:32:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
            Tick(time='23-04-11T09:33:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
        ]
        with pytest.raises(RiskControlError):
            SimulationBuilder.from_config(
                store_config=store_config,
                ticks=ticks,
                cash_amount=0.0,
                margin_amount=45449.0,
            )
