"""
将没有关联上的订单补挂到系统中
例如发出下单指令发生等待超时引发崩溃，事后人工核对该订单在券商系统中已提交，决定停服后使用该脚本补挂订单信息。
需要填写基本的订单属性，这些待补充的信息一般在日志中会有事前记录可供查找，后面系统刷新订单时会自行补充其他字段信息。
"""
import json
from hodl.state import *
from hodl.tools import *
from hodl.broker import *


symbol = input('symbol:\n')
var = VariableTools()
config = var.store_configs[symbol]
assert config

region = config.region
currency = config.currency
broker = config.broker
level = int(input('level:\n'))
order_day = input('orderDay, YYYY-mm-dd:\n')
direction = input('direction, BUY, SELL:\n')
qty = int(input('qty:\n'))
limit_price = float(input('limit_price, 0 for market price:\n'))
order_id = input('order id/contract id:\n')


match broker:
    case TigerApi.BROKER_NAME:
        order_id = int(order_id)

limit_price = limit_price if limit_price > 0 else None

order = Order()
order.currency = currency
order.symbol = symbol
order.region = region
order.broker = broker
order.level = level
order.order_day = order_day
order.create_timestamp = TimeTools.us_time_now().timestamp()
order.direction = direction
order.qty = qty
order.limit_price = limit_price
order.order_id = order_id
order.filled_qty = 0
order.avg_price = 0

state_file = config.state_file_path
assert state_file
print('state file:', state_file)

with open(state_file, 'r', encoding='utf8') as f:
    text = f.read()
state = json.loads(text)
state = State(state)
state.plan.append_order(order)

print(json.dumps(state.plan.d, indent=2))
input('confirm?')

config_text = json.dumps(state, indent=4)
with open(state_file, 'w', encoding='utf8') as f:
    f.write(config_text)

print('done')
