import asyncio
import threading
from telegram import Message, Update
from telegram.ext import Application
from hodl.bot.base import TelegramThreadBase
from hodl.thread_mixin import *
from hodl.tools import *


class TelegramThread(ThreadMixin, TelegramThreadBase):
    def __init__(self, app: Application, chat_id: int = None):
        super().__init__()
        self.app: Application = app
        self.chat_id = chat_id
        self.loop = asyncio.new_event_loop()
        self.ok_counter = 0
        self.error_counter = 0
        self.latest_msgs: list[tuple[str, str]] = list()

    def run(self):
        super().run()
        TelegramThreadBase.INSTANCE = self
        asyncio.set_event_loop(self.loop)

        from hodl.cli.threads.bot_conversation.monthly_earning import MonthlyEarning
        from hodl.cli.threads.bot_conversation.today_orders import TodayOrders
        from hodl.cli.threads.bot_conversation.settings import Settings
        from hodl.cli.threads.bot_conversation.lock_position import LockPosition
        from hodl.cli.threads.bot_conversation.enable_position import EnablePosition
        from hodl.cli.threads.bot_conversation.base_price_last_buy import BasePriceLastBuy
        from hodl.cli.threads.bot_conversation.max_shares import MaxShares
        from hodl.cli.threads.bot_conversation.temp_base_price import TempBasePrice
        from hodl.cli.threads.bot_conversation.report import Report
        from hodl.cli.threads.bot_conversation.delete_state import DeleteState
        from hodl.cli.threads.bot_conversation.base_price_day_low import BasePriceDayLow
        from hodl.cli.threads.bot_conversation.revive_store import ReviveStore
        from hodl.cli.threads.bot_conversation.give_up_price import GiveUpPrice

        dispatcher = self.app
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

        self.app.run_polling(
            timeout=15,
            read_timeout=15.0,
            write_timeout=15.0,
            allowed_updates=Update.ALL_TYPES,
            stop_signals=list(),
            close_loop=False,
            drop_pending_updates=False,
        )

    def application(self) -> Application:
        return self.app

    def send_message(self, text: str, block=True, disable_notification=None) -> Message | None:
        chat_id = self.chat_id
        bot = self.app.bot
        loop = self.loop
        msgs = self.latest_msgs.copy()
        now = TimeTools.us_time_now(tz='Asia/Shanghai')
        time = FormatTool.pretty_dt(now, region='CN', with_year=False, with_tz=False, with_ms=False)
        msgs.insert(0, (time, text, ))
        msgs = msgs[:3]
        self.latest_msgs = msgs

        if not chat_id:
            self.error_counter += 1
            raise ValueError
        evt = threading.Event()

        coro = bot.sendMessage(
            chat_id=chat_id,
            text=text,
            reply_to_message_id=None,
            disable_notification=disable_notification,
        )
        task = loop.create_task(coro)

        def _done(_s):
            evt.set()
            if task.exception():
                self.error_counter += 1
            else:
                self.ok_counter += 1

        task.add_done_callback(_done)

        if block:
            evt.wait()
            if e := task.exception():
                raise e
            return task.result()
        return None

    def primary_bar(self) -> list[BarElementDesc]:
        bar = list()
        elem = BarElementDesc(
            content=f'✅{self.ok_counter}❌{self.error_counter}',
        )
        bar.append(elem)
        return bar

    def warning_alert_bar(self) -> list[str]:
        result = [f'{t}: {s}' for t, s in self.latest_msgs]
        return result


__all__ = ['TelegramThread', ]
