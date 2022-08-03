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


symbol = input('输入symbol:\n')
print('输入相对于当前卖档基准价格比例的比例, 需要小于1, 假设当前最高执行过的卖出档位高于基准价格40%, 此处输入比例0.8。')
print('则修改其他后续档位的买入比例为, 140% * 0.8 = 112%, 后续流程会根据期望的112%比例和已卖出部分的加权买入因子，得出最高档的买入因子')
rate = float(input('输入比例值, 例如0.97(基于当前卖出价格缩小3%):'))
assert 1 > rate > 0


var = VariableTools()
config = var.store_configs[symbol]
assert config
state_file = config.state_file_path
assert state_file
print('状态文件路径:', state_file)


with open(state_file, 'r', encoding='utf8') as f:
    text = f.read()
state = json.loads(text)
state = State(state)

plan = state.plan

# 找到当前最高卖出的档位
level = plan.current_sell_level_filled()
assert level > 0

sr = plan.sell_rate
br = plan.buy_rate
w = plan.weight

# 找到当前最高卖出的档位的卖出价的比例因子
sell_rate = sr[level - 1]
# 算出剩余档位卖出因子按最高卖出的档位的因子全部覆盖的情形下，加权的卖出因子
st = sum([sr[i] * w[i] for i in range(level)]) + sum([sell_rate * w[i] for i in range(level, len(w))])
# 现有被卖出的档位，其加权的买入因子
bc = sum([br[i] * w[i] for i in range(level)])
# 没有被卖出的档位的权重和
wr = sum(w[level:])
assert wr
"""
已知期望买入的加权比例(st * rate)，扣除掉已卖出部分的加权买入因子，再除以未卖出部分的权重和，可以得到再期望比例下，全仓卖出后，平均的买入因子
下面会要求，新的买入因子大于等于当前的买入因子，这个要求不一定有必要，如果你需要自由设定足够低的买回价格。
"""
buy_rate = round((st * rate - bc) / wr, 4)

current_buy_rate = br[level - 1]
print('当前档位的卖出比例因子', sell_rate)
print('计算得到新的买回因子', buy_rate)
print('当前档位的买回比例因子', current_buy_rate)
assert sell_rate > buy_rate >= current_buy_rate

# 覆盖掉后续的卖出因子为当前卖出因子
new_sr = sr[:level] + [sell_rate] * (len(w) - level)
# 覆盖掉后续的买回因子为当前档位的买回比例因子
new_br = br[:level] + [current_buy_rate] * (len(w) - level)
# 最后一档的买回比例因子设定为计算得到新的买回因子
new_br[-1] = buy_rate

plan.sell_rate = new_sr
plan.buy_rate = new_br

# 旧的因子转移到其他地方，以备需要时使用
state.plan.d['shootOffFactors'] = {
    'sellRate': sr,
    'buyRate': br,
    'weight': w,
}

# 展示所有档位的因子和获利情况，检查因子设定是否会造成亏损
rows = StoreBase.build_table(store_config=config, plan=plan)
for row in rows:
    row: ProfitRow = row
    print(row, row.total_rate)

input('确认?')

config_text = json.dumps(state, indent=4)
with open(state_file, 'w', encoding='utf8') as f:
    f.write(config_text)

print('done')
