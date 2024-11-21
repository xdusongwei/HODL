import os
import tomllib
import tomlkit
import dataclasses
import requests
from telegram.ext import Application
from jinja2 import Environment, PackageLoader, select_autoescape
from hodl.tools.currency_config import CurrencyConfig
from hodl.tools.locate import LocateTools
from hodl.tools.store_config import StoreConfig
from hodl.tools.broker_meta import BrokerMeta, BrokerTradeType
from hodl.tools.tui_config import TuiConfig


@dataclasses.dataclass
class StoreKey:
    group: str = dataclasses.field()
    broker: str = dataclasses.field()
    symbol: str = dataclasses.field()

    @classmethod
    def from_store_config(cls, store_config: StoreConfig) -> 'StoreKey':
        return StoreKey(
            group=store_config.group,
            broker=store_config.broker,
            symbol=store_config.symbol,
        )

    def __hash__(self):
        return f'{self.group}.{self.broker}.{self.symbol}'.__hash__()


class VariableTools:
    """
    配置文件读写工具
    """
    DEBUG_CONFIG = dict()

    _HTTP_SESSION = requests.Session()

    @classmethod
    def http_session(cls):
        VariableTools._HTTP_SESSION.trust_env = False
        return VariableTools._HTTP_SESSION

    @classmethod
    def _get_config_path(cls):
        if path := os.getenv('TRADE_BOT_CONFIG', None):
            config_file = path
        else:
            config_file = LocateTools.locate_file('config.toml')
        return config_file

    def __init__(self, config_file: str = None):
        if not config_file:
            config_file = VariableTools._get_config_path()
        with open(config_file, 'r', encoding='utf8') as f:
            s = f.read()
            loads = tomllib.loads(s)
            loads.update(VariableTools.DEBUG_CONFIG)
            self._config: dict = loads

    def save_config(self):
        config_file = VariableTools._get_config_path()
        text = tomlkit.dumps(self._config)
        with open(config_file, 'w', encoding='utf8') as f:
            f.write(text)

    def find_by_symbol(self, symbol: str) -> None | dict:
        for d in self._config.get('store', dict()).values():
            if d.get('symbol') != symbol:
                continue
            return d
        else:
            return None

    @property
    def jinja_env(self):
        env = Environment(
            loader=PackageLoader("hodl"),
            autoescape=select_autoescape(),
        )
        return env

    def store_config_list(self) -> list[StoreConfig]:
        store_config_list = [StoreConfig(d) for d in self._config.get('store', dict()).values()]
        return store_config_list

    @property
    def store_configs(self) -> dict[str, StoreConfig]:
        """
        所有持仓配置的字典结构, 此方法是给测试使用的, 因为字典的键是symbol, 多个交易通道的持仓配置因此会冲突
        """
        store_config_list = self.store_config_list()
        return {store_config.symbol: store_config for store_config in store_config_list}

    def store_configs_by_group(self, group_name: str = 'default') -> dict[StoreKey, StoreConfig]:
        """
        根据分组返回持仓配置的字典结构，
        前面的方法有问题，一个持仓的唯一编码是由 分组名，券商通道和标的，即group, broker, symbol三元组合成的
        """
        store_config_list = self.store_config_list()
        return {
            StoreKey.from_store_config(store_config): store_config
            for store_config in store_config_list if store_config.group == group_name
        }

    def broker_config_dict(self, name):
        """
        指定broker的配置字典结构
        """
        broker: dict = self._config.get('broker')
        if not broker:
            return None
        broker = broker.get(name, None)
        if broker is None:
            return None
        return broker

    def broker_meta(self, name) -> list[BrokerMeta]:
        """
        指定broker的功能描述信息
        """
        result = list()
        meta_list: list[dict] = self._config.get('broker_meta', dict()).get(name, list())
        for meta in meta_list:
            result.append(
                BrokerMeta(
                    trade_type=BrokerTradeType[meta['trade_type'].upper()],
                    share_market_status=meta.get('share_market_status', False),
                    share_quote=meta.get('share_quote', False),
                    market_status_regions=set(meta.get('market_status_regions', list())),
                    quote_regions=set(meta.get('quote_regions', list())),
                    trade_regions=set(meta.get('trade_regions', list())),
                    vix_symbol=meta.get('vix_symbol', None),
                )
            )
        return result

    def telegram_application(self):
        """
        Telegram机器人连接设置
        """
        telegram: dict = self._config.get('telegram', dict())
        token = telegram.get('token')
        proxy_url = telegram.get('proxy_url')
        base_url = telegram.get('base_url')
        base_file_url = telegram.get('base_file_url')
        if not token:
            return None
        builder = Application.builder().token(token)
        builder.connect_timeout(20)
        builder.read_timeout(20)
        builder.write_timeout(20)
        builder.pool_timeout(6.0)
        builder.get_updates_connect_timeout(20)
        builder.get_updates_read_timeout(20)
        builder.get_updates_write_timeout(20)
        builder.get_updates_pool_timeout(6.0)

        if proxy_url:
            builder.proxy(proxy_url)
            builder.get_updates_proxy(proxy_url)
        if base_url:
            builder.base_url(base_url)
        if base_file_url:
            builder.base_file_url(base_file_url)
        app = builder.build()
        return app

    @property
    def telegram_chat_id(self) -> int:
        """
        Telegram群组id,通知消息
        """
        telegram: dict = self._config.get('telegram', dict())
        chat_id = telegram.get('chat_id')
        return chat_id

    @property
    def tui_config(self) -> TuiConfig:
        return TuiConfig(self._config.get('tui', dict()))

    @property
    def currency_config(self) -> CurrencyConfig:
        return CurrencyConfig(self._config.get('currency', dict()))

    @property
    def manager_state_path(self):
        """
        manager汇总持仓状态文件写入的路径
        """
        return self._config.get('manager_state_path')

    @property
    def db_path(self):
        """
        sqlite数据库路径
        部分功能需要数据库支持
        例如报警、归档持仓状态和订单记录、历史收益明细，临时基准价格等等
        """
        return self._config.get('db_path')

    @property
    def prefer_market_status_brokers(self) -> list[str]:
        """
        根据给定的broker类型顺序优先参考它们的市场状态信息
        比如证券交易，希望优先使用A券商的市场状态为主进行证券市场状态播报，而不是默认的broker顺序遍历市场状态
        """
        return self._config.get('prefer_market_status_brokers', list())

    @property
    def prefer_quote_brokers(self) -> list[str]:
        """
        根据给定的broker类型顺序优先使用他们的市场报价
        比如证券交易，优先使用A券商的行情数据，其次是B券商数据作为备用数据在A券商拉取失败时轮替
        """
        return self._config.get('prefer_quote_brokers', list())

    @property
    def sleep_limit(self) -> int:
        """
        持仓线程刷新的间隔时间
        Returns
        -------

        """
        limit = self._config.get('sleep_limit', 6)
        assert limit >= 1
        return limit

    @property
    def async_market_status(self) -> bool:
        """
        是否启用异步线程更新市场状态，这样尽量不去因为拉取市场状态接口的数据而阻塞到持仓线程.
        如果持仓数量多, 每个持仓线程都去遍历市场状态接口, 可能因为券商接口限速的原因, 处理时间非常长.
        """
        return self._config.get('async_market_status', False)

    @property
    def html_file_path(self) -> str | None:
        """
        将运行状态保存为网页文件
        """
        return self._config.get('html_file_path', None)

    @property
    def html_manifest_path(self) -> str | None:
        """
        PWA 清单文件的站点位置
        Returns
        -------

        """
        return self._config.get('html_manifest_path', None)

    @property
    def html_auto_refresh_time(self) -> int | None:
        """
        网页文件自带刷新时间间隔，单位毫秒
        """
        return self._config.get('html_auto_refresh_time', None)

    @property
    def html_monthly_earnings_currency(self) -> list[str]:
        """
        网页文件中按月统计收益图表的货币品种限制
        """
        return self._config.get('html_monthly_earnings_currency', ['USD', 'CNY', ])

    @property
    def html_total_earning_currency(self) -> list[str]:
        """
        网页文件中当前资产汇总部分的币种选择, 默认为 美元\人民币\港币 三种
        """
        return self._config.get('html_total_earning_currency', ['USD', 'CNY', 'HKD', ])

    @property
    def html_assets_currency(self) -> list[str]:
        """
        网页文件中当前资产汇总部分的币种选择, 默认为 美元\人民币\港币 三种
        """
        return self._config.get('html_assets_currency', ['USD', 'CNY', 'HKD', ])

    @property
    def broker_icon_path(self) -> str | None:
        """
        交易通道的图标目录路径
        """
        return self._config.get('broker_icon_path', None)

    def log_root(self, broker: str, region: str, symbol: str) -> str:
        """
        指定一个目录，用来专门保存持仓的日志
        Returns
        -------

        """
        path: str = self._config.get('log_root')
        if path:
            path = path.format(broker=broker, region=region, symbol=symbol)
            path = os.path.expanduser(path)
            os.makedirs(path, exist_ok=True)
        return path


class HotReloadVariableTools:
    """
    提供服务运行时热改动配置的能力
    """
    @classmethod
    def set_up_var(cls, var: VariableTools):
        setattr(HotReloadVariableTools, '__var', var)

    @classmethod
    def config(cls) -> VariableTools:
        var: VariableTools = getattr(HotReloadVariableTools, '__var', None)
        if var is None:
            var = VariableTools()
            cls.set_up_var(var)
        return var


__all__ = [
    'StoreKey',
    'VariableTools',
    'HotReloadVariableTools',
]
