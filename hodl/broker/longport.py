"""
长桥证券文档见
https://open.longportapp.com/docs
长桥 SDK 采用了预编译的软件包进行发布, 不适合的环境会导致系统安装失败, 如果需要使用长桥 SDK, 安装本项目需要使用命令:
pdm install -G longport
"""
import re
import tomllib
import threading
from datetime import datetime
from decimal import Decimal
import tomlkit
from hodl.broker.base import *
from hodl.exception_tools import *
from hodl.quote import *
from hodl.state import *
from hodl.tools import *


class TokenKeeper:
    """
    长桥证券的会话需要通过下发的 token 凭据验证身份,
    这个 token, 有有效期, 所以, 这个类负责当 token 快要到过期时间的时候通过 SDK 接口去下载新 token.

    因此, 初次使用的时候, 必须去他们的开发者网站上拿到新 token, 做成一个 toml 格式文件.
    这个 toml 文件需要设置两个字段, 分别是 token 和 expiry,
    token 字段填入给的令牌字符串,
    expiry 是过期时间的字符串, 例如 "2025-01-01T00:00:00.000000+00:00"
    没有这个 toml 文件, 或者 token 文件的 expiry 过期了, 系统便没办法连接到他们的接口上做自动更新, 因此会有启动上的问题.
    """
    LOCK = threading.RLock()

    def __init__(self, token_file: str):
        assert token_file
        self.token_file = token_file
        with TokenKeeper.LOCK:
            text = LocateTools.read_file(token_file)
            d = tomllib.loads(text)
            token, expiry = d.get('token'), d.get('expiry')
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


@broker_api(broker_name='longport', broker_display='长桥证券', booting_check=False, cash_currency='USD')
class LongPortApi(BrokerApiBase):
    TOKEN_BUCKET = LeakyBucket(6)
    MARKET_STATUS_BUCKET = LeakyBucket(15)
    QUOTE_BUCKET = LeakyBucket(60)
    ASSET_BUCKET = LeakyBucket(60)

    CONFIG = None
    QUOTE_CLIENT = None
    TRADE_CLIENT = None
    KEEPER = None

    def __post_init__(self):
        config_dict = self.broker_config
        auto_refresh_token = config_dict.get('auto_refresh_token', False)
        if self.longport_config is None:
            self._reset_client(config_dict)
        self.auto_refresh_token = auto_refresh_token

    @property
    def quote_client(self):
        from longport.openapi import QuoteContext
        client: QuoteContext = LongPortApi.QUOTE_CLIENT
        return client

    @property
    def trade_client(self):
        from longport.openapi import TradeContext
        client: TradeContext = LongPortApi.TRADE_CLIENT
        return client

    @property
    def longport_config(self):
        return LongPortApi.CONFIG

    @property
    def token_keeper(self) -> TokenKeeper:
        return LongPortApi.KEEPER

    @classmethod
    def _reset_client(cls, cfg: dict):
        from longport.openapi import Config, QuoteContext, TradeContext
        app_key = cfg.get('app_key')
        app_secret = cfg.get('app_secret')
        token_path = cfg.get('token_path')
        assert app_key
        assert app_secret
        LongPortApi.KEEPER = LongPortApi.KEEPER or TokenKeeper(token_path)
        config = Config(
            app_key=app_key,
            app_secret=app_secret,
            access_token=LongPortApi.KEEPER.token,
        )
        quote_ctx = QuoteContext(config)
        trade_ctx = TradeContext(config)
        LongPortApi.CONFIG = config
        LongPortApi.QUOTE_CLIENT = quote_ctx
        LongPortApi.TRADE_CLIENT = trade_ctx

    def try_refresh(self):
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
        # 尽量不要使用长桥证券提供的市场状态接口, 它返回的交易时段似乎不是动态的, 节假日仍提供交易时段.
        # 有可能当全市场临时休市的信息该证券平台不会正确提供.
        status_map = {
            'Normal': self.MS_TRADING,
            'Post': self.MS_CLOSED,
        }
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
                ts = self.MS_CLOSED
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
                status = status_map.get(ts, self.MS_CLOSED)
                display = ts
                rl.append(MarketStatusResult(region=region, status=status, display=display))
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

    @track_api
    def query_cash(self):
        try:
            with self.ASSET_BUCKET:
                self.try_refresh()
                resp = self.trade_client.account_balance('USD')
            for node in resp:
                if node.currency != 'USD':
                    continue
                cash = float(node.total_cash)
                return cash
            raise PrepareError('找不到指定币种的可用资金')
        except Exception as e:
            raise PrepareError(f'长桥证券资金接口调用失败: {e}')

    @track_api
    def query_chips(self):
        symbol = self.broker_symbol()
        try:
            with self.ASSET_BUCKET:
                self.try_refresh()
                items = self.trade_client.stock_positions().channels
            for channel in items:
                if channel.account_channel != 'lb':
                    continue
                for node in channel.positions:
                    if node.symbol != symbol:
                        continue
                    return int(node.quantity)
        except Exception as e:
            raise PrepareError(f'长桥证券持仓接口调用失败: {e}')

    @track_api
    def place_order(self, order: Order):
        from longport.openapi import OrderType, OrderSide, TimeInForceType, OutsideRTH
        symbol = self.broker_symbol()
        with self.ASSET_BUCKET:
            self.try_refresh()
            resp = self.trade_client.submit_order(
                symbol=symbol,
                order_type=OrderType.LO if order.limit_price else OrderType.MO,
                side=OrderSide.Buy if order.is_buy else OrderSide.Sell,
                outside_rth=OutsideRTH.RTHOnly,
                submitted_quantity=Decimal(order.qty),
                time_in_force=TimeInForceType.Day,
                submitted_price=Decimal(order.limit_price) if order.limit_price else None,
            )
            assert resp.order_id
            order.order_id = resp.order_id

    @track_api
    def cancel_order(self, order: Order):
        with self.ASSET_BUCKET:
            self.try_refresh()
            self.trade_client.cancel_order(order_id=order.order_id)

    @track_api
    def refresh_order(self, order: Order):
        from longport.openapi import OrderStatus
        with self.ASSET_BUCKET:
            self.try_refresh()
            resp = self.trade_client.order_detail(order_id=order.order_id)
            reason = ''
            if resp.status == OrderStatus.Rejected:
                reason = '已拒绝'
            if resp.status == OrderStatus.Expired:
                reason = '已过期'
            if resp.status == OrderStatus.PartialWithdrawal:
                reason = '部分撤单'
            self.modify_order_fields(
                order=order,
                qty=int(resp.quantity),
                filled_qty=int(resp.executed_quantity),
                avg_fill_price=float(resp.executed_price) if resp.executed_price else 0.0,
                trade_timestamp=None,
                reason=reason,
                is_cancelled=resp.status == OrderStatus.Canceled,
            )


__all__ = ['LongPortApi', 'TokenKeeper', ]
