import base58
import orjson
import xxhash
from decimal import Decimal
from datetime import datetime
import humanize
from currency_symbols import CurrencySymbols
from hodl.tools.time import TimeTools
from hodl.tools.store_config import StoreConfig


class FormatTool:
    _PRECISION_MAP = dict()

    @classmethod
    def _precision(cls, precision: int) -> Decimal:
        if precision not in FormatTool._PRECISION_MAP:
            FormatTool._PRECISION_MAP[precision] = Decimal(f"0.{'0' * precision}")
        return FormatTool._PRECISION_MAP[precision]

    @classmethod
    def adjust_precision(cls, f: float, precision: int) -> float:
        d = cls._precision(precision=precision)
        f = float(Decimal(f).quantize(d))
        return f

    @classmethod
    def pretty_dt(
            cls,
            v: None | int | float | datetime,
            region=None,
            with_year=True,
            with_tz=False,
    ) -> str:
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
            return f'{tz_name}: {iso_format}'
        return iso_format

    @classmethod
    def currency_to_unit(cls, currency: str) -> str:
        unit = CurrencySymbols.get_symbol(currency) or '$'
        return unit

    @classmethod
    def number_to_size(cls, number: int) -> str:
        return humanize.naturalsize(number, binary=True, format="%.2f")

    @classmethod
    def pretty_usd(
            cls,
            v: None | int | float,
            currency=None,
            unit='$',
            only_int=False,
            precision: int = 3,
            show_currency_name=False,
    ) -> str:
        if currency:
            unit = cls.currency_to_unit(currency)
            if show_currency_name:
                unit = f'{currency}{unit}'
        if v is None:
            intcomma = '--'
        elif only_int:
            v = int(v)
            intcomma = humanize.intcomma(v)
        else:
            intcomma = humanize.intcomma(v, ndigits=precision)
        return f'{unit}{intcomma}'

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
    def factor_to_percent(cls, v: None | int | float, fmt: str = '{:.0%}', base_100: bool = True) -> str:
        if v is not None and not base_100:
            v -= 1.0
        s = humanize.clamp(v, format=fmt)
        if s is None:
            return '--%'
        return s

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

    @classmethod
    def json_dumps(cls, d: list | dict, binary=False, default=None) -> bytes | str:
        option = orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS
        b = orjson.dumps(d, option=option, default=default)
        if not binary:
            return b.decode('utf8')
        return b

    @classmethod
    def json_loads(cls, b: bytes | str) -> dict:
        return orjson.loads(b)

    @classmethod
    def spread(cls, price: float, precision: int, spread, spread_rate) -> float:
        if isinstance(spread_rate, float):
            return cls.adjust_precision(abs(price * spread_rate), precision=precision)

        if isinstance(spread, float):
            return cls.adjust_precision(abs(spread), precision=precision)

        return 0.0


__all__ = ['FormatTool', ]
