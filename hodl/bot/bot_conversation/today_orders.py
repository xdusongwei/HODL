from telegram.ext import CommandHandler
from hodl.bot import TelegramBotBase
from hodl.storage import OrderRow
from hodl.tools import *


class TodayOrders(TelegramBotBase):
    async def today_orders(self, update, context):
        timestamp = int(TimeTools.us_time_now().timestamp()) - 24 * 60 * 60
        result = '没有数据库用于查询'
        if db := self.db:
            orders = OrderRow.items_after_create_time(con=db.conn, create_time=timestamp)
            if orders:
                result = '近24小时订单如下:\n'
                for order_row in orders:
                    result += f'{order_row.summary()}\n'
            else:
                result = '近24小时没有订单'
        await update.message.reply_text(result)

    @classmethod
    def handler(cls):
        o = cls()
        handler = CommandHandler("todayOrders", o.today_orders)
        return handler


__all__ = ['TodayOrders']
