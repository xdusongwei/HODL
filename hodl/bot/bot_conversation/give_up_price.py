from telegram import ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler
from telegram.ext.filters import Regex
from hodl.bot import TelegramBotBase
from hodl.state import *
from hodl.tools import *
from hodl.thread_mixin import ThreadMixin


class GiveUpPrice(TelegramBotBase):
    K_GUP_SELECT = 0
    K_GUP_INPUT = 1
    K_GUP_CONFIRM = 2

    async def give_up_price_start(self, update, context):
        lines = self._symbol_lines()
        idx_list = self._symbol_choice()
        if self.DB:
            await update.message.reply_text(
                f'你正在尝试设置修改[放弃价格]的设定。 '
                f'选择需要操作的标的序号\n'
                f'{lines}\n\n流程的任意阶段都可以使用 /cancel 取消',
                reply_markup=ReplyKeyboardMarkup(
                    idx_list, one_time_keyboard=True, input_field_placeholder='选择持仓标的序号'
                ),
            )
            return self.K_GUP_SELECT
        else:
            await update.message.reply_text(
                '没有设置数据库，不能设置此项。', reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END

    async def give_up_price_select(self, update, context):
        idx = int(update.message.text) - 1
        position = self._symbol_list()[idx]
        user_id = update.message.from_user.id
        self._create_session(user_id=user_id, position=position)
        await update.message.reply_text(
            f'选择了 {position.display} 操作[放弃价格]项目的修改。'
            f'请输入价格，格式要求必须带有小数部分，例如: 3.0。输入0.0代表清除该项目设定。',
            reply_markup=ReplyKeyboardRemove(),
        )
        return self.K_GUP_INPUT

    async def give_up_price_input(self, update, context):
        text = update.message.text
        price = float(text)
        if price <= 0:
            price = None
        user_id = update.message.from_user.id
        session = self._get_session(user_id=user_id)
        session.value = price
        price_text = FormatTool.pretty_price(price, config=session.position.config)
        await update.message.reply_text(
            f'确认针对{session.position.display}的[放弃价格]改动为{price_text}? 使用命令 /confirm 来确认',
            reply_markup=ReplyKeyboardRemove(),
        )
        return self.K_GUP_CONFIRM

    @classmethod
    async def give_up_price_confirm(cls, update, context):
        text = update.message.text
        user_id = update.message.from_user.id
        session = cls._get_session(user_id=user_id)
        match text:
            case '/confirm':
                await update.message.reply_text(
                    f'已经确认改动{session.position.display}的[放弃价格]',
                    reply_markup=ReplyKeyboardRemove(),
                )
                try:
                    state_path = session.position.config.state_file_path
                    if not state_path:
                        raise ValueError(f'不存在持仓状态文件位置')

                    broker = session.position.config.broker
                    region = session.position.config.region
                    symbol = session.position.symbol
                    store = ThreadMixin.find_by_tags(tags=('Store', broker, region, symbol,))
                    thread = store.current_thread
                    if not thread:
                        raise ValueError(f'找不到持仓对应的线程')

                    with open(state_path, mode='r', encoding='utf8') as f:
                        text = f.read()
                        state = FormatTool.json_loads(text)
                    state = State(state)
                    plan = state.plan
                    if v := session.value:
                        cog = plan.cog(precision=session.position.config.precision)
                        if cog is None:
                            raise ValueError(f'没有持仓卖出质点价格')
                        if v >= cog - session.position.config.buy_spread:
                            raise ValueError(f'设定价格{v}高于质点价格{cog}')
                        plan.give_up_price = v
                    else:
                        plan.give_up_price = None
                    text = FormatTool.json_dumps(state)
                    with open(state_path, mode='w', encoding='utf8') as f:
                        f.write(text)
                    await update.message.reply_text(
                        f'改动完成，[放弃价格]设定为{plan.give_up_price}',
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
                return cls.K_GUP_CONFIRM

    @classmethod
    def handler(cls):
        o = cls()
        handler = ConversationHandler(
            entry_points=[CommandHandler('giveUpPrice', o.give_up_price_start)],
            states={
                o.K_GUP_SELECT: [MessageHandler(Regex(r'^(\d+)$'), o.give_up_price_select)],
                o.K_GUP_INPUT: [MessageHandler(Regex(r'^(\d+\.\d+)$'), o.give_up_price_input)],
                o.K_GUP_CONFIRM: [
                    CommandHandler('confirm', o.give_up_price_confirm),
                ],
            },
            fallbacks=[o.cancel_handler()],
        )
        return handler


__all__ = ['GiveUpPrice']
