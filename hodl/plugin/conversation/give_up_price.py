from hodl.bot import *
from hodl.state import *
from hodl.tools import *
from hodl.thread_mixin import *


@bot_cmd(
    command='giveupprice',
    menu_desc='设置[放弃价格]',
    trade_strategy=TradeStrategyEnum.HODL,
    db_function=True,
)
class GiveUpPrice(SingleInputConversation):
    SELECT_TEXT = '你正在尝试设置修改[放弃价格]的设定。 '
    INPUT_REGEX = r'^(\d+\.\d+)$'

    async def input(self, update, context, position: TgSelectedPosition):
        await self.reply_text(
            update,
            f'选择了 {position.display} 操作[放弃价格]项目的修改。'
            f'请输入价格，格式要求必须带有小数部分，例如: 3.0。输入0.0代表清除该项目设定。',
        )

    async def confirm(self, update, context, position: TgSelectedPosition) -> int:
        text = update.message.text
        price = float(text)
        if price <= 0:
            price = None
        session = self.get_session(update)
        session.value = price
        price_text = FormatTool.pretty_price(price, config=session.position.config)
        await self.reply_text(
            update,
            f'确认针对{session.position.display}的[放弃价格]改动为{price_text}? 使用命令 /confirm 来确认',
        )
        return self.K_SIC_EXECUTE

    async def execute(self, update, context, position: TgSelectedPosition):
        await self.reply_text(
            update,
            f'已经确认改动{position.display}的[放弃价格]',
        )
        session = self.get_session(update)
        try:
            cfg = position.config
            state_path = cfg.state_file_path
            if not state_path:
                raise ValueError(f'不存在持仓状态文件位置')

            broker = cfg.broker
            region = cfg.region
            symbol = cfg.symbol
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
                cog = plan.cog(precision=cfg.precision)
                if cog is None:
                    raise ValueError(f'没有持仓卖出质点价格')
                if cfg.buy_spread is not None:
                    if v >= cog - cfg.buy_spread:
                        raise ValueError(f'设定价格{v}高于质点价格{cog}')
                if cfg.buy_spread_rate is not None:
                    if v >= cog * (1.0 - cfg.buy_spread_rate):
                        raise ValueError(f'设定价格{v}高于质点价格{cog}')

                plan.give_up_price = v
            else:
                plan.give_up_price = None
            text = FormatTool.json_dumps(state)
            with open(state_path, mode='w', encoding='utf8') as f:
                f.write(text)
            await self.reply_text(
                update,
                f'改动完成，[放弃价格]设定为{plan.give_up_price}',
            )
        except Exception as e:
            await self.reply_text(
                update,
                f'改动失败:{e}',
            )


__all__ = ['GiveUpPrice']
