from hodl.unit_test import *
from hodl.sleep_mixin import *


class SleepModeTestCase(HodlTestCase):
    def test_calendar(self):
        # 验证第三方交易日历模块可以正确判断各个市场的节假日，
        # 第三方交易日历模块从不用于决定开盘时段，市场开盘时段完全由券商提供的市场状态接口来判断。
        # 第三方交易日历模块仅用于当市场状态为非交易时段时，控制持仓线程的刷新时间间隔来节省线程计算量。
        var = self.config()
        us_store_config = var.store_configs['TEST']
        cn_store_config = var.store_configs['000001']
        us_calendar = us_store_config.trading_calendar
        cn_calendar = cn_store_config.trading_calendar
        is_trading_minute = SleepMixin.is_trading_minute

        us_tickets_table = [
            (Tick(time='23-04-10T09:29:00-04:00:00', pre_close=0.0, open=0.0, latest=0.0, ), False,),
            (Tick(time='23-04-10T09:30:00-04:00:00', pre_close=0.0, open=0.0, latest=0.0, ), True,),  # 开市
            (Tick(time='23-04-10T15:59:00-04:00:00', pre_close=0.0, open=0.0, latest=0.0, ), True,),
            (Tick(time='23-04-10T16:00:00-04:00:00', pre_close=0.0, open=0.0, latest=0.0, ), False,),  # 休市
            (Tick(time='23-04-07T09:30:00-04:00:00', pre_close=0.0, open=0.0, latest=0.0, ), False,),  # 耶稣受难日
        ]
        for ticket, result in us_tickets_table:
            time = ticket.to_fake_quote().time
            assert is_trading_minute(calendar=us_calendar, time=time) is result

        cn_tickets_table = [
            (Tick(time='23-04-10T09:29:00+08:00:00', pre_close=0.0, open=0.0, latest=0.0, ), False,),
            (Tick(time='23-04-10T09:30:00+08:00:00', pre_close=0.0, open=0.0, latest=0.0, ), True,),  # 开市
            (Tick(time='23-04-10T11:29:00+08:00:00', pre_close=0.0, open=0.0, latest=0.0, ), True,),
            (Tick(time='23-04-10T11:30:00+08:00:00', pre_close=0.0, open=0.0, latest=0.0, ), False,),  # 午间休市
            (Tick(time='23-04-10T12:59:00+08:00:00', pre_close=0.0, open=0.0, latest=0.0, ), False,),
            (Tick(time='23-04-10T13:00:00+08:00:00', pre_close=0.0, open=0.0, latest=0.0, ), True,),  # 开市
            (Tick(time='23-04-10T14:59:00+08:00:00', pre_close=0.0, open=0.0, latest=0.0, ), True,),
            (Tick(time='23-04-10T15:00:00+08:00:00', pre_close=0.0, open=0.0, latest=0.0, ), False,),  # 休市
            (Tick(time='23-05-01T09:30:00+08:00:00', pre_close=0.0, open=0.0, latest=0.0, ), False,),  # 劳动节休市
        ]
        for ticket, result in cn_tickets_table:
            time = ticket.to_fake_quote().time
            assert is_trading_minute(calendar=cn_calendar, time=time) is result
