from abc import ABC
from hodl.store_base import *
from hodl.tools import *


class SleepMixin(StoreBase, ABC):
    def sleep(self):
        secs = self.runtime_state.sleep_secs
        config = self.store_config
        sleep_mode_active = False
        if config.sleep_mode:
            calendar = config.trading_calendar
            if calendar:
                utc_now = TimeTools.utc_now()
                utc_now_1 = TimeTools.timedelta(utc_now, minutes=1)
                if calendar.is_trading_minute(utc_now) or calendar.is_trading_minute(utc_now_1):
                    pass
                else:
                    secs *= 2
                    sleep_mode_active = True
        self.state.sleep_mode_active = sleep_mode_active
        TimeTools.sleep(secs)


__all__ = ['SleepMixin', ]
