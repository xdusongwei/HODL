import os
import enum


class TradeStrategyEnum(enum.Enum):
    HODL = enum.auto()
    RECYCLE = enum.auto()


class StoreConfig(dict):
    @property
    def region(self) -> str:
        """
        证券市场所属地区
        US
        CN
        HK
        地区代码的主要作用是：
        匹配正确的市场，找到对应的市场状态；
        规定了持仓的时间时区。
        :return:
        """
        return self.get('region', 'US')

    @property
    def broker(self) -> str:
        """
        使用的券商服务
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
            case 'recycle':
                return TradeStrategyEnum.RECYCLE
            case _:
                return TradeStrategyEnum.HODL

    @property
    def trade_type(self) -> str:
        return self.get('trade_type', 'stock')

    @property
    def cost_price(self) -> float:
        """
        对于保本型拐点套利，必须设定建仓成本价，以便计算清仓价格
        """
        return self.get('cost_price', None)

    @property
    def recycle_rate(self) -> float:
        """
        对于保本型拐点套利，必须设定清仓比例，假设cost_price=10，recycle_rate设定0.01，那么市价低于10.1则触发清仓机制。
        """
        return self.get('cost_price', None)

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
        Returns
        -------

        """
        return self.get('name')

    @property
    def enable(self) -> bool:
        return self.get('enable')

    @property
    def max_shares(self) -> int:
        """
        可操作证券数量
        :return:
        """
        return self.get('max_shares')

    @property
    def prudent(self) -> bool:
        """
        是否使用惜售策略的因子
        :return:
        """
        return self.get('prudent', True)

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
            path = path.format(symbol=self.symbol)
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
            path = path.format(symbol=self.symbol)
            path = os.path.expanduser(path)
            os.makedirs(path, exist_ok=True)
        return path

    @property
    def buy_spread(self) -> float:
        """
        设置买入价时需要的点差
        :return:
        """
        return self.get('buy_spread', 0.01)

    @property
    def sell_spread(self) -> float:
        """
        设置卖出价时需要的点差
        :return:
        """
        return self.get('sell_spread', 0.01)

    @property
    def buy_order_rate(self) -> float:
        """
        如果买入价 >= 现价*因子 时，才会触发下单动作
        :return:
        """
        return self.get('buy_order_rate', 0.975)

    @property
    def sell_order_rate(self) -> float:
        return self.get('sell_order_rate', 1.025)

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
        证券一手多少股
        :return:
        """
        return self.get('shares_per_unit', 1)

    @property
    def legal_rate_daily(self) -> None | float:
        """
        对于有单日涨幅要求的证券，设置幅度因子
        例如 0.1 则在昨收10%内的价格范围内可以进行下单
        :return:
        """
        return self.get('legal_rate_daily', None)

    @property
    def booting_check(self) -> bool:
        """
        是否在持仓进程启动后开始做broker联通性检查。
        通常建议每个持仓都需要执行检查，保证市场状态/行情/持仓/资金可正常访问， 否则持仓线程中止。
        但是有些持仓的broker联通方面可能需要其他的维护动作，例如服务不是24小时随时可用，如果在broker对应的下游系统并未准备好的情况下，
        启动了本系统，该持仓的联通性检查会失败，导致持仓线程自杀，反而需要等到下游系统可用时，本系统进程方可启动, 搞得很复杂。
        另外的，对于这类broker，建议完善 detect_plug_in 方法，在持仓线程循环里提前ping一下broker系统，不可用时不影响持仓线程存活。
        Returns
        -------

        """
        return self.get('booting_check', False)

    @property
    def base_price_last_buy(self) -> bool:
        """
        设置此项后，上次平仓买入的价格也可以是 base_price 的参考选项
        :return:
        """
        return self.get('base_price_last_buy', False)

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
        这是一个控制开关，当启用 base_price_day_low 时：
        如果此设置打开，那么昨收价和今日最低价两者取其最高的价格，作为一个基准价格参考价项目。
        在证券暴跌时期，若采用到历史低点作为基准价格，很有可能增大执行计划全部卖飞的可能性，并且反弹时浪费了前几档卖出证券的套利价值，
        所以通过此设置项目，避免取到当日或者前日收盘的历史低价作为基准价格。
        """
        return self.get('base_price_tumble_protect', False)

    @property
    def tumble_protect_day_range(self) -> int:
        return abs(self.get('tumble_protect_day_range', 30))

    @property
    def lock_position(self) -> bool:
        """
        设置此项后，如果每日风控核对持仓数量不能跟配置 max_shares 一致，否则会触发风控异常
        不设置此项，之后每日核对后数量小于配置的 max_shares 时触发风控异常， 即不影响平时增持
        :return:
        """
        return self.get('lock_position', True)

    @property
    def price_rate(self) -> float:
        """
        买卖计划价格将乘以该系数
        利用此设置可以微调买卖因子的幅度。
        假设某个等级的卖出价是基准价格的3%, 买入价是基准价格的0%, 当这是设置0.333：
        则会使卖出幅度变为1% (3% * 0.333), 买入幅度变为0% (0% * 0.333)。
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
    def closing_time(self) -> str:
        """
        设定一个时间起点，格式为 %H:%M:%S，作为一天内的收盘时间段
        [<closing_time>, 次日00:00:00)
        对于加密货币交易所的持仓，这个设置有必要，需要留出一段自定义时间段作为一天订单的生命周期结束，以对接LSOD机制。
        设置此项后，
        当时间进入预定时间段，持仓状态的current状态将可以发生跳变 TRADING->CLOSING，此时会特别地触发撤销所有待成交订单。
        当时间离开预定时间段，持仓状态的current状态将发生跳变 CLOSING->TRADING，即开始新一天的持仓监控。
        Returns
        -------

        """
        return self.get('closing_time', None)

    @property
    def factors(self) -> list[tuple[float, float, float, ]]:
        """
        手动设置持仓下单因子，将根据列表项目的先后顺序逐级定义
        每个列表项表达了(卖出因子，买入因子，权重)三项
        设置此项将不参考默认因子，包括忽略惜售(prudent)配置项目
        Returns
        -------

        """
        return self.get('factors', None)

    @property
    def market_price_rate(self) -> float:
        """
        设置一个系数，当市场价格偏离预期价格多少比例时，下达市价单而非限价单。
        例如，假如这里设定0.05，此时市场价为10.6，计划卖出下单价格为10.0，那么10.6 > 1.05 * 10.0，则下达市价卖单。
        同理如果市场价为9.3，计划买入下单价格为10.0，那么9.3 < 0.95 * 10.0，则下达市价买单。
        """
        return self.get('market_price_rate', None)


__all__ = ['TradeStrategyEnum', 'StoreConfig', ]
