import unittest
from hodl.simulation.fake_quote import *
from hodl.simulation.main import *
from hodl.tools import *


class StoreTestCase(unittest.TestCase):
    def test_market_not_ready(self):
        tickets = [
            Ticket(day='23-04-10T09:29:00-04:00:00', ms='-', qs='NORMAL', pre_close=1.0, open=10.0, latest=10.0, ),
            Ticket(day='23-04-10T09:29:10-04:00:00', ms='-', qs='NORMAL', pre_close=1.0, open=10.0, latest=20.0, ),
            Ticket(day='23-04-10T09:29:20-04:00:00', ms='-', qs='NORMAL', pre_close=1.0, open=10.0, latest=30.0, ),
            Ticket(day='23-04-10T09:29:30-04:00:00', ms='-', qs='NORMAL', pre_close=1.0, open=10.0, latest=40.0, ),
        ]

        store = start_simulation(symbol='TEST', tickets=tickets)
        state = store.state
        assert state.chip_count is None

    def test_stock_not_ready(self):
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', ms='TRADING', qs='', pre_close=10.0, open=10.0, latest=10.0, ),
            Ticket(day='23-04-10T09:30:10-04:00:00', ms='TRADING', qs='', pre_close=10.0, open=10.0, latest=20.0, ),
            Ticket(day='23-04-10T09:30:20-04:00:00', ms='TRADING', qs='', pre_close=10.0, open=10.0, latest=30.0, ),
            Ticket(day='23-04-10T09:30:30-04:00:00', ms='TRADING', qs='', pre_close=10.0, open=10.0, latest=40.0, ),
        ]

        store = start_simulation(symbol='TEST', tickets=tickets)
        state = store.state
        plan = state.plan
        assert plan.sell_volume == 0

    def test_price_not_change(self):
        p = 10.0
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=p, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:10-04:00:00', pre_close=p, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:20-04:00:00', pre_close=p, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:30-04:00:00', pre_close=p, open=p, latest=p, ),
        ]

        store = start_simulation(symbol='TEST', tickets=tickets)
        state = store.state
        plan = state.plan
        max_shares = store.store_config.max_shares
        chip_day = state.chip_day
        chip_count = state.chip_count
        assert chip_day == '2023-04-10'
        assert chip_count == max_shares
        assert plan.sell_volume == 0
        assert plan.buy_volume == 0
        assert plan.cleanable

    def test_price_drop(self):
        pc = 20.0
        p = 10.0
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:10-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:20-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:30-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]

        store = start_simulation(symbol='TEST', tickets=tickets)
        state = store.state
        plan = state.plan
        max_shares = store.store_config.max_shares
        chip_day = state.chip_day
        chip_count = state.chip_count
        assert chip_day == '2023-04-10'
        assert chip_count == max_shares
        assert plan.cleanable

    def test_price_raise_3p(self):
        pc = 10.0
        p = pc * 1.03
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:10-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:20-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:30-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]

        store = start_simulation(symbol='TEST', tickets=tickets)
        state = store.state
        plan = state.plan
        max_shares = store.store_config.max_shares
        chip_day = state.chip_day
        chip_count = state.chip_count
        assert chip_day == '2023-04-10'
        assert chip_count == max_shares
        assert plan.sell_volume > 0
        assert plan.buy_volume == 0
        assert not plan.cleanable

    def test_quote_error(self):
        """
        模拟行情数据时间错乱, 推送了超过3%的旧数据, 结果应为不卖出股票
        Returns
        -------

        """
        pc = 10.0
        p0 = pc
        p3 = pc * 1.03
        tickets = [
            Ticket(day='23-04-10T09:35:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Ticket(day='23-04-10T09:36:10-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Ticket(day='23-04-10T09:35:00-04:00:00', pre_close=pc, open=p0, latest=p3, ),
            Ticket(day='23-04-10T09:37:30-04:00:00', pre_close=pc, open=p0, latest=p0, ),
        ]

        store = start_simulation(symbol='TEST', tickets=tickets)
        state = store.state
        plan = state.plan
        max_shares = store.store_config.max_shares
        chip_day = state.chip_day
        chip_count = state.chip_count
        assert chip_day == '2023-04-10'
        assert chip_count == max_shares
        assert plan.sell_volume == 0
        assert plan.buy_volume == 0
        assert plan.cleanable

    def test_sell_and_buy(self):
        """
        完成买卖完整一档, 并得到收益
        Returns
        -------

        """
        pc = 10.0
        p0 = pc
        p3 = pc * 1.03
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Ticket(day='23-04-10T09:30:10-04:00:00', pre_close=pc, open=p0, latest=p3, ),
            Ticket(day='23-04-10T09:30:20-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Ticket(day='23-04-10T09:30:30-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Ticket(day='23-04-10T09:30:40-04:00:00', pre_close=pc, open=p0, latest=p0, ),
        ]

        store = start_simulation(symbol='TEST', tickets=tickets)
        state = store.state
        plan = state.plan
        assert plan.earning > 0

    def test_enable(self):
        # 测试使能关闭, 不会开仓卖出
        store_config = VariableTools().store_configs['TEST']
        store_config['enable'] = False
        pc = 10.0
        p0 = pc
        p100 = pc * 2
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Ticket(day='23-04-10T09:30:10-04:00:00', pre_close=pc, open=p0, latest=p100, ),
        ]

        store = start_simulation(store_config=store_config, tickets=tickets)
        state = store.state
        plan = state.plan
        orders = plan.orders
        assert len(orders) == 0

    def test_state_file(self):
        store_config = VariableTools().store_configs['TEST']
        store_config['state_file_path'] = '/a/b/c.json'
        pc = 10.0
        p0 = pc
        p100 = pc * 2
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Ticket(day='23-04-10T09:30:10-04:00:00', pre_close=pc, open=p0, latest=p100, ),
        ]

        store = start_simulation(store_config=store_config, tickets=tickets)
        files = store.files
        assert files['/a/b/c.json']

    def test_bars(self):
        pc = 10.0
        p0 = pc
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
        ]

        store = start_simulation(symbol='TEST', tickets=tickets)
        store.primary_bar()
        store.secondary_bar()
        store.warning_alert_bar()
