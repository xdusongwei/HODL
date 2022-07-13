from telegram import ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler, Filters
from hodl.bot import TelegramBotBase
from hodl.tools import *


class LockPosition(TelegramBotBase):
    K_LP_SELECT = 0
    K_LP_DECISION = 1
    K_LP_CONFIRM = 2

    def lock_position_start(self, update, context):
        lines = self._symbol_lines()
        idx_list = self._symbol_choice()
        update.message.reply_text(
            f'你正在尝试设置修改[锁定持仓](lockPosition)的设定。 '
            f'[锁定]时，下单前会严格核对当前持仓量是否与[maxShares]一致，[解锁]时，允许当前持仓量是否大于或等于[maxShares]。'
            f'选择需要操作的标的序号\n'
            f'{lines}\n\n流程的任意阶段都可以使用 /cancel 取消',
            reply_markup=ReplyKeyboardMarkup(
                idx_list, one_time_keyboard=True, input_field_placeholder='选择持仓标的序号'
            ),
        )
        return self.K_LP_SELECT

    def lock_position_select(self, update, context):
        idx = int(update.message.text) - 1
        position = self._symbol_list()[idx]
        user_id = update.message.from_user.id
        self._create_session(user_id=user_id, position=position)
        update.message.reply_text(
            f'选择了 {position.display} 操作[锁定持仓]项目的修改。'
            f'当前状态为 {"[锁定]" if position.config.lock_position else "[解锁]"}。你可以选择命令 /lock 或者 /unlock 修改状态',
            reply_markup=ReplyKeyboardRemove(),
        )
        return self.K_LP_DECISION

    def lock_position_decision(self, update, context):
        text = update.message.text
        user_id = update.message.from_user.id
        session = self._get_session(user_id=user_id)
        match text:
            case '/lock':
                value = True
            case '/unlock':
                value = False
            case _:
                update.message.reply_text(
                    f'非法选择，请重新选择命令',
                    reply_markup=ReplyKeyboardRemove(),
                )
                return self.K_LP_DECISION
        session.value = value
        new_icon = "[锁定]" if value else "[解锁]"
        update.message.reply_text(
            f'确认针对{session.position.display}的[锁定持仓]改动为{new_icon}? 使用命令 /confirm 来确认',
            reply_markup=ReplyKeyboardRemove(),
        )
        return self.K_LP_CONFIRM

    def lock_position_confirm(self, update, context):
        text = update.message.text
        user_id = update.message.from_user.id
        session = self._get_session(user_id=user_id)
        match text:
            case '/confirm':
                update.message.reply_text(
                    f'已经确认改动{session.position.display}的[锁定持仓]',
                    reply_markup=ReplyKeyboardRemove(),
                )
                try:
                    symbol = session.position.symbol
                    var = VariableTools()
                    d = var.find_by_symbol(symbol=symbol)
                    d['lock_position'] = session.value
                    var.save_config()
                    update.message.reply_text(
                        f'改动完成',
                        reply_markup=ReplyKeyboardRemove(),
                    )
                except Exception as e:
                    update.message.reply_text(
                        f'改动失败:{e}',
                        reply_markup=ReplyKeyboardRemove(),
                    )
                finally:
                    self._clear_session(user_id=user_id)

                return ConversationHandler.END
            case _:
                update.message.reply_text(
                    f'非法选择，请重新选择命令',
                    reply_markup=ReplyKeyboardRemove(),
                )
                return self.K_LP_CONFIRM

    @classmethod
    def handler(cls):
        o = cls()
        handler = ConversationHandler(
            entry_points=[CommandHandler('lockPosition', o.lock_position_start)],
            states={
                o.K_LP_SELECT: [MessageHandler(Filters.regex(r'^(\d+)$'), o.lock_position_select)],
                o.K_LP_DECISION: [
                    CommandHandler('lock', o.lock_position_decision),
                    CommandHandler('unlock', o.lock_position_decision),
                ],
                o.K_LP_CONFIRM: [
                    CommandHandler('confirm', o.lock_position_confirm),
                ],
            },
            fallbacks=[o.cancel_handler()],
        )
        return handler


__all__ = ['LockPosition']
