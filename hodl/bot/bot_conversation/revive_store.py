import json
import threading
from telegram import ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler, Filters
from hodl.bot import TelegramBotBase
from hodl.state import *
from hodl.thread_mixin import *


class ReviveStore(TelegramBotBase):
    K_RS_SELECT = 0
    K_RS_DECISION = 1
    K_RS_CONFIRM = 2
    STORE_LIST: list[ThreadMixin] = list()

    @classmethod
    def set_store_list(cls, store_list):
        ReviveStore.STORE_LIST = store_list

    def revive_store_start(self, update, context):
        lines = self._symbol_lines()
        idx_list = self._symbol_choice()
        update.message.reply_text(
            f'你正在尝试重启死亡的持仓管理线程。 '
            f'如果线程因为下单动作导致的崩溃，需要确认订单是否下达到券商，若下达成功，则应先通过命令，人工连接订单基本信息到持仓状态中。'
            f'如果因为风控检查导致的崩溃，需首先人工确认持仓数量和现金额是否允许继续运行而不会引发混乱。'
            f'选择需要操作的标的序号\n'
            f'{lines}\n\n流程的任意阶段都可以使用 /cancel 取消',
            reply_markup=ReplyKeyboardMarkup(
                idx_list, one_time_keyboard=True, input_field_placeholder='选择持仓标的序号'
            ),
        )
        return self.K_RS_DECISION

    def revive_store_select(self, update, context):
        idx = int(update.message.text) - 1
        position = self._symbol_list()[idx]
        user_id = update.message.from_user.id
        self._create_session(user_id=user_id, position=position)
        update.message.reply_text(
            f'选择了 {position.display} 操作重启死亡的持仓管理线程。'
            f'使用命令 /confirm 来确认',
            reply_markup=ReplyKeyboardRemove(),
        )
        return self.K_RS_CONFIRM

    def revive_store_confirm(self, update, context):
        text = update.message.text
        user_id = update.message.from_user.id
        session = self._get_session(user_id=user_id)
        match text:
            case '/confirm':
                update.message.reply_text(
                    f'已经确认重启{session.position.display}的持仓线程',
                    reply_markup=ReplyKeyboardRemove(),
                )
                try:
                    state_path = session.position.config.state_file_path
                    if not state_path:
                        raise ValueError(f'不存在持仓状态文件位置，不能重置风控信息')

                    for store in ReviveStore.STORE_LIST:
                        thread = store.current_thread
                        if not thread:
                            continue
                        region = session.position.config.region
                        symbol = session.position.symbol
                        if f'Store([{region}]{symbol})' not in thread.name:
                            continue
                        if thread.is_alive():
                            raise ValueError(f'线程{store}仍然存活')
                        t = store
                        break
                    else:
                        raise ValueError(f'找不到持仓对应的线程')

                    with open(state_path, mode='r', encoding='utf8') as f:
                        text = f.read()
                        state = json.loads(text)
                    state = State(state)
                    if state.risk_control_break:
                        state.risk_control_break = False
                        state.risk_control_detail = ''
                        text = json.dumps(state, indent=4)
                        with open(state_path, mode='w', encoding='utf8') as f:
                            f.write(text)
                        update.message.reply_text(
                            f'已清除风控错误',
                            reply_markup=ReplyKeyboardRemove(),
                        )
                    t.unmount()
                    thread = threading.Thread(
                        name=f'Store([{region}]{symbol})',
                        target=t.run,
                        daemon=True,
                    )
                    thread.start()
                    update.message.reply_text(
                        f'已创建新线程',
                        reply_markup=ReplyKeyboardRemove(),
                    )
                    alert_bot = getattr(t, 'bot')
                    if alert_bot:
                        alert_bot.d = dict()
                except Exception as e:
                    update.message.reply_text(
                        f'改动失败:{e}',
                        reply_markup=ReplyKeyboardRemove(),
                    )
                finally:
                    self._clear_session(user_id=user_id)

                return ConversationHandler.END
            case _:
                update.message.reply_text(
                    f'非法选择，请重新选择命令',
                    reply_markup=ReplyKeyboardRemove(),
                )
                return self.K_RS_CONFIRM

    @classmethod
    def handler(cls):
        o = cls()
        handler = ConversationHandler(
            entry_points=[CommandHandler('reviveStore', o.revive_store_start)],
            states={
                o.K_RS_DECISION: [MessageHandler(Filters.regex(r'^(\d+)$'), o.revive_store_select)],
                o.K_RS_CONFIRM: [
                    CommandHandler('confirm', o.revive_store_confirm),
                ],
            },
            fallbacks=[o.cancel_handler()],
        )
        return handler


__all__ = ['ReviveStore']
