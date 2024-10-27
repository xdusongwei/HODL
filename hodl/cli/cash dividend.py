"""
除去正在进行交易(存在历史订单)的持仓的现金红利，
将基准价格和所有订单价格统一去除现金红利。
"""
from hodl.state import *
from hodl.tools import *


broker = input('broker:\n')
symbol = input('symbol:\n')
var = VariableTools()
config = var.store_configs_by_group()[StoreKey('default', broker, symbol, )]
assert config


cash = float(input('cash dividend per share:'))
assert cash > 0

state_file = config.state_file_path
assert state_file
print('state file:', state_file)
with open(state_file, 'r', encoding='utf8') as f:
    text = f.read()
state = FormatTool.json_loads(text)
state = State(state)
if not state.plan.base_price:
    raise ValueError(f'base_price not exists')
orders = state.plan.orders
if not orders:
    raise ValueError(f'orders is empty')
for order in orders:
    if order.is_waiting_filling:
        raise ValueError(f'{order} is alive')


print(f'\n\nsymbol:{symbol}\ncash dividend per share:{FormatTool.pretty_price(cash, config=config)}')
current_price = state.plan.base_price
new_price = FormatTool.adjust_precision(current_price - cash, precision=config.precision)
print(f'base_price: {FormatTool.pretty_price(current_price, config=config)} to {FormatTool.pretty_price(new_price, config=config)}')
assert new_price > 0
state.plan.base_price = new_price
for order in orders:
    current_price = order.avg_price
    new_price = FormatTool.adjust_precision(current_price - cash, precision=config.precision)
    print(f'{order}: {FormatTool.pretty_price(current_price, config=config)} to {FormatTool.pretty_price(new_price, config=config)}')
    assert new_price > 0
    order.avg_price = new_price
input('confirm?')

config_text = FormatTool.json_dumps(state)
with open(state_file, 'w', encoding='utf8') as f:
    f.write(config_text)

print('done')
