import os
import unittest
from hodl.plan_calc import *
from hodl.simulation.main import start_simulation, SimulationStore
from hodl.state import *
from hodl.tools import *


class FullDataTestCase(unittest.TestCase):
    STORE: SimulationStore = None

    def setUp(self):
        print('running setUp')

    @classmethod
    def full_mode(cls) -> str:
        env = os.environ
        full_test_mode = env.get('TEST_FULL_DATA', 'full')
        return full_test_mode

    def test_full_data(self):
        full_test_mode = self.full_mode()
        quote_length = 0
        if full_test_mode == 'brief':
            quote_length = 30
        elif full_test_mode == 'skip':
            return
        quote_csv = LocateTools.locate_file('data/tigr.csv')
        self.STORE = start_simulation(symbol='TIGR', quote_csv=quote_csv, quote_length=quote_length)

    def tearDown(self):
        print('running tearDown')
        if self.full_mode() == 'skip':
            return
        var = VariableTools()
        store_config = var.store_configs['TIGR']
        print(
            'total earning: ', self.STORE.earning,
            'use prudent:', store_config.prudent,
            'base_price_last_buy:', store_config.base_price_last_buy,
            sep=' ',
        )
        plan = Plan.new_plan(store_config)
        plan.base_price = 10.0
        table = SimulationStore.build_table(store_config=store_config, plan=plan)
        for lv, times in sorted(self.STORE.times_per_level.items(), key=lambda i: i[0]):
            level: ProfitRow = table[lv-1]
            print(lv, times, f'{((level.total_rate - 1) * 100 * times):+.2f}%')
