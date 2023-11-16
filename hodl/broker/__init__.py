from typing import Type
from hodl.broker.base import *
from hodl.broker.tiger import *
from hodl.broker.citics import *
from hodl.broker.okx import *
from hodl.broker.binance import *
from hodl.broker.futu import *
from hodl.broker.interactive_brokers import *
from hodl.broker.myquant import *


BROKERS: list[Type[BrokerApiBase]] = [
    TigerApi,
    CiticsRestApi,
    OkxRestApi,
    BinanceApi,
    FutuApi,
    InteractiveBrokersApi,
    MyQuantApi,
]
