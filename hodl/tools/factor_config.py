

class FactorConfig(dict):
    @property
    def name(self):
        return self.get('name')

    @property
    def fear_and_greed(self):
        return self.get('fear_and_greed', 'neutral')

    @property
    def trade_type(self) -> str:
        return self.get('trade_type', None)

    @property
    def region(self) -> str:
        return self.get('region', None)

    @property
    def broker(self) -> str:
        return self.get('broker', None)

    @property
    def symbol(self) -> str:
        return self.get('symbol', None)

    @property
    def sell_factors(self) -> list[float]:
        return self.get('sell_factors', list())

    @property
    def buy_factors(self) -> list[float]:
        return self.get('buy_factors', list())

    @property
    def weight_factors(self) -> list[float]:
        return self.get('weight_factors', list())


__all__ = ['FactorConfig', ]
