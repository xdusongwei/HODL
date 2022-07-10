from hodl.broker.base import *
from hodl.broker.tiger import *
from hodl.broker.citics import *
from hodl.broker.okx import *
from hodl.broker.binance import *
from hodl.broker.futu import *


BROKERS: list = [
    TigerApi,
    CiticsRestApi,
    OkxRestApi,
    BinanceApi,
    FutuApi,
]
