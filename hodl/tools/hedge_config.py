

class HedgeConfig(dict):
    @property
    def type(self) -> str:
        return self.get('type')

    @property
    def name(self) -> str:
        return self.get('name')

    @property
    def master(self) -> str:
        return self.get('master')

    @property
    def slave(self) -> str:
        return self.get('slave')


__all__ = ['HedgeConfig', ]
