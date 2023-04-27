import unittest
from hodl.unit_test import *
from hodl.tools import *
from hodl.sleep_mixin import *


class SleepModeTestCase(unittest.TestCase):
    def test_calendar(self):
        var = VariableTools()
        us_store_config = var.store_configs['TEST']
        cn_store_config = var.store_configs['000001']
        us_calendar = us_store_config.trading_calendar
        cn_calendar = cn_store_config.trading_calendar
        is_trading_minute = SleepMixin.is_trading_minute

        us_tickets_table = [
            (Ticket(day='23-04-10T09:29:00-04:00:00', pre_close=0.0, open=0.0, latest=0.0, ), False, ),
            (Ticket(day='23-04-10T09:30:00-04:00:00', pre_close=0.0, open=0.0, latest=0.0, ), True, ),  # 开市
            (Ticket(day='23-04-10T15:59:00-04:00:00', pre_close=0.0, open=0.0, latest=0.0, ), True, ),
            (Ticket(day='23-04-10T16:00:00-04:00:00', pre_close=0.0, open=0.0, latest=0.0, ), False, ),  # 休市
            (Ticket(day='23-04-07T09:30:00-04:00:00', pre_close=0.0, open=0.0, latest=0.0, ), False, ),  # 耶稣受难日
        ]
        for ticket, result in us_tickets_table:
            time = ticket.to_fake_quote().time
            assert is_trading_minute(calendar=us_calendar, time=time) is result

        cn_tickets_table = [
            (Ticket(day='23-04-10T09:29:00+08:00:00', pre_close=0.0, open=0.0, latest=0.0, ), False,),
            (Ticket(day='23-04-10T09:30:00+08:00:00', pre_close=0.0, open=0.0, latest=0.0, ), True,),  # 开市
            (Ticket(day='23-04-10T11:29:00+08:00:00', pre_close=0.0, open=0.0, latest=0.0, ), True,),
            (Ticket(day='23-04-10T11:30:00+08:00:00', pre_close=0.0, open=0.0, latest=0.0, ), False,),  # 午间休市
            (Ticket(day='23-04-10T12:59:00+08:00:00', pre_close=0.0, open=0.0, latest=0.0, ), False,),
            (Ticket(day='23-04-10T13:00:00+08:00:00', pre_close=0.0, open=0.0, latest=0.0, ), True,),  # 开市
            (Ticket(day='23-04-10T14:59:00+08:00:00', pre_close=0.0, open=0.0, latest=0.0, ), True,),
            (Ticket(day='23-04-10T15:00:00+08:00:00', pre_close=0.0, open=0.0, latest=0.0, ), False,),  # 休市
            (Ticket(day='23-05-01T09:30:00+08:00:00', pre_close=0.0, open=0.0, latest=0.0, ), False,),  # 劳动节休市
        ]
        for ticket, result in cn_tickets_table:
            time = ticket.to_fake_quote().time
            assert is_trading_minute(calendar=cn_calendar, time=time) is result
