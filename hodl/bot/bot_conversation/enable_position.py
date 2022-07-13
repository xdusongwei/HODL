from telegram import ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler, Filters
from hodl.bot import TelegramBotBase
from hodl.tools import *


class EnablePosition(TelegramBotBase):
    K_EN_SELECT = 0
    K_EN_DECISION = 1
    K_EN_CONFIRM = 2

    def enable_start(self, update, context):
        lines = self._symbol_lines()
        idx_list = self._symbol_choice()
        update.message.reply_text(
            f'你正在尝试设置修改[使能](enable)的设定。 '
            f'[开启]时，正常交易时段可以执行下单逻辑，[关闭]时，正常交易时段不允许执行下单逻辑。'
            f'开启前，仔细确认[基准价格宽松]，[锁定持仓]以及[登记股数]是否会影响到期望的设定。'
            f'选择需要操作的标的序号\n'
            f'{lines}\n\n流程的任意阶段都可以使用 /cancel 取消',
            reply_markup=ReplyKeyboardMarkup(
                idx_list, one_time_keyboard=True, input_field_placeholder='选择持仓标的序号'
            ),
        )
        return self.K_EN_SELECT

    def enable_select(self, update, context):
        idx = int(update.message.text) - 1
        position = self._symbol_list()[idx]
        user_id = update.message.from_user.id
        self._create_session(user_id=user_id, position=position)
        update.message.reply_text(
            f'选择了 {position.display} 操作[使能]项目的修改。'
            f'当前状态为 {"[开启]" if position.config.enable else "[关闭]"}。你可以选择命令 /on 或者 /off 修改状态',
            reply_markup=ReplyKeyboardRemove(),
        )
        return self.K_EN_DECISION

    def enable_decision(self, update, context):
        text = update.message.text
        user_id = update.message.from_user.id
        session = self._get_session(user_id=user_id)
        match text:
            case '/on':
                value = True
            case '/off':
                value = False
            case _:
                update.message.reply_text(
                    f'非法选择，请重新选择命令',
                    reply_markup=ReplyKeyboardRemove(),
                )
                return self.K_EN_DECISION
        session.value = value
        new_icon = "[开启]" if value else "[关闭]"
        update.message.reply_text(
            f'确认针对{session.position.display}的[使能]改动为{new_icon}? 使用命令 /confirm 来确认',
            reply_markup=ReplyKeyboardRemove(),
        )
        return self.K_EN_CONFIRM

    def enable_confirm(self, update, context):
        text = update.message.text
        user_id = update.message.from_user.id
        session = self._get_session(user_id=user_id)
        match text:
            case '/confirm':
                update.message.reply_text(
                    f'已经确认改动{session.position.display}的[使能]',
                    reply_markup=ReplyKeyboardRemove(),
                )
                try:
                    symbol = session.position.symbol
                    var = VariableTools()
                    d = var.find_by_symbol(symbol=symbol)
                    d['enable'] = session.value
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
                return self.K_EN_CONFIRM

    @classmethod
    def handler(cls):
        o = cls()
        handler = ConversationHandler(
            entry_points=[CommandHandler('enable', o.enable_start)],
            states={
                o.K_EN_SELECT: [MessageHandler(Filters.regex(r'^(\d+)$'), o.enable_select)],
                o.K_EN_DECISION: [
                    CommandHandler('on', o.enable_decision),
                    CommandHandler('off', o.enable_decision),
                ],
                o.K_EN_CONFIRM: [
                    CommandHandler('confirm', o.enable_confirm),
                ],
            },
            fallbacks=[o.cancel_handler()],
        )
        return handler


__all__ = ['EnablePosition']
