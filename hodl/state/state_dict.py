import re
from hodl.tools import *
from hodl.state.state_plan import Plan


class State(dict):
    @classmethod
    def new(cls, d: dict = None):
        if d:
            s: State = State(d)
        else:
            s: State = State()
        now = TimeTools.us_time_now()
        ymd = now.strftime('%y%m%d')
        prefix = now.strftime('%y%m%d%H%M%S')
        if not s.version or not s.version.startswith(ymd):
            s.version = FormatTool.base58_hash(
                salt=str(id(s)),
                data=str(now.timestamp()),
                prefix=prefix,
            )
        return s

    @property
    def has_plan(self):
        return bool(self.get('plan'))

    @property
    def plan(self):
        return Plan(self.get('plan'))

    @property
    def template_plan(self):
        """
        Jinja内置函数优先识别plan键，而不是plan属性, 这是一个jinja专用字段
        """
        return self.plan

    @plan.setter
    def plan(self, v: Plan):
        if v is not None:
            self['plan'] = v.d
        else:
            self['plan'] = None

    @property
    def name(self):
        return self.get('name')

    @name.setter
    def name(self, v: str):
        self['name'] = v

    @property
    def version(self) -> str:
        return self.get('version')

    @version.setter
    def version(self, v: str):
        self['version'] = v

    def _get_snapshot(self, snapshot: str, key: str):
        snapshot_d = self.get(snapshot, dict())
        return snapshot_d.get(key)

    def _set_snapshot(self, snapshot: str, key: str, v):
        snapshot_d = self.get(snapshot, dict())
        snapshot_d[key] = v
        self[snapshot] = snapshot_d

    @property
    def chip_day(self) -> str:
        return self._get_snapshot('dailySnapshot', 'chipDay')

    @chip_day.setter
    def chip_day(self, v: str):
        self._set_snapshot('dailySnapshot', 'chipDay', v)

    @property
    def chip_count(self) -> int:
        return self._get_snapshot('dailySnapshot', 'chipCount')

    @chip_count.setter
    def chip_count(self, v: int):
        self._set_snapshot('dailySnapshot', 'chipCount', v)

    @property
    def cash_day(self) -> str:
        return self._get_snapshot('dailySnapshot', 'cashDay')

    @cash_day.setter
    def cash_day(self, v: str):
        self._set_snapshot('dailySnapshot', 'cashDay', v)

    @property
    def cash_amount(self) -> int:
        return self._get_snapshot('dailySnapshot', 'cashAmount')

    @cash_amount.setter
    def cash_amount(self, v: int):
        self._set_snapshot('dailySnapshot', 'cashAmount', v)

    @property
    def quote_symbol(self):
        return self._get_snapshot('latestSnapshot', 'quoteSymbol')

    @quote_symbol.setter
    def quote_symbol(self, v: str):
        self._set_snapshot('latestSnapshot', 'quoteSymbol', v)

    @property
    def quote_time(self) -> float:
        return self._get_snapshot('latestSnapshot', 'quoteTime')

    @quote_time.setter
    def quote_time(self, v: int):
        self._set_snapshot('latestSnapshot', 'quoteTime', v)

    @property
    def quote_open(self):
        return self._get_snapshot('latestSnapshot', 'quoteOpen')

    @quote_open.setter
    def quote_open(self, v: float):
        self._set_snapshot('latestSnapshot', 'quoteOpen', v)

    @property
    def quote_status(self) -> str:
        return self._get_snapshot('latestSnapshot', 'quoteStatus')

    @quote_status.setter
    def quote_status(self, v: str):
        self._set_snapshot('latestSnapshot', 'quoteStatus', v)

    @property
    def quote_enable_trade(self):
        return self.quote_status == 'NORMAL'

    @property
    def quote_pre_close(self):
        return self._get_snapshot('latestSnapshot', 'quotePreClose')

    @quote_pre_close.setter
    def quote_pre_close(self, v: float):
        self._set_snapshot('latestSnapshot', 'quotePreClose', v)

    @property
    def quote_latest_price(self):
        return self._get_snapshot('latestSnapshot', 'quoteLatestPrice')

    @quote_latest_price.setter
    def quote_latest_price(self, v: float):
        self._set_snapshot('latestSnapshot', 'quoteLatestPrice', v)

    @property
    def quote_low_price(self):
        return self._get_snapshot('latestSnapshot', 'quoteLowPrice')

    @quote_low_price.setter
    def quote_low_price(self, v: float):
        self._set_snapshot('latestSnapshot', 'quoteLowPrice', v)

    @property
    def quote_high_price(self):
        return self._get_snapshot('latestSnapshot', 'quoteHighPrice')

    @quote_high_price.setter
    def quote_high_price(self, v: float):
        self._set_snapshot('latestSnapshot', 'quoteHighPrice', v)

    @property
    def market_status(self) -> str:
        return self._get_snapshot('latestSnapshot', 'marketStatus')

    @market_status.setter
    def market_status(self, v: str):
        self._set_snapshot('latestSnapshot', 'marketStatus', v)

    @property
    def reset_day(self) -> str:
        return self.get('resetDay', '0001-01-01')

    @reset_day.setter
    def reset_day(self, v: str):
        self['resetDay'] = v

    def is_today_get_off(self, tz=None) -> bool:
        today = TimeTools.us_day_now(tz=tz)
        return today == self.reset_day

    @property
    def current(self) -> str:
        return self.get('current', '不活跃')

    @current.setter
    def current(self, v: str):
        self['current'] = v

    @property
    def risk_control_break(self) -> bool:
        return self.get('riskControlBreak', False)

    @risk_control_break.setter
    def risk_control_break(self, v: bool):
        self['riskControlBreak'] = v

    @property
    def risk_control_detail(self) -> str:
        return self.get('riskControlDetail')

    @risk_control_detail.setter
    def risk_control_detail(self, v: str):
        self['riskControlDetail'] = v

    def reset_lsod(self):
        """
        重置下次下单日(last submit order day)图章信息
        :return:
        """
        self['lsod'] = f'[D{TimeTools.us_day_now()}]'

    @property
    def lsod(self):
        return self.get('lsod', '')

    @lsod.setter
    def lsod(self, v: str):
        self['lsod'] = v

    def lsod_day(self):
        lsod = self.lsod
        if not lsod:
            raise ValueError(f'未重置过的LSOD不能查询日期信息')
        if search := re.search(r'\[D([0-9\-]+)]', lsod):
            day = search.groups()[0]
            return day
        raise ValueError(f'数据错误: 非空LSOD不包含日期信息')

    @property
    def is_lsod_today(self) -> bool:
        lsod = self.lsod
        return f'[D{TimeTools.us_day_now()}]' in lsod

    def seal_lsod(self, seal):
        assert seal
        seal = f'[{seal}]'
        lsod = self.lsod
        if not lsod:
            raise ValueError(f'未重置过的LSOD不能加入图章')
        if seal not in self.lsod:
            lsod += seal
        self.lsod = lsod

    def has_lsod_seal(self, seal) -> bool:
        assert seal
        seal = f'[{seal}]'
        lsod = self.lsod
        if not lsod:
            raise ValueError(f'未重置过的LSOD不能检查图章')
        return seal in lsod

    @property
    def is_plug_in(self):
        return self.get('isPlugIn', True)

    @is_plug_in.setter
    def is_plug_in(self, v: bool):
        self['isPlugIn'] = v

    @property
    def quote_rate(self) -> None | float:
        pre_close = self.quote_pre_close
        latest = self.quote_latest_price
        rate = None
        if pre_close and latest:
            rate = round(latest / pre_close - 1.0, 4)
        return rate

    @property
    def sleep_mode_active(self):
        return self.get('sleepModeActive', True)

    @sleep_mode_active.setter
    def sleep_mode_active(self, v: bool):
        self['sleepModeActive'] = v

    @property
    def ta_vix_high(self) -> float:
        return self._get_snapshot('ta', 'vixHigh')

    @ta_vix_high.setter
    def ta_vix_high(self, v: float):
        self._set_snapshot('ta', 'vixHigh', v)

    @property
    def ta_tumble_protect_flag(self) -> bool:
        return self._get_snapshot('ta', 'tumbleProtectFlag')

    @ta_tumble_protect_flag.setter
    def ta_tumble_protect_flag(self, v: bool):
        self._set_snapshot('ta', 'tumbleProtectFlag', v)

    @property
    def ta_tumble_protect_alert_price(self) -> float:
        return self._get_snapshot('ta', 'tumbleProtectAlertPrice')

    @ta_tumble_protect_alert_price.setter
    def ta_tumble_protect_alert_price(self, v: float):
        self._set_snapshot('ta', 'tumbleProtectAlertPrice', v)

    @property
    def ta_tumble_protect_ma5(self) -> float:
        return self._get_snapshot('ta', 'tumbleProtectMa5')

    @ta_tumble_protect_ma5.setter
    def ta_tumble_protect_ma5(self, v: float):
        self._set_snapshot('ta', 'tumbleProtectMa5', v)

    @property
    def ta_tumble_protect_ma10(self) -> float:
        return self._get_snapshot('ta', 'tumbleProtectMa10')

    @ta_tumble_protect_ma10.setter
    def ta_tumble_protect_ma10(self, v: float):
        self._set_snapshot('ta', 'tumbleProtectMa10', v)


__all__ = [
    'State',
]
