from hodl.plan_calc import ProfitRow
from hodl.state import *
from hodl.bot import *
from hodl.store_base import *
from hodl.store_hodl import *
from hodl.thread_mixin import *
from hodl.tools import *


@bot_cmd(
    command='report',
    menu_desc='持仓的执行计划',
    trade_strategy=TradeStrategyEnum.HODL
)
class Report(SimpleTelegramConversation):
    SELECT_TEXT = '此命令可以查看持仓的买卖计划。 '

    async def confirm(self, update, context, position: TgSelectedPosition):
        store_config = position.config

        broker = position.config.broker
        region = position.config.region
        symbol = position.symbol
        store: StoreBase = ThreadMixin.find_by_tags(tags=('Store', broker, region, symbol,))

        with store.thread_lock():
            state = store.state
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
                await self.reply_text(
                    update,
                    '\n'.join(lines),
                )
                return self.K_SIMPLE_END
        await self.reply_text(
            update,
            '该持仓目前没有任何执行计划。'
        )
        return self.K_SIMPLE_END

    @classmethod
    def build_table(cls, store_config: StoreConfig, plan: Plan):
        return StoreHodl.build_table(store_config=store_config, plan=plan)


__all__ = ['Report']
