import unittest
from hodl.unit_test import *
from hodl.storage import *


class BasePriceTestCase(unittest.TestCase):
    def test_bp_pre_close(self):
        pc = 10.0
        p0 = pc
        p3 = pc * 1.03
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=p0, ),
            Ticket(day='23-04-10T09:30:01-04:00:00', pre_close=pc, open=pc, latest=p3, ),
        ]
        db = LocalDb(':memory:')
        store = start_simulation('TEST', db=db, tickets=tickets)
        state = store.state
        plan = state.plan
        assert plan.sell_volume > 0

    def test_bp_last_buy(self):
        pc = 10.0
        p0 = pc
        p3 = pc * 1.03
        pn5 = pc * 0.95
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=p0, ),
            Ticket(day='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p3, ),
            Ticket(day='23-04-10T09:32:00-04:00:00', pre_close=pc, open=pc, latest=pn5, ),
            Ticket(day='23-04-10T09:33:00-04:00:00', pre_close=pc, open=pc, latest=pn5, ),
            Ticket(day='23-04-10T09:33:00-04:00:00', pre_close=pc, open=pc, latest=pn5, ),
            Ticket(day='23-04-10T20:00:00-04:00:00', ms='CLOSING', pre_close=pc, open=pc, latest=pn5, ),
        ]
        db = LocalDb(':memory:')
        store = start_simulation('TEST', db=db, tickets=tickets)
        state = store.state
        plan = state.plan
        assert plan.earning
        assert plan.buy_back_price == pn5
        tickets = [
            Ticket(day='23-04-11T09:30:00-04:00:00', pre_close=pn5, open=pn5, latest=p0, ),
            Ticket(day='23-04-11T09:31:00-04:00:00', pre_close=pn5, open=pn5, latest=p0, ),
        ]
        store = start_simulation(store=store, db=db, tickets=tickets)
        state = store.state
        plan = state.plan
        assert plan.sell_volume > 0
        assert plan.orders[0].avg_price == p0

    def test_bp_day_low(self):
        pc = 10.0
        p0 = pc
        pn5 = pc * 0.95

        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=pn5, low=pn5, ),
            Ticket(day='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p0, low=pn5, ),
        ]
        db = LocalDb(':memory:')
        store = start_simulation('TEST', db=db, tickets=tickets)
        state = store.state
        plan = state.plan
        assert plan.sell_volume > 0
        assert plan.orders[0].avg_price == p0
