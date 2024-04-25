from telegram.ext import CommandHandler
from hodl.bot import TelegramBotBase
from hodl.storage import EarningRow, TempBasePriceRow
from hodl.tools import FormatTool


class Settings(TelegramBotBase):
    async def settings(self, update, context):
        text = ''
        for item in self._symbol_list():
            last_buyback_price = ''
            temp_base_price = ''
            if db := self.DB:
                days = item.config.base_price_last_buy_days
                row = EarningRow.latest_earning_by_symbol(con=db.conn, symbol=item.symbol, days=days)
                if row and row.buyback_price:
                    last_buyback_price = FormatTool.pretty_price(row.buyback_price, config=item.config)
                row = TempBasePriceRow.query_by_symbol(con=db.conn, symbol=item.symbol)
                if row and row.price:
                    temp_base_price = FormatTool.pretty_price(row.price, config=item.config)
            part = \
                f'{item.display}:\n' \
                f'使能: {item.enable}\n' \
                f'锁定持仓: {item.lock_position}\n' \
                f'基准价格买回: {item.base_price_last_buy}\n' \
                f'基准价格日低: {item.base_price_day_low}\n' \
                f'登记股数: {item.max_shares}\n' \
                f'上次买回价格: {last_buyback_price if last_buyback_price else "无"}\n' \
                f'临时基准价格: {temp_base_price if temp_base_price else "无"}\n'
            text += part
        await update.message.reply_text(text)

    @classmethod
    def handler(cls):
        o = cls()
        handler = CommandHandler("settings", o.settings, block=False)
        return handler


__all__ = ['Settings']
