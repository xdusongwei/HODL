from hodl.storage import *
from hodl.bot import *
from hodl.tools import *


@bot_cmd(
    command='tempbaseprice',
    menu_desc='设置[临时基准价格]',
    trade_strategy=TradeStrategyEnum.HODL,
    db_function=True,
)
class TempBasePrice(SingleInputConversation):
    SELECT_TEXT = '你正在尝试设置修改[临时基准价]的设定，指定持仓未有任何买卖单时会有效执行, 设置后有效作用时间为5分钟。 '
    INPUT_REGEX = r'^(\d+\.\d+)$'

    async def input(self, update, context, position: TgSelectedPosition):
        base_price_row = TempBasePriceRow.query_by_symbol(
            con=self.DB.conn,
            broker=position.config.broker,
            symbol=position.symbol,
        )
        current_price = '当前没有有效值。'
        if base_price_row and base_price_row.price > 0:
            price = base_price_row.price
            current_price = f'当前设置价格为: {FormatTool.pretty_price(price, config=position.config)}。'
        await self.reply_text(
            update,
            f'选择了 {position.display} 操作[临时基准价]项目的修改。'
            f'{current_price}'
            f'请输入价格，格式要求必须带有小数部分，例如: 3.0。',
        )

    async def confirm(self, update, context, position: TgSelectedPosition) -> int:
        text = update.message.text
        price = float(text)
        if price > 0:
            session = self.get_session(update)
            session.value = price
            price_text = FormatTool.pretty_price(price, config=session.position.config)
            await self.reply_text(
                update,
                f'确认针对{session.position.display}的[临时基准价]改动为{price_text}? 使用命令 /confirm 来确认',
            )
            return self.K_SIC_EXECUTE
        else:
            await self.reply_text(
                update,
                f'请重新输入价格，格式要求必须带有小数部分，例如: 3.0。',
            )
            return self.K_SIC_CONFIRM

    async def execute(self, update, context, position: TgSelectedPosition):
        await self.reply_text(
            update,
            f'已经确认改动{position.display}的[临时基准价]',
        )
        session = self.get_session(update)
        try:
            symbol = position.symbol
            ts = int(TimeTools.us_time_now().timestamp())
            row = TempBasePriceRow(
                broker=position.config.broker,
                symbol=symbol,
                price=session.value,
                expiry_time=ts + 300,
                update_time=ts,
            )
            row.save(con=self.DB.conn)
            await self.reply_text(
                update,
                f'改动完成',
            )
        except Exception as e:
            await self.reply_text(
                update,
                f'改动失败:{e}',
            )


__all__ = ['TempBasePrice']
