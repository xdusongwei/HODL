import unittest
from hodl.unit_test import *
from hodl.tools import *


class MultistageRocketTestCase(unittest.TestCase):
    def test_multistage_rocket(self):
        """
        首先卖出前6档的股票，
        之后验证使用剩余股票卖出3档，并买回，
        再测试还原状态后能否正常全部买回，
        """
        var = VariableTools()
        store_config = var.store_configs['TEST']
        store_config['state_file_path'] = '/path/to/state-{symbol}-stage{stage}.json'

        store_config['multistage_rocket'] = [
            {'max_shares': 100_000, 'recover_price': 0.0, },
        ]
        pc = 10.0
        p_sell = pc * 1.27
        p_buy = pc * 1.14
        tickets = [
            Tick(day='23-04-10T09:32:00-04:00:00', pre_close=pc, open=p_sell, latest=p_sell, ),
            Tick(day='23-04-10T09:32:01-04:00:00', pre_close=pc, open=p_sell, latest=p_sell, ),
            Tick(day='23-04-10T09:32:02-04:00:00', pre_close=pc, open=p_sell, latest=p_sell, ),
            Tick(day='23-04-10T09:32:03-04:00:00', pre_close=pc, open=p_sell, latest=p_sell, ),
            Tick(day='23-04-10T09:32:04-04:00:00', pre_close=pc, open=p_sell, latest=p_sell, ),
            Tick(day='23-04-10T09:32:05-04:00:00', pre_close=pc, open=p_sell, latest=p_sell, ),
            Tick(day='23-04-10T09:32:06-04:00:00', pre_close=pc, open=p_sell, latest=p_sell, ),
            Tick(day='23-04-10T20:00:00-04:00:00', ms='CLOSING', pre_close=pc, open=p_sell, latest=p_sell, ),
        ]
        store = SimulationBuilder.from_config(store_config=store_config, tickets=tickets)
        plan = store.state.plan
        chips = plan.total_chips
        remain = chips + plan.buy_volume - plan.sell_volume
        assert len(plan.orders) == 6
        assert remain == 59091
        assert '/path/to/state-TEST-stage1.json' in store.files

        store_config['multistage_rocket'] = [
            {'max_shares': 100_000, 'recover_price': 0.0, },
            {'max_shares': 59091, 'recover_price': p_buy, },
        ]
        pc_lv2 = p_sell
        p_sell_lv2 = pc_lv2 * 1.09
        p_buy_lv2 = pc_lv2 * 1.03
        tickets = [
            Tick(day='23-04-11T09:32:00-04:00:00', pre_close=pc_lv2, open=pc_lv2, latest=pc_lv2, ),
            Tick(day='23-04-11T09:32:00-04:00:00', pre_close=pc_lv2, open=pc_lv2, latest=p_sell_lv2, ),
            Tick(day='23-04-11T09:32:01-04:00:00', pre_close=pc_lv2, open=pc_lv2, latest=p_sell_lv2, ),
            Tick(day='23-04-11T09:32:02-04:00:00', pre_close=pc_lv2, open=pc_lv2, latest=p_sell_lv2, ),
            Tick(day='23-04-11T09:33:01-04:00:00', pre_close=pc_lv2, open=pc_lv2, latest=p_buy_lv2, ),
            Tick(day='23-04-11T09:33:02-04:00:00', pre_close=pc_lv2, open=pc_lv2, latest=p_buy_lv2, ),
            Tick(day='23-04-11T09:33:02-04:00:00', pre_close=pc_lv2, open=pc_lv2, latest=p_buy_lv2, ),
            Tick(day='23-04-11T20:00:00-04:00:00', ms='CLOSING', pre_close=pc_lv2, open=pc_lv2, latest=p_buy_lv2, ),
        ]
        store = SimulationBuilder.resume(store=store, tickets=tickets)
        plan = store.state.plan
        chips = plan.total_chips
        remain = chips + plan.buy_volume - plan.sell_volume
        assert len(plan.orders) == 4
        assert remain == 59091
        assert plan.earning > 0
        assert '/path/to/state-TEST-stage2.json' in store.files

        store_config['multistage_rocket'] = [
            {'max_shares': 100_000, 'recover_price': 0.0, },
        ]
        tickets = [
            Tick(day='23-04-12T09:32:00-04:00:00', pre_close=p_buy_lv2, open=p_buy_lv2, latest=p_buy, ),
            Tick(day='23-04-12T09:32:01-04:00:00', pre_close=p_buy_lv2, open=p_buy_lv2, latest=p_buy, ),
            Tick(day='23-04-12T09:32:02-04:00:00', pre_close=p_buy_lv2, open=p_buy_lv2, latest=p_buy, ),
            Tick(day='23-04-12T09:32:02-04:00:00', pre_close=p_buy_lv2, open=p_buy_lv2, latest=p_buy, ),
        ]
        store = SimulationBuilder.resume(store=store, tickets=tickets)
        plan = store.state.plan
        chips = plan.total_chips
        remain = chips + plan.buy_volume - plan.sell_volume
        assert len(plan.orders) == 7
        assert remain == 100_000
