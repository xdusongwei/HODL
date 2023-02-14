"""
接入富途证券的API文档
https://openapi.futunn.com/futu-api-doc/
"""
from hodl.broker.base import *


class FutuApi(BrokerApiBase):
    BROKER_NAME = 'futu'
    BROKER_DISPLAY = '富途证券'
    META = [
        ApiMeta(
            trade_type=BrokerTradeType.STOCK,
            share_market_state=False,
            share_quote=False,
            market_status_regions={'US', 'HK', 'CN', },
            quote_regions={'US', 'HK', 'CN', },
            trade_regions={'US', 'HK', },
        ),
    ]


__all__ = ['FutuApi', ]
