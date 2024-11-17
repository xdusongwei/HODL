from hodl.state import *
from hodl.tools import TimeTools, StoreConfig
from hodl.exception_tools import *
from hodl.tools import FormatTool as FMT


class RiskControl:
    """
    检查分为两个入口
    __init__: 根据持仓的状态做出判断
    place_order_check: 对下单指令和持仓的状态做判断
    如果判断为异常，异常信息会记录到持仓状态，Store对象将自杀以拒绝主体(下单)工作，除非人工核对完成，并删除了持仓状态中的风控字段，方可再启动进程.
    模块围绕持仓状态去做一些判断工作，出现的问题必须人工介入，为防呆，风控异常的Store对象即便重启进程仍不能正常工作
    注意，像下单动作发到broker中间出了问题，比如broker返回的结果网络丢包, 这边的系统超时会抛出非风控错误,
    由于这类非风控异常不涉及持仓状态数据的改动记录，不是风控模块管理范围，而且这种情况没有任何防呆设计，
    没有核对系统异常状态信息即重启系统可能会重放订单！

    LSOD
    lsod(上一次提交订单日)提供了一组机制，保证确认前一个交易日内的订单生命周期有效结束
    a) 盘中时，如果在新的交易日时发现持仓的lsod订单提交日没有盖章[ClosingChecked]，则出现异常；否则下单时会重置lsod信息字段，标记交易日当日
    b) 收盘阶段时，如果lsod字段盖过章则无误；若是当日需要盖章，则进行盖章；否则出现异常
    基于此，来记录事实: 下单日系统在闭市阶段时仍然活着，且更新过当日订单，订单里面的数值不会再变化，订单的生命周期可以确认结束
    这个机制需要市场存在”收盘“状态，比如加密货币交易所不存在”收盘“，以及broker没有当日自动撤单的机制，需要设定一天内的一部分时间作为撤单收盘时段，

    核算持仓数量
    对于[锁定持仓]开启的持仓，需要根据当日持仓情况与历史订单核对一次总数量是否与配置中的max_shares一致

    当日首单检查-不能做空
    重新核对历史订单和当日持仓数量，确保下单不会使持仓为负

    当日首单检查-现金足够
    根据当日现金额确认能否满足下单金额，这个方式约束比较有限

    当日首单检查-现金足够买回剩余股票
    检查当日待买标的的数量和价格，当日剩余金额能否支持全部买回

    市价单成交价格检查
    成交的市价单根据其保护限价(protect_price)比对, 判断是否按照错误价格进行了成交
    """
    ORDER_DICT = dict()
    # 记录运行时产生的订单, 作为检查来源, 防止在重复的状态版本下重复的订单level和重复的订单方向
    ORDER_LEVEL_DICT: dict[tuple[str, str, int], Order] = dict()

    def __init__(
            self,
            store_config: StoreConfig,
            margin_amount: float,
            state: State,
            cash_balance_func,
            latest_price: float,
            max_shares: int,
            order_checked: bool,
    ):
        assert max_shares > 0
        assert margin_amount >= 0.0
        self.state = state
        self.max_shares = max_shares
        self.cash_balance_func = cash_balance_func
        self.latest_price = latest_price
        self.store_config = store_config
        self.margin_amount = margin_amount

        if self.state.market_status == 'TRADING':
            self.when_trading()
        if self.state.market_status == 'CLOSING':
            self.when_closing(order_checked=order_checked)
        for order in state.plan.orders:
            RiskControl.ORDER_DICT[order.unique_id] = order
        self.market_order_check()

    @classmethod
    def _increase_times(cls, order: Order, state: State):
        if order.unique_id in RiskControl.ORDER_DICT:
            raise RiskControlError(f'订单uniqueId:{order.unique_id}重复出现')
        RiskControl.ORDER_DICT[order.unique_id] = order
        level_key = state.version, order.direction, order.level
        if duplicate_order := RiskControl.ORDER_LEVEL_DICT.get(level_key):
            if duplicate_order.has_error or duplicate_order.is_canceled:
                RiskControl.ORDER_LEVEL_DICT[level_key] = order
            else:
                raise RiskControlError(f'状态版本{state.version} 订单{order}重复出现')

    @classmethod
    def today_order_times_by_symbol(cls, symbol: str) -> int:
        orders = [order for order in RiskControl.ORDER_DICT.values() if order.is_today and order.symbol == symbol]
        return len(orders)

    def _cash_balance_check(self, order: Order):
        if not order.is_buy:
            return
        cash_balance = self.cash_balance_func() + self.margin_amount
        if order.limit_price:
            value = order.limit_price * order.qty
        else:
            value = self.latest_price * order.qty
        if value > cash_balance:
            raise RiskControlError(f'账户现金无法购买价值{FMT.pretty_price(value, config=self.store_config)}的订单{order}')

    def _order_day_times_check(self, order: Order):
        us_day = TimeTools.us_day_now()
        if order.order_day != us_day:
            raise RiskControlError(f'下单日期({order.order_day}不是当天{us_day}')

        times = self.today_order_times_by_symbol(symbol=order.symbol)
        if times == 0:
            quote_time = self.state.quote_time
            chip_day = self.state.chip_day
            cash_day = self.state.cash_day
            if TimeTools.date_to_ymd(TimeTools.from_timestamp(quote_time)) != us_day:
                raise RiskControlError(f'每日最新行情日期({TimeTools.from_timestamp(quote_time)}不是当天{us_day}')
            if chip_day != us_day:
                raise RiskControlError(f'每日持仓检查日期({chip_day}不是当天{us_day}')
            if cash_day != us_day:
                raise RiskControlError(f'每日现金检查日期({cash_day}不是当天{us_day}')
            orders = self.state.plan.orders
            chip_count = self.state.chip_count
            cash_amount = self.state.cash_amount + self.margin_amount
            total_sell = sum(order.filled_qty for order in orders if order.is_sell)
            total_buy = sum(order.filled_qty for order in orders if order.is_buy)
            if self.store_config.lock_position:
                base_chip_count = chip_count
                if self.max_shares != base_chip_count + total_sell - total_buy:
                    raise RiskControlError(
                        f'持仓核算失败, 应清算核对共计{self.max_shares:,}股, '
                        f'实际持仓{chip_count:,}股, '
                        f'已累计卖出{total_sell:,}股, 已累计买入{total_buy:,}股'
                    )
            if not self.store_config.market_price_rate and not order.limit_price:
                raise RiskControlError(f'当日首单交易不能是市价单')
            elif diff := total_sell - total_buy:
                if diff < 0:
                    raise RiskControlError(f'当日首单检查时,总买卖量差额({diff:,})出现了做空情形')
                if order.is_buy and order.limit_price:
                    if diff > 0 and cash_amount / order.limit_price < diff:
                        cash_text = FMT.pretty_price(cash_amount, self.store_config)
                        raise RiskControlError(
                            f'当日首单检查时, '
                            f'现金无法完全买入总买卖量差量的股票: 差额{diff:,}股, '
                            f'现金{cash_text}'
                        )
                    if order.qty * order.limit_price > cash_amount:
                        cash_text = FMT.pretty_price(cash_amount, self.store_config)
                        order_value = FMT.pretty_price(order.qty * order.limit_price, self.store_config)
                        raise RiskControlError(
                            f'当日首单检查时, '
                            f'限价单价值({order_value})超过现金额{cash_text}'
                        )

        order_day_times_limit = self.state.plan.plan_calc().table_size * 2 + 1
        if times >= order_day_times_limit:
            raise RiskControlError(f'当日({us_day})订单数量达到上限{times}')

    def _total_sell_check(self, order: Order, orders: list[Order]):
        """
        非今天的订单统计实际成交部分
        今天非活跃订单统计实际成交部分
        今天活跃订单统计最大成交数量
        :param order:
        :param orders:
        :return:
        """
        total = 0
        for order in orders + [order, ]:
            if not order.is_sell:
                continue
            if not order.is_today:
                total += order.filled_qty
            if order.is_today and order.is_waiting_filling:
                total += order.qty
            if order.is_today and not order.is_waiting_filling:
                total += order.filled_qty
        if total > self.max_shares:
            raise RiskControlError(f'总卖量({total})超出设定值{self.max_shares}')
        return total

    def _total_buy_check(self, order: Order, orders: list[Order]):
        """
        非今天的订单统计实际成交部分
        今天非活跃订单统计实际成交部分
        今天活跃订单统计最大成交数量
        :param order:
        :param orders:
        :return:
        """
        total = 0
        for order in orders + [order, ]:
            if not order.is_buy:
                continue
            if not order.is_today:
                total += order.filled_qty
            if order.is_today and order.is_waiting_filling:
                total += order.qty
            if order.is_today and not order.is_waiting_filling:
                total += order.filled_qty
        if total > self.max_shares:
            raise RiskControlError(f'检查总买量({total})超出设定值{self.max_shares}')
        return total

    def place_order_check(self, order: Order, function):
        orders = self.state.plan.orders
        self._order_day_times_check(order=order)
        sell_total = self._total_sell_check(order=order, orders=orders)
        buy_total = self._total_buy_check(order=order, orders=orders)
        diff = sell_total - buy_total
        if diff > self.max_shares:
            raise RiskControlError(f'检查总买卖量相对值差距过大: {diff}')
        if diff < 0:
            raise RiskControlError(f'检查总买卖量出现了做空情形: {diff}')
        self._cash_balance_check(order=order)
        result = function()
        self._increase_times(order=order, state=self.state)
        self.state.reset_lsod()
        return result

    def when_trading(self):
        state = self.state
        if not state.lsod:
            return
        if state.is_lsod_today:
            if state.has_lsod_seal():
                # 系统默认会将一些交易通道接口给出的市场状态中, 未表达的时段设置为闭市,
                # 比如长桥证券, 它仅提供了每个证券市场的正常运行时段, 而不像其他交易通道报告当前各个证券市场的状态.
                # 对于加密货币交易所, 其市场状态实际上是用报告的维护时间段在24小时中扣除的结果.
                #
                # 对于类似长桥证券的A股市场状态数据: 中午休市时段只能被动会标记为闭市, 因为其系统市场状态枚举中没有休市这钟非闭市非开市的字段
                # 这会导致一天闭市两次, 意味着中午休市时段会对今天上午的订单执行了今天 LSOD 完整周期, 而下午产生的新订单 LSOD 检查将被跳过
                # 所以, 这里有一些方案, 如果系统被指示为开市, 那么今天的订单检查的图章需要被去除.
                # 如此, 一天内多次发生闭市, 不会让任何今天的订单跳过检查.
                state.pop_seal()
            return
        if not state.has_lsod_seal():
            raise RiskControlError(
                f'交易时段发现上次订单日期({state.lsod_day()})没有在收盘时更新过订单，'
                f'继续运行可能导致历史订单数据过时')

    def when_closing(self, order_checked: bool):
        state = self.state
        if not state.lsod:
            return
        if state.is_lsod_today:
            if order_checked:
                state.seal_lsod()
        elif not state.has_lsod_seal():
            raise RiskControlError(
                f'收盘时发现上次订单日期({state.lsod_day()})不是今天，即之前有下单的那天没有在收盘阶段更新过订单，'
                f'继续运行可能导致历史订单数据过时')

    def market_order_check(self):
        orders = self.state.plan.orders
        for order in orders:
            if order.limit_price:
                continue
            if not order.protect_price:
                continue
            if not order.avg_price:
                continue
            avg_price = order.avg_price
            protect_price = order.protect_price
            assert 0 < avg_price
            assert 0 < protect_price
            if order.is_buy and avg_price > protect_price:
                raise RiskControlError(f'风控检查到市价单买入成交价格{avg_price}于预期{protect_price}出现严重偏差')
            if order.is_sell and avg_price < protect_price:
                raise RiskControlError(f'风控检查到市价单卖出成交价格{avg_price}于预期{protect_price}出现严重偏差')


__all__ = ['RiskControl', ]
