from hodl.unit_test import *
from hodl.storage import *


class BasePriceTestCase(unittest.TestCase):
    def test_bp_pre_close(self):
        # 验证开盘后涨3%时，根据昨收为基准价格而卖出。
        pc = 10.0
        p0 = pc
        p3 = pc * 1.03
        ticks = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=p0, ),
            Tick(time='23-04-10T09:30:01-04:00:00', pre_close=pc, open=pc, latest=p3, ),
        ]
        db = LocalDb(':memory:')
        store = SimulationBuilder.from_symbol('TEST', db=db, ticks=ticks)
        state = store.state
        plan = state.plan
        assert plan.sell_volume > 0

    def test_bp_last_buy(self):
        # 验证上次买回价格可以作为基准价格，

        # 首先第一天制造一次涨3%卖，跌5%买回的记录，这样上次买回价应该为 pn5
        pc = 10.0
        p0 = pc
        p3 = pc * 1.03
        pn5 = pc * 0.95
        ticks = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=p0, ),
            Tick(time='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p3, ),
            Tick(time='23-04-10T09:32:00-04:00:00', pre_close=pc, open=pc, latest=pn5, ),
            Tick(time='23-04-10T09:33:00-04:00:00', pre_close=pc, open=pc, latest=pn5, ),
            Tick(time='23-04-10T09:33:00-04:00:00', pre_close=pc, open=pc, latest=pn5, ),
            Tick(time='23-04-10T20:00:00-04:00:00', ms='CLOSING', pre_close=pc, open=pc, latest=pn5, ),
        ]
        db = LocalDb(':memory:')
        store = SimulationBuilder.from_symbol('TEST', db=db, ticks=ticks)
        state = store.state
        plan = state.plan
        assert plan.earning
        assert plan.buy_back_price == pn5

        # 第二天从跌5%价格恢复到0%的价格，完全可以根据上次买回价格为基准价格，触发新的卖出订单。
        ticks = [
            Tick(time='23-04-11T09:30:00-04:00:00', pre_close=pn5, open=pn5, latest=p0, ),
            Tick(time='23-04-11T09:31:00-04:00:00', pre_close=pn5, open=pn5, latest=p0, ),
        ]
        store = SimulationBuilder.resume(store=store, ticks=ticks)
        state = store.state
        plan = state.plan
        assert plan.sell_volume > 0
        assert plan.orders[0].avg_price == p0

    def test_bp_day_low(self):
        # 验证当日最低价格可以作为基准价格。
        # 当日最低价为跌5%，若现价恢复到0%，完全可以根据当日最低价为基准价格，触发新的卖出订单。
        pc = 10.0
        p0 = pc
        pn5 = pc * 0.95

        ticks = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=pc, latest=pn5, low=pn5, ),
            Tick(time='23-04-10T09:31:00-04:00:00', pre_close=pc, open=pc, latest=p0, low=pn5, ),
        ]
        db = LocalDb(':memory:')
        store = SimulationBuilder.from_symbol('TEST', db=db, ticks=ticks)
        state = store.state
        plan = state.plan
        assert plan.sell_volume > 0
        assert plan.orders[0].avg_price == p0
