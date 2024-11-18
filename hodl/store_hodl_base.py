from hodl.exception_tools import *
from hodl.state import *
from hodl.store import *
from hodl.tools import *


class StoreHodlBase(IsolatedStore):
    STATE_SLEEP = '被抑制'
    STATE_TRADE = '监控中'
    STATE_GET_OFF = '已套利'

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
