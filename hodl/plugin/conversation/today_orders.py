from hodl.bot import *
from hodl.storage import *
from hodl.tools import *


@bot_cmd(
    command='todayorders',
    menu_desc='24小时订单',
    db_function=True,
)
class TodayOrders(SimpleTelegramConversation):
    async def select(self, update, context):
        timestamp = int(TimeTools.us_time_now().timestamp()) - 24 * 60 * 60
        result = '没有配置数据库可用于查询'
        if db := self.db:
            orders = OrderRow.items_after_create_time(con=db.conn, create_time=timestamp)
            if orders:
                result = '近24小时订单如下:\n'
                for order_row in orders:
                    result += f'{order_row.summary()}\n'
            else:
                result = '近24小时没有订单'
        await self.reply_text(update, result)
        return self.K_SIMPLE_END


__all__ = ['TodayOrders']
