import pytest
import unittest
from hodl.exception_tools import *
from hodl.proxy import *
from hodl.unit_test import *
from hodl.tools import *


class CurrencyTestCase(unittest.TestCase):
    def test_currency_unique(self):
        """
        验证货币对对象在集合中具有特定的唯一性
        """
        CurrencyProxy._CURRENCY = {
            CurrencyNode(base_currency='X', target_currency='Y', rate=1.0),
            CurrencyNode(base_currency='X', target_currency='Z', rate=1.0),
            CurrencyNode(base_currency='Y', target_currency='X', rate=1.0),
            CurrencyNode(base_currency='Y', target_currency='Z', rate=1.0),
            CurrencyNode(base_currency='Z', target_currency='X', rate=1.0),
            CurrencyNode(base_currency='Z', target_currency='Y', rate=1.0),
        }
        # 3种币种的6个货币汇率对组合一半是重复的, 只需记录 3 种
        assert len(CurrencyProxy._CURRENCY) == 3

    def test_currency_exchange(self):
        """
        验证汇率计算函数的正确性
        """
        CurrencyProxy._CURRENCY = {
            CurrencyNode(base_currency='USD', target_currency='XYZ', rate=1.0),
        }
        # 不存在这样的货币转换信息
        with pytest.raises(ValueError):
            CurrencyProxy.convert_currency('USD', 'ABC', 100, 2)

        # 测试简单汇率计算
        assert CurrencyProxy.convert_currency('USD', 'XYZ', 100, 2) == 100
        assert CurrencyProxy.convert_currency('XYZ', 'USD', 100, 2) == 100

        # 验证人民币换离岸人民币, 应等于 100 / 7.1 * 7.2
        CurrencyProxy._CURRENCY = {
            CurrencyNode(base_currency='USD', target_currency='CNY', rate=7.1),
            CurrencyNode(base_currency='USD', target_currency='CNH', rate=7.2),
        }
        assert CurrencyProxy.convert_currency('CNY', 'CNH', 100, 2) == 101.41

        CurrencyProxy._CURRENCY = {
            CurrencyNode(base_currency='A', target_currency='B', rate=1),
            CurrencyNode(base_currency='B', target_currency='C', rate=2),
            CurrencyNode(base_currency='D', target_currency='C', rate=3),
            CurrencyNode(base_currency='D', target_currency='E', rate=4),
        }
        # 验证 A币 换 E币, 应等于 100 * 1 * 2 / 3 * 4
        assert CurrencyProxy.convert_currency('A', 'E', 100, 2) == 266.67
        # 验证 E币 换 A币, 应等于 100 / 4 * 3 / 2 * 1
        assert CurrencyProxy.convert_currency('E', 'A', 100, 2) == 37.5

        CurrencyProxy._CURRENCY = {
            CurrencyNode(base_currency='A', target_currency='B', rate=1),
            CurrencyNode(base_currency='B', target_currency='C', rate=2),
            CurrencyNode(base_currency='B', target_currency='D', rate=3),
            CurrencyNode(base_currency='C', target_currency='E', rate=4),
            CurrencyNode(base_currency='D', target_currency='E', rate=4),
        }
        # 验证 A币 换 E币, 这里有两种间接兑换的路径, 哪一种都是合理的
        assert CurrencyProxy.convert_currency('A', 'E', 100, 2) in {800, 1200, }
        # 五种货币任意兑换, 包括自己兑自己
        for base_currency in ['A', 'B', 'C', 'D', 'E', ]:
            for target_currency in ['A', 'B', 'C', 'D', 'E', ]:
                assert CurrencyProxy.convert_currency(base_currency, target_currency, 100, 2)

    def test_store_currency(self):
        """
        更改持仓的币种为 XYZ, USDXYZ 汇率为 1, 第一天卖出一档, 第二天买回, 应通过.
        """
        var = VariableTools()
        CurrencyProxy._CURRENCY = {CurrencyNode(base_currency='USD', target_currency='XYZ', rate=1.0), }
        store_config = var.store_configs['TEST']
        store_config['currency'] = 'XYZ'

        pc = 10.0
        p_sell = pc * 1.03
        p_buy = pc * 1.0
        tickets = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Tick(time='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Tick(time='23-04-10T20:00:00-04:00:00', ms='CLOSING', pre_close=pc, open=p_sell, latest=p_sell, ),
            Tick(time='23-04-11T09:31:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
            Tick(time='23-04-11T09:32:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
            Tick(time='23-04-11T09:33:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
        ]
        store = SimulationBuilder.from_config(store_config=store_config, ticks=tickets, broker_currency='USD')
        plan = store.state.plan
        assert plan.earning

    def test_store_currency_limit(self):
        """
        更改持仓的币种为 XYZ, USDXYZ 汇率为 0.00455, 第一天卖出一档, 第二天买回, 应通过.
        第一档卖出 4545 股, 而模拟环境默认可用资金是 1千万 USD, 就是说, 如果汇率 USDXYZ 大于 0.004545, 其美元现金不影响第二天买入
        """
        var = VariableTools()
        CurrencyProxy._CURRENCY = {CurrencyNode(base_currency='USD', target_currency='XYZ', rate=0.00455), }
        store_config = var.store_configs['TEST']
        store_config['currency'] = 'XYZ'

        pc = 10.0
        p_sell = pc * 1.03
        p_buy = pc * 1.0
        tickets = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Tick(time='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Tick(time='23-04-10T20:00:00-04:00:00', ms='CLOSING', pre_close=pc, open=p_sell, latest=p_sell, ),
            Tick(time='23-04-11T09:31:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
            Tick(time='23-04-11T09:32:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
            Tick(time='23-04-11T09:33:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
        ]
        store = SimulationBuilder.from_config(store_config=store_config, ticks=tickets, broker_currency='USD')
        plan = store.state.plan
        assert plan.earning

    def test_store_currency_buy_error(self):
        """
        更改持仓的币种为 XYZ, USDXYZ 汇率为 0.00454, 第一天卖出一档, 第二天买回, 不应通过.
        第一档卖出 4545 股, 而模拟环境默认可用资金是 1千万 USD, 就是说, 如果汇率 USDXYZ 小于 0.004545, 其美元现金会影响第二天买入
        """
        var = VariableTools()
        CurrencyProxy._CURRENCY = {CurrencyNode(base_currency='USD', target_currency='XYZ', rate=0.00454), }
        store_config = var.store_configs['TEST']
        store_config['currency'] = 'XYZ'

        pc = 10.0
        p_sell = pc * 1.03
        p_buy = pc * 1.0
        tickets = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Tick(time='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Tick(time='23-04-10T20:00:00-04:00:00', ms='CLOSING', pre_close=pc, open=p_sell, latest=p_sell, ),
            Tick(time='23-04-11T09:31:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
            Tick(time='23-04-11T09:32:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
            Tick(time='23-04-11T09:33:00-04:00:00', pre_close=p_sell, open=p_buy, latest=p_buy, ),
        ]
        with pytest.raises(RiskControlError):
            SimulationBuilder.from_config(store_config=store_config, ticks=tickets, broker_currency='USD')

    def tearDown(self):
        CurrencyProxy._CURRENCY = set()
    