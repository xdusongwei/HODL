import unittest
from hodl.unit_test import *
from hodl.storage import *
from hodl.tools import *


class StoreTestCase(unittest.TestCase):
    """
    持仓测试验证持仓处理可以正确处理市场信号，计算正确的状态数据，
    下达预期的买卖指令等。
    """

    def test_market_not_ready(self):
        """
        验证即便时间进入新的一天，但没有正确的开盘信号前，不应将当日持仓数量(chip_count)写入状态中，
        chip_count 是一个每日盘中初始时去更新的数据之一，盘前任何时段，系统都不应进行改动这些数据项。
        """
        tickets = [
            Tick(day='23-04-10T09:29:00-04:00:00', ms='-', qs='NORMAL', pre_close=1.0, open=10.0, latest=10.0, ),
            Tick(day='23-04-10T09:29:10-04:00:00', ms='-', qs='NORMAL', pre_close=1.0, open=10.0, latest=20.0, ),
            Tick(day='23-04-10T09:29:20-04:00:00', ms='-', qs='NORMAL', pre_close=1.0, open=10.0, latest=30.0, ),
            Tick(day='23-04-10T09:29:30-04:00:00', ms='-', qs='NORMAL', pre_close=1.0, open=10.0, latest=40.0, ),
        ]

        store = SimulationBuilder.from_symbol(symbol='TEST', ticks=tickets)
        state = store.state
        assert state.chip_count is None

    def test_stock_not_ready(self):
        """
        验证即便市场信号已经是盘中交易时段(TRADING)，但是行情状态并非正常(NORMAL)，即使股价非常高，系统不应下达卖出指令。
        """
        tickets = [
            Tick(day='23-04-10T09:30:00-04:00:00', ms='TRADING', qs='', pre_close=10.0, open=10.0, latest=10.0, ),
            Tick(day='23-04-10T09:30:10-04:00:00', ms='TRADING', qs='', pre_close=10.0, open=10.0, latest=20.0, ),
            Tick(day='23-04-10T09:30:20-04:00:00', ms='TRADING', qs='', pre_close=10.0, open=10.0, latest=30.0, ),
            Tick(day='23-04-10T09:30:30-04:00:00', ms='TRADING', qs='', pre_close=10.0, open=10.0, latest=40.0, ),
        ]

        store = SimulationBuilder.from_symbol(symbol='TEST', ticks=tickets)
        state = store.state
        plan = state.plan
        assert plan.sell_volume == 0

    def test_price_not_change(self):
        """
        验证平盘开盘时，系统的一些关键持仓状态属性被正确更新，而且因为平盘，不应下达过任何买卖指令。
        """
        p = 10.0
        tickets = [
            Tick(day='23-04-10T09:30:00-04:00:00', pre_close=p, open=p, latest=p, ),
            Tick(day='23-04-10T09:30:10-04:00:00', pre_close=p, open=p, latest=p, ),
            Tick(day='23-04-10T09:30:20-04:00:00', pre_close=p, open=p, latest=p, ),
            Tick(day='23-04-10T09:30:30-04:00:00', pre_close=p, open=p, latest=p, ),
        ]

        store = SimulationBuilder.from_symbol(symbol='TEST', ticks=tickets)
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
        """
        验证暴跌开盘，系统的一些关键持仓状态属性被正确更新，而且因为股价未上涨，不应下达卖出指令。
        """
        pc = 20.0
        p = 10.0
        tickets = [
            Tick(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p, latest=p, ),
            Tick(day='23-04-10T09:30:10-04:00:00', pre_close=pc, open=p, latest=p, ),
            Tick(day='23-04-10T09:30:20-04:00:00', pre_close=pc, open=p, latest=p, ),
            Tick(day='23-04-10T09:30:30-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]

        store = SimulationBuilder.from_symbol(symbol='TEST', ticks=tickets)
        state = store.state
        plan = state.plan
        max_shares = store.store_config.max_shares
        chip_day = state.chip_day
        chip_count = state.chip_count
        assert chip_day == '2023-04-10'
        assert chip_count == max_shares
        assert plan.cleanable

    def test_price_raise_3p(self):
        """
        验证涨3%开盘，系统的一些关键持仓状态属性被正确更新，而且因为股价上涨符合预期，应下达卖出指令，产生卖出交易量。
        """
        pc = 10.0
        p = pc * 1.03
        tickets = [
            Tick(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p, latest=p, ),
            Tick(day='23-04-10T09:30:10-04:00:00', pre_close=pc, open=p, latest=p, ),
            Tick(day='23-04-10T09:30:20-04:00:00', pre_close=pc, open=p, latest=p, ),
            Tick(day='23-04-10T09:30:30-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]

        store = SimulationBuilder.from_symbol(symbol='TEST', ticks=tickets)
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
        模拟行情数据时间错乱, 推送了超过3%的旧数据, 结果应为不卖出股票。
        """
        pc = 10.0
        p0 = pc
        p3 = pc * 1.03
        tickets = [
            Tick(day='23-04-10T09:35:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Tick(day='23-04-10T09:36:10-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Tick(day='23-04-10T09:35:00-04:00:00', pre_close=pc, open=p0, latest=p3, ),
            Tick(day='23-04-10T09:37:30-04:00:00', pre_close=pc, open=p0, latest=p0, ),
        ]

        store = SimulationBuilder.from_symbol(symbol='TEST', ticks=tickets)
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
        完成买卖完整一档, 即涨3%卖出一部分, 跌回0%买回卖出的部分，并得到收益，
        """
        db = LocalDb(':memory:')
        pc = 10.0
        p0 = pc
        p3 = pc * 1.03
        tickets = [
            Tick(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Tick(day='23-04-10T09:30:10-04:00:00', pre_close=pc, open=p0, latest=p3, ),
            Tick(day='23-04-10T09:30:20-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Tick(day='23-04-10T09:30:30-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Tick(day='23-04-10T09:30:40-04:00:00', pre_close=pc, open=p0, latest=p0, ),
        ]

        store = SimulationBuilder.from_symbol(symbol='TEST', db=db, ticks=tickets)
        state = store.state
        plan = state.plan
        assert plan.earning > 0
        store.call_bars()

        VariableTools.DEBUG_CONFIG.clear()

    def test_enable(self):
        # 测试使能关闭, 不会开仓卖出
        store_config = VariableTools().store_configs['TEST']
        store_config['enable'] = False
        pc = 10.0
        p0 = pc
        p100 = pc * 2
        tickets = [
            Tick(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Tick(day='23-04-10T09:30:10-04:00:00', pre_close=pc, open=p0, latest=p100, ),
        ]

        store = SimulationBuilder.from_config(store_config=store_config, ticks=tickets)
        state = store.state
        plan = state.plan
        orders = plan.orders
        assert len(orders) == 0
        store.call_bars()

    def test_state_file(self):
        # 验证开盘后，模拟状态文件写盘动作被触发。
        store_config = VariableTools().store_configs['TEST']
        store_config['state_file_path'] = '/a/b/c.json'
        pc = 10.0
        p0 = pc
        p100 = pc * 2
        tickets = [
            Tick(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Tick(day='23-04-10T09:30:10-04:00:00', pre_close=pc, open=p0, latest=p100, ),
        ]

        store = SimulationBuilder.from_config(store_config=store_config, ticks=tickets)
        files = store.files
        assert files['/a/b/c.json']

    def test_bars(self):
        # 触发持仓线程的监控可视化状态更新动作，覆盖测试相关代码。
        pc = 10.0
        p0 = pc
        tickets = [
            Tick(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
        ]

        store = SimulationBuilder.from_symbol(symbol='TEST', ticks=tickets)
        store.call_bars()
