"""
接入盈透证券的API文档
https://interactivebrokers.github.io/cpwebapi/
"""
from hodl.broker.base import *


class InteractiveBrokers(BrokerApiBase):
    BROKER_NAME = 'interactiveBrokers'
    BROKER_DISPLAY = '盈透证券'
    META = [
        ApiMeta(
            trade_type=BrokerTradeType.STOCK,
            share_market_state=False,
            share_quote=False,
            market_status_regions={'US', },
            quote_regions={'US', },
            trade_regions={'US', },
        ),
    ]


__all__ = ['InteractiveBrokers', ]
