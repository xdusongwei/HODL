"""
将没有关联上的订单补挂到系统中
例如发出下单指令发生等待超时引发崩溃，事后人工核对该订单在券商系统中已提交，决定停服后使用该脚本补挂订单信息。
需要填写基本的订单属性，这些待补充的信息一般在日志中会有事前记录可供查找，后面系统刷新订单时会自行补充其他字段信息。
"""
import json
from hodl.state import *
from hodl.tools import *
from hodl.broker import *


print('补挂订单信息脚本')
symbol = input('输入symbol:\n')
var = VariableTools()
config = var.store_configs[symbol]
assert config

region = config.region
currency = config.currency
broker = config.broker
level = int(input('输入level:\n'))
order_day = input('输入orderDay, 格式为YYYY-mm-dd:\n')
direction = input('输入direction, 可以是BUY, SELL:\n')
qty = int(input('输入订单数量qty:\n'))
limit_price = float(input('输入订单限价, 0代表市价单:\n'))
order_id = input('输入订单号/委托号/合同号:\n')
filled_volume = input('(可选)输入已成交数量，不需要设置则直接回车:\n')
filled_price = input('(可选)输入已成交均价，不需要设置则直接回车:\n')


match broker:
    case TigerApi.BROKER_NAME:
        order_id = int(order_id)

limit_price = limit_price if limit_price > 0 else None
spread = config.buy_spread if direction == 'BUY' else config.sell_spread

order = Order.new_order(
    symbol=symbol,
    region=region,
    broker=broker,
    currency=currency,
    level=level,
    direction=direction,
    qty=qty,
    limit_price=limit_price,
    precision=config.precision,
    spread=spread,
    create_timestamp=TimeTools.us_time_now().timestamp(),
    order_day=order_day,
)
order.order_id = order_id
order.filled_qty = int(filled_volume) if filled_volume else 0
order.avg_price = float(filled_price) if filled_price else 0

state_file = config.state_file_path
assert state_file
print('状态文件位置:', state_file)

with open(state_file, 'r', encoding='utf8') as f:
    text = f.read()
state = json.loads(text)
state = State(state)
state.plan.append_order(order)

print(json.dumps(state.plan.d, indent=2))
input('确认?')

config_text = json.dumps(state, indent=4)
with open(state_file, 'w', encoding='utf8') as f:
    f.write(config_text)

print('已完成')
