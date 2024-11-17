from typing import Type
from hodl.tools import *
from hodl.quote_mixin import *
from hodl.trade_mixin import *
from hodl.storage import *


class Store(QuoteMixin, TradeMixin):
    STORE_MAP: dict[str, Type['Store']] = dict()
    
    def run(self):
        super().run()

    @classmethod
    def all_store_type(cls) -> list[Type['Store']]:
        return list(Store.STORE_MAP.values())

    @classmethod
    def register_strategy(cls, strategy_name: str, store_type: Type['Store']):
        assert issubclass(store_type, Store)
        if strategy_name in Store.STORE_MAP:
            raise ValueError(f'注册{store_type} 使用的策略名: {strategy_name} 重复注册')
        Store.STORE_MAP[strategy_name] = store_type

    @classmethod
    def factory(cls, store_config: StoreConfig, db: LocalDb) -> 'Store':
        strategy = store_config.trade_strategy
        if strategy not in Store.STORE_MAP:
            raise NotImplementedError(f'策略{strategy}找不到对应的类型映射')
        t = Store.STORE_MAP[strategy]
        return t(store_config=store_config, db=db)


def trade_strategy(strategy_name: str):
    def decorator(cls: Type[Store]):
        Store.register_strategy(strategy_name, cls)
        return cls
    return decorator


__all__ = [
    'Store',
    'trade_strategy',
]
