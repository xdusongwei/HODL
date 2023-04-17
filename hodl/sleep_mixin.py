from abc import ABC
from datetime import datetime
import exchange_calendars
from hodl.store_base import *
from hodl.tools import *


class SleepMixin(StoreBase, ABC):
    @classmethod
    def is_trading_minute(
            cls,
            calendar: exchange_calendars.ExchangeCalendar,
            time: datetime,
            forward_minutes: int = 0,
    ) -> bool:
        for offset in range(forward_minutes + 1):
            offset_time = TimeTools.timedelta(time, minutes=offset)
            if calendar.is_trading_minute(offset_time):
                return True
        return False

    def sleep(self):
        secs = self.runtime_state.sleep_secs
        config, state, _ = self.args()
        calendar = config.trading_calendar
        sleep_mode_active = False
        if config.sleep_mode and calendar and state.market_status != 'TRADING':
            utc_now = TimeTools.utc_now()
            if not self.is_trading_minute(calendar=calendar, time=utc_now, forward_minutes=1):
                secs *= 4
                sleep_mode_active = True
        if not config.visible:
            secs *= 4
        self.state.sleep_mode_active = sleep_mode_active
        TimeTools.sleep(secs)


__all__ = ['SleepMixin', ]
