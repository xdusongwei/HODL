import unittest
import pytest
from hodl.exception_tools import *
from hodl.simulation.fake_quote import *
from hodl.simulation.main import *


class LsodTestCase(unittest.TestCase):
    def test_lsod(self):
        seal = 'ClosingChecked'
        pc = 10.0
        p = pc * 1.03
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:10-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:20-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:30-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]
        store = start_simulation(symbol='TEST', tickets=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert state.is_lsod_today
            assert not state.has_lsod_seal(seal)

        tickets = [
            Ticket(day='23-04-10T20:00:00-04:00:00', ms='CLOSING', qs='NORMAL', pre_close=pc, open=p, latest=p, ),
        ]
        store = start_simulation(store=store, tickets=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert state.is_lsod_today
            assert state.has_lsod_seal(seal)

        tickets = [
            Ticket(day='23-04-11T09:00:00-04:00:00', ms='PRE_MARKET', qs='NORMAL', pre_close=pc, open=p, latest=p, ),
        ]
        store = start_simulation(store=store, tickets=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert not state.is_lsod_today
            assert state.has_lsod_seal(seal)

        tickets = [
            Ticket(day='23-04-11T09:30:00-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]
        store = start_simulation(store=store, tickets=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert state.is_lsod_today
            assert not state.has_lsod_seal(seal)

        # 下面的例子中, 盘中没有任何下单, 所以, lsod字段应为空, 即不需要记录当天需要待检查订单
        pc = 10.0
        p = pc
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:10-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:20-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:30-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]
        store = start_simulation(symbol='TEST', tickets=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert not state.lsod
            assert not state.is_lsod_today

        tickets = [
            Ticket(day='23-04-10T20:00:00-04:00:00', ms='CLOSING', qs='NORMAL', pre_close=pc, open=p, latest=p, ),
        ]
        store = start_simulation(store=store, tickets=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert not state.lsod
            assert not state.is_lsod_today

    def test_lsod_except_at_trading(self):
        seal = 'ClosingChecked'
        pc = 10.0
        p = pc * 1.03
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:10-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:20-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:30-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]
        store = start_simulation(symbol='TEST', tickets=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert state.is_lsod_today
            assert not state.has_lsod_seal(seal)

        tickets = [
            Ticket(day='23-04-11T09:30:00-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]
        store = start_simulation(store=store, tickets=tickets, auto_run=False)
        with store:
            with pytest.raises(RiskControlError):
                store.run(output_state=False)

    def test_lsod_except_at_closing(self):
        seal = 'ClosingChecked'
        pc = 10.0
        p = pc * 1.03
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:10-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:20-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:30-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]
        store = start_simulation(symbol='TEST', tickets=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert state.is_lsod_today
            assert not state.has_lsod_seal(seal)

        tickets = [
            Ticket(day='23-04-11T20:00:00-04:00:00', ms='CLOSING', qs='NORMAL', pre_close=pc, open=p, latest=p, ),
        ]
        store = start_simulation(store=store, tickets=tickets, auto_run=False)
        with store:
            with pytest.raises(RiskControlError):
                store.run(output_state=False)

    def test_lsod_crypto(self):
        seal = 'ClosingChecked'
        pc = 30000.0
        p = pc * 1.03
        tickets = [
            Ticket(day='23-04-10T22:30:00-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T22:30:10-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T22:30:20-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T22:30:30-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]
        store = start_simulation(symbol='BTC', tickets=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert state.is_lsod_today
            assert not state.has_lsod_seal(seal)

        tickets = [
            Ticket(day='23-04-10T23:00:00-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]
        store = start_simulation(store=store, tickets=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert state.is_lsod_today
            assert state.has_lsod_seal(seal)
