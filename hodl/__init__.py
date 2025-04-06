from hodl.tools import LocateTools

# 预载券商和机器人对话的模块, 使它们的类被注册
LocateTools.discover_plugins('hodl.plugin.broker')
LocateTools.discover_plugins('hodl.plugin.conversation')
