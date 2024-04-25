import os
from telegram import ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler
from telegram.ext.filters import Regex
from hodl.bot import TelegramBotBase
from hodl.thread_mixin import *
from hodl.tools import *


class DeleteState(TelegramBotBase):
    K_DS_SELECT = 0
    K_DS_INPUT = 1
    K_DS_CONFIRM = 2
    STORE_LIST: list[ThreadMixin] = list()

    @classmethod
    async def set_store_list(cls, store_list):
        DeleteState.STORE_LIST = store_list

    async def delete_state_start(self, update, context):
        lines = self._symbol_lines()
        idx_list = self._symbol_choice()
        await update.message.reply_text(
            f'你正在尝试[清除持仓状态]。警告，只用此功能前确认目标持仓没有任何订单记录，或者，目标持仓是已套利的状态。 '
            f'选择需要操作的标的序号\n'
            f'{lines}\n\n流程的任意阶段都可以使用 /cancel 取消',
            reply_markup=ReplyKeyboardMarkup(
                idx_list, one_time_keyboard=True, input_field_placeholder='选择持仓标的序号'
            ),
        )
        return self.K_DS_SELECT

    async def delete_state_select(self, update, context):
        idx = int(update.message.text) - 1
        position = self._symbol_list()[idx]
        user_id = update.message.from_user.id
        self._create_session(user_id=user_id, position=position)
        if position.config.trade_strategy != TradeStrategyEnum.HODL:
            await update.message.reply_text(
                f'该持仓不是”长期持有套利(HODL)“控制模式，无法[清除持仓状态]。',
                reply_markup=ReplyKeyboardRemove(),
            )
            return ConversationHandler.END
        elif path := position.config.state_file_path:
            await update.message.reply_text(
                f'确认针对{position.display}执行[清除持仓状态]? 状态文件在:{path}。 使用命令 /confirm 来确认',
                reply_markup=ReplyKeyboardRemove(),
            )
            return self.K_DS_CONFIRM
        else:
            await update.message.reply_text(
                f'该持仓不存储状态数据的位置，无法[清除持仓状态]。',
                reply_markup=ReplyKeyboardRemove(),
            )
            return ConversationHandler.END

    async def delete_state_confirm(self, update, context):
        text = update.message.text
        user_id = update.message.from_user.id
        session = self._get_session(user_id=user_id)
        match text:
            case '/confirm':
                await update.message.reply_text(
                    f'已经确认对{session.position.display}执行[清除持仓状态]',
                    reply_markup=ReplyKeyboardRemove(),
                )
                try:
                    broker = session.position.config.broker
                    region = session.position.config.region
                    symbol = session.position.symbol
                    thread = ThreadMixin.find_by_tags(tags=('Store', broker, region, symbol,))
                    if thread:
                        with thread.thread_lock():
                            count = thread.thread_action(method='prepare_delete_state')
                            if count:
                                await update.message.reply_text(
                                    f'已撤销{count}个订单',
                                    reply_markup=ReplyKeyboardRemove(),
                                )
                            state_path = session.position.config.state_file_path
                            os.remove(state_path)
                            await update.message.reply_text(
                                f'清除完成',
                                reply_markup=ReplyKeyboardRemove(),
                            )
                    else:
                        raise ValueError(f'找不到持仓对应的线程')
                except FileNotFoundError:
                    await update.message.reply_text(
                        f'改动完成(不存在状态文件)',
                        reply_markup=ReplyKeyboardRemove(),
                    )
                except Exception as e:
                    await update.message.reply_text(
                        f'改动失败:{e}',
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
                return self.K_DS_CONFIRM

    @classmethod
    def handler(cls):
        o = cls()
        handler = ConversationHandler(
            entry_points=[CommandHandler('deleteState', o.delete_state_start)],
            states={
                o.K_DS_SELECT: [MessageHandler(Regex(r'^(\d+)$'), o.delete_state_select)],
                o.K_DS_CONFIRM: [
                    CommandHandler('confirm', o.delete_state_confirm),
                ],
            },
            fallbacks=[o.cancel_handler()],
            conversation_timeout=60.0,
            block=False,
        )
        return handler


__all__ = ['DeleteState']
