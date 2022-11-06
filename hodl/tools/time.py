import threading
import time
from datetime import datetime, timedelta
import pytz
import humanize
from hodl.tools.store_state_base import StoreStateBase


class TimeTools:
    THREAD_TZ: dict[int, str] = dict()

    @classmethod
    def thread_register(cls, region: str):
        thread_id = threading.current_thread().native_id
        TimeTools.THREAD_TZ[thread_id] = cls.region_to_tz(region=region)

    @classmethod
    def region_to_tz(cls, region: str) -> str:
        match region:
            case 'US':
                return 'US/Eastern'
            case 'CN' | 'HK':
                return 'Asia/Shanghai'
            case _:
                raise ValueError(f'无法将Region:{region}转为特定时区')

    @classmethod
    def current_tz(cls):
        local = threading.local()
        runtime_state: StoreStateBase = getattr(local, 'runtime_store_state', None)
        if runtime_state and runtime_state.tz_name:
            return runtime_state.tz_name
        thread_id = threading.current_thread().native_id
        return TimeTools.THREAD_TZ.get(thread_id, 'US/Eastern')

    @classmethod
    def utc_now(cls):
        return datetime.utcnow()

    @classmethod
    def us_time_now(cls, tz: str = None) -> datetime:
        tz = tz if tz else cls.current_tz()
        return pytz.utc.localize(cls.utc_now()).astimezone(pytz.timezone(tz))

    @classmethod
    def date_to_ymd(cls, date: datetime, join=True) -> str:
        if join:
            return date.strftime('%Y-%m-%d')
        else:
            return date.strftime('%Y%m%d')

    @classmethod
    def us_day_now(cls, tz=None) -> str:
        day = cls.us_time_now(tz=tz)
        return cls.date_to_ymd(day)

    @classmethod
    def from_timestamp(cls, timestamp, tz=None) -> datetime:
        """
        秒单位时间戳
        :param timestamp:
        :return:
        """
        tz = tz if tz else cls.current_tz()
        date = datetime.utcfromtimestamp(timestamp)
        return pytz.utc.localize(date).astimezone(pytz.timezone(tz))

    @classmethod
    def sleep(cls, secs: float):
        if secs <= 0.0:
            return
        time.sleep(secs)

    @classmethod
    def last_sunday_utc(cls, date: datetime, weeks=-1) -> datetime:
        sunday = date - timedelta(days=date.weekday()) + timedelta(days=6, weeks=weeks)
        sunday = datetime(year=sunday.year, month=sunday.month, day=sunday.day, tzinfo=pytz.timezone('UTC'))
        return sunday

    @classmethod
    def precisedelta(cls, value, minimum_unit='seconds', suppress=(), format='%0.2f'):
        return humanize.precisedelta(value=value, minimum_unit=minimum_unit, suppress=suppress, format=format)


__all__ = ['TimeTools', ]
