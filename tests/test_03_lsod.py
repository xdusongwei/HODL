import unittest
import pytest
from hodl.exception_tools import *
from hodl.unit_test import *


class LsodTestCase(unittest.TestCase):
    def test_lsod(self):
        # 第一天触发卖出, 并且运行到收盘时段, 第二天盘中再触发买入, 整个过程lsod检测符合正常预期，应通过。
        seal = 'ClosingChecked'
        pc = 10.0
        p0 = pc
        p3 = pc * 1.03
        tickets = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=p3, ),
            Tick(time='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p3, ),
            Tick(time='23-04-10T09:32:00-04:00:00', pre_close=pc, open=pc, latest=p3, ),
            Tick(time='23-04-10T09:33:00-04:00:00', pre_close=pc, open=pc, latest=p3, ),
        ]
        store = SimulationBuilder.from_symbol(symbol='TEST', ticks=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert state.is_lsod_today
            assert not state.has_lsod_seal(seal)

        tickets = [
            Tick(time='23-04-10T20:00:00-04:00:00', ms='CLOSING', pre_close=pc, open=pc, latest=p3, ),
        ]
        store = SimulationBuilder.resume(store=store, ticks=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert state.is_lsod_today
            assert state.has_lsod_seal(seal)

        tickets = [
            Tick(time='23-04-11T09:00:00-04:00:00', ms='PRE_MARKET', pre_close=pc, open=pc, latest=p3, ),
        ]
        store = SimulationBuilder.resume(store=store, ticks=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert not state.is_lsod_today
            assert state.has_lsod_seal(seal)

        tickets = [
            Tick(time='23-04-11T09:30:00-04:00:00', pre_close=p3, open=p0, latest=p0, ),
            Tick(time='23-04-11T09:31:00-04:00:00', pre_close=p3, open=p0, latest=p0, ),
        ]
        store = SimulationBuilder.resume(store=store, ticks=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert state.is_lsod_today
            assert not state.has_lsod_seal(seal)

    def test_lsod_empty_orders(self):
        # 下面的例子中, 盘中没有任何下单, 所以, lsod字段应为空, 即不需要设定收盘时需要检查活动订单的状态。
        pc = 10.0
        p = pc
        tickets = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p, latest=p, ),
            Tick(time='23-04-10T09:30:10-04:00:00', pre_close=pc, open=p, latest=p, ),
            Tick(time='23-04-10T09:30:20-04:00:00', pre_close=pc, open=p, latest=p, ),
            Tick(time='23-04-10T09:30:30-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]
        store = SimulationBuilder.from_symbol(symbol='TEST', ticks=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert not state.lsod
            assert not state.is_lsod_today

        tickets = [
            Tick(time='23-04-10T20:00:00-04:00:00', ms='CLOSING', qs='NORMAL', pre_close=pc, open=p, latest=p, ),
        ]
        store = SimulationBuilder.resume(store=store, ticks=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert not state.lsod
            assert not state.is_lsod_today

    def test_lsod_except_at_trading(self):
        # 验证第一天下单，但是未运行到收盘时段，没有检查活动订单的状态，第二天开盘，lsod检查应触发风控异常。
        seal = 'ClosingChecked'
        pc = 10.0
        p = pc * 1.03
        tickets = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p, latest=p, ),
            Tick(time='23-04-10T09:30:10-04:00:00', pre_close=pc, open=p, latest=p, ),
            Tick(time='23-04-10T09:30:20-04:00:00', pre_close=pc, open=p, latest=p, ),
            Tick(time='23-04-10T09:30:30-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]
        store = SimulationBuilder.from_symbol(symbol='TEST', ticks=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert state.is_lsod_today
            assert not state.has_lsod_seal(seal)

        tickets = [
            Tick(time='23-04-11T09:30:00-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]
        store = SimulationBuilder.resume(store=store, ticks=tickets, auto_run=False)
        with store:
            with pytest.raises(RiskControlError):
                store.run(output_state=False)

    def test_lsod_except_at_closing(self):
        # 验证第一天下单，但是未运行到收盘时段，没有检查活动订单的状态，第二天收盘恢复系统运行，lsod检查应触发风控异常，
        # 即验证当日的订单检查必须是当天的收盘时段。
        seal = 'ClosingChecked'
        pc = 10.0
        p = pc * 1.03
        tickets = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p, latest=p, ),
            Tick(time='23-04-10T09:30:10-04:00:00', pre_close=pc, open=p, latest=p, ),
            Tick(time='23-04-10T09:30:20-04:00:00', pre_close=pc, open=p, latest=p, ),
            Tick(time='23-04-10T09:30:30-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]
        store = SimulationBuilder.from_symbol(symbol='TEST', ticks=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert state.is_lsod_today
            assert not state.has_lsod_seal(seal)

        tickets = [
            Tick(time='23-04-11T20:00:00-04:00:00', ms='CLOSING', qs='NORMAL', pre_close=pc, open=p, latest=p, ),
        ]
        store = SimulationBuilder.resume(store=store, ticks=tickets, auto_run=False)
        with store:
            with pytest.raises(RiskControlError):
                store.run(output_state=False)

    def test_lsod_crypto(self):
        # 加密货币的持仓中人工设定的一天收盘时间段配置，应可以正确处理订单状态检查。
        seal = 'ClosingChecked'
        pc = 30000.0
        p = pc * 1.03
        tickets = [
            Tick(time='23-04-10T22:30:00-04:00:00', pre_close=pc, open=p, latest=p, ),
            Tick(time='23-04-10T22:30:10-04:00:00', pre_close=pc, open=p, latest=p, ),
            Tick(time='23-04-10T22:30:20-04:00:00', pre_close=pc, open=p, latest=p, ),
            Tick(time='23-04-10T22:30:30-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]
        store = SimulationBuilder.from_symbol(symbol='BTC', ticks=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert state.is_lsod_today
            assert not state.has_lsod_seal(seal)

        tickets = [
            Tick(time='23-04-10T23:00:00-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]
        store = SimulationBuilder.resume(store=store, ticks=tickets, auto_run=False)
        with store:
            store.run()
            state = store.state
            assert state.is_lsod_today
            assert state.has_lsod_seal(seal)
