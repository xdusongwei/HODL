from abc import ABC
from threading import Lock
from hodl.quote import *
from hodl.store import *
from hodl.exception_tools import *
from hodl.tools import *


class QuoteMixin(IsolatedStoreBase, ABC):
    CACHE_MARKET_STATUS = True
    CACHE_LOCK = Lock()
    LAST_TIMESTAMP = 0
    CACHE_TTL = 12
    CACHE = None

    @classmethod
    def change_cache_ttl(cls, ttl: int):
        assert 0 <= ttl
        QuoteMixin.CACHE_TTL = ttl

    def _pull_market_status(self):
        if QuoteMixin.CACHE_MARKET_STATUS:
            with QuoteMixin.CACHE_LOCK:
                if TimeTools.us_time_now().timestamp() - QuoteMixin.LAST_TIMESTAMP > QuoteMixin.CACHE_TTL:
                    self.market_status_proxy.pull_market_status()
                    QuoteMixin.LAST_TIMESTAMP = TimeTools.us_time_now().timestamp()
        else:
            self.market_status_proxy.pull_market_status()

    def current_market_status(self) -> tuple[str, str, str, ]:
        if not self.runtime_state.variable.async_market_status:
            self._pull_market_status()
        return self.market_status_proxy.query_status(self.store_config)

    def _query_quote(self) -> Quote:
        quote = self.broker_proxy.query_quote()
        return quote

    def current_quote(self) -> Quote:
        state = self.state
        quote = self._query_quote()
        if state.quote_time:
            if TimeTools.from_timestamp(state.quote_time) > quote.time:
                raise QuoteOutdatedError(
                    f'系统存储的行情({TimeTools.from_timestamp(state.quote_time)})'
                    f'比请求的行情({quote.time})新'
                )

        return quote

    def assert_quote_time_diff(self):
        quote_delay_secs = self.runtime_state.store_config.quote_delay_secs
        state = self.state
        quote_time = state.quote_time
        now = TimeTools.us_time_now()
        if abs(quote_time - now.timestamp()) > quote_delay_secs:
            time = TimeTools.from_timestamp(quote_time)
            raise QuoteOutdatedError(
                f'请求的行情时间{time}差距明显'
                f'({abs(int((time - now).total_seconds()))}秒), '
                f'本机时间{now}'
            )


__all__ = ['QuoteMixin', ]
