import re
import pytest
import unittest
from datetime import datetime
from hodl.broker.base import *
from hodl.tools import *


class BasicTestCase(unittest.TestCase):
    def test_read_config(self):
        symbol = 'TEST'
        var = VariableTools()
        store_config = var.store_configs[symbol]

        assert store_config.broker == 'tiger'
        assert store_config.region == 'US'
        assert store_config.symbol == 'TEST'
        assert store_config.currency == 'USD'
        assert store_config.max_shares == 100_000

    def test_precision(self):
        adjust_precision = FormatTool.adjust_precision
        assert adjust_precision(0.01, 2) == 0.01
        assert adjust_precision(0.01 + 0.02, 2) == 0.03
        assert adjust_precision(0.014, 2) == 0.01
        assert adjust_precision(1.016, 2) == 1.02
        assert adjust_precision(0.0014, 3) == 0.001
        assert adjust_precision(0.0016, 3) == 0.002

    def test_date_format(self):
        date = TimeTools.us_time_now()
        assert re.match(r'\d{4}-\d{2}-\d{2}', TimeTools.date_to_ymd(date))
        assert re.match(r'\d{4}\d{2}\d{2}', TimeTools.date_to_ymd(date, join=False))
        assert re.match(r'\d{4}-\d{2}-\d{2}', TimeTools.us_day_now())
        assert TimeTools.from_timestamp(date.timestamp()) == date

    def test_date_timezone_context(self):
        TimeTools.THREAD_TZ.clear()

        TimeTools.thread_register('CN')
        date = TimeTools.us_time_now()
        assert date.tzname() == 'CST'
        assert TimeTools.current_tz() == 'Asia/Shanghai'

        TimeTools.thread_register('HK')
        date = TimeTools.us_time_now()
        assert date.tzname() == 'CST'
        assert TimeTools.current_tz() == 'Asia/Shanghai'

        TimeTools.thread_register('US')
        date = TimeTools.us_time_now()
        assert date.tzname() == 'EDT'
        assert TimeTools.current_tz() == 'US/Eastern'

        TimeTools.THREAD_TZ.clear()

    def test_date_calc(self):
        date = TimeTools.us_time_now()
        next_day = TimeTools.timedelta(date, days=1)
        assert (next_day - date).days == 1

        date = TimeTools.us_time_now()
        next_minute = TimeTools.timedelta(date, minutes=1)
        assert (next_minute - date).seconds == 60

        date = datetime(year=2023, month=4, day=25)
        sunday = TimeTools.last_sunday_utc(date, weeks=-1)
        assert sunday.year == 2023
        assert sunday.month == 4
        assert sunday.day == 23

        date = datetime(year=2023, month=4, day=25)
        sunday = TimeTools.last_sunday_utc(date, weeks=0)
        assert sunday.year == 2023
        assert sunday.month == 4
        assert sunday.day == 30

        date = datetime(year=2023, month=4, day=25)
        sunday = TimeTools.last_sunday_utc(date, weeks=1)
        assert sunday.year == 2023
        assert sunday.month == 5
        assert sunday.day == 7

        date = datetime(year=2023, month=4, day=25)
        sunday = TimeTools.last_sunday_utc(date, weeks=-2)
        assert sunday.year == 2023
        assert sunday.month == 4
        assert sunday.day == 16

    def test_sleep(self):
        start = datetime.now()
        TimeTools.sleep(0.05)
        end = datetime.now()
        assert (end - start).total_seconds() >= 0.05

    def test_broker_meta(self):
        var = VariableTools()
        store_config = var.store_configs['TEST']
        meta_list = var.broker_meta('tiger')
        assert len(meta_list) == 1
        meta = meta_list[0]
        assert meta.trade_type == BrokerTradeType.STOCK
        assert meta.trade_type.value == store_config.trade_type
        assert store_config.region in meta.trade_regions

    def test_track_api(self):
        class _MyApi:
            BROKER_DISPLAY = 'display_name'

            @track_api
            def my_api(self):
                return True

            @track_api
            def my_error_api(self):
                raise NotImplementedError

        api = _MyApi()
        api.my_api()
        with pytest.raises(NotImplementedError):
            api.my_error_api()

        report_list = track_api_report()
        ok_api, error_api = report_list[0], report_list[1]
        assert ok_api.api_name == 'my_api'
        assert error_api.api_name == 'my_error_api'

        assert ok_api.ok_times == 1 and ok_api.error_times == 0
        assert 0 <= ok_api.slowest_time < 0.01
        assert ok_api.frequency <= 1.0 / 600 * 60

        assert error_api.ok_times == 0 and error_api.error_times == 1
        assert 0 <= error_api.slowest_time < 0.01
        assert error_api.frequency <= 1.0 / 600 * 60
