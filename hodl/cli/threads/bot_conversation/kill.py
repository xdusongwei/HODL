from telegram import ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler
from telegram.ext.filters import Regex
from hodl.bot import TelegramBotBase
from hodl.thread_mixin import *


class KillStore(TelegramBotBase):
    K_KS_SELECT = 0
    K_KS_DECISION = 1
    K_KS_CONFIRM = 2

    async def kill_store_start(self, update, context):
        lines = self._symbol_lines()
        idx_list = self._symbol_choice()
        await update.message.reply_text(
            f'你正在尝试杀死的持仓管理线程。 '
            f'选择需要操作的持仓序号\n'
            f'{lines}\n\n流程的任意阶段都可以使用 /cancel 取消',
            reply_markup=ReplyKeyboardMarkup(
                idx_list, one_time_keyboard=True, input_field_placeholder='选择持仓序号'
            ),
        )
        return self.K_KS_DECISION

    async def kill_store_select(self, update, context):
        idx = int(update.message.text) - 1
        position = self._symbol_list()[idx]
        user_id = update.message.from_user.id
        self._create_session(user_id=user_id, position=position)
        await update.message.reply_text(
            f'选择了 {position.display} 操作杀死持仓管理线程。'
            f'使用命令 /confirm 来确认',
            reply_markup=ReplyKeyboardRemove(),
        )
        return self.K_KS_CONFIRM

    async def kill_store_confirm(self, update, context):
        text = update.message.text
        user_id = update.message.from_user.id
        session = self._get_session(user_id=user_id)
        match text:
            case '/confirm':
                await update.message.reply_text(
                    f'已经确认将要杀死{session.position.display}线程',
                    reply_markup=ReplyKeyboardRemove(),
                )
                try:
                    broker = session.position.config.broker
                    region = session.position.config.region
                    symbol = session.position.symbol
                    store = ThreadMixin.find_by_tags(tags=('Store', broker, region, symbol, ))
                    thread = store.current_thread
                    if thread:
                        if not thread.is_alive():
                            raise ValueError(f'线程{thread}已经死亡')
                    else:
                        raise ValueError(f'找不到持仓对应的线程')

                    with store.thread_lock():
                        store.kill()

                    await update.message.reply_text(
                        f'已杀死线程',
                        reply_markup=ReplyKeyboardRemove(),
                    )
                except Exception as e:
                    await update.message.reply_text(
                        f'操作失败:{e}',
                        reply_markup=ReplyKeyboardRemove(),
                    )
                finally:
                    self._clear_session(user_id=user_id)

                return ConversationHandler.END
            case _:
                await update.message.reply_text(
                    f'非法选择，请重新选择命令',
                    reply_markup=ReplyKeyboardRemove(),
                )
                return self.K_KS_CONFIRM

    @classmethod
    def handler(cls):
        o = cls()
        handler = ConversationHandler(
            entry_points=[CommandHandler('killStore', o.kill_store_start)],
            states={
                o.K_KS_DECISION: [MessageHandler(Regex(r'^(\d+)$'), o.kill_store_select)],
                o.K_KS_CONFIRM: [
                    CommandHandler('confirm', o.kill_store_confirm),
                ],
            },
            fallbacks=[o.cancel_handler()],
            conversation_timeout=60.0,
            block=False,
        )
        return handler


__all__ = ['KillStore']
