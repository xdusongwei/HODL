import abc
from dataclasses import dataclass
from typing import Self, Type
from expiringdict import ExpiringDict
from telegram import ReplyKeyboardRemove, Message, ReplyKeyboardMarkup
from telegram.ext import Application, ConversationHandler, CommandHandler, MessageHandler
from telegram.ext.filters import Regex
from hodl.tools import *
from hodl.storage import *


@dataclass
class TgSelectedPosition:
    idx: str
    symbol: str
    display: str
    config: StoreConfig


@dataclass
class _Session:
    user_id: int
    position: TgSelectedPosition
    value: bool = None


class TelegramThreadBase(abc.ABC):
    INSTANCE: Self = None

    def application(self) -> Application:
        raise NotImplementedError

    def send_message(self, text: str, block=True, disable_notification=None) -> Message:
        raise NotImplementedError


class TelegramBotBase:
    APP: Application = None
    DB: LocalDb = None
    SESSION = ExpiringDict(max_len=1024, max_age_seconds=600)
    STORES = list()

    def __init__(self, db: LocalDb = None):
        if db and not TelegramBotBase.DB:
            TelegramBotBase.DB = db

    @classmethod
    def pull_thread(cls) -> TelegramThreadBase:
        return TelegramThreadBase.INSTANCE

    @property
    def db(self):
        return TelegramBotBase.DB


class TelegramConversationBase(TelegramBotBase):
    _ALL_CONVERSATION_TYPES = list()

    # 用于限定命令可操作的持仓策略
    TRADE_STRATEGY: str | None = None
    # 电报需要注册的命令, 例如 mycommand
    COMMAND: str = ''
    # 对电报命令的描述, 用于给 @botfather 提供每个命令菜单项的简单描述
    MENU_DESC: str = ''
    # 命令是否涉及数据库的操作, 对于 SimpleTelegramConversation 编写的命令,
    # 可以在用户选择了持仓之后, 过滤掉不支持的功能而结束对话.
    REQUIRE_DB_FUNCTION: bool = False

    @classmethod
    async def reply_text(cls, update, text: str):
        await update.message.reply_text(
            text,
            reply_markup=ReplyKeyboardRemove(),
        )

    @classmethod
    def all_conversation_type(cls) -> list[Type['TelegramConversationBase']]:
        return TelegramConversationBase._ALL_CONVERSATION_TYPES.copy()

    @classmethod
    def register_conversation_type(
            cls,
            command: str,
            menu_desc: str,
            conversation_type: Type['TelegramConversationBase'],
            trade_strategy: str | None,
            db_function: bool = False,
    ):
        assert issubclass(conversation_type, TelegramConversationBase)
        if conversation_type in TelegramConversationBase._ALL_CONVERSATION_TYPES:
            return
        conversation_type.COMMAND = command
        conversation_type.MENU_DESC = menu_desc
        conversation_type.TRADE_STRATEGY = trade_strategy
        conversation_type.REQUIRE_DB_FUNCTION = db_function
        TelegramConversationBase._ALL_CONVERSATION_TYPES.append(conversation_type)

    @classmethod
    def handler(cls) -> ConversationHandler:
        raise NotImplementedError

    @classmethod
    def _symbol_list(cls):
        var = HotReloadVariableTools.config()
        values = var.store_configs_by_group().values()
        values = sorted(values, key=lambda i: i.full_name)
        result = list()
        for idx, v in enumerate(values):
            result.append(
                TgSelectedPosition(
                    idx=str(idx + 1),
                    symbol=v.symbol,
                    display=f'{idx + 1}: {v.full_name}',
                    config=v,
                )
            )
        return result

    @classmethod
    def _create_session(cls, user_id, position):
        assert user_id
        item = _Session(user_id=user_id, position=position)
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

    async def _cancel_handler(self, update, context) -> int:
        """Cancels and ends the conversation."""
        await update.message.reply_text(
            '已取消对话', reply_markup=ReplyKeyboardRemove()
        )
        user_id = update.message.from_user.id
        self._clear_session(user_id=user_id)
        return ConversationHandler.END

    def cancel_handler(self):
        return CommandHandler('cancel', self._cancel_handler)


class SimpleTelegramConversation(TelegramConversationBase):
    """
    "选择持仓-确认-执行" 模式的简单对话控制
    """
    # 选择持仓时机器人回复的描述
    SELECT_TEXT = ''

    K_SIMPLE_END = ConversationHandler.END
    K_SIMPLE_CONFIRM = 0
    K_SIMPLE_EXECUTE = 1

    async def _select(self, update, context):
        if self.REQUIRE_DB_FUNCTION and not self.DB:
            await self.reply_text(update, '没有设置数据库，不能此命令。')
            return self.K_SIMPLE_END

        code = await self.select(update, context)
        return code

    @classmethod
    def next_step_after_select(cls) -> int:
        return cls.K_SIMPLE_CONFIRM

    async def after_select_check(self, update) -> int | None:
        idx = int(update.message.text) - 1

        positions = self._symbol_list()

        if idx < 0 or idx >= len(positions):
            return self.K_SIMPLE_END

        position = positions[idx]
        user_id = update.message.from_user.id

        if self.TRADE_STRATEGY and self.TRADE_STRATEGY != position.config.trade_strategy:
            await self.reply_text(
                update,
                f'非法选择，请重新选择命令',
            )
            return self.K_SIMPLE_END

        self._create_session(user_id=user_id, position=position)
        return None

    def get_session(self, update) -> _Session:
        user_id = update.message.from_user.id
        session = self._get_session(user_id=user_id)
        return session

    async def _confirm(self, update, context):
        code = await self.after_select_check(update)
        if code is not None:
            return code

        session = self.get_session(update)
        position = session.position
        code = await self.confirm(update, context, position)
        return code

    async def _execute(self, update, context):
        text = update.message.text
        session = self.get_session(update)
        user_id = session.user_id
        position = session.position
        match text:
            case '/confirm':
                try:
                    await self.execute(update, context, position)
                finally:
                    self._clear_session(user_id=user_id)

                return self.K_SIMPLE_END
            case _:
                await self.reply_text(
                    update,
                    f'非法选择，请重新选择命令',
                )
                return self.K_SIMPLE_EXECUTE

    async def select(self, update, context):
        lines = self._symbol_lines()
        idx_list = self._symbol_choice()
        await update.message.reply_text(
            f'{self.SELECT_TEXT} '
            f'选择需要操作的持仓序号\n'
            f'{lines}\n\n流程的任意阶段都可以使用 /cancel 取消',
            reply_markup=ReplyKeyboardMarkup(
                idx_list, one_time_keyboard=True, input_field_placeholder='选择持仓序号'
            ),
        )
        return self.next_step_after_select()

    async def confirm(self, update, context, position: TgSelectedPosition) -> int:
        raise NotImplementedError

    async def execute(self, update, context, position: TgSelectedPosition):
        raise NotImplementedError

    @classmethod
    def handler(cls):
        o = cls()
        handler = ConversationHandler(
            entry_points=[CommandHandler(cls.COMMAND, o._select)],
            states={
                o.K_SIMPLE_CONFIRM: [MessageHandler(Regex(r'^(\d+)$'), o._confirm)],
                o.K_SIMPLE_EXECUTE: [
                    CommandHandler('confirm', o._execute),
                ],
            },
            fallbacks=[o.cancel_handler()],
            conversation_timeout=60.0,
            block=False,
        )
        return handler


class SingleInputConversation(SimpleTelegramConversation):
    """
    "选择持仓-输入字符-确认-执行" 模式的对话控制
    """
    K_SIC_END = ConversationHandler.END
    K_SIC_INPUT = 0
    K_SIC_CONFIRM = 1
    K_SIC_EXECUTE = 2

    # 选择持仓时机器人回复的描述
    SELECT_TEXT = ''
    # 对输入的数据提供的正则校验
    INPUT_REGEX = r'^(.+)$'

    @classmethod
    def next_step_after_select(cls) -> int:
        return cls.K_SIC_INPUT

    async def _input(self, update, context) -> int:
        code = await self.after_select_check(update)
        if code is not None:
            return code

        session = self.get_session(update)
        position = session.position
        await self.input(update, context, position)
        return self.K_SIC_CONFIRM

    async def _confirm(self, update, context):
        session = self.get_session(update)
        position = session.position
        code = await self.confirm(update, context, position)
        return code

    async def input(self, update, context, position: TgSelectedPosition):
        raise NotImplementedError

    @classmethod
    def handler(cls):
        o = cls()
        handler = ConversationHandler(
            entry_points=[CommandHandler(cls.COMMAND, o._select)],
            states={
                o.K_SIC_INPUT: [MessageHandler(Regex(r'^(\d+)$'), o._input)],
                o.K_SIC_CONFIRM: [MessageHandler(Regex(cls.INPUT_REGEX), o._confirm)],
                o.K_SIC_EXECUTE: [
                    CommandHandler('confirm', o._execute),
                ],
            },
            fallbacks=[o.cancel_handler()],
            conversation_timeout=60.0,
            block=False,
        )
        return handler


def bot_cmd(
        command: str,
        menu_desc: str,
        trade_strategy: str | None = None,
        db_function: bool = False,
):
    assert command not in {'cancel', 'confirm', }
    assert command and menu_desc

    def decorator(cls: Type[TelegramConversationBase]):
        TelegramConversationBase.register_conversation_type(
            command=command,
            menu_desc=menu_desc,
            conversation_type=cls,
            trade_strategy=trade_strategy,
            db_function=db_function,
        )
        return cls

    return decorator


__all__ = [
    'TgSelectedPosition',
    'TelegramBotBase',
    'TelegramThreadBase',
    'TelegramConversationBase',
    'SimpleTelegramConversation',
    'SingleInputConversation',
    'bot_cmd',
]
