import pytest
from hodl.exception_tools import *
from hodl.unit_test import *
from hodl.tools import *


class OrderTestCase(HodlTestCase):
    def test_market_price_order(self):
        # 验证股价已按照设定，大幅偏离执行计划的价格，买卖订单应使用市价单。
        config = self.config().store_configs['TEST']
        config['market_price_rate'] = 0.02
        pc = 10.0
        p_sell = FormatTool.adjust_precision(pc * 1.03 * (1 + config.market_price_rate) + 0.02, 2)
        p_buy = FormatTool.adjust_precision(pc * 1.00 * (1 - config.market_price_rate) - 0.02, 2)
        tickets = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=pc, ),
            Tick(time='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Tick(time='23-04-10T09:32:00-04:00:00', pre_close=pc, open=pc, latest=p_buy, ),
        ]
        store = SimulationBuilder.from_config(store_config=config, ticks=tickets)
        state = store.state
        plan = state.plan
        assert len(plan.orders) == 2
        sell_order, buy_order = plan.orders[0], plan.orders[1]
        assert sell_order.limit_price is None
        assert sell_order.is_filled
        assert buy_order.limit_price is None
        assert buy_order.is_filled

    def test_market_price_order_risk_control(self):
        # 验证股价已按照设定，大幅偏离执行计划的价格，买卖订单应使用市价单, 但成交价格异常导致触发了风控错误。
        config = self.config().store_configs['TEST']
        config['market_price_rate'] = 0.02
        pc = 10.0
        p_sell = FormatTool.adjust_precision(pc * 1.03 * (1 + config.market_price_rate) + 0.02, 2)
        tickets = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=pc, ),
            Tick(time='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
        ]
        store = SimulationBuilder.from_config(store_config=config, ticks=tickets)
        state = store.state
        plan = state.plan
        assert len(plan.orders) == 1
        sell_order = plan.orders[0]
        assert sell_order.limit_price is None
        assert sell_order.is_filled
        assert sell_order.protect_price == pc * 1.03
        # 修改订单的成交价格为等于保护限价, 继续运行不会有异常
        sell_order.avg_price = sell_order.protect_price
        tickets = [
            Tick(time='23-04-10T09:32:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
        ]
        store = SimulationBuilder.resume(store=store, ticks=tickets)
        # 修改订单的成交价格为低于保护限价, 继续运行触发风控异常
        sell_order.avg_price = FormatTool.adjust_precision(sell_order.protect_price - 0.01, 2)
        tickets = [
            Tick(time='23-04-10T09:33:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
        ]
        with pytest.raises(RiskControlError):
            SimulationBuilder.resume(store=store, ticks=tickets)

    def test_price_rate(self):
        # 验证 price_rate 设定对执行计划的幅度进行缩放，
        # 默认涨3%开始卖出，由于缩放系数是 0.5，那么应涨1.5%时应卖出，保持涨0%(0% * 0.5 = 0%)时买入。
        config = self.config().store_configs['TEST']
        config['price_rate'] = 0.5
        pc = 10.0
        p_sell = pc * 1.015
        tickets = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=pc, ),
            Tick(time='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Tick(time='23-04-10T09:32:00-04:00:00', pre_close=pc, open=pc, latest=pc, ),
        ]
        store = SimulationBuilder.from_config(store_config=config, ticks=tickets)
        state = store.state
        plan = state.plan
        assert len(plan.orders) == 2
        sell_order, buy_order = plan.orders[0], plan.orders[1]
        assert sell_order.is_sell
        assert sell_order.is_filled
        assert buy_order.is_buy
        assert buy_order.is_filled

    def test_spread_by_points(self):
        # 验证点差(交易所成本，固定费用)被计算在执行计划的价格中。
        config = self.config().store_configs['TEST']
        config['sell_spread'] = 0.03
        config['buy_spread'] = 0.04
        pc = 10.0
        p_sell = pc * 1.03 + 0.03
        p_buy = pc - 0.04
        tickets = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=pc, ),
            Tick(time='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Tick(time='23-04-10T09:32:00-04:00:00', pre_close=pc, open=pc, latest=p_buy, ),
        ]
        store = SimulationBuilder.from_config(store_config=config, ticks=tickets)
        state = store.state
        plan = state.plan
        assert len(plan.orders) == 2
        sell_order, buy_order = plan.orders[0], plan.orders[1]
        assert sell_order.spread == 0.03
        assert buy_order.spread == 0.04

    def test_spread_by_rate(self):
        # 验证点差(交易所成本，按预期价格乘以设定的费用比例)被计算在执行计划的价格中。
        config = self.config().store_configs['TEST']
        config['sell_spread_rate'] = None
        config['buy_spread_rate'] = None
        config['sell_spread_rate'] = 0.003
        config['buy_spread_rate'] = 0.004
        pc = 10.0
        p_sell = pc * 1.03 * (1 + 0.003)
        p_buy = pc * (1 - 0.004)
        tickets = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=pc, ),
            Tick(time='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Tick(time='23-04-10T09:32:00-04:00:00', pre_close=pc, open=pc, latest=p_buy, ),
        ]
        store = SimulationBuilder.from_config(store_config=config, ticks=tickets)
        state = store.state
        plan = state.plan
        assert len(plan.orders) == 2
        sell_order, buy_order = plan.orders[0], plan.orders[1]
        assert sell_order.spread == 0.03
        assert buy_order.spread == 0.04

    def test_custom_factors(self):
        # 验证自定义因子表可以计算出自定义的执行计划，并且可以正常下单使用。
        config = self.config().store_configs['TEST']
        config['factors'] = [
            [1.1, 1.0, 1.0, ],
            [1.2, 1.1, 1.0, ],
        ]
        max_shares = config.max_shares
        sell_order_qty = max_shares // 2
        pc = 10.0
        p10 = pc * 1.1
        p20 = pc * 1.2
        tickets = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=pc, ),
            Tick(time='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p10, ),
            Tick(time='23-04-10T09:32:00-04:00:00', pre_close=pc, open=pc, latest=p20, ),
            Tick(time='23-04-10T09:33:00-04:00:00', pre_close=pc, open=pc, latest=p10, ),
        ]
        store = SimulationBuilder.from_config(store_config=config, ticks=tickets)
        state = store.state
        plan = state.plan
        assert len(plan.orders) == 3
        sell1, sell2, buy = plan.orders[0], plan.orders[1], plan.orders[2]
        assert sell1.qty >= sell_order_qty
        assert sell2.qty >= sell_order_qty
        assert buy.qty == max_shares
