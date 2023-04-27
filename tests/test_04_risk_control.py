import unittest
import pytest
from hodl.exception_tools import *
from hodl.unit_test import *


class RiskControlTestCase(unittest.TestCase):
    def test_lock_position(self):
        # 测试锁定持仓的检查可以生效
        class _Store(SimulationStore):
            USE_SUPER_CHIP_MOCK = False

            def current_chip_mock(self):
                if _Store.USE_SUPER_CHIP_MOCK:
                    return super().current_chip_mock()
                else:
                    return self.store_config.max_shares // 2

        pc = 10.0
        p = pc * 1.03
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:01-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]
        store = start_simulation(symbol='TEST', auto_run=False, tickets=tickets, store_type=_Store, output_state=False)
        with pytest.raises(RiskControlError):
            with store:
                store.run(output_state=False)
        assert len(store.state.plan.orders) == 0

        # 已经是风控异常的状态, 即便恢复逻辑, 再次启动仍不能继续运行
        _Store.USE_SUPER_CHIP_MOCK = True
        store.state.chip_day = ''
        start_simulation(store=store, tickets=tickets, output_state=False)
        assert len(store.state.plan.orders) == 0

        # 修改风控异常状态, 可以正常运行
        store.state.risk_control_break = False
        store.state.risk_control_detail = ''
        _Store.USE_SUPER_CHIP_MOCK = True
        start_simulation(store=store, tickets=tickets, output_state=False)
        assert len(store.state.plan.orders) == 1

    def test_bad_day(self):
        # 测试持仓、现金、行情的日期检查可以生效
        class _BadChipDayStore(SimulationStore):
            def try_fire_orders(self):
                self.state.chip_day = '2000-01-01'
                super().try_fire_orders()

        class _BadCashDayStore(SimulationStore):
            def try_fire_orders(self):
                self.state.cash_day = '2000-01-01'
                super().try_fire_orders()

        class _BadQuoteDayStore(SimulationStore):
            def try_fire_orders(self):
                self.state.quote_time = 1
                super().try_fire_orders()

        pc = 10.0
        p0 = pc * 1.00
        p3 = pc * 1.03
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p0, latest=p0, ),
            Ticket(day='23-04-10T09:30:01-04:00:00', pre_close=pc, open=p0, latest=p3, ),
        ]
        for store_type in [_BadChipDayStore, _BadCashDayStore, _BadQuoteDayStore]:
            with pytest.raises(RiskControlError):
                start_simulation(
                    symbol='TEST',
                    store_type=store_type,
                    tickets=tickets,
                    auto_run=True,
                    output_state=False,
                )
