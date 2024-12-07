from hodl.proxy import *
from hodl.state import *
from hodl.broker import *
from hodl.unit_test import *


class PreferBrokerTestCase(HodlTestCase):
    """
    验证市场状态、行情 proxy 机制可以找到到正确的匹配顺序
    """

    def test_market_status_empty(self):
        """
        没有任何 broker 可以提供市场状态
        """
        @broker_api('a', 'a')
        class _A_Broker(BrokerApiBase):
            pass

        var = self.config()
        var._config['broker'] = {
            'a': {},
        }
        var._config['broker_meta'] = {
            'a': [
                {
                    'trade_type': 'stock',
                    'share_market_status': False,
                    'market_status_regions': [],
                },
            ],
        }

        msp = MarketStatusProxy(var=var)
        assert msp.brokers == []

    def test_market_status_empty_regions(self):
        """
        即使某个 broker 开启了共享市场状态, 但是 regions 为空, 依然没有任何 broker 可以提供市场状态
        """
        @broker_api('a', 'a')
        class _A_Broker(BrokerApiBase):
            pass

        var = self.config()
        var._config['broker'] = {
            'a': {},
        }
        var._config['broker_meta'] = {
            'a': [
                {
                    'trade_type': 'stock',
                    'share_market_status': True,
                    'market_status_regions': [],
                },
            ],
        }

        msp = MarketStatusProxy(var=var)
        assert msp.brokers == []

    def test_market_status_on(self):
        """
        brokerA 提供市场状态功能
        """
        @broker_api('a', 'a')
        class _A_Broker(BrokerApiBase):
            pass

        var = self.config()
        var._config['broker'] = {
            'a': {},
        }
        var._config['broker_meta'] = {
            'a': [
                {
                    'trade_type': 'stock',
                    'share_market_status': True,
                    'market_status_regions': ['US'],
                },
            ],
        }

        msp = MarketStatusProxy(var=var)
        assert len(msp.brokers) == 1
        assert any(isinstance(broker, _A_Broker) for broker in msp.brokers)

    def test_prefer_market_status(self):
        """
        三个 broker 均提供市场状态, 并且要求 b 和 a 优先, 那么最终的 brokers 顺序应为 b, a, c
        """
        @broker_api('a', 'a')
        class _A_Broker(BrokerApiBase):
            pass

        @broker_api('b', 'b')
        class _B_Broker(BrokerApiBase):
            pass

        @broker_api('c', 'c')
        class _C_Broker(BrokerApiBase):
            pass

        var = self.config()
        var._config['broker'] = {
            'a': {},
            'b': {},
            'c': {},
        }
        var._config['broker_meta'] = {
            'a': [
                {
                    'trade_type': 'stock',
                    'share_market_status': True,
                    'market_status_regions': ['US'],
                },
            ],
            'b': [
                {
                    'trade_type': 'stock',
                    'share_market_status': True,
                    'market_status_regions': ['US'],
                },
            ],
            'c': [
                {
                    'trade_type': 'stock',
                    'share_market_status': True,
                    'market_status_regions': ['US'],
                },
            ],
        }
        var._config['prefer_market_status_brokers'] = ['b', 'a', ]

        msp = MarketStatusProxy(var=var)
        assert len(msp.brokers) == 3
        assert isinstance(msp.brokers[0], _B_Broker)
        assert isinstance(msp.brokers[1], _A_Broker)
        assert isinstance(msp.brokers[2], _C_Broker)

    def test_quote_empty(self):
        """
        没有任何 broker 可以提供行情
        """
        @broker_api('a', 'a')
        class _A_Broker(BrokerApiBase):
            pass

        var = self.config()
        var._config['broker'] = {
            'a': {},
        }
        var._config['broker_meta'] = {
            'a': [
                {
                    'trade_type': 'stock',
                    'share_quote': False,
                    'quote_regions': [],
                },
            ],
        }

        store_config = var.store_configs['TEST']
        ss = StoreState(
            store_config=store_config,
            variable=var,
        )
        bp = BrokerProxy(ss)
        assert bp.quote_brokers == []

    def test_quote_empty_regions(self):
        """
        即使某个 broker 开启了共享行情, 但是 regions 为空, 依然没有任何 broker 可以提供行情
        """
        @broker_api('a', 'a')
        class _A_Broker(BrokerApiBase):
            pass

        var = self.config()
        var._config['broker'] = {
            'a': {},
        }
        var._config['broker_meta'] = {
            'a': [
                {
                    'trade_type': 'stock',
                    'share_quote': True,
                    'quote_regions': [],
                },
            ],
        }

        store_config = var.store_configs['TEST']
        ss = StoreState(
            store_config=store_config,
            variable=var,
        )
        bp = BrokerProxy(ss)
        assert bp.quote_brokers == []

    def test_quote_on(self):
        """
        brokerA 提供行情功能
        """
        @broker_api('a', 'a')
        class _A_Broker(BrokerApiBase):
            pass

        var = self.config()
        var._config['broker'] = {
            'a': {},
        }
        var._config['broker_meta'] = {
            'a': [
                {
                    'trade_type': 'stock',
                    'share_quote': True,
                    'quote_regions': ['US'],
                },
            ],
        }

        store_config = var.store_configs['TEST']
        ss = StoreState(
            store_config=store_config,
            variable=var,
        )
        bp = BrokerProxy(ss)
        assert len(bp.quote_brokers) == 1
        assert any(isinstance(broker, _A_Broker) for broker in bp.quote_brokers)

    def test_prefer_quote(self):
        """
        三个 broker 均提供行情, 并且要求 c 和 a 优先, 那么最终的 brokers 顺序应为 c, a, b
        """
        @broker_api('a', 'a')
        class _A_Broker(BrokerApiBase):
            pass

        @broker_api('b', 'b')
        class _B_Broker(BrokerApiBase):
            pass

        @broker_api('c', 'c')
        class _C_Broker(BrokerApiBase):
            pass

        var = self.config()
        var._config['broker'] = {
            'a': {},
            'b': {},
            'c': {},
        }
        var._config['broker_meta'] = {
            'a': [
                {
                    'trade_type': 'stock',
                    'share_quote': True,
                    'quote_regions': ['US'],
                },
            ],
            'b': [
                {
                    'trade_type': 'stock',
                    'share_quote': True,
                    'quote_regions': ['US'],
                },
            ],
            'c': [
                {
                    'trade_type': 'stock',
                    'share_quote': True,
                    'quote_regions': ['US'],
                },
            ],
        }
        var._config['prefer_quote_brokers'] = ['c', 'a', ]

        store_config = var.store_configs['TEST']
        ss = StoreState(
            store_config=store_config,
            variable=var,
        )
        bp = BrokerProxy(ss)
        assert len(bp.quote_brokers) == 3
        assert isinstance(bp.quote_brokers[0], _C_Broker)
        assert isinstance(bp.quote_brokers[1], _A_Broker)
        assert isinstance(bp.quote_brokers[2], _B_Broker)

    def test_prefer_quote_with_store_config(self):
        """
        三个 broker 均提供行情, 并且根配置要求 c 和 a 优先, 持仓配置要求 a 和 c 优先, 那么最终的 brokers 顺序应为 a, c, b
        """

        @broker_api('a', 'a')
        class _A_Broker(BrokerApiBase):
            pass

        @broker_api('b', 'b')
        class _B_Broker(BrokerApiBase):
            pass

        @broker_api('c', 'c')
        class _C_Broker(BrokerApiBase):
            pass

        var = self.config()
        var._config['broker'] = {
            'a': {},
            'b': {},
            'c': {},
        }
        var._config['broker_meta'] = {
            'a': [
                {
                    'trade_type': 'stock',
                    'share_quote': True,
                    'quote_regions': ['US'],
                },
            ],
            'b': [
                {
                    'trade_type': 'stock',
                    'share_quote': True,
                    'quote_regions': ['US'],
                },
            ],
            'c': [
                {
                    'trade_type': 'stock',
                    'share_quote': True,
                    'quote_regions': ['US'],
                },
            ],
        }
        var._config['prefer_quote_brokers'] = ['c', 'a', ]

        store_config = var.store_configs['TEST']
        store_config['prefer_quote_brokers'] = ['a', 'c', ]
        ss = StoreState(
            store_config=store_config,
            variable=var,
        )
        bp = BrokerProxy(ss)
        assert len(bp.quote_brokers) == 3
        assert isinstance(bp.quote_brokers[0], _A_Broker)
        assert isinstance(bp.quote_brokers[1], _C_Broker)
        assert isinstance(bp.quote_brokers[2], _B_Broker)

    def tearDown(self):
        BrokerApiBase._ALL_BROKER_TYPES = list()
