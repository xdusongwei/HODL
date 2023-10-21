import unittest
from hodl.unit_test import *


class ChineseShareTestCase(unittest.TestCase):
    def test_chinese_stock_share(self):
        """
        测试当日卖出价格限制在昨收价的110%,
        并且执行计划中的卖出股数以100为倍数,
        核算全部卖出量等于总持仓量.
        """
        pc = 10.0
        p0 = pc
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p0, latest=10.0, ),
            Ticket(day='23-04-10T09:31:00-04:00:00', pre_close=pc, open=p0, latest=11.0, ),
            Ticket(day='23-04-10T09:32:00-04:00:00', pre_close=pc, open=p0, latest=12.0, ),
            Ticket(day='23-04-10T09:33:00-04:00:00', pre_close=pc, open=p0, latest=13.0, ),
            Ticket(day='23-04-10T09:34:00-04:00:00', pre_close=pc, open=p0, latest=14.0, ),
        ]
        store = start_simulation(symbol='000001', tickets=tickets)
        store_config, state, plan = store.args()
        orders = plan.orders
        table = store.build_table(store_config=store_config, plan=plan)
        assert not any(True for row in table if row.shares % 100 != 0)
        assert sum(row.shares for row in table) == store_config.max_shares
        assert not any(True for order in orders if order.avg_price > 11)
