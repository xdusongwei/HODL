import os
import toml
from telegram.ext import Updater
from jinja2 import Environment, PackageLoader, select_autoescape
from hodl.tools.locate import LocateTools
from hodl.tools.store_config import StoreConfig
from hodl.tools.tui_config import TuiConfig


class VariableTools:
    """
    配置文件读写工具
    """
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
            self._config: dict = toml.loads(f.read())

    def save_config(self):
        config_file = VariableTools._get_config_path()
        text = toml.dumps(self._config)
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

    @property
    def store_configs(self) -> dict[str, StoreConfig]:
        """
        所有持仓配置的字典结构
        """
        store_config_list = [StoreConfig(d) for d in self._config.get('store', dict()).values()]
        return {store_config.symbol: store_config for store_config in store_config_list}

    def broker_config_dict(self, name):
        """
        指定broker的配置字典结构
        """
        broker: dict = self._config.get('broker')
        if not broker:
            return None
        broker = broker.get(name, dict())
        if not broker:
            return None
        return broker

    def telegram_updater(self) -> None | Updater:
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
        return Updater(
            base_url=base_url,
            base_file_url=base_file_url,
            token=token,
            use_context=True,
            request_kwargs={
                'proxy_url': proxy_url,
            },
        )

    @property
    def telegram_chat_id(self) -> int:
        """
        Telegram群组id,通知消息
        """
        telegram: dict = self._config.get('telegram', dict())
        chat_id = telegram.get('chat_id')
        return chat_id

    @property
    def tui_configs(self) -> list[TuiConfig]:
        tui_config_list = [TuiConfig(d) for d in self._config.get('tui', list())]
        return tui_config_list

    @property
    def manager_state_path(self):
        """
        manager汇总持仓状态文件写入的路径
        """
        return self._config.get('manager_state_path')

    @property
    def earning_json_path(self) -> str:
        """
        收益json文件写入的路径
        """
        return self._config.get('earning_json_path')

    @property
    def earning_recent_weeks(self) -> int:
        """
        收益文件近期可展示的时间范围
        """
        return self._config.get('earning_csv_weeks', 4)

    @property
    def db_path(self):
        """
        sqlite数据库路径
        部分功能需要数据库支持
        例如报警、归档持仓状态和订单记录、历史收益明细，临时基准价格等等
        """
        return self._config.get('db_path')

    @property
    def prefer_market_state_brokers(self) -> list[str]:
        """
        根据给定的broker类型顺序优先参考它们的市场状态信息
        比如证券交易，希望优先使用A券商的市场状态为主进行证券市场状态播报，而不是默认的broker顺序遍历市场状态
        """
        return self._config.get('prefer_market_state_brokers', list())

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
        是否启用异步线程更新市场状态，这样尽量不去阻塞到持仓线程
        """
        return self._config.get('async_market_status', False)

    @property
    def html_file_path(self) -> str:
        """
        将运行状态保存为网页文件
        """
        return self._config.get('html_file_path', None)


__all__ = ['VariableTools', ]
