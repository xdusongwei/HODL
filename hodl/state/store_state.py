from dataclasses import dataclass, field
import exchange_calendars
from requests import Session
from hodl.tools import *


@dataclass
class StoreState(StoreStateBase):
    store_config: StoreConfig = field(default=None)
    http_session: Session = field(default=None)
    enable: bool = field(default=None)
    alive_log: Logger = field(default=None)
    log: Logger = field(default=None)
    variable: VariableTools = field(default_factory=VariableTools)
    sleep_secs: int = field(default=12)
    state_compare: tuple[str, str] = field(default=('', '', ))
    low_price_compare: tuple[int, float] = field(default=(-1, 0.0, ))
    high_price_compare: tuple[int, float] = field(default=(-1, 0.0, ))
    calendar: exchange_calendars.ExchangeCalendar = field(default=None)

    def __post_init__(self):
        store_config = self.store_config

        self.enable = store_config.enable
        self.tz_name = TimeTools.region_to_tz(region=store_config.region)

        log_root = self.variable.log_root(
            broker=store_config.broker,
            region=store_config.region,
            symbol=store_config.symbol,
        )
        self.alive_log = Logger(
            logger_name=f'alive-{store_config.broker}-{store_config.symbol}',
            log_root=log_root,
            log_level='DEBUG',
            write_stdout=False,
            write_json=False,
            file_max_size=12 * 1024,
            file_max_count=1,
        )
        self.alive_log.set_up()
        self.log = Logger(
            logger_name=f'main-{store_config.broker}-{store_config.symbol}',
            log_root=log_root,
            write_stdout=False,
            write_json=False,
            file_max_size=128 * 1024,
        )
        self.log.set_up()

        self.http_session.trust_env = False


__all__ = ['StoreState', ]
