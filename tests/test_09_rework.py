import unittest
from hodl.tools import *
from hodl.unit_test import *


class ReworkTestCase(unittest.TestCase):
    def test_rework(self):
        # 验证清除持仓状态功能计算了正确的目标价格
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
        store = SimulationBuilder.from_config(store_config=config, tickets=tickets)
        _, _, plan = store.args()
        assert plan.earning
        assert plan.rework_price == p3
