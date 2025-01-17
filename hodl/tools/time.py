import re
import time
import threading
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, UTC, timezone
import humanize
from hodl.tools.store_state_base import StoreStateBase


class TimeTools:
    # 一个由线程id为键用于存储线程应使用的默认时区信息
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
            case 'CN':
                return 'Asia/Shanghai'
            case 'HK':
                return 'Asia/Hong_Kong'
            case 'SG':
                return 'Asia/Singapore'
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
    def get_utc(cls):
        return datetime.now(timezone.utc)

    @classmethod
    def utc_now(cls):
        """
        获取utc时间对象, 测试时此函数将被mock,
        如果某些机制, 比如计算处理耗时, 不希望使用被mock破坏的时间函数, 则应使用get_utc方法
        Returns
        -------

        """
        return cls.get_utc()

    @classmethod
    def us_time_now(cls, tz: str = None) -> datetime:
        """
        通常用于获取当前线程的时间日期对象，会附上线程设置的时区信息。
        函数名中的us是开发历史问题，并非指美国地区当前时间。
        """
        tz = tz if tz else cls.current_tz()
        return cls.utc_now().astimezone(ZoneInfo(tz))

    @classmethod
    def date_to_ymd(cls, date: datetime, join=True) -> str:
        if join:
            return date.strftime('%Y-%m-%d')
        else:
            return date.strftime('%Y%m%d')

    @classmethod
    def format_ymd(cls, s: str | int) -> str:
        if s is None:
            return '--'
        elif isinstance(s, int):
            s = str(s)
        if m := re.match(r'^(\d{4})(\d{2})(\d{2})$', s):
            yyyy, mm, dd = m.groups()
            return f'{yyyy}-{mm}-{dd}'
        elif re.match(r'^(\d{4})-(\d{2})-(\d{2})$', s):
            return s
        else:
            return s

    @classmethod
    def us_day_now(cls, tz=None) -> str:
        day = cls.us_time_now(tz=tz)
        return cls.date_to_ymd(day)

    @classmethod
    def timedelta(cls, date: datetime, days=0, minutes=0, seconds=0):
        return date + timedelta(days=days, minutes=minutes, seconds=seconds)

    @classmethod
    def from_timestamp(cls, timestamp, tz: str = None) -> datetime:
        """
        秒单位时间戳
        :param timestamp:
        :param tz:
        :return:
        """
        tz = tz if tz else cls.current_tz()
        date = datetime.fromtimestamp(timestamp, UTC)
        return date.astimezone(ZoneInfo(tz))

    @classmethod
    def from_params(cls, year: int, month: int, day: int, hour: int, minute: int, second: int, tz: str):
        return datetime(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            second=second,
            tzinfo=ZoneInfo(tz),
        )

    @classmethod
    def sleep(cls, secs: float):
        if secs <= 0.0:
            return
        time.sleep(secs)

    @classmethod
    def last_sunday_utc(cls, date: datetime, weeks=-1) -> datetime:
        sunday = date - timedelta(days=date.weekday()) + timedelta(days=6, weeks=weeks)
        sunday = datetime(year=sunday.year, month=sunday.month, day=sunday.day, tzinfo=UTC)
        return sunday

    @classmethod
    def precisedelta(cls, value, minimum_unit='seconds', suppress=(), format='%0.2f'):
        return humanize.precisedelta(value=value, minimum_unit=minimum_unit, suppress=suppress, format=format)


__all__ = ['TimeTools', ]
