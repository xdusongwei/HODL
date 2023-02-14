from typing import Type
from hodl.broker.base import *
from hodl.broker.tiger import *
from hodl.broker.citics import *
from hodl.broker.okx import *
from hodl.broker.binance import *
from hodl.broker.futu import *


BROKERS: list[Type[BrokerApiBase]] = [
    TigerApi,
    CiticsRestApi,
    OkxRestApi,
    BinanceApi,
    FutuApi,
]


def broker_display(broker_name: str) -> str:
    for broker in BROKERS:
        if broker.BROKER_NAME == broker_name:
            return broker.BROKER_DISPLAY
    return broker_name or '--'
