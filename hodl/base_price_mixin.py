from abc import ABC
from hodl.store_base import *
from hodl.storage import *
from hodl.tools import *


class BasePriceMixin(StoreBase, ABC):
    def calc_base_price(self) -> float:
        self._set_up_ta_info()

        state = self.state
        store_config = self.store_config
        symbol = store_config.symbol
        quote_pre_close = self.state.quote_pre_close
        low_price = self.state.quote_low_price
        db = self.db
        match store_config.trade_strategy:
            case TradeStrategyEnum.HODL:
                if db:
                    con = db.conn
                    base_price_row = TempBasePriceRow.query_by_symbol(con=con, symbol=symbol)
                    if base_price_row and base_price_row.price > 0:
                        return base_price_row.price

                if state.ta_tumble_protect_alert_price is not None:
                    return state.ta_tumble_protect_alert_price

                price_list = [quote_pre_close, ]
                if db:
                    con = db.conn
                    base_price_row = TempBasePriceRow.query_by_symbol(con=con, symbol=symbol)
                    if base_price_row and base_price_row.price > 0:
                        price_list.append(base_price_row.price)
                if store_config.base_price_day_low:
                    if low_price is not None:
                        price_list.append(low_price)
                price = min(price_list)
                assert price > 0.0
                return price
            case _:
                raise NotImplementedError

    def _set_up_ta_info(self):
        state = self.state
        store_config = self.store_config
        state.ta_vix_high = None
        if store_config.vix_tumble_protect is not None:
            vix_quote = self.broker_proxy.query_vix()
            if vix_quote:
                state.ta_vix_high = vix_quote.day_high
        state.ta_tumble_protect_flag = self._detect_lowest_days()
        state.ta_tumble_protect_alert_price = None
        if state.ta_tumble_protect_flag:
            state.ta_tumble_protect_alert_price = self._tumble_protect_alert_price()

    def _query_history(self, days: int, day_low=True):
        db = self.db
        if not db:
            return list()
        store_config = self.store_config
        end_day = TimeTools.us_time_now()
        begin_day = TimeTools.timedelta(end_day, days=-days)
        args = dict(
            con=db.conn,
            broker=store_config.broker,
            region=store_config.region,
            symbol=store_config.symbol,
            begin_day=int(TimeTools.date_to_ymd(begin_day, join=False)),
            end_day=int(TimeTools.date_to_ymd(end_day, join=False)),
        )
        if day_low:
            history = QuoteLowHistoryRow.query_by_symbol(**args)
        else:
            history = QuoteHighHistoryRow.query_by_symbol(**args)
        return history

    def _detect_lowest_days(self) -> bool:
        store_config = self.store_config
        history: list[QuoteLowHistoryRow] = self._query_history(days=store_config.tumble_protect_day_range * 9)
        if len(history) <= store_config.tumble_protect_day_range:
            return False
        recent = history[:store_config.tumble_protect_day_range]
        return min(day.low_price for day in history) * 1.01 >= min(day.low_price for day in recent)

    def _tumble_protect_alert_price(self):
        ma5_days: list[QuoteHighHistoryRow] = self._query_history(days=5, day_low=False)
        ma5_price_list = [day.high_price for day in ma5_days]
        ma10_days: list[QuoteHighHistoryRow] = self._query_history(days=10, day_low=False)
        ma10_price_list = [day.high_price for day in ma10_days]
        if not ma5_price_list or not ma10_price_list:
            return None
        ma5 = sum(ma5_price_list) / len(ma5_price_list)
        self.state.ta_tumble_protect_ma5 = ma5
        ma10 = sum(ma10_price_list) / len(ma10_price_list)
        self.state.ta_tumble_protect_ma10 = ma10
        assert ma5 > 0
        assert ma10 > 0
        return max(ma5, ma10)


__all__ = ['BasePriceMixin', ]


