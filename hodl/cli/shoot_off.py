"""
弹射掉剩余持仓以当前档位的卖出价格执行卖出，
以换取比下单计划中较高的价格全部买回，
达到在预测标的大幅上涨前尽快全部买回，使得下次卖出开仓的基准价格变高，防止未来剧烈波动全部卖飞或短期无法套利的目的。
"""
import json
from hodl.plan_calc import ProfitRow
from hodl.state import *
from hodl.store_base import StoreBase
from hodl.tools import *


symbol = input('symbol:\n')
rate = float(input('change rate, 0.97 = 3%:'))
assert 1 > rate > 0


var = VariableTools()
config = var.store_configs[symbol]
assert config
state_file = config.state_file_path
assert state_file
print('state file:', state_file)


with open(state_file, 'r', encoding='utf8') as f:
    text = f.read()
state = json.loads(text)
state = State(state)

plan = state.plan

level = plan.current_sell_level_filled()
assert level > 0

sr = plan.sell_rate
br = plan.buy_rate
w = plan.weight

sell_rate = sr[level - 1]
st = sum([sr[i] * w[i] for i in range(level)]) + sum([sell_rate * w[i] for i in range(level, len(w))])
bc = sum([br[i] * w[i] for i in range(level)])
wr = sum(w[level:])
assert wr
buy_rate = round((st * rate - bc) / wr, 4)

current_buy_rate = br[level - 1]
print('target sell_rate', sell_rate)
print('target buy_rate', buy_rate)
print('current buy_rate', current_buy_rate)
assert sell_rate > buy_rate >= current_buy_rate

new_sr = sr[:level] + [sell_rate] * (len(w) - level)
new_br = br[:level] + [current_buy_rate] * (len(w) - level)
new_br[-1] = buy_rate

plan.sell_rate = new_sr
plan.buy_rate = new_br

state.plan.d['shootOffFactors'] = {
    'sellRate': sr,
    'buyRate': br,
    'weight': w,
}

rows = StoreBase.build_table(store_config=config, plan=plan)
for row in rows:
    row: ProfitRow = row
    print(row, row.total_rate)

input('confirm?')

config_text = json.dumps(state, indent=4)
with open(state_file, 'w', encoding='utf8') as f:
    f.write(config_text)

print('done')
