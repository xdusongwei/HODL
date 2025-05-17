from hodl.exception_tools import *
from hodl.state import *
from hodl.store_isolated import *
from hodl.tools import *


class StoreHodlBase(IsolatedStore):
    ENABLE_LOG_ALIVE = True
    SHOW_EXCEPTION_DETAIL = False

    STATE_SLEEP = '被抑制'
    STATE_TRADE = '监控中'
    STATE_GET_OFF = '已套利'

    def args(self) -> tuple[StoreConfig, State, Plan, ]:
        return self.store_config, self.state, self.state.plan,

    @property
    def exception(self) -> Exception | None:
        return getattr(self, '_exception', None)

    @exception.setter
    def exception(self, v: Exception):
        setattr(self, '_exception', v)

    def before_loop(self):
        self.load_state()
        setattr(self, '_begin_time', TimeTools.get_utc())
        return True

    def after_loop(self):
        self.save_state()
        now = TimeTools.get_utc()
        begin_time = getattr(self, '_begin_time', now)
        process_time = FormatTool.adjust_precision((now - begin_time).total_seconds(), 3)
        self.process_time = process_time

    @classmethod
    def build_table(cls, store_config: StoreConfig, plan: Plan):
        plan_calc = plan.plan_calc()
        profit_table = plan_calc.profit_rows(
            base_price=plan.base_price,
            max_shares=plan.total_chips,
            buy_spread=store_config.buy_spread,
            sell_spread=store_config.sell_spread,
            precision=store_config.precision,
            shares_per_unit=store_config.shares_per_unit,
            buy_spread_rate=store_config.buy_spread_rate,
            sell_spread_rate=store_config.sell_spread_rate,
        )
        return profit_table

    def current_table(self):
        return self.build_table(store_config=self.store_config, plan=self.state.plan)

    def margin_amount(self) -> float:
        try:
            if self.broker_proxy:
                trade_broker = self.broker_proxy.trade_broker
                broker_config = trade_broker.query_broker_config()
            else:
                broker_config = dict()
        except BrokerMismatchError:
            broker_config = dict()
        return abs(broker_config.get('margin_amount', 0.0))


__all__ = ['StoreHodlBase']
