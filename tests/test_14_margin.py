import pytest
import unittest
from hodl.exception_tools import *
from hodl.unit_test import *
from hodl.tools import *


class MarginTestCase(unittest.TestCase):
    def test_margin(self):
        """
        限制可用资金为 0, 保证金上限为 45450, 第一天卖出一档, 第二天买回, 应通过.
        第一档卖出 4545 股, 买入价格为 10.00, 那么刚好可以购回剩余股票
        """
        var = VariableTools()
        store_config = var.store_configs['TEST']

        pc = 10.0
        p_sell = pc * 1.03
        p_buy = pc * 1.0
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Ticket(day='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Ticket(day='23-04-10T20:00:00-04:00:00', ms='CLOSING', pre_close=pc, open=p_sell, latest=p_sell, ),
            Ticket(day='23-04-11T09:31:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
            Ticket(day='23-04-11T09:32:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
            Ticket(day='23-04-11T09:33:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
        ]
        store = start_simulation(store_config=store_config, tickets=tickets, cash_amount=0.0, margin_amount=45450.0)
        plan = store.state.plan
        assert plan.earning

    def test_margin_buy_error(self):
        """
        限制可用资金为 0, 保证金上限为 45449, 第一天卖出一档, 第二天买回, 不应通过.
        第一档卖出 4545 股, 买入价格为 10.00, 差一块钱可以购回剩余股票
        """
        var = VariableTools()
        store_config = var.store_configs['TEST']

        pc = 10.0
        p_sell = pc * 1.03
        p_buy = pc * 1.0
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Ticket(day='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Ticket(day='23-04-10T20:00:00-04:00:00', ms='CLOSING', pre_close=pc, open=p_sell, latest=p_sell, ),
            Ticket(day='23-04-11T09:31:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
            Ticket(day='23-04-11T09:32:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
            Ticket(day='23-04-11T09:33:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
        ]
        with pytest.raises(RiskControlError):
            start_simulation(store_config=store_config, tickets=tickets, cash_amount=0.0, margin_amount=45449.0)
