"""
文档见
https://open.longportapp.com/docs
"""
import re
import tomllib
import threading
from datetime import datetime
import tomlkit
from hodl.broker.base import *
from hodl.exception_tools import *
from hodl.quote import *
from hodl.state import *
from hodl.tools import *


class TokenKeeper:
    LOCK = threading.RLock()

    def __init__(self, token_file: str):
        assert token_file
        self.token_file = token_file
        with TokenKeeper.LOCK:
            text = LocateTools.read_file(token_file)
            d = tomllib.loads(text)
            token, expiry = d['token'], d.get('expiry')
            assert token
            self.token = token
            self.expiry = datetime.fromisoformat(expiry)
            if self.is_expired:
                raise ValueError(f'长桥证券的访问令牌已经过期{self.expiry}')

    @property
    def is_expired(self):
        if not self.expiry:
            return False
        if TimeTools.us_time_now() >= self.expiry:
            return True
        return False

    @property
    def should_refresh(self):
        now = TimeTools.us_time_now()
        if now >= self.expiry:
            return False
        if now >= TimeTools.timedelta(self.expiry, days=-3):
            return True
        return False

    def update_token(self, token: str, expiry: datetime):
        assert self.token_file
        assert token
        assert expiry
        with TokenKeeper.LOCK:
            self.token = token
            self.expiry = expiry
            d = {
                'token': self.token,
                'expiry': self.expiry.isoformat(),
            }
            text = tomlkit.dumps(d)
            LocateTools.write_file(self.token_file, text)


class LongPortApi(BrokerApiBase):
    BROKER_NAME = 'longport'
    BROKER_DISPLAY = '长桥证券'
    ENABLE_BOOTING_CHECK = False
    TOKEN_BUCKET = LeakyBucket(6)
    MARKET_STATUS_BUCKET = LeakyBucket(15)
    QUOTE_BUCKET = LeakyBucket(60)
    CONFIG = None
    QUOTE_CLIENT = None
    KEEPER = None

    def __post_init__(self):
        config_dict = self.broker_config
        auto_refresh_token = config_dict.get('auto_refresh_token', False)
        if LongPortApi.QUOTE_CLIENT is None:
            self._reset_client(config_dict)
        self.token_keeper = LongPortApi.KEEPER
        self.auto_refresh_token = auto_refresh_token
        self._update_client()

    def _update_client(self):
        self.longport_config = LongPortApi.CONFIG
        self.quote_client = LongPortApi.QUOTE_CLIENT

    @classmethod
    def _reset_client(cls, cfg: dict):
        from longport.openapi import Config, QuoteContext
        app_key = cfg.get('app_key')
        app_secret = cfg.get('app_secret')
        token_path = cfg.get('token_path')
        assert app_key
        assert app_secret
        LongPortApi.KEEPER = TokenKeeper(token_path)
        config = Config(
            app_key=app_key,
            app_secret=app_secret,
            access_token=LongPortApi.KEEPER.token,
        )
        ctx = QuoteContext(config)
        LongPortApi.CONFIG = config
        LongPortApi.QUOTE_CLIENT = ctx

    def try_refresh(self):
        self._update_client()
        if not self.auto_refresh_token:
            return
        cfg = self.longport_config
        keeper = self.token_keeper
        with keeper.LOCK:
            if not keeper.should_refresh:
                return
            now = TimeTools.utc_now()
            expiry = TimeTools.timedelta(now, days=90)
            with self.TOKEN_BUCKET:
                token = cfg.refresh_access_token()
                assert token
            keeper.update_token(token, expiry)
            self._reset_client(self.broker_config)
            self._update_client()

    def broker_symbol(self):
        symbol = self.symbol
        if not symbol:
            raise ValueError(f'symbol字段无效')
        if re.match(r'^[56]\d{5}$', symbol):
            symbol = f'{symbol}.SH'
        elif re.match(r'^[013]\d{5}$', symbol):
            symbol = f'{symbol}.SZ'
        elif re.match(r'^\d{5}$', symbol):
            symbol = f'{symbol}.HK'
        else:
            symbol = f'{symbol}.US'
        return symbol

    def symbol_tz(self):
        symbol = self.symbol
        if not symbol:
            raise ValueError(f'symbol字段无效')
        if re.match(r'^[56]\d{5}$', symbol):
            return 'Asia/Shanghai'
        elif re.match(r'^[013]\d{5}$', symbol):
            return 'Asia/Shanghai'
        elif re.match(r'^\d{5}$', symbol):
            return 'Asia/Shanghai'
        else:
            return 'US/Eastern'

    @track_api
    def fetch_market_status(self) -> BrokerMarketStatusResult:
        result = BrokerMarketStatusResult()
        rl: list[MarketStatusResult] = list()
        ctx = self.quote_client
        try:
            with self.MARKET_STATUS_BUCKET:
                self.try_refresh()
                items = ctx.trading_session()
            for item in items:
                market = item.market
                sessions = item.trade_sessions
                region = str(market).replace('Market.', '')
                tz = TimeTools.region_to_tz(region)
                now = TimeTools.us_time_now(tz)
                ts = 'CLOSING'
                for session in sessions:
                    begin_time = TimeTools.from_params(
                        year=now.year,
                        month=now.month,
                        day=now.day,
                        hour=session.begin_time.hour,
                        minute=session.begin_time.minute,
                        second=session.begin_time.second,
                        tz=tz
                    )
                    end_time = TimeTools.from_params(
                        year=now.year,
                        month=now.month,
                        day=now.day,
                        hour=session.end_time.hour,
                        minute=session.end_time.minute,
                        second=session.end_time.second,
                        tz=tz
                    )
                    if begin_time <= now < end_time:
                        ts = str(session.trade_session).replace('TradeSession.', '')
                rl.append(MarketStatusResult(region=region, status=ts))
            result.append(BrokerTradeType.STOCK, rl)
            return result
        except Exception as e:
            raise PrepareError(f'长桥证券快照接口调用失败: {e}')

    @track_api
    def fetch_quote(self) -> Quote:
        ctx = self.quote_client
        try:
            with self.QUOTE_BUCKET:
                self.try_refresh()
                resp = ctx.quote([self.broker_symbol(), ])
            if not resp:
                raise ValueError
            item = resp[0]
            trade_time = TimeTools.from_timestamp(item.timestamp.timestamp(), self.symbol_tz())
            return Quote(
                symbol=self.symbol,
                open=float(item.open),
                pre_close=float(item.prev_close),
                latest_price=float(item.last_done),
                time=trade_time,
                status='NORMAL' if item.trade_status == 0 else 'UNABLE',
                day_low=float(item.low),
                day_high=float(item.high),
                broker_name=self.BROKER_NAME,
                broker_display=self.BROKER_DISPLAY,
            )
        except Exception as e:
            raise PrepareError(f'长桥证券快照接口调用失败: {e}')


__all__ = ['LongPortApi', 'TokenKeeper', ]
