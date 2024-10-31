import pytest
import unittest
from hodl.exception_tools import *
from hodl.proxy import *
from hodl.unit_test import *
from hodl.tools import *


class CurrencyTestCase(unittest.TestCase):
    def test_currency(self):
        """
        更改持仓的币种为 XYZ, 汇率为 1, 第一天卖出一档, 第二天买回, 应通过.
        """
        var = VariableTools()
        CurrencyProxy._CURRENCY = [CurrencyNode(base_currency='USD', target_currency='XYZ', rate=1.0)]
        store_config = var.store_configs['TEST']
        store_config['currency'] = 'XYZ'

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
        store = start_simulation(store_config=store_config, tickets=tickets, broker_currency='USD')
        plan = store.state.plan
        assert plan.earning

    def test_currency_limit(self):
        """
        更改持仓的币种为 XYZ, 汇率为 0.00455, 第一天卖出一档, 第二天买回, 应通过.
        第一档卖出 4545 股, 而模拟环境默认可用资金是 1千万 USD, 就是说, 如果汇率 USDXYZ 大于 0.004545, 其美元现金不影响第二天买入
        """
        var = VariableTools()
        CurrencyProxy._CURRENCY = [CurrencyNode(base_currency='USD', target_currency='XYZ', rate=0.00455)]
        store_config = var.store_configs['TEST']
        store_config['currency'] = 'XYZ'

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
        store = start_simulation(store_config=store_config, tickets=tickets, broker_currency='USD')
        plan = store.state.plan
        assert plan.earning

    def test_currency_buy_error(self):
        """
        更改持仓的币种为 XYZ, 汇率为 0.00454, 第一天卖出一档, 第二天买回, 不应通过.
        第一档卖出 4545 股, 而模拟环境默认可用资金是 1千万 USD, 就是说, 如果汇率 USDXYZ 小于 0.004545, 其美元现金会影响第二天买入
        """
        var = VariableTools()
        CurrencyProxy._CURRENCY = [CurrencyNode(base_currency='USD', target_currency='XYZ', rate=0.00454)]
        store_config = var.store_configs['TEST']
        store_config['currency'] = 'XYZ'

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
            start_simulation(store_config=store_config, tickets=tickets, broker_currency='USD')
    