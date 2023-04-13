from unittest.mock import patch, MagicMock, Mock
from hodl.quote_mixin import QuoteMixin
from hodl.tools import TimeTools
from hodl.store import Store


def basic_mock(client_type: type, method: str, side_effect=None, return_value=None, autospec=True):
    if side_effect is not None:
        m = Mock()
        m.side_effect = side_effect
        return patch.object(client_type, method, new=side_effect)
    else:
        return patch.object(client_type, method, side_effect=MagicMock(return_value=return_value), autospec=autospec)


def now_mock(new_function):
    return basic_mock(TimeTools, 'utc_now', side_effect=new_function)


def sleep_mock(new_function):
    return basic_mock(TimeTools, 'sleep', side_effect=new_function)


def quote_mock(new_function):
    return basic_mock(QuoteMixin, '_query_quote', side_effect=new_function)


def market_status_mock(new_function):
    return basic_mock(QuoteMixin, 'current_market_status', side_effect=new_function)


def refresh_order_mock(function):
    return basic_mock(Store, '_get_order', side_effect=function)


def cancel_order_mock(function):
    return basic_mock(Store, '_cancel_order', side_effect=function)


def submit_order_mock(function):
    return basic_mock(Store, '_submit_order', side_effect=function)


def cash_amount_mock(function):
    return basic_mock(Store, 'current_cash', side_effect=function)


def chip_count_mock(function):
    return basic_mock(Store, 'current_chip', side_effect=function)


__all__ =[
    'now_mock',
    'sleep_mock',
    'quote_mock',
    'market_status_mock',
    'refresh_order_mock',
    'cancel_order_mock',
    'submit_order_mock',
    'cash_amount_mock',
    'chip_count_mock',
]
