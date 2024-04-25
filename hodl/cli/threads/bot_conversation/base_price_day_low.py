from telegram import ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler
from telegram.ext.filters import Regex
from hodl.bot import TelegramBotBase
from hodl.tools import *


class BasePriceDayLow(TelegramBotBase):
    K_BPDL_SELECT = 0
    K_BPDL_DECISION = 1
    K_BPDL_CONFIRM = 2

    async def bpdl_start(self, update, context):
        lines = self._symbol_lines()
        idx_list = self._symbol_choice()
        await update.message.reply_text(
            f'你正在尝试设置修改[基准价格-日低](basePriceDayLow)的设定，指定持仓未有任何买卖单时会有效执行。 '
            f'[开启]时，[基准价格]可以参考[当日最低价]取最小的; [关闭]时，[基准价格]不考虑[当日最低价]。'
            f'选择需要操作的标的序号\n'
            f'{lines}\n\n流程的任意阶段都可以使用 /cancel 取消',
            reply_markup=ReplyKeyboardMarkup(
                idx_list, one_time_keyboard=True, input_field_placeholder='选择持仓标的序号'
            ),
        )
        return self.K_BPDL_SELECT

    async def bpdl_select(self, update, context):
        idx = int(update.message.text) - 1
        position = self._symbol_list()[idx]
        user_id = update.message.from_user.id
        self._create_session(user_id=user_id, position=position)
        await update.message.reply_text(
            f'选择了 {position.display} 操作[基准价格-日低]项目的修改。'
            f'当前状态为 {"[开启]" if position.config.base_price_day_low else "[关闭]"}。你可以选择命令 /on 或者 /off 修改状态',
            reply_markup=ReplyKeyboardRemove(),
        )
        return self.K_BPDL_DECISION

    async def bpdl_decision(self, update, context):
        text = update.message.text
        user_id = update.message.from_user.id
        session = self._get_session(user_id=user_id)
        match text:
            case '/on':
                value = True
            case '/off':
                value = False
            case _:
                await update.message.reply_text(
                    f'非法选择，请重新选择命令',
                    reply_markup=ReplyKeyboardRemove(),
                )
                return self.K_BPDL_DECISION
        session.value = value
        new_icon = "[开启]" if value else "[关闭]"
        await update.message.reply_text(
            f'确认针对{session.position.display}的[基准价格-日低]改动为{new_icon}? 使用命令 /confirm 来确认',
            reply_markup=ReplyKeyboardRemove(),
        )
        return self.K_BPDL_CONFIRM

    async def bpdl_confirm(self, update, context):
        text = update.message.text
        user_id = update.message.from_user.id
        session = self._get_session(user_id=user_id)
        match text:
            case '/confirm':
                await update.message.reply_text(
                    f'已经确认改动{session.position.display}的[基准价格-日低]',
                    reply_markup=ReplyKeyboardRemove(),
                )
                try:
                    symbol = session.position.symbol
                    var = VariableTools()
                    d = var.find_by_symbol(symbol=symbol)
                    d['base_price_day_low'] = session.value
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
                return self.K_BPDL_CONFIRM

    @classmethod
    def handler(cls):
        o = cls()
        handler = ConversationHandler(
            entry_points=[CommandHandler('basePriceDayLow', o.bpdl_start)],
            states={
                o.K_BPDL_SELECT: [MessageHandler(Regex(r'^(\d+)$'), o.bpdl_select)],
                o.K_BPDL_DECISION: [
                    CommandHandler('on', o.bpdl_decision),
                    CommandHandler('off', o.bpdl_decision),
                ],
                o.K_BPDL_CONFIRM: [
                    CommandHandler('confirm', o.bpdl_confirm),
                ],
            },
            fallbacks=[o.cancel_handler()],
            conversation_timeout=60.0,
            block=False,
        )
        return handler


__all__ = ['BasePriceDayLow']
