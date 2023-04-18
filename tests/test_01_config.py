import unittest
from hodl.tools import *


class ConfigTestCase(unittest.TestCase):
    def test_read_config(self):
        symbol = 'TEST'
        var = VariableTools()
        store_config = var.store_configs[symbol]

        assert store_config.broker == 'tiger'
        assert store_config.region == 'US'
        assert store_config.symbol == 'TEST'
        assert store_config.currency == 'USD'
        assert store_config.max_shares == 100_000
