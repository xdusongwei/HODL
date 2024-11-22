from hodl.tools import *
from hodl.tools import FormatTool as FMT


class Order(DictWrapper):
    DISPLAY_SHOW_SYMBOL = True
    DISPLAY_SHOW_LEVEL = True
    IGNORE_REASONS = {
        'Change order succeeded',
    }

    @classmethod
    def new_config_order(
            cls,
            store_config: StoreConfig,
            direction: str,
            qty: int,
            limit_price: float | None,
            create_timestamp: float = None,
            order_day: str = None,
            protect_price: float = None,
            level: int = 0,
    ):
        if direction == 'BUY':
            config_spread = store_config.buy_spread
            config_spread_rate = store_config.buy_spread_rate
        else:
            config_spread = store_config.sell_spread
            config_spread_rate = store_config.sell_spread_rate

        return cls.new_order(
            symbol=store_config.symbol,
            region=store_config.region,
            broker=store_config.broker,
            currency=store_config.currency,
            level=level,
            direction=direction,
            qty=qty,
            limit_price=limit_price,
            precision=store_config.precision,
            config_spread=config_spread,
            config_spread_rate=config_spread_rate,
            create_timestamp=create_timestamp,
            order_day=order_day,
            protect_price=protect_price,
        )

    @classmethod
    def new_order(
            cls,
            symbol: str,
            region: str,
            broker: str,
            currency: str,
            level: int,
            direction: str,
            qty: int,
            limit_price: float | None,
            precision: int = 2,
            config_spread: float = None,
            config_spread_rate: float = None,
            create_timestamp: float = None,
            order_day: str = None,
            protect_price: float = None,
    ) -> 'Order':
        o = Order()
        now = TimeTools.us_time_now()
        if create_timestamp is None:
            create_timestamp = FormatTool.adjust_precision(now.timestamp(), precision=3)
        if order_day is None:
            order_day = TimeTools.date_to_ymd(now)
        if limit_price:
            o.order_type = 'limit'
        else:
            o.order_type = 'market'
        o.symbol = symbol
        o.region = region
        o.broker = broker
        o.currency = currency
        o.level = level
        o.direction = direction
        o.qty = qty
        o.limit_price = limit_price
        o.precision = precision
        o.config_spread = config_spread
        o.config_spread_rate = config_spread_rate
        o.create_timestamp = create_timestamp
        o.order_day = order_day
        o.protect_price = protect_price
        return o

    # 创建对象时必填的字段
    @property
    def symbol(self) -> str:
        return self.d.get('symbol')

    @symbol.setter
    def symbol(self, v: str):
        self.d['symbol'] = v

    @property
    def region(self):
        return self.d.get('region', 'US')

    @region.setter
    def region(self, v):
        self.d['region'] = v

    @property
    def broker(self):
        return self.d.get('broker', 'tiger')

    @broker.setter
    def broker(self, v):
        self.d['broker'] = v

    @property
    def create_timestamp(self) -> float:
        return self.d.get('createTime')

    @create_timestamp.setter
    def create_timestamp(self, v: float):
        self.d['createTime'] = v

    @property
    def level(self) -> int:
        return self.d.get('level')

    @level.setter
    def level(self, v):
        self.d['level'] = v

    @property
    def order_day(self) -> str:
        return self.d.get('orderDay')

    @order_day.setter
    def order_day(self, v: str):
        self.d['orderDay'] = v

    @property
    def direction(self) -> str:
        return self.d.get('direction')

    @direction.setter
    def direction(self, v):
        self.d['direction'] = v

    @property
    def qty(self) -> int:
        return self.d.get('qty', 0)

    @qty.setter
    def qty(self, v):
        self.d['qty'] = v

    @property
    def limit_price(self) -> float:
        return self.d.get('limitPrice')

    @limit_price.setter
    def limit_price(self, v: float):
        """
        设置订单的价格，市价单填入0
        Parameters
        ----------
        v

        Returns
        -------

        """
        self.d['limitPrice'] = v

    @property
    def spread(self) -> float:
        spread = 0.0
        if isinstance(self.avg_price, (float, int, )):
            spread = FMT.spread(self.avg_price, self.precision, self.config_spread, self.config_spread_rate)
        return spread

    @property
    def config_spread(self) -> float:
        return self.d.get('configSpread', None)

    @config_spread.setter
    def config_spread(self, v: float):
        self.d['configSpread'] = v

    @property
    def config_spread_rate(self) -> float:
        return self.d.get('configSpreadRate', None)

    @config_spread_rate.setter
    def config_spread_rate(self, v: float):
        self.d['configSpreadRate'] = v

    @property
    def currency(self) -> str | None:
        return self.d.get('currency')

    @currency.setter
    def currency(self, v: str):
        """
        货币代码，仅用于显示正确的货币单位
        Parameters
        ----------
        v

        Returns
        -------

        """
        self.d['currency'] = v

    @property
    def precision(self):
        return self.d.get('precision', 2)

    @precision.setter
    def precision(self, v):
        self.d['precision'] = v

    # 交易系统创建订单产生的字段
    @property
    def order_type(self):
        return self.d.get('orderType', 'limit')

    @order_type.setter
    def order_type(self, v: str):
        self.d['orderType'] = v

    @property
    def order_id(self):
        """
        非中国内地证券交易一般记录的是"订单号码"，
        中国内地证券交易则记录的是"委托号码"或者称"合同号码"。
        考虑到中国内地订单号码规则，以及支持多券商，order_id 属性已不能作为唯一订单标识
        Returns
        -------

        """
        return self.d.get('orderId')

    @order_id.setter
    def order_id(self, v):
        self.d['orderId'] = v

    # 交易系统刷新的字段
    @property
    def error_reason(self) -> str:
        return self.d.get('errorReason')

    @error_reason.setter
    def error_reason(self, v: str):
        self.d['errorReason'] = v

    @property
    def trade_timestamp(self) -> float:
        return self.d.get('tradeTimestamp')

    @trade_timestamp.setter
    def trade_timestamp(self, v):
        self.d['tradeTimestamp'] = v

    @property
    def filled_qty(self) -> int:
        return self.d.get('filledQty', 0)

    @filled_qty.setter
    def filled_qty(self, v):
        self.d['filledQty'] = v

    @property
    def remain_qty(self) -> int:
        return self.d.get('remainQty')

    @remain_qty.setter
    def remain_qty(self, v):
        self.d['remainQty'] = v

    @property
    def avg_price(self) -> float:
        return self.d.get('avgPrice')

    @avg_price.setter
    def avg_price(self, v: float):
        self.d['avgPrice'] = v

    @property
    def is_canceled(self) -> bool:
        return self.d.get('isCanceled', False)

    @is_canceled.setter
    def is_canceled(self, v: bool):
        self.d['isCanceled'] = v

    # 运行时计算的字段
    @property
    def unique_id(self):
        return f'{self.broker}.{self.order_day}.{self.order_id}'

    @property
    def has_error(self):
        reason = self.error_reason
        if reason and reason not in self.IGNORE_REASONS:
            return True
        return False

    @property
    def is_filled(self):
        return bool(self.qty == self.filled_qty)

    @property
    def filled_value(self) -> float:
        price = 0.0
        if self.avg_price:
            if self.is_buy:
                price = self.avg_price + abs(self.spread)
            if self.is_sell:
                price = self.avg_price - abs(self.spread)
        return (self.filled_qty or 0.0) * price

    @property
    def is_today(self):
        tz = TimeTools.region_to_tz(region=self.region)
        today = TimeTools.us_day_now(tz=tz)
        return today == self.order_day

    @property
    def is_buy(self) -> bool:
        return self.direction == 'BUY'

    @property
    def is_sell(self) -> bool:
        return self.direction == 'SELL'

    @property
    def protect_price(self) -> float:
        """
        原中信证券需要在市价单中填写保护限价,
        为了防止行情源错误数据触发了市价, 市价成交之后会确认成交价是否在 protect_price 合理价格内,
        如果检查失败, 则触发风控错误.
        """
        return self.d['protectPrice']

    @protect_price.setter
    def protect_price(self, v: float):
        self.d['protectPrice'] = v

    @property
    def refreshable(self) -> bool:
        """
        是否是可更新状态的订单
        = 今天的 && 没有返回错误信息的 && 没有全成交的
        不使用 is_canceled 是因为取消订单动作是异步的，如果发出指令到处理完成期间有成交变动，还是需要再次更新订单信息的
        :return:
        """
        return self.is_today and not self.has_error and not self.is_filled

    @property
    def cancelable(self):
        return self.is_waiting_filling

    @property
    def is_waiting_filling(self) -> bool:
        """
        是否是今天的，未异常的，未取消的，未完全成交的订单。
        例：今天仍在待成交量的订单
        :return:
        """
        return self.is_today and not self.has_error and not self.is_canceled and not self.is_filled

    @property
    def order_flags(self) -> list[str]:
        flags = list()
        if self.has_error:
            flags.append('止')
        if self.is_canceled:
            flags.append('撤')
        return flags

    @property
    def order_emoji(self):
        tz = TimeTools.region_to_tz(region=self.region)
        date = TimeTools.us_time_now(tz=tz)
        day = date.strftime('%Y-%m-%d')
        is_today = day == self.order_day
        if not is_today:
            icon = '💾'
        elif self.is_filled:
            icon = '✅'
        elif self.is_waiting_filling:
            icon = '⏳'
        elif self.order_flags:
            icon = '❌'
        else:
            icon = '✅'
        return icon

    def __str__(self):
        flags = '{}{}'.format('[E]' if self.has_error else '', '[C]' if self.is_canceled else '')
        symbol = ''
        level = ''
        if self.DISPLAY_SHOW_SYMBOL:
            symbol = self.symbol
        if self.DISPLAY_SHOW_LEVEL:
            level = f'Level{self.level} '
        return f'<Order {self.order_id} {symbol}{flags}({level}' \
               f'{FMT.pretty_usd(self.limit_price, currency=self.currency)}@{self.order_day}) ' \
               f'{self.direction} ' \
               f'avg{FMT.pretty_usd(self.avg_price, currency=self.currency)}@{self.filled_qty:,}(maxQty:{self.qty:,})>'

    def __repr__(self):
        return self.__str__()


__all__ = ['Order', ]
