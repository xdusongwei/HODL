from hodl.bot import *
from hodl.state import *
from hodl.store_base import *
from hodl.thread_mixin import *
from hodl.tools import *


@bot_cmd(
    command='revivestore',
    menu_desc='复活持仓线程',
    trade_strategy=TradeStrategyEnum.HODL,
)
class ReviveStore(SimpleTelegramConversation):
    SELECT_TEXT = f'你正在尝试重启死亡的持仓管理线程。 '
    f'如果线程因为下单动作导致的崩溃，需要确认订单是否下达到券商，若下达成功，则应先通过命令，人工连接订单基本信息到持仓状态中。'
    f'如果因为风控检查导致的崩溃，需首先人工确认持仓数量和现金额是否允许继续运行而不会引发混乱。'

    async def confirm(self, update, context, position: TgSelectedPosition):
        await self.reply_text(
            update,
            f'选择了 {position.display} 操作重启死亡的持仓管理线程。。使用命令 /confirm 来确认',
        )
        return self.K_SIMPLE_EXECUTE

    async def execute(self, update, context, position: TgSelectedPosition):
        await self.reply_text(
            update,
            f'已经确认重启{position.display}的持仓线程',
        )
        try:
            state_path = position.config.state_file_path
            if not state_path:
                raise ValueError(f'不存在持仓状态文件位置，不能重置风控信息')

            broker = position.config.broker
            region = position.config.region
            symbol = position.symbol
            store: StoreBase = ThreadMixin.find_by_tags(tags=('Store', broker, region, symbol,))
            thread = store.current_thread
            if thread:
                if thread.is_alive():
                    raise ValueError(f'线程{thread}仍然存活')
            else:
                raise ValueError(f'找不到持仓对应的线程')

            text = LocateTools.read_file(state_path)
            state = FormatTool.json_loads(text)
            state = State(state)
            if state.risk_control_break:
                state.risk_control_break = False
                state.risk_control_detail = ''
                state.lsod = ''
                await self.reply_text(
                    update,
                    f'已清除风控错误',
                )
            state.cash_day = None
            state.chip_day = None
            text = FormatTool.json_dumps(state)
            LocateTools.write_file(state_path, text)
            store.thread_version += 1
            store.start(name=position.config.thread_name)
            await self.reply_text(
                update,
                f'已创建新线程',
            )
        except Exception as e:
            await self.reply_text(
                update,
                f'改动失败:{e}',
            )


__all__ = ['ReviveStore']
