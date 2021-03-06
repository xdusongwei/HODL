import os
import json
import time
from threading import Thread
from hodl.bot import AlertBot, ConversationBot
from hodl.storage import LocalDb
from hodl.store import Store
from hodl.quote_mixin import QuoteMixin
from hodl.broker.broker_proxy import *
from hodl.tools import *


class Manager:
    CONVERSATION_BOT = None
    MARKET_STATUS_THREAD: Thread = None

    @classmethod
    def write_system_state(cls, items: list[tuple[str, Store, Thread]], sleep_secs):
        path = VariableTools().manager_state_path
        if not path:
            return
        ms = BrokerProxy.MARKET_STATUS or dict()
        ms = {broker_type.BROKER_NAME: detail for broker_type, detail in ms.items()}
        d = {
            'pid': os.getpid(),
            'time': TimeTools.us_time_now().timestamp(),
            'storeSleepSecs': sleep_secs,
            'marketStatus': ms,
            'marketStatusThread': {
                'name': Manager.MARKET_STATUS_THREAD.name,
                'id': Manager.MARKET_STATUS_THREAD.native_id,
                'dead': not Manager.MARKET_STATUS_THREAD.is_alive(),
            } if Manager.MARKET_STATUS_THREAD else {},
            'items': [
                {
                    'symbol': symbol,
                    'thread': {
                        'name': thread.name,
                        'id': thread.native_id,
                        'dead': not thread.is_alive(),
                    },
                    'store': {
                        'state': store.state,
                        'exception': str(store.exception or ''),
                        'hasDb': bool(store.db),
                        'hasAlertBot': store.bot.is_alive,
                        'processTime': store.process_time,
                    },
                    'config': {
                        'name': store.store_config.name,
                        'symbol': store.store_config.symbol,
                        'maxShares': store.store_config.max_shares,
                        'enable': store.store_config.enable,
                        'prudent': store.store_config.prudent,
                        'broker': store.store_config.broker,
                        'tradeType': store.store_config.trade_type,
                        'region': store.store_config.region,
                        'precision': store.store_config.precision,
                        'lockPosition': store.store_config.lock_position,
                        'basePriceLastBuy': store.store_config.base_price_last_buy,
                        'basePriceDayLow': store.store_config.base_price_day_low,
                        'currency': store.store_config.currency,
                        'reworkLevel': store.store_config.rework_level,
                    },
                    'broker': {
                        'tradeBroker': str(store.broker_proxy.trade_broker),
                    } if store.broker_proxy else {},
                }
                for symbol, store, thread in items if store.state],
        }
        text = json.dumps(d, indent=4, sort_keys=True)
        with open(path, 'w', encoding='utf8') as f:
            f.write(text)

    @classmethod
    def monitor_alert(cls, items: list[tuple[str, Store, Thread]]):
        for symbol, store, thread in items:
            if thread.is_alive():
                continue
            text = f'??????????[{thread.name}]????????????\n'
            if detail := store.state.risk_control_detail:
                text += f'????????????:{detail}\n'
            if e := store.exception:
                text += f'????????????:{e}\n'
            store.bot.set_alarm(AlertBot.K_THREAD_DEAD, text=text)

    @classmethod
    def rework_store(cls, items: list[tuple[str, Store, Thread]]):
        for symbol, store, thread in items:
            if not store.store_config.enable:
                continue
            state = store.state
            plan = state.plan
            state_path = store.store_config.state_file_path
            if not state_path:
                continue
            if not state.is_today_get_off:
                continue
            if not plan.rework_price:
                continue
            latest_price = state.quote_latest_price
            if not latest_price:
                continue
            if plan.rework_price > latest_price:
                continue
            if not os.path.exists(state_path):
                continue
            try:
                with store.lock:
                    os.remove(state_path)
                rework_price = FormatTool.pretty_price(plan.rework_price, config=store.store_config)
                store.bot.send_text(f'{thread.name}?????????????????????{rework_price}, ???????????????????????????')
            except FileNotFoundError:
                pass
            except Exception as e:
                store.bot.send_text(f'{thread.name}???????????????????????????, ?????????????????????????????????: {e}')

    @classmethod
    def run(cls):
        var = VariableTools()
        store_configs = var.store_configs
        if not store_configs:
            print('????????????????????????')
            return

        db = None
        if path := var.db_path:
            db = LocalDb(db_path=path)
        try:
            cls.CONVERSATION_BOT = ConversationBot(updater=var.telegram_updater(), db=db)
            stores = [Store(store_config=config, db=db) for config in store_configs.values()]
            symbols = [store.store_config.symbol for store in stores]
            threads = [Thread(name=f'Store({store.store_config.symbol})', target=store.idle, daemon=True)
                       for store in stores]
            items = list(zip(symbols, stores, threads))
            for thread in threads:
                thread.start()
        except Exception as e:
            if db:
                db.conn.close()
            raise e

        if var.async_market_status:
            print(f'????????????????????????????????????')
            store = stores[0]
            proxy = store.broker_proxy
            proxy.pull_market_status()
            print(f'???????????????????????????')

            def _loop(s: Store):
                while True:
                    s.broker_proxy.pull_market_status()

            Manager.MARKET_STATUS_THREAD = Thread(
                name='marketStatusPuller',
                target=_loop,
                daemon=True,
                args=(store, )
            )
            Manager.MARKET_STATUS_THREAD.start()
            print(f'?????????????????????')

        while True:
            try:
                time.sleep(4)
                variable = VariableTools()
                sleep_secs = variable.sleep_limit
                store_configs = variable.store_configs
                if len(store_configs) != len(items):
                    print(f'??????????????????????????????????????????????????????????????????????????????')
                    return
                for store in stores:
                    symbol = store.store_config.symbol
                    new_config = store_configs.get(symbol)
                    if new_config:
                        with store.lock:
                            store.runtime_state.store_config = new_config
                            store.runtime_state.variable = variable
                    else:
                        print(f'???????????????{symbol}?????????????????????')
                        return
                    store.runtime_state.sleep_secs = sleep_secs
                    QuoteMixin.change_cache_ttl(sleep_secs)
                cls.write_system_state(
                    items=items,
                    sleep_secs=sleep_secs,
                )
                cls.monitor_alert(items=items)
                cls.rework_store(items=items)
            except KeyboardInterrupt:
                for thread in threads:
                    if thread.is_alive():
                        thread.join()
                if db:
                    db.conn.close()
                return


Manager.run()
