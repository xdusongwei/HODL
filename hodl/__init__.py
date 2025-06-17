from hodl.tools import LocateTools
from hodl.store import *


# 预载券商和机器人对话的模块, 使它们的类被注册
LocateTools.discover_plugins('hodl.plugin.broker')
LocateTools.discover_plugins('hodl.plugin.conversation')
cls_list = LocateTools.discover_plugins('hodl.plugin.strategy')
for t in cls_list:
    if not issubclass(t, Store):
        continue
    if not issubclass(t, StrategySelector):
        continue
    Store.STRATEGY_SELECTOR_SET.add(t)
