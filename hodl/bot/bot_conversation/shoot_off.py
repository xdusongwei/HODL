from telegram import ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler, Filters
from hodl.bot import TelegramBotBase
from hodl.tools import *


class ShootOff(TelegramBotBase):
    K_SO_SELECT = 0
    K_SO_DECISION = 1
    K_SO_CONFIRM = 2

    def shoot_off_start(self, update, context):
        lines = self._symbol_lines()
        idx_list = self._symbol_choice()
        update.message.reply_text(
            f'你正在尝试使持仓进入[弹射]模式，指定持仓将按照当前档位卖价卖出剩余股票，并根据当前的档位买价买回全部股票。 '
            f'选择需要操作的标的序号\n'
            f'{lines}\n\n流程的任意阶段都可以使用 /cancel 取消',
            reply_markup=ReplyKeyboardMarkup(
                idx_list, one_time_keyboard=True, input_field_placeholder='选择持仓标的序号'
            ),
        )
        return self.K_SO_SELECT

    def shoot_off_select(self, update, context):
        idx = int(update.message.text) - 1
        position = self._symbol_list()[idx]
        user_id = update.message.from_user.id
        self._create_session(user_id=user_id, position=position)
        update.message.reply_text(
            f'选择了 {position.display} 进入[弹射]模式。'
            f'你可以选择命令 /next 进一步确认',
            reply_markup=ReplyKeyboardRemove(),
        )
        return self.K_SO_DECISION

    def shoot_off_decision(self, update, context):
        text = update.message.text
        user_id = update.message.from_user.id
        session = self._get_session(user_id=user_id)
        match text:
            case '/next':

                value = True
            case _:
                update.message.reply_text(
                    f'非法选择，请重新选择命令',
                    reply_markup=ReplyKeyboardRemove(),
                )
                return self.K_SO_DECISION
        session.value = value
        new_icon = "[开启]" if value else "[关闭]"
        update.message.reply_text(
            f'确认针对{session.position.display}的[惜售]改动为{new_icon}? 使用命令 /confirm 来确认',
            reply_markup=ReplyKeyboardRemove(),
        )
        return self.K_SO_CONFIRM

    def shoot_off_confirm(self, update, context):
        text = update.message.text
        user_id = update.message.from_user.id
        session = self._get_session(user_id=user_id)
        match text:
            case '/confirm':
                update.message.reply_text(
                    f'已经确认改动{session.position.display}的[惜售]',
                    reply_markup=ReplyKeyboardRemove(),
                )
                try:
                    symbol = session.position.symbol
                    var = VariableTools()
                    d = var.find_by_symbol(symbol=symbol)
                    d['prudent'] = session.value
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
                return self.K_SO_CONFIRM

    @classmethod
    def handler(cls):
        o = cls()
        handler = ConversationHandler(
            entry_points=[CommandHandler('shootOff', o.shoot_off_start)],
            states={
                o.K_SO_SELECT: [MessageHandler(Filters.regex(r'^(\d+)$'), o.shoot_off_select)],
                o.K_SO_DECISION: [
                    CommandHandler('next', o.shoot_off_decision),
                ],
                o.K_SO_CONFIRM: [
                    CommandHandler('confirm', o.shoot_off_confirm),
                ],
            },
            fallbacks=[o.cancel_handler()],
        )
        return handler


__all__ = ['ShootOff']
