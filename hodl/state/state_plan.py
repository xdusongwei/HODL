from hodl.state.state_order import Order
from hodl.plan_calc import PlanCalc
from hodl.tools import *


class Plan(DictWrapper):
    """
    下单计划状态记录运行时的下单计划重要信息。
    主要围绕订单和因子参数，
    以及其他在运行时不可改变的设置会从持仓配置中复制过来。
    """
    @classmethod
    def new_plan(
            cls,
            store_config: StoreConfig,
    ):
        plan = Plan()
        plan.total_chips = store_config.max_shares
        plan.prudent = store_config.prudent
        plan.price_rate = store_config.price_rate
        return plan

    @property
    def master_total_chips(self):
        return self.d.get('masterTotalChips', 0)

    @master_total_chips.setter
    def master_total_chips(self, v: int):
        assert isinstance(v, int)
        assert v >= 0
        self.d['masterTotalChips'] = v

    @property
    def master_sold_chips(self):
        return self.d.get('masterSoldChips', 0)

    @master_sold_chips.setter
    def master_sold_chips(self, v: int):
        assert isinstance(v, int)
        assert v >= 0
        self.d['masterSoldChips'] = v

    @property
    def base_price(self):
        return self.d.get('basePrice')

    @base_price.setter
    def base_price(self, v: float):
        self.d['basePrice'] = v

    @property
    def prudent(self):
        return self.d.get('prudent', True)

    @prudent.setter
    def prudent(self, v):
        self.d['prudent'] = v

    @property
    def total_chips(self) -> int:
        return self.d.get('totalChips')

    @total_chips.setter
    def total_chips(self, v: int):
        self.d['totalChips'] = v

    @property
    def latest_order_day(self):
        return self.d.get('latestOrderDay')

    @latest_order_day.setter
    def latest_order_day(self, v: str):
        self.d['latestOrderDay'] = v

    @property
    def earning(self):
        return self.d.get('earning')

    @earning.setter
    def earning(self, v: int):
        self.d['earning'] = v

    @property
    def buy_back_price(self):
        return self.d.get('buyBackPrice')

    @buy_back_price.setter
    def buy_back_price(self, v: float):
        self.d['buyBackPrice'] = v

    @property
    def weight(self) -> list[float]:
        return self.d.get('weight')

    @weight.setter
    def weight(self, v: list[float]):
        self.d['weight'] = v

    @property
    def sell_rate(self) -> list[float]:
        return self.d.get('sellRate')

    @sell_rate.setter
    def sell_rate(self, v: list[float]):
        self.d['sellRate'] = v

    @property
    def buy_rate(self) -> list[float]:
        return self.d.get('buyRate')

    @buy_rate.setter
    def buy_rate(self, v: list[float]):
        self.d['buyRate'] = v

    @property
    def factor_type(self) -> str:
        return self.d.get('factorType', '--')

    @factor_type.setter
    def factor_type(self, v: str):
        self.d['factorType'] = v

    @property
    def has_factors(self) -> bool:
        return bool(self.weight and self.buy_rate and self.sell_rate)

    @property
    def price_rate(self) -> float:
        return self.d.get('priceRate', 1.0)

    @price_rate.setter
    def price_rate(self, v: float):
        self.d['priceRate'] = v

    @property
    def rework_price(self):
        return self.d.get('reworkPrice')

    @rework_price.setter
    def rework_price(self, v: float):
        assert v > 0.0
        self.d['reworkPrice'] = v

    @property
    def give_up_price(self):
        return self.d.get('giveUpPrice', None)

    @give_up_price.setter
    def give_up_price(self, v: float):
        assert v > 0.0
        self.d['giveUpPrice'] = v

    @property
    def orders(self) -> list[Order]:
        if 'orders' not in self.d:
            self.d['orders'] = list()
        return [Order(i) for i in self.d.get('orders')]

    @property
    def sell_volume(self):
        orders = self.orders
        sell_orders = [order for order in orders if order.is_sell and not order.is_waiting_filling]
        sell_volume = sum(order.filled_qty for order in sell_orders)
        return sell_volume

    @property
    def buy_volume(self):
        orders = self.orders
        buy_orders = [order for order in orders if order.is_buy and not order.is_waiting_filling]
        buy_volume = sum(order.filled_qty for order in buy_orders)
        return buy_volume

    @property
    def should_today_get_off(self) -> bool:
        """
        根据没有·有没有完全成交的今天买单确定是否今天应该收工
        = 今天的 && 买入方向 && 全成交
        订单空集时返回False
        :return:
        """
        orders = self.orders
        for order in orders:
            if order.is_today and order.is_filled and order.is_buy:
                return True
        else:
            if self.sell_volume and self.sell_volume == self.buy_volume:
                return True
        return False

    @property
    def today_not_contain_sell_order(self) -> bool:
        """
        是否不存在今天的任何卖单
        :return:
        """
        orders = self.orders
        orders = [order for order in orders if order.is_today and order.is_sell]
        return not orders

    @property
    def all_today_sell_completed(self) -> bool:
        """
        确定今天的卖单不存在今天的，未异常的，未取消的，未完全成交的订单。
        如果今天没有卖单则返回False， 以避免第二条件项会反而满足第一条件项
        :return:
        """
        orders = [order for order in self.orders if order.is_today and order.is_sell]
        if not orders:
            return False
        return not any(order for order in orders if order.is_waiting_filling)

    def append_order(self, order: Order):
        """
        将订单加入orders列表
        :param order:
        :return:
        """
        if 'orders' not in self.d:
            self.d['orders'] = list()
        orders: list[dict] = self.d['orders']
        orders.append(order.d)

    def clean_orders(self):
        """
        清理掉非今天的，没有成交的订单信息
        :return:
        """
        orders = self.orders
        result = list()
        for order in orders:
            if order.is_today:
                result.append(order.d)
            elif order.filled_qty:
                result.append(order.d)
        self.d['orders'] = result

    @property
    def cleanable(self) -> bool:
        """
        根据订单状态(有今天的订单 或者 非今天但有成交的订单)确定Plan对象是否可清理
        :return:
        """
        if not self.d:
            return True
        orders = self.orders
        any_today = any(order for order in orders if order.is_today)
        if any_today:
            return False
        elif self.earning is not None:
            return True
        return not any(order for order in orders if order.filled_qty and not order.is_today)

    def total_sell_by_level(self, level: int) -> int:
        """
        统计指定level所有卖单的实际成交量，只适用于单日未下任何卖单时
        :param level:
        :return:
        """
        orders = self.orders
        orders = [order for order in orders if order.is_sell and order.level == level]
        return sum(order.filled_qty for order in orders)

    def today_contains_buy_level(self, level: int) -> bool:
        """
        今天的买单是否存在指定level的订单
        :param level:
        :return:
        """
        orders = self.orders
        orders = [order for order in orders if order.is_today and order.is_buy and order.level == level]
        return any(orders)

    def sell_order_active_count(self) -> int:
        """
        卖单待成交的订单数量。
        空集合返回True
        :return:
        """
        orders = self.orders
        orders = [order for order in orders if order.is_sell and order.is_waiting_filling]
        return len(orders)

    def buy_order_not_active(self) -> bool:
        """
        没有任何买单是待成交的。
        没有任何买单返回True
        :return:
        """
        return self.buy_order_active_count() == 0

    def buy_order_active_count(self) -> int:
        """
        买单待成交的订单数量。
        空集合返回True
        :return:
        """
        orders = self.orders
        orders = [order for order in orders if order.is_buy and order.is_waiting_filling]
        return len(orders)

    def total_volume_not_active(self, assert_zero=True) -> int:
        """
        计算除了待成交卖单以外的所有成交量差额。
        = 总卖量 - 总买量
        :return:
        """
        sell_volume = self.sell_volume
        buy_volume = self.buy_volume
        result = sell_volume - buy_volume
        if assert_zero:
            assert result > 0
        return result

    def current_sell_level(self) -> int:
        """
        查找全部卖单中level最大值，没有则返回0
        :return:
        """
        orders = self.orders
        orders = [order for order in orders if order.is_sell]
        return max([order.level for order in orders], default=0)

    def current_sell_level_filled(self) -> int:
        """
        查找卖单全成交level最大值，没有则返回0
        :return:
        """
        orders = self.orders
        orders = [order for order in orders if order.is_sell and order.is_filled]
        return max([order.level for order in orders], default=0)

    def latest_today_buy_order(self) -> Order | None:
        """
        返回今天最新产生的买单，如果有
        :return:
        """
        orders = self.orders
        orders = [order for order in orders if order.is_today and order.is_buy]
        orders = sorted(orders, key=lambda i: i.create_timestamp, reverse=True)
        if orders:
            return orders[0]
        else:
            return None

    def calc_earning(self) -> int:
        """
        计算收益
        :return:
        """
        orders = self.orders
        sell_cost = sum(order.filled_value for order in orders if order.is_sell)
        buy_income = sum(order.filled_value for order in orders if order.is_buy)
        return int(sell_cost - buy_income)

    def cog(self, precision: int = None) -> float | None:
        """
        卖出部分的质点价格
        Returns
        -------

        """
        orders = self.orders
        sell_cost = sum(order.filled_value for order in orders if order.is_sell)
        buy_income = sum(order.filled_value for order in orders if order.is_buy)
        sell_value = sell_cost - buy_income
        sell_volume = self.sell_volume - self.buy_volume
        if sell_volume:
            if precision is None:
                precision = 3
            return FormatTool.adjust_precision(sell_value / sell_volume, precision)
        return None

    @property
    def table_ready(self) -> bool:
        return not self.earning and self.base_price

    def plan_calc(self):
        return PlanCalc(
            weight=self.weight,
            sell_rate=self.sell_rate,
            buy_rate=self.buy_rate,
            price_rate=self.price_rate,
        )


__all__ = [
    'Plan',
]
