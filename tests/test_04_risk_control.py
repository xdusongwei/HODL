import unittest
import pytest
from hodl.exception_tools import *
from hodl.simulation.fake_quote import *
from hodl.simulation.main import *


class RiskControlTestCase(unittest.TestCase):
    def test_lock_position(self):
        # 测试锁定持仓的检查可以生效
        class _Store(SimulationStore):
            def current_chip_mock(self):
                return self.store_config.max_shares // 2

        pc = 10.0
        p = pc * 1.03
        tickets = [
            Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=pc, open=p, latest=p, ),
            Ticket(day='23-04-10T09:30:01-04:00:00', pre_close=pc, open=p, latest=p, ),
        ]
        with pytest.raises(RiskControlError):
            start_simulation(symbol='LOCK', tickets=tickets, auto_run=True, store_type=_Store, output_state=False)

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
