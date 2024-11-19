from hodl.quote_mixin import *
from hodl.trade_mixin import *


class IsolatedStore(QuoteMixin, TradeMixin):
    pass


__all__ = ['IsolatedStore', ]
