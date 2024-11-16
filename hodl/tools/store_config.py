import os
import enum
import exchange_calendars


class TradeStrategyEnum(enum.Enum):
    # 根据基准价格分价分量高价卖出, 当股价低于当前挡的买入价时买回卖出的部分, 以挣取差价
    HODL = enum.auto()


class StoreConfig(dict):
    READONLY = False

    @property
    def group(self) -> str:
        """
        持仓的分组识别名，如果这个系统工作于多个用户，需要彼此隔离数据，此处可以分别将各种持仓标识成组
        """
        return self.get('group', 'default')

    @property
    def region(self) -> str:
        """
        证券市场所属地区
        US
        CN
        HK
        地区代码的主要作用是：
        匹配正确的市场，找到对应的市场状态；
        证券产品根据地区映射到对应交易所，从而可以判断交易所是否开市；
        规定了持仓的时间时区。
        :return:
        """
        return self.get('region', 'US')

    @property
    def broker(self) -> str:
        """
        使用的券商服务，其值参考 BrokerApiBase 的子类设定的 BROKER_NAME 成员，
        例如可以是：
        tiger
        citics
        :return:
        """
        return self.get('broker', 'tiger')

    @property
    def currency(self) -> str | None:
        """
        持仓标的计价的货币单位
        Returns
        -------

        """
        return self.get('currency', None)

    @property
    def trade_strategy(self) -> TradeStrategyEnum:
        """
        持仓使用的交易策略，可以是：
        hodl：默认，长期持有套利；
        recycle：保本型拐点套利；
        """
        strategy = self.get('trade_strategy', 'hodl')
        match strategy:
            case 'hodl':
                return TradeStrategyEnum.HODL
            case _:
                return TradeStrategyEnum.HODL

    @property
    def trade_type(self) -> str:
        return self.get('trade_type', 'stock')

    @property
    def symbol(self) -> str:
        symbol = self.get('symbol')
        assert symbol
        return symbol

    @property
    def name(self) -> str:
        """
        如果不考虑某些证券系统同证券代码会有多种标的，名称可以随便起。
        否则需要设置正式名称以便供有些证券系统去做重复项的匹配。
        比如中信证券，可能存在同代码多个交易标的，那么设定的name可以用来找到真正的项。
        Returns
        -------

        """
        return self.get('name', '--')

    @property
    def enable(self) -> bool:
        return self.get('enable', False)

    @property
    def visible(self) -> bool:
        """
        是否展示在html或者tui中
        """
        return self.get('visible', True)

    @property
    def max_shares(self) -> int:
        """
        可操作证券数量
        :return:
        """
        rocket = self.multistage_rocket
        if rocket:
            shares = rocket[-1][0]
            assert shares > 0
            return shares
        else:
            return self.get('max_shares')

    @property
    def lock_position(self) -> bool:
        """
        设置此项后，如果每日风控核对持仓数量不能跟配置 max_shares 一致，否则会触发风控异常
        不设置此项，之后每日核对后数量小于配置的 max_shares 时触发风控异常， 即不影响平时增持
        :return:
        """
        return self.get('lock_position', True)

    @property
    def state_file_path(self) -> str:
        """
        指定一个路径，来保存持仓状态文件
        除了测试，这个设置是必要的
        Returns
        -------

        """
        path: str = self.get('state_file_path')
        if path:
            path = path.format(
                group=self.group,
                broker=self.broker,
                region=self.region,
                symbol=self.symbol,
                stage=self.stage
            )
            path = os.path.expanduser(path)
        return path

    @property
    def state_archive_folder(self) -> str:
        """
        指定一个目录，每日归档该持仓状态文件
        Returns
        -------

        """
        path: str = self.get('state_archive_folder')
        if path:
            path = path.format(
                broker=self.broker,
                region=self.region,
                symbol=self.symbol,
            )
            path = os.path.expanduser(path)
            if not StoreConfig.READONLY:
                os.makedirs(path, exist_ok=True)
        return path

    @property
    def buy_spread(self) -> float | None:
        """
        此方法已过时，
        设置买入价时需要舍去的点差(佣金、成本)
        :return:
        """
        return self.get('buy_spread', None)

    @property
    def sell_spread(self) -> float | None:
        """
        此方法已过时，
        设置卖出价时需要舍去的点差(佣金、成本)
        :return:
        """
        return self.get('sell_spread', None)

    @property
    def buy_spread_rate(self) -> float | None:
        """
        设置买入价时需要舍去的点差(佣金、成本), 以目标价格的比例进行计算.
        例如这里设置 0.005, 假如一个预期买入价格是 10, 那么实际买入价格 = 10 * (1 - 0.005) = 9.95
        :return:
        """
        return self.get('buy_spread_rate', None)

    @property
    def sell_spread_rate(self) -> float | None:
        """
        设置卖出价时需要舍去的点差(佣金、成本), 以目标价格的比例进行计算.
        例如这里设置 0.005, 假如一个预期卖出价格是 10, 那么实际卖出价格 = 10 * (1 + 0.005) = 10.05
        :return:
        """
        return self.get('sell_spread_rate', None)

    @property
    def buy_order_rate(self) -> float:
        """
        如果 买入价 * (1 + 此因子) >= 现价 时，才会触发下单动作
        :return:
        """
        v = self.get('buy_order_rate', 0.01)
        assert 0 <= v <= 1.0
        return v

    @property
    def sell_order_rate(self) -> float:
        """
        如果 卖出价 * (1 - 此因子) <= 现价 时，才会触发下单动作
        :return:
        """
        v = self.get('sell_order_rate', 0.01)
        assert 0 <= v <= 1.0
        return v

    @property
    def precision(self) -> int:
        """
        证券报价精度
        :return:
        """
        return self.get('precision', 2)

    @property
    def shares_per_unit(self) -> int:
        """
        证券一手多少股，主要针对 A股和港股
        :return:
        """
        return self.get('shares_per_unit', 1)

    @property
    def legal_rate_daily(self) -> None | float:
        """
        对于有单日涨幅要求的证券，设置幅度因子，主要针对 A股。
        例如 0.1 则在昨收10%内的价格范围内可以进行下单
        :return:
        """
        return self.get('legal_rate_daily', None)

    @property
    def base_price_last_buy(self) -> bool:
        """
        设置此项后，上次平仓买入的价格也可以是 base_price 的参考选项
        :return:
        """
        return self.get('base_price_last_buy', False)

    @property
    def base_price_last_buy_days(self) -> int:
        """
        上次买回价格的有效天数，比如这里设定 14，那么早于(超过)14天前的买回记录将失效
        """
        days = self.get('base_price_last_buy_days', 9)
        assert days > 0
        return days

    @property
    def base_price_isolated(self) -> bool:
        """
        查询上次买回价格时限制范围为指定交易通道的记录, 以使同品种标的的不同券商持仓不共享买回价
        """
        return self.get('base_price_isolated', False)

    @property
    def base_price_day_low(self) -> bool:
        """
        设置此项后， 当日最低价也可以是 base_price 的参考选项
        :return:
        """
        return self.get('base_price_day_low', False)

    @property
    def base_price_tumble_protect(self) -> bool:
        """
        这是一个控制开关，
        如果此设置打开，当<tumble_protect_day_range>日内最低价格接近历史最低价时，只根据 Ma5 和 Ma10 选择较高的价格作为基准价格。
        这里的历史最低价根据<tumble_protect_sample_range>日内的最低价格而定。
        在证券暴跌时期，若采用到历史低点作为基准价格，很有可能增大执行计划全部卖飞的可能性，并且反弹时浪费了前几档卖出证券的套利价值，
        所以通过此设置项目，避免取到当日或者前日收盘的历史低价作为基准价格。
        """
        return self.get('base_price_tumble_protect', False)

    @property
    def tumble_protect_day_range(self) -> int:
        return abs(self.get('tumble_protect_day_range', 10))

    @property
    def tumble_protect_sample_range(self) -> int:
        return abs(self.get('tumble_protect_sample_range', 180))

    @property
    def vix_tumble_protect(self) -> float | None:
        """
        根据 vix 上限设置保护持仓不被贱卖。
        当持仓计划为空时，这里设定 30，
        表示当 vix指数当日最高 >= 30 时，不会开仓卖出。
        这个功能仅在 async_market_status 开启时有效工作，否则会引起不能下单问题。
        """
        return self.get('vix_tumble_protect', None)

    @property
    def tumble_protect_rsi(self) -> bool:
        """
        是否启用RSI暴跌保护机制。
        Returns
        -------

        """
        return self.get('tumble_protect_rsi', False)

    @property
    def tumble_protect_rsi_period(self) -> int:
        """
        RSI暴跌保护的指标周期，默认 RSI6
        Returns
        -------

        """
        period = self.get('tumble_protect_rsi_period', 6)
        assert 2 <= period < 120
        return period

    @property
    def tumble_protect_rsi_lock_limit(self) -> int:
        """
        盘中若为空执行计划时，若 RSI 低于此限制值，将启用 RSI暴跌保护锁定
        Returns
        -------

        """
        limit = self.get('tumble_protect_rsi_lock_limit', 20)
        assert 0 <= limit <= 100
        return limit

    @property
    def tumble_protect_rsi_unlock_limit(self) -> int:
        """
        RSI 暴跌保护锁定后，若历史盘中 RSI 到达过此限制值以上，将解除 RSI 暴跌保护锁定
        Returns
        -------

        """
        limit = self.get('tumble_protect_rsi_unlock_limit', 75)
        assert 0 <= limit <= 100
        return limit

    @property
    def tumble_protect_rsi_warning_limit(self) -> int | None:
        """
        如果需要根据 RSI 低于指定阈值时,调整基准价格的比较函数为中位数函数,
        这里设定一个 RSI 警戒阈值;
        Returns
        -------

        """
        limit = self.get('tumble_protect_rsi_warning_limit', None)
        assert limit is None or 0 <= limit <= 100
        return limit

    @property
    def price_rate(self) -> float:
        """
        买卖计划价格将乘以该系数
        利用此设置可以微调买卖因子的幅度。
        假设某个等级的卖出价是基准价格的 3%, 而买入价是基准价格的0%, 当这是设置 0.333：
        则会使卖出幅度变为 1% (3% * 0.333), 买入幅度变为 0% (0% * 0.333)。
        :return:
        """
        return self.get('price_rate', 1.0)

    @property
    def rework_level(self) -> int:
        """
        这里可以设置持仓下单因子的等级号码，使得：
        当日已套利后，根据当时计划(plan)中的的基准价格对应此设置的等级的卖出价，作为重置持仓状态的触发价格。
        当当日标的价格重新到达(>=)该触发价格时，进程将"删除"该持仓的状态文件。
        即该持仓重新开始当日的下单计划，使得一天内可以重复套利。
        Returns
        -------

        """
        return self.get('rework_level', 0)

    @property
    def closing_time(self) -> str | None:
        """
        设定一个时间起点，格式为 %H:%M:%S，作为一天内的收盘时间段
        [<closing_time>, 次日 00:00:00)
        对于加密货币交易所的持仓，这个设置有必要，需要留出一段自定义时间段作为一天订单的生命周期结束，以对接 LSOD 机制。
        设置此项后，
        当时间进入预定时间段，持仓状态的current状态将可以发生跳变 TRADING -> CLOSING，此时会特别地触发撤销所有待成交订单。
        当时间离开预定时间段，持仓状态的current状态将发生跳变 CLOSING -> TRADING，即开始新一天的持仓监控。
        Returns
        -------

        """
        return self.get('closing_time', None)

    @property
    def market_price_rate(self) -> float | None:
        """
        设置一个系数，当市场价格偏离预期价格多少比例时，下达市价单而非限价单。
        例如，假如这里设定 0.05，此时市场价为 10.6，计划卖出下单价格为 10.0，那么 10.6 > 1.05 * 10.0，则下达市价卖单。
        同理如果市场价为 9.3，计划买入下单价格为 10.0，那么 9.3 < 0.95 * 10.0，则下达市价买单。
        """
        return self.get('market_price_rate', None)

    @property
    def sleep_mode(self) -> bool:
        """
        是否启用休眠模式，需要证券交易所开盘收盘时间表支持。
        开启后，如果发现当前或者下一分钟在开市时间段内，持仓线程的循环睡眠时间正常，
        否则会拉大持仓线程的循环睡眠时间，以节省计算机资源。
        Returns
        -------

        """
        return self.get('sleep_mode', False)

    @property
    def factors(self) -> list[tuple[float, float, float,]] | None:
        """
        手动设置持仓下单因子，将根据列表项目的先后顺序逐级定义
        每个列表项表达了(卖出因子，买入因子，权重)三项
        设置此项将不参考任何默认因子，包括忽略惜售(prudent)配置项目
        Returns
        -------

        """
        return self.get('factors', None)

    @property
    def factor_fear_and_greed(self) -> str:
        """
        手动选择使用何种内置因子模板，
        可以是 fear, neutral, greed 三项，
        持仓将使用对应的因子模板进行操作
        """
        return self.get('factor_fear_and_greed', 'neutral')

    @property
    def cost_price(self) -> None | float:
        """
        持仓成本，如果设定了此项，因子模板的选择将根据当前股价配合与 factor_fear_rate_limit 和 factor_greed_rate_limit 的计算来选择。
        """
        return self.get('cost_price', None)

    @property
    def factor_fear_rate_limit(self) -> float:
        """
        股价低于这个阈值比例时，将使用恐慌因子模板
        """
        return self.get('factor_fear_rate_limit', 0.85)

    @property
    def factor_greed_rate_limit(self) -> float:
        """
        股价高于这个阈值比例时，将使用贪婪因子模板
        """
        return self.get('factor_greed_rate_limit', 1.8)

    @property
    def multistage_rocket(self) -> list[tuple[int, float,]]:
        """
        多级火箭机制
        假如已卖出较大比例证券，并且股价维持在高位，我们可以通过按剩余持仓股份重新套利，减少浪费掉可以继续套利的时间和机会。
        若之后股价下跌到原先的买入价时，我们可以在配置中还原回原来的状态，这样原先的状态继续正常套利，不受到影响。
        实现原理是我们根据这个配置项的列表项数，来确定使用 stage 为路径参数的状态文件，保存和隔离不同阶段的状态文件。
        !   如果此项目有有效设定值，max_shares 配置将从这里获取最新(列表最后一项)的持仓设定股数
        !   编辑此项目最好是当日无有效订单，或者在未开市的时段，以免使用旧有的状态文件触发 LSOD 警报

        举例，假如原计划持股 45000, state_file_path="{broker}-{symbol}-stage{stage}.json"
        我们在此项配置设定:
            [
                { max_shares = 45000, recover_price = 0.0 },
            ]
        此时，系统将使用"{broker}-{symbol}-stage1.json"状态文件管理此持仓

        当股价涨至 $4.6,剩余股票 16000，买回价格是 $3.4, 我们打算在这个价位用剩余股票继续套利，
        我们在此项配置设定:
            [
                { max_shares = 45000, recover_price = 0.0 },
                { max_shares = 16000, recover_price = 3.4 },
            ]
        这样就可以让 16000 股重新套利，并且记录了还原状态需要的价格条件，
        此时，我们将使用"{broker}-{symbol}-stage2.json"状态文件管理此持仓

        假如股价下跌到 $3.4, 我们可以得到给定的价格预警提示，去删去配置中的最后一行来还原回状态文件即可：
            [
                { max_shares = 45000, recover_price = 0.0 },
            ]
        此时，我们将使用"{broker}-{symbol}-stage1.json"状态文件管理此持仓
        """
        stages: list[dict] = self.get('multistage_rocket', list())
        result = [(item['max_shares'], item['recover_price'],) for item in stages]
        return result

    @property
    def stage(self) -> int:
        return len(self.multistage_rocket)

    @property
    def full_name(self) -> str:
        return f'{{{self.broker}}}[{self.region}]{self.symbol}({self.name})'

    @property
    def thread_name(self) -> str:
        return f'Store([{self.broker}]{self.symbol})'

    @property
    def trading_calendar(self) -> None | exchange_calendars.ExchangeCalendar:
        """
        通过日历判断是否开启休眠模式
        """
        match self.trade_type:
            case 'stock':
                match self.region:
                    case 'US':
                        return exchange_calendars.get_calendar('XNYS')
                    case 'HK':
                        return exchange_calendars.get_calendar('XHKG')
                    case 'CN':
                        return exchange_calendars.get_calendar('XSHG')
        return None


__all__ = ['TradeStrategyEnum', 'StoreConfig', ]
