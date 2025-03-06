from hodl.unit_test import *


class OddOrderTestCase(HodlTestCase):
    """
    验证部成现象出现时系统的应对情况
    """

    def test_sell_odd(self):
        # 这里预设了一种场景, 假设卖出到第二档, 但是第二档只是部分成交, 比如成交了1股
        # 接着股价掉回 0% 位置, 触发了第一档的买入价格条件
        # 在第一档数量买回后, 需要补充第二档部分成交的部分, 即那1股, 使用市价单.
        pc = 10.0
        p0 = pc
        p3 = pc * 1.03
        p55 = pc * 1.055

        ticks = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Tick(time='23-04-10T09:35:00-04:00:00', pre_close=pc, open=p0, latest=p3, ),
        ]
        store = SimulationBuilder.from_symbol(symbol='TEST', ticks=ticks)
        ticks = [
            Tick(time='23-04-10T09:40:00-04:00:00', pre_close=pc, open=p0, latest=p55, ),
        ]
        with store.order_behavior(filled_qty=1, freeze_qty=True):
            SimulationBuilder.resume(store, ticks)

        ticks = [
            Tick(time='23-04-10T09:45:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Tick(time='23-04-10T09:50:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Tick(time='23-04-10T09:55:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
        ]
        SimulationBuilder.resume(store, ticks)

        plan = store.state.plan
        orders = plan.orders
        assert len(orders) == 4

        odd_sell_order = orders[1]
        lv1_buy_order, odd_buy_order = orders[2], orders[3]

        assert odd_sell_order.is_sell
        assert odd_sell_order.filled_qty == 1

        assert lv1_buy_order.is_buy
        assert lv1_buy_order.is_filled

        assert odd_buy_order.is_buy
        assert odd_buy_order.is_filled
        assert odd_buy_order.filled_qty == 1
        assert odd_buy_order.limit_price is None

        assert plan.earning > 0

    def test_sell_odd_multi_day(self):
        # 类似上一个用例, 但是第一天第二档部成1股, 第二天继续部成第二档1股
        # 因为是在第二天进行的买入, 所以, 当时套利的买入订单, 即第一个买入订单,
        # 订单下达的数量应为 第一档卖出量 + 第一天的卖出部成量,
        # 严格来说, 需要下达的是已结算的总卖减去总买的量.
        # 因此, 第二天的第二个买入订单, 只需补充买回1股, 就是当天哪个部成的差量即可.
        pc = 10.0
        p0 = pc
        p3 = pc * 1.03
        p55 = pc * 1.055

        ticks = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Tick(time='23-04-10T09:35:00-04:00:00', pre_close=pc, open=p0, latest=p3, ),
        ]
        store = SimulationBuilder.from_symbol(symbol='TEST', ticks=ticks)

        ticks = [
            Tick(time='23-04-10T09:40:00-04:00:00', pre_close=pc, open=p0, latest=p55, ),
            Tick(time='23-04-10T16:00:00-04:00:00', ms='CLOSING', pre_close=pc, open=p55, latest=p55, ),
            Tick(time='23-04-11T09:30:00-04:00:00', pre_close=p55, open=p55, latest=p55, ),
        ]
        with store.order_behavior(filled_qty=1, freeze_qty=True):
            SimulationBuilder.resume(store, ticks)

        ticks = [
            Tick(time='23-04-11T09:40:00-04:00:00', pre_close=p55, open=p55, latest=p0, ),
            Tick(time='23-04-11T09:45:00-04:00:00', pre_close=p55, open=p55, latest=p0, ),
            Tick(time='23-04-11T09:50:00-04:00:00', pre_close=p55, open=p55, latest=p0, ),
        ]
        SimulationBuilder.resume(store, ticks)

        plan = store.state.plan
        orders = plan.orders
        assert len(orders) == 5

        lv1_buy_order, odd_buy_order = orders[3], orders[4]

        assert lv1_buy_order.is_buy
        assert lv1_buy_order.is_filled

        assert odd_buy_order.is_buy
        assert odd_buy_order.is_filled
        assert odd_buy_order.filled_qty == 1
        assert odd_buy_order.limit_price is None

        assert plan.earning > 0

    def test_sell_odd_multi_day_2(self):
        # 类似上一个用例, 但是第一天第二档部成2000股, 第二天成交另一半, 而且第二天正常卖出了第三档, 且跌回买入价
        pc = 10.0
        p0 = pc
        p3 = pc * 1.03
        p55 = pc * 1.055
        p9 = pc * 1.09

        ticks = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Tick(time='23-04-10T09:35:00-04:00:00', pre_close=pc, open=p0, latest=p3, ),
        ]
        store = SimulationBuilder.from_symbol(symbol='TEST', ticks=ticks)

        ticks = [
            Tick(time='23-04-10T09:40:00-04:00:00', pre_close=pc, open=p0, latest=p55, ),
            Tick(time='23-04-10T16:00:00-04:00:00', ms='CLOSING', pre_close=pc, open=p55, latest=p55, ),
        ]
        with store.order_behavior(filled_qty=2000):
            SimulationBuilder.resume(store, ticks)

        ticks = [
            Tick(time='23-04-11T09:30:00-04:00:00', pre_close=p55, open=p55, latest=p55, ),
            Tick(time='23-04-11T09:35:00-04:00:00', pre_close=p55, open=p55, latest=p9, ),
            Tick(time='23-04-11T09:40:00-04:00:00', pre_close=p55, open=p55, latest=p3, ),
            Tick(time='23-04-11T09:45:00-04:00:00', pre_close=p55, open=p55, latest=p3, ),
            Tick(time='23-04-11T09:50:00-04:00:00', pre_close=p55, open=p55, latest=p3, ),
        ]
        SimulationBuilder.resume(store, ticks)

        plan = store.state.plan
        orders = plan.orders
        assert len(orders) == 5
        qty_seq = [order.filled_qty for order in orders]
        level_seq = [order.level for order in orders]
        sell_seq = [order.is_sell for order in orders]
        assert qty_seq == [4545, 2000, 2545, 5455, 14545, ]
        assert level_seq == [1, 2, 2, 3, 3, ]
        assert sell_seq == [True, True, True, True, False, ]

    def test_buy_odd(self):
        # 预设首先上涨到+3%, 卖出第一档
        # 之后跌回0%, 但是买入部成1股
        # 验证第二天继续0%时, 下达买入的数量是缺失的买入量
        pc = 10.0
        p0 = pc
        p3 = pc * 1.03

        ticks = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Tick(time='23-04-10T09:35:00-04:00:00', pre_close=pc, open=p0, latest=p3, ),
        ]
        store = SimulationBuilder.from_symbol(symbol='TEST', ticks=ticks)

        ticks = [
            Tick(time='23-04-10T09:40:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Tick(time='23-04-10T16:00:00-04:00:00', ms='CLOSING', pre_close=pc, open=p0, latest=p0, ),
        ]
        with store.order_behavior(filled_qty=1):
            SimulationBuilder.resume(store, ticks)

        ticks = [
            Tick(time='23-04-11T09:30:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Tick(time='23-04-11T09:35:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Tick(time='23-04-11T09:40:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
        ]
        SimulationBuilder.resume(store, ticks)

        plan = store.state.plan
        orders = plan.orders
        assert len(orders) == 3
        qty_seq = [order.filled_qty for order in orders]
        level_seq = [order.level for order in orders]
        sell_seq = [order.is_sell for order in orders]
        assert qty_seq == [4545, 1, 4544, ]
        assert level_seq == [1, 1, 1, ]
        assert sell_seq == [True, False, False, ]

    def test_sell_odd_buy_odd(self):
        # 同花顺用例
        # 这是一种非常极端的情形, 既出现了卖出部成现象, 也出现了买入部成
        # 系统需要正确计算下单的数量: 根据已结算的总卖总买量差额去进行正确下单.
        # 第一天: 3%卖出, 5.5%卖出1股,
        # 第二天: 0%买入一股
        # 第三天: 0%买入4545股
        pc = 10.0
        p0 = pc
        p3 = pc * 1.03
        p55 = pc * 1.055
        ticks = {
            'day1sellLv1': [
                Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
                Tick(time='23-04-10T09:35:00-04:00:00', pre_close=pc, open=p0, latest=p3, ),
            ],
            'day1sellLv2': [
                Tick(time='23-04-10T09:40:00-04:00:00', pre_close=pc, open=p0, latest=p55, ),
                Tick(time='23-04-10T16:00:00-04:00:00', ms='CLOSING', pre_close=pc, open=p0, latest=p55, ),
            ],
            'day2': [
                Tick(time='23-04-11T09:30:00-04:00:00', pre_close=p55, open=p55, latest=p0, ),
                Tick(time='23-04-11T09:35:00-04:00:00', pre_close=p55, open=p55, latest=p0, ),
                Tick(time='23-04-11T16:00:00-04:00:00', ms='CLOSING', pre_close=p55, open=p55, latest=p0, ),
            ],
            'day3': [
                Tick(time='23-04-12T09:30:00-04:00:00', pre_close=p0, open=p0, latest=p0, ),
                Tick(time='23-04-12T09:35:00-04:00:00', pre_close=p0, open=p0, latest=p0, ),
                Tick(time='23-04-12T09:40:00-04:00:00', pre_close=p0, open=p0, latest=p0, ),
            ],
        }
        store = SimulationBuilder.from_symbol(symbol='TEST', ticks=ticks['day1sellLv1'])
        with store.order_behavior(filled_qty=1):
            SimulationBuilder.resume(store, ticks['day1sellLv2'])
            SimulationBuilder.resume(store, ticks['day2'])
        SimulationBuilder.resume(store, ticks['day3'])

        plan = store.state.plan
        orders = plan.orders
        assert len(orders) == 4
        qty_seq = [order.filled_qty for order in orders]
        level_seq = [order.level for order in orders]
        sell_seq = [order.is_sell for order in orders]
        assert qty_seq == [4545, 1, 1, 4545, ]
        assert level_seq == [1, 2, 1, 1, ]
        assert sell_seq == [True, True, False, False, ]

    def test_sell_odd_buy_odd_with_cancel(self):
        # 同花大顺用例
        # 这是一种非常极端的情形, 既出现了卖出部成, 也出现了买入部成, 同时存在日内出现了撤单的场景
        # 第一天: 3%卖出, 5.5%卖出4544股,
        # 第二天: 0%买入4544股, 5.5%卖出1股, 接近9%产生待成交卖单, 然后1.5%买回, 取消0%的买单
        pc = 10.0
        p0 = pc
        p15 = pc * 1.015
        p3 = pc * 1.03
        p55 = pc * 1.055
        p9 = pc * 1.089
        ticks = {
            'day1sellLv1': [
                Tick(time='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
                Tick(time='23-04-10T09:35:00-04:00:00', pre_close=pc, open=p0, latest=p3, ),
            ],
            'day1sellLv2': [
                Tick(time='23-04-10T09:40:00-04:00:00', pre_close=pc, open=p0, latest=p55, ),
                Tick(time='23-04-10T16:00:00-04:00:00', ms='CLOSING', pre_close=pc, open=p0, latest=p55, ),
            ],
            'day2buyLv1': [
                Tick(time='23-04-11T09:30:00-04:00:00', pre_close=p55, open=p55, latest=p0, ),
                Tick(time='23-04-11T09:35:00-04:00:00', pre_close=p55, open=p55, latest=p0, ),
                Tick(time='23-04-11T09:40:00-04:00:00', pre_close=p55, open=p55, latest=p0, ),
            ],
            'day2sellLv2': [
                Tick(time='23-04-11T10:30:00-04:00:00', pre_close=p55, open=p55, latest=p55, ),
                Tick(time='23-04-11T10:35:00-04:00:00', pre_close=p55, open=p55, latest=p9, ),
            ],
            'day2buyLv2': [
                Tick(time='23-04-11T10:40:00-04:00:00', pre_close=p55, open=p55, latest=p15, ),
                Tick(time='23-04-11T10:45:00-04:00:00', pre_close=p55, open=p55, latest=p15, ),
                Tick(time='23-04-11T10:50:00-04:00:00', pre_close=p55, open=p55, latest=p15, ),
            ],
        }
        store = SimulationBuilder.from_symbol(symbol='TEST', ticks=ticks['day1sellLv1'])
        with store.order_behavior(filled_qty=4544, freeze_qty=True):
            SimulationBuilder.resume(store, ticks['day1sellLv2'])
            SimulationBuilder.resume(store, ticks['day2buyLv1'])
        SimulationBuilder.resume(store, ticks['day2sellLv2'])
        SimulationBuilder.resume(store, ticks['day2buyLv2'])

        plan = store.state.plan
        orders = plan.orders
        assert len(orders) == 6
        qty_seq = [order.filled_qty for order in orders]
        level_seq = [order.level for order in orders]
        sell_seq = [order.is_sell for order in orders]
        assert qty_seq == [4545, 4544, 4544, 1, 0, 4546, ]
        assert level_seq == [1, 2, 1, 2, 3, 2, ]
        assert sell_seq == [True, True, False, True, True, False, ]
        buy_cancel = orders[2]
        sell_cancel = orders[4]
        assert buy_cancel.is_canceled
        assert sell_cancel.is_canceled
