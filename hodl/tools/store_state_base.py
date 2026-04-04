from dataclasses import dataclass, field


@dataclass
class StoreStateBase:
    tz_name: str = field(default='America/New_York')


__all__ = ['StoreStateBase', ]
