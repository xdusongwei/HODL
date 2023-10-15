from telegram import ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler
from telegram.ext.filters import Regex
from hodl.bot import TelegramBotBase
from hodl.tools import *


class MaxShares(TelegramBotBase):
    K_MS_SELECT = 0
    K_MS_INPUT = 1
    K_MS_CONFIRM = 2

    async def max_shares_start(self, update, context):
        lines = self._symbol_lines()
        idx_list = self._symbol_choice()
        await update.message.reply_text(
            f'你正在尝试设置修改[登记股数](maxShares)的设定，指定持仓未有任何买卖单时会有效执行。 '
            f'选择需要操作的标的序号\n'
            f'{lines}\n\n流程的任意阶段都可以使用 /cancel 取消',
            reply_markup=ReplyKeyboardMarkup(
                idx_list, one_time_keyboard=True, input_field_placeholder='选择持仓标的序号'
            ),
        )
        return self.K_MS_SELECT

    async def max_shares_select(self, update, context):
        idx = int(update.message.text) - 1
        position = self._symbol_list()[idx]
        user_id = update.message.from_user.id
        self._create_session(user_id=user_id, position=position)
        await update.message.reply_text(
            f'选择了 {position.display} 操作[登记股数]项目的修改。'
            f'当前数量为: {FormatTool.pretty_number(position.config.max_shares)}。请输入新数量',
            reply_markup=ReplyKeyboardRemove(),
        )
        return self.K_MS_INPUT

    async def max_shares_input(self, update, context):
        text = update.message.text
        max_shares = int(text)
        if max_shares >= 0:
            user_id = update.message.from_user.id
            session = self._get_session(user_id=user_id)
            session.value = max_shares
            max_shares_text = FormatTool.pretty_number(max_shares)
            await update.message.reply_text(
                f'确认针对{session.position.display}的[登记股数]改动为{max_shares_text}? 使用命令 /confirm 来确认',
                reply_markup=ReplyKeyboardRemove(),
            )
            return self.K_MS_CONFIRM
        else:
            await update.message.reply_text(
                f'请重新输入股数',
                reply_markup=ReplyKeyboardRemove(),
            )
            return self.K_MS_INPUT

    async def max_shares_confirm(self, update, context):
        text = update.message.text
        user_id = update.message.from_user.id
        session = self._get_session(user_id=user_id)
        match text:
            case '/confirm':
                await update.message.reply_text(
                    f'已经确认改动{session.position.display}的[登记股数]',
                    reply_markup=ReplyKeyboardRemove(),
                )
                try:
                    symbol = session.position.symbol
                    var = VariableTools()
                    d = var.find_by_symbol(symbol=symbol)
                    d['max_shares'] = session.value
                    var.save_config()
                    await update.message.reply_text(
                        f'改动完成',
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
                return self.K_MS_CONFIRM

    @classmethod
    def handler(cls):
        o = cls()
        handler = ConversationHandler(
            entry_points=[CommandHandler('maxShares', o.max_shares_start)],
            states={
                o.K_MS_SELECT: [MessageHandler(Regex(r'^(\d+)$'), o.max_shares_select)],
                o.K_MS_INPUT: [MessageHandler(Regex(r'^(\d+)$'), o.max_shares_input)],
                o.K_MS_CONFIRM: [
                    CommandHandler('confirm', o.max_shares_confirm),
                ],
            },
            fallbacks=[o.cancel_handler()],
        )
        return handler


__all__ = ['MaxShares']
