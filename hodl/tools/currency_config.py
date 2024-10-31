

class CurrencyConfig(dict):
    @property
    def url(self):
        """
        拉取汇率信息接口的地址
        """
        return self.get('url')

    @property
    def timeout(self) -> float:
        return self.get('timeout', 8.0)


__all__ = ['CurrencyConfig', ]
