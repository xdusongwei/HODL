from telegram import ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler
from telegram.ext.filters import Regex
from hodl.storage import TempBasePriceRow
from hodl.bot import TelegramBotBase
from hodl.tools import *


class TempBasePrice(TelegramBotBase):
    K_TBP_SELECT = 0
    K_TBP_INPUT = 1
    K_TBP_CONFIRM = 2

    async def temp_base_price_start(self, update, context):
        lines = self._symbol_lines()
        idx_list = self._symbol_choice()
        if self.DB:
            await update.message.reply_text(
                f'你正在尝试设置修改[临时基准价]的设定，指定持仓未有任何买卖单时会有效执行, 设置后有效作用时间为5分钟。 '
                f'选择需要操作的标的序号\n'
                f'{lines}\n\n流程的任意阶段都可以使用 /cancel 取消',
                reply_markup=ReplyKeyboardMarkup(
                    idx_list, one_time_keyboard=True, input_field_placeholder='选择持仓标的序号'
                ),
            )
            return self.K_TBP_SELECT
        else:
            await update.message.reply_text(
                '没有设置数据库，不能设置此项。', reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END

    async def temp_base_price_select(self, update, context):
        idx = int(update.message.text) - 1
        position = self._symbol_list()[idx]
        user_id = update.message.from_user.id
        self._create_session(user_id=user_id, position=position)
        base_price_row = TempBasePriceRow.query_by_symbol(con=self.DB.conn, symbol=position.symbol)
        current_price = '当前没有有效值。'
        if base_price_row and base_price_row.price > 0:
            price = base_price_row.price
            current_price = f'当前设置价格为: {FormatTool.pretty_price(price, config=position.config)}。'
        await update.message.reply_text(
            f'选择了 {position.display} 操作[临时基准价]项目的修改。'
            f'{current_price}'
            f'请输入价格，格式要求必须带有小数部分，例如: 3.0。',
            reply_markup=ReplyKeyboardRemove(),
        )
        return self.K_TBP_INPUT

    async def temp_base_price_input(self, update, context):
        text = update.message.text
        price = float(text)
        if price > 0:
            user_id = update.message.from_user.id
            session = self._get_session(user_id=user_id)
            session.value = price
            price_text = FormatTool.pretty_price(price, config=session.position.config)
            await update.message.reply_text(
                f'确认针对{session.position.display}的[临时基准价]改动为{price_text}? 使用命令 /confirm 来确认',
                reply_markup=ReplyKeyboardRemove(),
            )
            return self.K_TBP_CONFIRM
        else:
            await update.message.reply_text(
                f'请重新输入价格，格式要求必须带有小数部分，例如: 3.0。',
                reply_markup=ReplyKeyboardRemove(),
            )
            return self.K_TBP_INPUT

    async def temp_base_price_confirm(cls, update, context):
        text = update.message.text
        user_id = update.message.from_user.id
        session = cls._get_session(user_id=user_id)
        match text:
            case '/confirm':
                await update.message.reply_text(
                    f'已经确认改动{session.position.display}的[临时基准价]',
                    reply_markup=ReplyKeyboardRemove(),
                )
                try:
                    symbol = session.position.symbol
                    ts = int(TimeTools.us_time_now().timestamp())
                    row = TempBasePriceRow(
                        symbol=symbol,
                        price=session.value,
                        expiry_time=ts + 300,
                        update_time=ts,
                    )
                    row.save(con=cls.DB.conn)
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
                    cls._clear_session(user_id=user_id)

                return ConversationHandler.END
            case _:
                await update.message.reply_text(
                    f'非法选择，请重新选择命令',
                    reply_markup=ReplyKeyboardRemove(),
                )
                return cls.K_TBP_CONFIRM

    @classmethod
    def handler(cls):
        o = cls()
        handler = ConversationHandler(
            entry_points=[CommandHandler('tempBasePrice', o.temp_base_price_start)],
            states={
                o.K_TBP_SELECT: [MessageHandler(Regex(r'^(\d+)$'), o.temp_base_price_select)],
                o.K_TBP_INPUT: [MessageHandler(Regex(r'^(\d+\.\d+)$'), o.temp_base_price_input)],
                o.K_TBP_CONFIRM: [
                    CommandHandler('confirm', o.temp_base_price_confirm),
                ],
            },
            fallbacks=[o.cancel_handler()],
            conversation_timeout=60.0,
            block=False,
        )
        return handler


__all__ = ['TempBasePrice']
