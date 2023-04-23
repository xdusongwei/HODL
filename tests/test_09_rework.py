import unittest
from hodl.tools import *
from hodl.simulation.fake_quote import *
from hodl.simulation.main import *


class ReworkTestCase(unittest.TestCase):
    def test_rework(self):
        config = VariableTools().store_configs['TEST']
        config['rework_level'] = 1
        pc = 10.0
        p0 = pc
        p3 = pc * 1.03
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Ticket(day='23-04-10T09:31:00-04:00:00', pre_close=pc, open=p0, latest=p3, ),
            Ticket(day='23-04-10T09:32:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Ticket(day='23-04-10T09:33:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Ticket(day='23-04-10T09:34:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
        ]
        store = start_simulation(store_config=config, tickets=tickets)
        _, _, plan = store.args()
        assert plan.earning
        assert plan.rework_price == p3
