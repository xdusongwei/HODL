import os
import unittest
from hodl.plan_calc import ProfitRow
from hodl.simulation.main import start_simulation, SimulationStore
from hodl.tools import *


class FullDataTestCase(unittest.TestCase):
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
        start_simulation(symbol='TIGR', quote_csv=quote_csv, quote_length=quote_length)

    def tearDown(self):
        print('running tearDown')
        if self.full_mode() == 'skip':
            return
        var = VariableTools()
        store_config = var.store_configs['TIGR']
        print(
            'total earning: ', SimulationStore.EARNING,
            'use prudent:', store_config.prudent,
            'base_price_last_buy:', store_config.base_price_last_buy,
            sep=' ',
        )
        for lv, times in sorted(SimulationStore.TIMES_PER_LEVEL.items(), key=lambda i: i[0]):
            level: ProfitRow = SimulationStore.PLAN[lv-1]
            print(lv, times, f'{((level.total_rate - 1) * 100 * times):+.2f}%')
