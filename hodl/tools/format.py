from decimal import Decimal
from datetime import datetime
from currency_symbols import CurrencySymbols
from hodl.tools.time import TimeTools
from hodl.tools.store_config import StoreConfig


class FormatTool:
    @classmethod
    def adjust_precision(cls, f: float, precision: int) -> float:
        d = Decimal(f"0.{'0' * precision}")
        f = float(Decimal(f).quantize(d))
        return f

    @classmethod
    def pretty_dt(cls, v: None | int | float | datetime, region=None, with_year=True, with_tz=False) \
            -> str:
        if v is None:
            return '--'
        dt = v
        if isinstance(v, (int, float)):
            dt = TimeTools.from_timestamp(v)
        tz_name = 'EDT'
        match region:
            case 'US':
                pass
            case 'CN':
                dt = TimeTools.from_timestamp(dt.timestamp(), tz='Asia/Shanghai')
                tz_name = 'CST'
            case _:
                pass
        iso_format = dt.isoformat(timespec='milliseconds')
        if not with_year:
            iso_format = iso_format[5:]
        if with_tz:
            return f'{tz_name}:{iso_format}'
        return iso_format

    @classmethod
    def currency_to_unit(cls, currency: str) -> str:
        unit = CurrencySymbols.get_symbol(currency) or '$'
        return unit

    @classmethod
    def pretty_usd(cls, v: None | int | float, currency=None, unit='$', only_int=False) -> str:
        if currency:
            match currency:
                case 'USDT':
                    unit = 'USDT'
                case 'USDC':
                    unit = 'USDC'
                case _:
                    unit = cls.currency_to_unit(currency)
        if v is None:
            return f'{unit}--'
        if only_int:
            v = int(v)
            return unit + '{:,}'.format(v)
        else:
            return unit + '{:,.3f}'.format(v)

    @classmethod
    def pretty_price(cls, v: None | int | float, config: StoreConfig, only_int=False):
        return cls.pretty_usd(
            v=v,
            currency=config.currency,
            only_int=only_int,
        )

    @classmethod
    def pretty_number(cls, v: None | int | float):
        return cls.pretty_usd(
            v=v,
            unit='',
            only_int=True,
        )


__all__ = ['FormatTool', ]
