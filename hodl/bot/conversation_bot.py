from telegram.ext import Updater
from hodl.storage import *
from hodl.bot import TelegramBotBase


class ConversationBot(TelegramBotBase):
    def __init__(self, updater: Updater = None, db: LocalDb = None):
        super(ConversationBot, self).__init__(updater=updater, db=db)
        if updater:
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

            dispatcher = updater.dispatcher
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


__all__ = ['ConversationBot', ]
