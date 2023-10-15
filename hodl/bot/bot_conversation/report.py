from telegram import ReplyKeyboardRemove, ReplyKeyboardMarkup, Update
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler
from telegram.ext.filters import Regex
from hodl.plan_calc import ProfitRow
from hodl.state import *
from hodl.storage import StateRow
from hodl.bot import *
from hodl.store_base import StoreBase
from hodl.tools import *


class Report(TelegramBotBase):
    K_RP_SELECT = 0

    async def report_start(self, update: Update, context):
        lines = self._symbol_lines()
        idx_list = self._symbol_choice()
        if self.DB:
            await update.message.reply_text(
                f'此命令可以查看持仓的买卖计划。 '
                f'选择需要操作的标的序号\n'
                f'{lines}\n\n流程的任意阶段都可以使用 /cancel 取消',
                reply_markup=ReplyKeyboardMarkup(
                    idx_list, one_time_keyboard=True, input_field_placeholder='选择持仓标的序号'
                ),
            )
            return self.K_RP_SELECT
        else:
            await update.message.reply_text(
                '没有设置数据库，不能查看此项。', reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END

    async def report_select(self, update: Update, context):
        idx = int(update.message.text) - 1
        position = self._symbol_list()[idx]
        store_config = position.config

        row = StateRow.query_by_symbol_latest(con=self.DB.conn, symbol=position.symbol)
        if row and row.content:
            d = FormatTool.json_loads(row.content)
            state = State(d)
            plan = state.plan
            if plan.table_ready:
                base_value = (plan.total_chips or 0) * (plan.base_price or 0.0)
                max_level = plan.current_sell_level_filled()
                bp_text = FormatTool.pretty_price(plan.base_price, config=store_config)
                profit_table = self.build_table(store_config=store_config, plan=plan)
                lines = list()
                lines.append(f'基准价格: {bp_text}')
                lines.append(f'全部卖出价格:')
                for idx, table_row in enumerate(profit_table):
                    level = idx + 1
                    table_row: ProfitRow = table_row
                    sell_at = FormatTool.pretty_price(table_row.sell_at, config=store_config)
                    qty = FormatTool.pretty_number(table_row.shares)
                    hit = '[√]' if max_level >= level else '[-]'
                    lines.append(f'{hit}{level} {sell_at} 股数: {qty}')
                lines.append(f'全部买回价格:')
                for idx, table_row in enumerate(profit_table):
                    level = idx + 1
                    table_row: ProfitRow = table_row
                    earning_forecast = base_value * (table_row.total_rate - 1)
                    earning_forecast = FormatTool.pretty_usd(
                        earning_forecast,
                        only_int=True,
                        currency=store_config.currency,
                    )
                    buy_at = FormatTool.pretty_price(table_row.buy_at, config=store_config)
                    rate = -round(table_row.total_rate * 100 - 100, 2)
                    hit = '[当前]' if max_level == level else ''
                    lines.append(f'{hit}{idx + 1} {buy_at}: {rate:+.2f}%(+{earning_forecast})')
                await update.message.reply_text(
                    '\n'.join(lines), reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
        await update.message.reply_text(
            '该持仓目前没有任何执行计划。', reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    @classmethod
    def handler(cls):
        o = cls()
        handler = ConversationHandler(
            entry_points=[CommandHandler('report', o.report_start)],
            states={
                o.K_RP_SELECT: [MessageHandler(Regex(r'^(\d+)$'), o.report_select)],
            },
            fallbacks=[o.cancel_handler()],
        )
        return handler

    @classmethod
    def build_table(cls, store_config: StoreConfig, plan: Plan):
        return StoreBase.build_table(store_config=store_config, plan=plan)


__all__ = ['Report']
