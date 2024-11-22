from hodl.quote_mixin import *
from hodl.trade_mixin import *


class IsolatedStore(QuoteMixin, TradeMixin):
    """
    继承这个类可以编写基于固定持仓标的的自定义策略,
    提供了包装过的市场行情交易的自动代理对象,
    使用自定义策略需要自行创建启动脚本, 使得自定义策略类被加载, 然后调用 Manager.run() 方法.

    @trade_strategy(strategy_name='myStrategy')
    class MyStrategy(IsolatedStore):
        def run(self):
            super().run()
            while True:
                TimeTools.sleep(6.0)
                broker_name, broker_display, market_status = self.current_market_status()
                quote = self.current_quote()
                cash_amount = self.current_cash()
                chip_count = self.current_chip()
                ...
                
        def extra_html(self):
            return '<div>my strategy html report</div>'
    """
    pass


__all__ = ['IsolatedStore', ]
