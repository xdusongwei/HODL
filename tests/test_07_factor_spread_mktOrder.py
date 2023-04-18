import unittest
from hodl.simulation.fake_quote import *
from hodl.simulation.main import *
from hodl.tools import *


class OrderTestCase(unittest.TestCase):
    def test_market_price_order(self):
        config = VariableTools().store_configs['MKT']
        pc = 10.0
        p_sell = pc * 1.03 * (1 + config.market_price_rate) + 0.01
        p_buy = pc * 1.00 * (1 - config.market_price_rate) - 0.01
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=pc, ),
            Ticket(day='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p_sell, ),
            Ticket(day='23-04-10T09:32:00-04:00:00', pre_close=pc, open=pc, latest=p_buy, ),
        ]
        store = start_simulation('MKT', tickets=tickets)
        state = store.state
        plan = state.plan
        assert len(plan.orders) == 2
        sell_order, buy_order = plan.orders[0], plan.orders[1]
        assert sell_order.limit_price is None
        assert sell_order.is_filled
        assert buy_order.limit_price is None
        assert buy_order.is_filled
