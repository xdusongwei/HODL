import os
import unittest
from hodl.plan_calc import *
from hodl.unit_test import *
from hodl.state import *
from hodl.tools import *


class FullDataTestCase(unittest.TestCase):
    STORE: SimulationStore = None

    def setUp(self):
        print('running setUp')

    @classmethod
    def full_mode(cls) -> str:
        env = os.environ
        full_test_mode = env.get('TEST_FULL_DATA', 'brief')
        return full_test_mode

    def test_full_data(self):
        full_test_mode = self.full_mode()
        quote_length = 0
        if full_test_mode == 'brief':
            quote_length = 30
        elif full_test_mode == 'skip':
            return
        quote_csv = LocateTools.locate_file('tests/data/tigr.csv')
        self.STORE = start_simulation(symbol='TIGR', quote_csv=quote_csv, quote_length=quote_length)

    def tearDown(self):
        print('running tearDown')
        if self.full_mode() == 'skip':
            return
        var = VariableTools()
        store_config = var.store_configs['TIGR']
        print(
            'total earning: ', self.STORE.earning,
            'base_price_last_buy:', store_config.base_price_last_buy,
            sep=' ',
        )
        for lv, times in sorted(self.STORE.times_per_level.items(), key=lambda i: i[0]):
            print(lv, times)
