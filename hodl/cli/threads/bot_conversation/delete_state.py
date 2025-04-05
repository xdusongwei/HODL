import os
from hodl.bot import *
from hodl.thread_mixin import *
from hodl.tools import *


@bot_cmd(
    command='deleteState',
    menu_desc='清除[持仓状态]',
    trade_strategy=TradeStrategyEnum.HODL,
)
class DeleteState(SimpleTelegramConversation):
    SELECT_TEXT = '你正在尝试[清除持仓状态]。警告，只用此功能前确认目标持仓没有任何订单记录，或者，目标持仓是已套利的状态。 '

    async def confirm(self, update, context, position: TgSelectedPosition):
        if position.config.trade_strategy != TradeStrategyEnum.HODL:
            await self.reply_text(
                update,
                f'该持仓不是”长期持有套利(HODL)“交易策略，无法[清除持仓状态]。',
            )
            return self.K_SIMPLE_END
        elif path := position.config.state_file_path:
            await self.reply_text(
                update,
                f'确认针对{position.display}执行[清除持仓状态]? 状态文件在:{path}。 使用命令 /confirm 来确认',
            )
            return self.K_SIMPLE_EXECUTE
        else:
            await self.reply_text(
                update,
                f'该持仓不存储状态数据的位置，无法[清除持仓状态]。',
            )
            return self.K_SIMPLE_END

    async def execute(self, update, context, position: TgSelectedPosition):
        await self.reply_text(
            update,
            f'已经确认对{position.display}执行[清除持仓状态]',
        )
        try:
            broker = position.config.broker
            region = position.config.region
            symbol = position.symbol
            thread = ThreadMixin.find_by_tags(tags=('Store', broker, region, symbol,))
            if thread:
                with thread.thread_lock():
                    count = thread.thread_action(method='prepare_delete_state')
                    if count:
                        await self.reply_text(
                            update,
                            f'已撤销{count}个订单',
                        )
                    state_path = position.config.state_file_path
                    os.remove(state_path)
                    await self.reply_text(
                        update,
                        f'清除完成',
                    )
            else:
                raise ValueError(f'找不到持仓对应的线程')
        except FileNotFoundError:
            await self.reply_text(
                update,
                f'改动完成(不存在状态文件)',
            )
        except Exception as e:
            await self.reply_text(
                update,
                f'改动失败:{e}',
            )


__all__ = ['DeleteState']
