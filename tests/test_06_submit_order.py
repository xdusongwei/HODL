import unittest
from hodl.unit_test import *
from hodl.tools import *


class SubmitOrderTestCase(unittest.TestCase):
    def test_submit_order(self):
        # 根据持仓状态的执行计划，计算得出的价格，验证边界价格不会触发下单。
        # 差一个变动单位的价差(该测试持仓的价格精度是两位小数，那么这里即0.01)都不应下达买卖订单
        config = VariableTools().store_configs['TEST']
        pc = 10.0
        p0 = pc
        p1_sell = pc * 1.03
        p1_buy = p0
        p_not_sell = FormatTool.adjust_precision(
            p1_sell * (1 - config.sell_order_rate - 0.001),
            precision=config.precision
        )

        p_submit_sell = FormatTool.adjust_precision(
            p1_sell * (1 - config.sell_order_rate),
            precision=config.precision
        )
        p_sell = FormatTool.adjust_precision(
            p1_sell,
            precision=config.precision
        )
        p_not_buy = FormatTool.adjust_precision(
            p1_buy * (config.buy_order_rate + 1 + 0.001),
            precision=config.precision
        )
        p_submit_buy = FormatTool.adjust_precision(
            p1_buy * (config.buy_order_rate + 1),
            precision=config.precision
        )
        p_buy = pc
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=p0, ),
            Ticket(day='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p_not_sell, ),
        ]
        store = SimulationBuilder.from_symbol('TEST', tickets=tickets)
        state = store.state
        plan = state.plan
        assert len(plan.orders) == 0
        assert plan.sell_volume == 0

        tickets = [
            Ticket(day='23-04-10T09:32:00-04:00:00', pre_close=pc, open=pc, latest=p_submit_sell, ),
        ]
        store = SimulationBuilder.resume(store=store, tickets=tickets)
        state = store.state
        plan = state.plan
        assert len(plan.orders) == 1
        order = plan.orders[-1]
        assert order.is_sell and order.filled_qty == 0

        tickets = [
            Ticket(day='23-04-10T09:33:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
        ]
        store = SimulationBuilder.resume(store=store, tickets=tickets)
        state = store.state
        plan = state.plan
        assert len(plan.orders) == 1
        assert plan.orders[-1].is_filled

        tickets = [
            Ticket(day='23-04-10T09:34:00-04:00:00', pre_close=pc, open=pc, latest=p_not_buy, ),
        ]
        store = SimulationBuilder.resume(store=store, tickets=tickets)
        state = store.state
        plan = state.plan
        assert len(plan.orders) == 1

        tickets = [
            Ticket(day='23-04-10T09:35:00-04:00:00', pre_close=pc, open=pc, latest=p_submit_buy, ),
        ]
        store = SimulationBuilder.resume(store=store, tickets=tickets)
        state = store.state
        plan = state.plan
        assert len(plan.orders) == 2
        order = plan.orders[-1]
        assert order.is_buy and order.filled_qty == 0

        tickets = [
            Ticket(day='23-04-10T09:36:00-04:00:00', pre_close=pc, open=pc, latest=p_buy, ),
        ]
        store = SimulationBuilder.resume(store=store, tickets=tickets)
        state = store.state
        plan = state.plan
        assert len(plan.orders) == 2
        order = plan.orders[-1]
        assert order.is_buy and order.is_filled

