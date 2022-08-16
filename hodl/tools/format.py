import base58
import xxhash
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
    def pretty_usd(
            cls,
            v: None | int | float,
            currency = None,
            unit = '$',
            only_int = False,
            precision: int = 3,
    ) -> str:
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
            template = f'{{:,.{precision}f}}'
            return unit + template.format(v)

    @classmethod
    def pretty_price(cls, v: None | int | float, config: StoreConfig, only_int=False):
        return cls.pretty_usd(
            v=v,
            currency=config.currency,
            only_int=only_int,
            precision=config.precision,
        )

    @classmethod
    def pretty_number(cls, v: None | int | float):
        return cls.pretty_usd(
            v=v,
            unit='',
            only_int=True,
        )

    @classmethod
    def base58_hash(
            cls,
            data: str,
            length: int = 16,
            prefix='',
            salt: str = '',
            cipher=xxhash.xxh3_64,
    ) -> str:
        binary = (salt + str(data)).encode("utf8") if salt else data.encode("utf8")
        hash_key = cipher(binary).digest()
        slice_key = base58.b58encode(hash_key)[:length]
        if type(slice_key) is bytes:
            slice_key = slice_key.decode("utf8")
        key = "{}{}".format(prefix, slice_key)
        return key


__all__ = ['FormatTool', ]
