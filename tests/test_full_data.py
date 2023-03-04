import unittest
from hodl.plan_calc import ProfitRow
from hodl.simulation.main import start_simulation, SimulationStore
from hodl.tools import VariableTools


class FullDataTestCase(unittest.TestCase):
    def setUp(self):
        print('running setUp')

    def test_full_data(self):
        start_simulation()

    def tearDown(self):
        print('running tearDown')
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
