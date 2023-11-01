from dataclasses import dataclass
from hodl.storage import *
from hodl.tools import *
from hodl.bot.base import TelegramBotBase


@dataclass
class AlertKey:
    key_template: str
    save_db: bool


class AlertBot(TelegramBotBase):
    K_THREAD_DEAD = AlertKey(key_template='K_THREAD_DEAD.{symbol}', save_db=False)
    K_TRADE_SERVICE = AlertKey(key_template='K_TRADE_SERVICE.{broker}.{symbol}', save_db=True)

    def __init__(self, broker: str, symbol: str, chat_id=None, db: LocalDb = None):
        super(AlertBot, self).__init__(db=db)
        self.broker = broker
        self.symbol = symbol
        self.chat_id = chat_id
        self.d = dict()
        self.is_alive = bool(self.pull_thread() and chat_id)

    def _format_key(self, key_template: str):
        key = key_template.format(
            symbol=self.symbol,
            broker=self.broker,
        )
        return key

    def _latest_value(self, key, save_db=False) -> bool:
        if save_db and self.db:
            row = AlarmRow.query_by_key(con=self.db.conn, key=key)
            return bool(row.is_set)
        else:
            return self.d.get(key, False)

    def _save_value(self, key, value: bool, save_db=False):
        if save_db and self.db:
            row = AlarmRow(
                key=key,
                is_set=int(value),
                symbol=self.symbol,
                broker=self.broker,
                update_time=int(TimeTools.us_time_now().timestamp()),
            )
            row.save(con=self.db.conn)
        else:
            self.d[key] = value

    def unset_alarm(self, alert_key: AlertKey, text: str = None, disable_notification=None):
        key = self._format_key(key_template=alert_key.key_template)
        latest = self._latest_value(key=key, save_db=alert_key.save_db)
        if latest:
            self._save_value(key=key, value=False, save_db=alert_key.save_db)
            if text:
                self.send_text(text=text, disable_notification=disable_notification)

    def set_alarm(self, alert_key: AlertKey, text: str, disable_notification=None):
        key = self._format_key(key_template=alert_key.key_template)
        latest = self._latest_value(key=key, save_db=alert_key.save_db)
        if not latest:
            self._save_value(key=key, value=True, save_db=alert_key.save_db)
            self.send_text(text=text, disable_notification=disable_notification)

    def send_text(self, text: str, block=True, disable_notification=None):
        if not self.is_alive:
            return
        try:
            interface = self.pull_thread()
            interface.send_message(text=text, block=block, disable_notification=disable_notification)
        except Exception as e:
            return e


__all__ = ['AlertBot', ]
