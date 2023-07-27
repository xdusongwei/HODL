from dataclasses import dataclass
from expiringdict import ExpiringDict
from telegram import ReplyKeyboardRemove
from telegram.ext import Updater, ConversationHandler, CommandHandler
from hodl.tools import *
from hodl.storage import *


@dataclass
class _Position:
    idx: str
    symbol: str
    display: str
    config: StoreConfig
    enable: str = None
    lock_position: str = None
    base_price_last_buy: str = None
    base_price_day_low: str = None
    max_shares: str = None


@dataclass
class _Session:
    position: _Position
    value: bool = None


class TelegramBotBase:
    UPDATER = None
    BOT = None
    DB: LocalDb = None
    SESSION = ExpiringDict(max_len=1024, max_age_seconds=3600)
    STORES = list()

    def __init__(self, updater: Updater = None, db: LocalDb = None):
        if updater and not TelegramBotBase.BOT:
            TelegramBotBase.UPDATER = updater
            updater.start_polling()
            TelegramBotBase.BOT = updater.bot
        if db and not TelegramBotBase.DB:
            TelegramBotBase.DB = db

    @property
    def updater(self):
        return TelegramBotBase.UPDATER

    @property
    def bot(self):
        return TelegramBotBase.BOT

    @property
    def db(self):
        return TelegramBotBase.DB

    @classmethod
    def _symbol_list(cls):
        var = VariableTools()
        values = var.store_configs.values()
        values = sorted(values, key=lambda i: i.symbol)
        result = list()
        for idx, v in enumerate(values):
            result.append(
                _Position(
                    idx=str(idx + 1),
                    symbol=v.symbol,
                    display=f'{idx + 1}: [{v.region}]{v.symbol} {v.name or ""}',
                    config=v,
                    enable='开启' if v.enable else '关闭',
                    lock_position='锁定' if v.lock_position else '解锁',
                    base_price_last_buy='开启' if v.base_price_last_buy else '关闭',
                    base_price_day_low='开启' if v.base_price_day_low else '关闭',
                    max_shares=FormatTool.pretty_number(v.max_shares),
                )
            )
        return result

    @classmethod
    def _create_session(cls, user_id, position):
        assert user_id
        item = _Session(position=position)
        cls.SESSION[user_id] = item
        return item

    @classmethod
    def _get_session(cls, user_id) -> _Session:
        return cls.SESSION[user_id]

    @classmethod
    def _clear_session(cls, user_id):
        assert user_id
        cls.SESSION[user_id] = None

    @classmethod
    def _symbol_lines(cls):
        return '\n'.join([item.display for item in cls._symbol_list()])

    @classmethod
    def _symbol_choice(cls):
        return [[item.idx for item in cls._symbol_list()]]

    def _cancel_handler(self, update, context) -> int:
        """Cancels and ends the conversation."""
        update.message.reply_text(
            '已取消对话', reply_markup=ReplyKeyboardRemove()
        )
        user_id = update.message.from_user.id
        self._clear_session(user_id=user_id)
        return ConversationHandler.END

    def cancel_handler(self):
        return CommandHandler('cancel', self._cancel_handler)


__all__ = ['TelegramBotBase', ]
