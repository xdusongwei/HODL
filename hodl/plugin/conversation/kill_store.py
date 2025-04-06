from hodl.bot import *
from hodl.store_base import *
from hodl.thread_mixin import *


@bot_cmd(
    command='killstore',
    menu_desc='杀死持仓线程',
)
class KillStore(SimpleTelegramConversation):
    SELECT_TEXT = '你正在尝试杀死的持仓管理线程。 '

    async def confirm(self, update, context, position: TgSelectedPosition):
        await self.reply_text(
            update,
            f'选择了 {position.display} 操作杀死持仓管理线程。使用命令 /confirm 来确认',
        )
        return self.K_SIMPLE_EXECUTE

    async def execute(self, update, context, position: TgSelectedPosition):
        await self.reply_text(
            update,
            f'已经确认将要杀死{position.display}线程',
        )
        try:
            broker = position.config.broker
            region = position.config.region
            symbol = position.symbol
            store: StoreBase = ThreadMixin.find_by_tags(tags=('Store', broker, region, symbol, ))
            thread = store.current_thread
            if thread:
                if not thread.is_alive():
                    raise ValueError(f'线程{thread}已经死亡')
            else:
                raise ValueError(f'找不到持仓对应的线程')

            with store.thread_lock():
                store.thread_version += 1
            store.kill()

            await self.reply_text(
                update,
                f'已杀死线程',
            )
        except Exception as e:
            await self.reply_text(
                update,
                f'操作失败:{e}',
            )


__all__ = ['KillStore']
