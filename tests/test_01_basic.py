import re
import time
import pytest
import unittest
from datetime import datetime
from hodl.broker.base import *
from hodl.tools import *


class BasicTestCase(unittest.TestCase):
    """
    基本测试主要验证tools包下面的基础模块的工作情况，
    大多与配置读取、线程时区上下文，浮点精度，日期计算等有关。
    """

    def test_read_config(self):
        """
        这里验证读取测试配置文件的一个持仓配置节的基本情况，
        一些关键数据应该被正确读取。
        """
        symbol = 'TEST'
        var = VariableTools()
        store_config = var.store_configs[symbol]

        assert store_config.broker == 'tiger'
        assert store_config.region == 'US'
        assert store_config.symbol == 'TEST'
        assert store_config.currency == 'USD'
        assert store_config.max_shares == 100_000

    def test_precision(self):
        """
        测试浮点数精度四舍五入是否有效
        """
        adjust_precision = FormatTool.adjust_precision
        assert adjust_precision(0.01, 2) == 0.01
        assert adjust_precision(0.01 + 0.02, 2) == 0.03
        assert adjust_precision(0.014, 2) == 0.01
        assert adjust_precision(1.016, 2) == 1.02
        assert adjust_precision(0.0014, 3) == 0.001
        assert adjust_precision(0.0016, 3) == 0.002

    def test_date_format(self):
        """
        测试日期格式化函数
        """
        # 验证格式化为字符串的结果
        date = TimeTools.us_time_now()
        assert re.match(r'\d{4}-\d{2}-\d{2}', TimeTools.date_to_ymd(date))
        assert re.match(r'\d{4}\d{2}\d{2}', TimeTools.date_to_ymd(date, join=False))
        assert re.match(r'\d{4}-\d{2}-\d{2}', TimeTools.us_day_now())
        # 验证产生的日期对象的时间戳，可以被用来还原回值比较相同的日期对象
        assert TimeTools.from_timestamp(date.timestamp()) == date
        # 处理格式化日期字符串
        assert TimeTools.format_ymd(20200101) == '2020-01-01'
        assert TimeTools.format_ymd('20200101') == '2020-01-01'
        assert TimeTools.format_ymd('2020-01-01') == '2020-01-01'
        right = date.strftime('%m-%dT%H:%M:%S')
        assert FormatTool.pretty_dt(date, with_year=False, with_tz=False, with_ms=False) == right

    def test_date_timezone_context(self):
        """
        验证线程被注册为中国，香港，美国地区时，
        当前线程时区应分别对应正确的时区缩写，以及完整的时区描述。
        """
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
        assert date.tzname() == 'EST'
        assert TimeTools.current_tz() == 'US/Eastern'

        TimeTools.THREAD_TZ.clear()

    def test_date_calc(self):
        # 验证时间偏移计算符合预期
        date = TimeTools.us_time_now()
        next_day = TimeTools.timedelta(date, days=1)
        assert (next_day - date).days == 1

        date = TimeTools.us_time_now()
        next_minute = TimeTools.timedelta(date, minutes=1)
        assert (next_minute - date).seconds == 60

        # 验证向前向后多个星期推算周日的功能
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
        # 验证线程sleep包装函数正常工作
        start = datetime.now()
        TimeTools.sleep(0.05)
        end = datetime.now()
        assert (end - start).total_seconds() >= 0.05

    def test_broker_meta(self):
        # 读取一个券商通道元数据项，验证读取的属性正确
        # 券商通道元数据项描述了通道服务可以做什么，处理那些交易品种等权限范围
        var = VariableTools()
        store_config = var.store_configs['TEST']
        meta_list = var.broker_meta('tiger')
        assert len(meta_list) == 1
        meta = meta_list[0]
        assert meta.trade_type == BrokerTradeType.STOCK
        assert meta.trade_type.value == store_config.trade_type
        assert store_config.region in meta.trade_regions

    def test_track_api(self):
        # 验证 @track_api 装饰器可以统计函数调用情况，
        # 这个装饰器是给 BrokerApiBase 的子类对象使用的，
        # 这里简化了继承处理，故意设置了 BROKER_DISPLAY 成员。
        class _MyApi:
            BROKER_DISPLAY = 'display_name'

            @track_api
            def my_api(self):
                return True

            @track_api
            def my_error_api(self):
                raise NotImplementedError

        """
        分别调用一个正常函数，和异常函数
        确认:
            函数名被正确记录
            各函数的成功次数和异常次数
            可计算函数最慢时间和函数频率
        """
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

    def test_leaky_bucket(self):
        # 验证漏桶的阻塞功能

        # 漏桶初始时默认带一个可用令牌，所以消费函数不会阻塞
        seconds_per_token = 0.1
        leak_rate = 600
        bucket = LeakyBucket(leak_rate=leak_rate)
        start = time.time()
        bucket.consume()
        end = time.time()
        assert end - start < seconds_per_token

        # 漏桶初始没有了可用令牌，消费一次，应等待一个单位的时间
        seconds_per_token = 0.1
        leak_rate = 600
        bucket = LeakyBucket(leak_rate=leak_rate, used_tokens=1)
        start = time.time()
        bucket.consume()
        end = time.time()
        assert seconds_per_token < end - start < seconds_per_token * 2

        # 漏桶初始没有了可用令牌，消费两次，应等待两个单位的时间
        seconds_per_token = 0.1
        leak_rate = 600
        bucket = LeakyBucket(leak_rate=leak_rate, used_tokens=1)
        start = time.time()
        bucket.consume()
        bucket.consume()
        end = time.time()
        assert seconds_per_token * 2 < end - start < seconds_per_token * 3

        # 一些错误参数应被报告异常
        with pytest.raises(AssertionError):
            LeakyBucket(leak_rate=leak_rate, capacity=-1)
        with pytest.raises(AssertionError):
            LeakyBucket(leak_rate=leak_rate, capacity=0)
        with pytest.raises(AssertionError):
            LeakyBucket(leak_rate=leak_rate, used_tokens=-1)
        with pytest.raises(AssertionError):
            LeakyBucket(leak_rate=leak_rate, capacity=1, used_tokens=2)
