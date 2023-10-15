import asyncio
import threading
from telegram import Message, Update
from telegram.ext import Application
from hodl.bot.base import TelegramThreadBase
from hodl.thread_mixin import ThreadMixin


class TelegramThread(ThreadMixin, TelegramThreadBase):
    def __init__(self, app: Application, chat_id: int = None):
        super().__init__()
        self.app = app
        self.chat_id = chat_id
        self.loop = asyncio.new_event_loop()

        from hodl.bot.bot_conversation.monthly_earning import MonthlyEarning
        from hodl.bot.bot_conversation.today_orders import TodayOrders
        from hodl.bot.bot_conversation.settings import Settings
        from hodl.bot.bot_conversation.lock_position import LockPosition
        from hodl.bot.bot_conversation.enable_position import EnablePosition
        from hodl.bot.bot_conversation.base_price_last_buy import BasePriceLastBuy
        from hodl.bot.bot_conversation.max_shares import MaxShares
        from hodl.bot.bot_conversation.temp_base_price import TempBasePrice
        from hodl.bot.bot_conversation.report import Report
        from hodl.bot.bot_conversation.delete_state import DeleteState
        from hodl.bot.bot_conversation.base_price_day_low import BasePriceDayLow
        from hodl.bot.bot_conversation.revive_store import ReviveStore
        from hodl.bot.bot_conversation.give_up_price import GiveUpPrice

        dispatcher = app
        dispatcher.add_handler(MonthlyEarning.handler())
        dispatcher.add_handler(TodayOrders.handler())
        dispatcher.add_handler(Settings.handler())
        dispatcher.add_handler(LockPosition.handler())
        dispatcher.add_handler(EnablePosition.handler())
        dispatcher.add_handler(BasePriceLastBuy.handler())
        dispatcher.add_handler(MaxShares.handler())
        dispatcher.add_handler(TempBasePrice.handler())
        dispatcher.add_handler(Report.handler())
        dispatcher.add_handler(DeleteState.handler())
        dispatcher.add_handler(BasePriceDayLow.handler())
        dispatcher.add_handler(ReviveStore.handler())
        dispatcher.add_handler(GiveUpPrice.handler())

    def run(self):
        super().run()
        TelegramThreadBase.INSTANCE = self
        asyncio.set_event_loop(self.loop)
        self.app.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=list(), close_loop=False)

    def application(self) -> Application:
        return self.app

    def send_message(self, text: str) -> Message:
        chat_id = self.chat_id
        bot = self.app.bot
        loop = self.loop
        if not chat_id:
            raise ValueError
        evt = threading.Event()

        coro = bot.sendMessage(
            chat_id=chat_id,
            text=text,
            reply_to_message_id=None,
        )
        task = loop.create_task(coro)
        task.add_done_callback(lambda s: evt.set())
        evt.wait()
        if e := task.exception():
            raise e
        return task.result()


__all__ = ['TelegramThread', ]
