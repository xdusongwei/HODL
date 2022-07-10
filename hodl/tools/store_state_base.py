from dataclasses import dataclass, field


@dataclass
class StoreStateBase:
    tz_name: str = field(default='US/Eastern')


__all__ = ['StoreStateBase', ]
