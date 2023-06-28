

class ConfigReadError(ValueError):
    pass


class LockError(ValueError):
    pass


class BotError(ValueError):
    @property
    def thread_killer(self) -> bool:
        return getattr(self, '_thread_killer', False)

    @thread_killer.setter
    def thread_killer(self, v: bool):
        setattr(self, '_thread_killer', v)


class PrepareError(BotError):
    def __init__(self, *args):
        super(PrepareError, self).__init__(*args)
        self.thread_killer = False


class PlugInError(PrepareError):
    pass


class QuoteOutdatedError(PrepareError):
    pass


class QuoteFieldError(PrepareError):
    pass


class IbkrConidMissingError(PrepareError):
    pass


class QuoteScheduleOver(PrepareError):
    pass


class OrderOutdatedError(PrepareError):
    pass


class OrderRefreshError(PrepareError):
    pass


class TradingError(BotError):
    pass


class CiticsError(TradingError):
    pass


class RiskControlError(BotError):
    def __init__(self, *args):
        super(RiskControlError, self).__init__(*args)
        self.thread_killer = True


class BrokerMismatchError(BotError):
    def __init__(self, *args):
        super(BrokerMismatchError, self).__init__(*args)
        self.thread_killer = True


__all__ = [
    'ConfigReadError',
    'LockError',
    'BotError',
    'PrepareError',
    'PlugInError',
    'QuoteOutdatedError',
    'QuoteFieldError',
    'IbkrConidMissingError',
    'QuoteScheduleOver',
    'OrderOutdatedError',
    'OrderRefreshError',
    'TradingError',
    'CiticsError',
    'RiskControlError',
    'BrokerMismatchError',
]
