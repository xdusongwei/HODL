from telegram.ext import CommandHandler
from hodl.bot import TelegramBotBase
from hodl.storage import EarningRow
from hodl.tools import FormatTool


class MonthlyEarning(TelegramBotBase):
    def monthly_earning(self, update, context):
        result = '没有数据库用于查询'
        if db := self.db:
            result = ''
            items = EarningRow.total_earning_group_by_month(con=db.conn, month=7)
            items.sort(key=lambda i: (i.currency, i.month, ), reverse=True)
            for item in items:
                month = f'{str(item.month)[:-2]}-{str(item.month)[-2:]}'
                amount = FormatTool.pretty_usd(item.total, currency=item.currency, only_int=True)
                result += f'[{item.currency}]{month}: {amount}\n'
            result += '------------------\n'
            for currency in set([item.currency for item in items]):
                currency_items = [item for item in items if item.currency == currency]
                month_count = len(currency_items)
                total = sum([item.total for item in currency_items])
                forcast = int(total / month_count * 12) // 1000 * 1000
                amount = FormatTool.pretty_usd(forcast, currency=currency, only_int=True)
                result += f'[{currency}]预测12个月总收入{amount}\n'
        update.message.reply_text(result)

    @classmethod
    def handler(cls):
        o = cls()
        handler = CommandHandler("monthlyEarning", o.monthly_earning)
        return handler


__all__ = ['MonthlyEarning']
