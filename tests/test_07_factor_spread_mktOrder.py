import unittest
from hodl.simulation.fake_quote import *
from hodl.simulation.main import *
from hodl.tools import *


class OrderTestCase(unittest.TestCase):
    def test_market_price_order(self):
        config = VariableTools().store_configs['TEST']
        config['market_price_rate'] = 0.02
        pc = 10.0
        p_sell = pc * 1.03 * (1 + config.market_price_rate) + 0.01
        p_buy = pc * 1.00 * (1 - config.market_price_rate) - 0.01
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=pc, ),
            Ticket(day='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Ticket(day='23-04-10T09:32:00-04:00:00', pre_close=pc, open=pc, latest=p_buy, ),
        ]
        store = start_simulation(store_config=config, tickets=tickets)
        state = store.state
        plan = state.plan
        assert len(plan.orders) == 2
        sell_order, buy_order = plan.orders[0], plan.orders[1]
        assert sell_order.limit_price is None
        assert sell_order.is_filled
        assert buy_order.limit_price is None
        assert buy_order.is_filled

    def test_price_rate(self):
        config = VariableTools().store_configs['TEST']
        config['price_rate'] = 0.5
        pc = 10.0
        p_sell = pc * 1.015
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=pc, ),
            Ticket(day='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Ticket(day='23-04-10T09:32:00-04:00:00', pre_close=pc, open=pc, latest=pc, ),
        ]
        store = start_simulation(store_config=config, tickets=tickets)
        state = store.state
        plan = state.plan
        assert len(plan.orders) == 2
        sell_order, buy_order = plan.orders[0], plan.orders[1]
        assert sell_order.is_sell
        assert sell_order.is_filled
        assert buy_order.is_buy
        assert buy_order.is_filled

    def test_spread_by_points(self):
        config = VariableTools().store_configs['TEST']
        config['sell_spread'] = 0.03
        config['buy_spread'] = 0.04
        pc = 10.0
        p_sell = pc * 1.03 + 0.03
        p_buy = pc - 0.04
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=pc, ),
            Ticket(day='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Ticket(day='23-04-10T09:32:00-04:00:00', pre_close=pc, open=pc, latest=p_buy, ),
        ]
        store = start_simulation(store_config=config, tickets=tickets)
        state = store.state
        plan = state.plan
        assert len(plan.orders) == 2
        sell_order, buy_order = plan.orders[0], plan.orders[1]
        assert sell_order.spread == 0.03
        assert buy_order.spread == 0.04

    def test_spread_by_rate(self):
        config = VariableTools().store_configs['TEST']
        config['sell_spread_rate'] = None
        config['buy_spread_rate'] = None
        config['sell_spread_rate'] = 0.003
        config['buy_spread_rate'] = 0.004
        pc = 10.0
        p_sell = pc * 1.03 * (1 + 0.003)
        p_buy = pc * (1 - 0.004)
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=pc, ),
            Ticket(day='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Ticket(day='23-04-10T09:32:00-04:00:00', pre_close=pc, open=pc, latest=p_buy, ),
        ]
        store = start_simulation(store_config=config, tickets=tickets)
        state = store.state
        plan = state.plan
        assert len(plan.orders) == 2
        sell_order, buy_order = plan.orders[0], plan.orders[1]
        assert sell_order.spread == 0.03
        assert buy_order.spread == 0.04

    def test_custom_factors(self):
        config = VariableTools().store_configs['TEST']
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
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=pc, ),
            Ticket(day='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p10, ),
            Ticket(day='23-04-10T09:32:00-04:00:00', pre_close=pc, open=pc, latest=p20, ),
            Ticket(day='23-04-10T09:33:00-04:00:00', pre_close=pc, open=pc, latest=p10, ),
        ]
        store = start_simulation(store_config=config, tickets=tickets)
        state = store.state
        plan = state.plan
        assert len(plan.orders) == 3
        sell1, sell2, buy = plan.orders[0], plan.orders[1], plan.orders[2]
        assert sell1.qty >= sell_order_qty
        assert sell2.qty >= sell_order_qty
        assert buy.qty == max_shares
