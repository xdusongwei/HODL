import os
import threading
import requests
from hodl.risk_control import *
from hodl.tools import *
from hodl.storage import *
from hodl.bot import *
from hodl.broker.broker_proxy import *
from hodl.thread_mixin import *
from hodl.state import *


class StoreBase(ThreadMixin):
    STATE_SLEEP = '被抑制'
    STATE_TRADE = '监控中'
    STATE_GET_OFF = '已套利'

    ENABLE_LOG_ALIVE = True
    ENABLE_BROKER = True
    SHOW_EXCEPTION_DETAIL = False

    SESSION = requests.Session()

    def __init__(
            self,
            store_config: StoreConfig,
            db: LocalDb = None,
    ):
        self.runtime_state: StoreState = StoreState(
            store_config=store_config,
            http_session=self.SESSION,
            calendar=store_config.trading_calendar,
        )
        self.thread_context = self.runtime_state
        self.state: State = State.new()
        self.db = db
        self.lock = threading.RLock()
        self.on_state_changed = set()

        variable = self.runtime_state.variable
        self.bot = AlertBot(
            broker=store_config.broker,
            symbol=store_config.symbol,
            chat_id=variable.telegram_chat_id,
            db=db,
        )

        try:
            self.init_trade_service()
        except Exception as e:
            self.logger.exception(e)
            self.exception = e
            raise e

    @property
    def market_status_proxy(self) -> MarketStatusProxy:
        return getattr(self, '_market_status_proxy', None)

    @market_status_proxy.setter
    def market_status_proxy(self, v: MarketStatusProxy):
        setattr(self, '_market_status_proxy', v)

    @property
    def broker_proxy(self) -> BrokerProxy:
        return getattr(self, '_broker_proxy', None)

    @broker_proxy.setter
    def broker_proxy(self, v: BrokerProxy):
        setattr(self, '_broker_proxy', v)

    @property
    def risk_control(self) -> RiskControl:
        return getattr(self, '_risk_control', None)

    @risk_control.setter
    def risk_control(self, v: RiskControl):
        setattr(self, '_risk_control', v)

    @property
    def process_time(self) -> float | None:
        return getattr(self, '_process_time', None)

    @process_time.setter
    def process_time(self, v: float):
        setattr(self, '_process_time', v)

    @property
    def exception(self) -> Exception | None:
        return getattr(self, '_exception', None)

    @exception.setter
    def exception(self, v: Exception):
        setattr(self, '_exception', v)

    @classmethod
    def read_state(cls, content: str):
        state = FormatTool.json_loads(content)
        return State.new(state)

    def load_state(self):
        if not self.state_file:
            return
        text = LocateTools.read_file(self.state_file)
        if text is None:
            self.state = State.new()
        else:
            runtime_state = self.runtime_state
            runtime_state.state_compare = TimeTools.us_day_now(), text
            self.state = self.read_state(text)
        self.state.name = self.store_config.name

    def save_state(self):
        runtime_state = self.runtime_state
        text = FormatTool.json_dumps(self.state)
        day = TimeTools.us_time_now()
        today = TimeTools.date_to_ymd(day)
        changed = (today, text,) != runtime_state.state_compare
        if changed:
            if self.state_file:
                LocateTools.write_file(self.state_file, text)
            if self.state_archive:
                archive_path = os.path.join(self.state_archive, f'{today}.json')
                LocateTools.write_file(archive_path, text)
            if db := self.db:
                row = StateRow(
                    version=self.state.version,
                    day=int(TimeTools.date_to_ymd(day, join=False)),
                    symbol=self.store_config.symbol,
                    content=text,
                    update_time=int(TimeTools.us_time_now().timestamp()),
                )
                row.save(con=db.conn)
        for cb in self.on_state_changed:
            if not changed:
                continue
            try:
                cb(self)
            except Exception as e:
                self.logger.exception(f'回调状态文件变更时遇到异常{e}')

    @property
    def logger(self):
        return self.runtime_state.log.logger()

    @property
    def alive_logger(self):
        return self.runtime_state.alive_log.logger()

    @property
    def store_config(self) -> StoreConfig:
        return self.runtime_state.store_config

    @property
    def state_file(self) -> str | None:
        return self.store_config.state_file_path

    @property
    def state_archive(self) -> str | None:
        return self.store_config.state_archive_folder

    @property
    def thread_context(self) -> StoreState:
        ctx = threading.local()
        return ctx.runtime_store_state

    @thread_context.setter
    def thread_context(self, runtime_state: StoreState):
        ctx = threading.local()
        ctx.runtime_store_state = runtime_state

    def before_loop(self):
        self.load_state()
        setattr(self, '_begin_time', TimeTools.get_utc())
        return True

    def after_loop(self):
        self.save_state()
        now = TimeTools.get_utc()
        begin_time = getattr(self, '_begin_time', now)
        self.process_time = (now - begin_time).total_seconds()

    @classmethod
    def build_table(cls, store_config: StoreConfig, plan: Plan):
        plan_calc = plan.plan_calc()
        profit_table = plan_calc.profit_rows(
            base_price=plan.base_price,
            max_shares=plan.total_chips,
            buy_spread=store_config.buy_spread,
            sell_spread=store_config.sell_spread,
            precision=store_config.precision,
            shares_per_unit=store_config.shares_per_unit,
            buy_spread_rate=store_config.buy_spread_rate,
            sell_spread_rate=store_config.sell_spread_rate,
        )
        return profit_table

    def current_table(self):
        return self.build_table(store_config=self.store_config, plan=self.state.plan)

    def init_trade_service(self):
        if not self.ENABLE_BROKER:
            return
        self.broker_proxy = BrokerProxy(
            runtime_state=self.runtime_state,
        )
        self.market_status_proxy = MarketStatusProxy(
            var=self.runtime_state.variable,
            session=self.runtime_state.http_session,
        )
        self.broker_proxy.on_init()

    @classmethod
    def state_bar(cls, thread_alive: bool, config: StoreConfig, state: State) -> list[BarElementDesc]:
        cross_mark = '❌'
        skull = '💀'
        money_bag = '💰'
        plug = '🔌'
        check = '✅'
        no_entry = '⛔'
        if config.enable:
            if not thread_alive:
                system_status = skull
                system_tooltip = '持仓管理线程已经崩溃'
            elif state.current == StoreBase.STATE_GET_OFF:
                system_status = money_bag
                earning = state.plan.earning
                system_tooltip = f'持仓完成套利{FormatTool.pretty_price(earning, config=config, only_int=True)}'
            elif not state.is_plug_in:
                system_status = plug
                system_tooltip = '券商系统连通未成功'
            elif state.current == StoreBase.STATE_TRADE:
                system_status = check
                system_tooltip = '监控中'
            else:
                system_status = cross_mark
                system_tooltip = '其他三项不能达到工作条件'
        else:
            system_status = no_entry
            system_tooltip = '使能关闭'
        market_status = check if state.market_status == 'TRADING' else cross_mark
        return [
            BarElementDesc(
                content=f'{system_status}系统',
                tooltip=system_tooltip,
            ),
            BarElementDesc(
                content=f'{market_status}市场',
                tooltip=f'指示持仓所属市场是否开市',
            ),
            BarElementDesc(
                content=f'{check if state.quote_enable_trade else cross_mark}标的',
                tooltip=f'持仓标的没有异常状态，例如停牌、熔断',
            ),
            BarElementDesc(
                content=f'{cross_mark if state.risk_control_break else check}风控',
                tooltip=f'持仓量、现金额、下单是否触发了风控限制',
            ),
        ]

    @classmethod
    def buff_bar(cls, config: StoreConfig, state: State, process_time: float = None) -> list[BarElementDesc]:
        bar = list()
        plan = state.plan

        if config.lock_position:
            lock_position = '🔒'
            bar.append(BarElementDesc(content=lock_position, tooltip='持仓量核对已纳入风控，不可随时加仓'))

        factor_content = '🎛️'
        tooltip = ''
        if config.factors:
            tooltip += '自定义因子表.'
            factor_content += '自定'
        elif config.cost_price:
            tooltip += '自动选择恐慌贪婪因子表.'
            factor_content += '自动'
        elif factor_type := config.factor_fear_and_greed:
            tooltip += f'指定{factor_type}因子表.'
            factor_content += '指定'
        else:
            tooltip += '未知的因子表.'
            factor_content += '未知'
        tooltip += '基准价格参考: 昨收价, 开盘价, '
        if config.base_price_day_low:
            tooltip += ', 当日最低价格'
        if config.base_price_last_buy:
            tooltip += f', 上次买回价格({config.base_price_last_buy_days}个自然天内). '
        tooltip += f'价格比较函数: {state.bp_function}.'
        bar.append(BarElementDesc(content=factor_content, tooltip=tooltip))

        if config.stage > 1:
            stages = config.multistage_rocket
            current = stages[-1]
            target_price = current[1]
            factor_content = f'🚀Lv{config.stage}'
            tooltip = '当前持仓正在多级状态下工作'
            if price := state.quote_latest_price:
                if target_price and price <= target_price:
                    factor_content = '🛬'
                    tooltip = '当前价格可以还原上一级的状态'
            bar.append(BarElementDesc(content=factor_content, tooltip=tooltip))

        if price := plan.give_up_price:
            factor_content = '🏳️'
            tooltip = f'买回指定价格: {FormatTool.pretty_price(price, config=config)}'
            bar.append(BarElementDesc(content=factor_content, tooltip=tooltip))

        if plan.base_price and not len(plan.orders):
            anchor_content = '⚓'
            tooltip = f'基准价格: {FormatTool.pretty_price(plan.base_price, config=config)}'
            bar.append(BarElementDesc(content=anchor_content, tooltip=tooltip))

        if rework_price := state.plan.rework_price:
            rework_set = f'🔁'
            tooltip = f'已计划重置状态数据, 使套利持仓重新工作, 触发价格:{FormatTool.pretty_price(rework_price, config=config)}'
            bar.append(BarElementDesc(content=rework_set, tooltip=tooltip))

        if plan.price_rate != 1.0:
            price_rate = plan.price_rate
            price_rate_text = f'🎢{FormatTool.factor_to_percent(price_rate)}'
            bar.append(BarElementDesc(content=price_rate_text, tooltip='按缩放系数重新调整买卖价格的幅度'))

        if rate := config.market_price_rate:
            market_price_set = '⚡'
            tooltip = f'市场价格偏离超过预期幅度{FormatTool.factor_to_percent(rate)}触发市价单'
            bar.append(BarElementDesc(content=market_price_set, tooltip=tooltip))

        show_tp_elem = False
        tp_alarm_mode = False
        content = '🛡️'
        tooltip = ''

        if config.base_price_tumble_protect:
            show_tp_elem = True
            tooltip += f'启用MA暴跌保护.'
        if rate := config.vix_tumble_protect:
            show_tp_elem = True
            tooltip += f'启用VIX暴跌保护.'
            vix_high = state.ta_vix_high
            tooltip += f'VIX当日最高到达{FormatTool.pretty_usd(rate, precision=2)}时将阻止卖出订单. '
            tooltip += f'VIX当日最高:{FormatTool.pretty_usd(vix_high, precision=2)}.'
        if config.tumble_protect_rsi:
            show_tp_elem = True
            tooltip += f'启用RSI暴跌保护.'
            rsi_name = f'RSI{config.tumble_protect_rsi_period}'
            tooltip += f'盘中{rsi_name}低于{config.tumble_protect_rsi_lock_limit}将阻止卖出计划. '
            if rsi_current := state.ta_tumble_protect_rsi_current:
                tooltip += f'当前{rsi_name}为{rsi_current}. '
        if show_tp_elem:
            tooltip += '\n'

        if state.ta_tumble_protect_flag:
            show_tp_elem = True
            tp_alarm_mode = True
        if state.ta_vix_high and config.vix_tumble_protect and state.ta_vix_high >= config.vix_tumble_protect:
            show_tp_elem = True
            tp_alarm_mode = True
        if state.ta_tumble_protect_rsi:
            show_tp_elem = True
            tp_alarm_mode = True
        if show_tp_elem:
            if tp_alarm_mode:
                content = '🚨'
            bar.append(BarElementDesc(content=content, tooltip=tooltip))

        if state.sleep_mode_active:
            content = '💤'
            tooltip = '非交易时段，休眠模式启动，持仓更新变慢'
            bar.append(BarElementDesc(content=content, tooltip=tooltip))

        battery = '🔋'
        chips = plan.total_chips
        diff = plan.total_volume_not_active(assert_zero=False)
        remain_rate = None
        if chips and (chips - diff) >= 0:
            remain = chips - diff
            remain_rate = remain / chips
        if remain_rate is not None and remain_rate < 0.5:
            battery = '🪫'
        battery += FormatTool.factor_to_percent(remain_rate)
        bar.append(BarElementDesc(content=battery, tooltip='剩余持仓占比'))

        unit = 'ms'
        if process_time is not None:
            if process_time >= 1.0:
                unit = 's'
                process_time = f'{process_time:.2f}'
            else:
                process_time = f'{int(process_time * 1000)}'
        else:
            process_time = '--'
        process_time_text = f'📶{process_time}{unit}'
        bar.append(BarElementDesc(content=process_time_text, tooltip='持仓处理耗时'))

        return bar

    def primary_bar(self) -> list[BarElementDesc]:
        return self.state_bar(
            thread_alive=self.current_thread.is_alive() if self.current_thread else False,
            config=self.store_config,
            state=self.state,
        )

    def secondary_bar(self) -> list[BarElementDesc]:
        return self.buff_bar(
            config=self.store_config,
            state=self.state,
            process_time=self.process_time,
        )

    def warning_alert_bar(self) -> list[str]:
        result = list()
        config = self.store_config
        state = self.state
        if not state.is_plug_in:
            result.append(f'🔌券商系统需要恢复联通')
        if state.quote_outdated:
            result.append(f'⚠️行情的快照数据过时.')
        if state.ta_tumble_protect_flag:
            ma5 = FormatTool.pretty_price(state.ta_tumble_protect_ma5, config=config)
            ma10 = FormatTool.pretty_price(state.ta_tumble_protect_ma10, config=config)
            result.append(f'⚠️近期最低价格已触发MA暴跌保护, 基准价格将参考MA5({ma5})和MA10({ma10}).')
        if state.ta_vix_high and config.vix_tumble_protect and state.ta_vix_high >= config.vix_tumble_protect:
            result.append(f'🚫当日VIX最高价已触发VIX暴跌保护.')
        if limit := state.ta_tumble_protect_rsi:
            rsi_name = f'RSI{config.tumble_protect_rsi_period}'
            rsi_day = TimeTools.format_ymd(state.ta_tumble_protect_rsi_day)
            result.append(f'🚫{rsi_day}盘中触及到RSI暴跌保护，{rsi_name}高于{limit}时恢复卖出计划.')
        return result

    def thread_lock(self) -> threading.RLock:
        return self.lock

    def thread_tags(self) -> tuple:
        config = self.store_config
        return 'Store', config.broker, config.region, config.symbol,

    @classmethod
    def rewrite_earning_json(cls, db: LocalDb, earning_json_path: str, now, weeks=2):
        last_sunday_utc = TimeTools.last_sunday_utc(now, weeks=-weeks)
        create_time = int(last_sunday_utc.timestamp())
        items = EarningRow.items_after_time(con=db.conn, create_time=create_time)
        total_list = [(currency, EarningRow.total_amount_before_time(db.conn, create_time, currency))
                      for currency in ('USD', 'CNY', )]
        recent_earnings = list()
        for item in items:
            day = str(item.day)
            day_now = f'{day[:4]}-{day[4:6]}-{day[6:]}'
            recent_earnings.append({
                'type': 'earningItem',
                'day': day_now,
                'name': item.symbol,
                'broker': item.broker,
                'region': item.region,
                'symbol': item.symbol,
                'earning': item.amount,
                'currency': item.currency,
            })
        for currency, earning in total_list:
            recent_earnings.append({
                'type': 'earningHistory',
                'day': TimeTools.date_to_ymd(last_sunday_utc),
                'name': '历史',
                'broker': None,
                'region': None,
                'symbol': None,
                'earning': earning,
                'currency': currency,
            })
        monthly_list = list()
        monthly_rows = EarningRow.total_earning_group_by_month(con=db.conn)
        for row in monthly_rows:
            monthly_list.append({
                'month': row.month,
                'currency': row.currency,
                'total': row.total,
            })
        file_dict = {
            'type': 'earningReport',
            'recentEarnings': recent_earnings,
            'monthlyEarnings': monthly_list,
        }
        file_body = FormatTool.json_dumps(file_dict)
        LocateTools.write_file(earning_json_path, file_body)

    def args(self) -> tuple[StoreConfig, State, Plan, ]:
        return self.store_config, self.state, self.state.plan,

    class ProfitRowTool:
        def __init__(self, config: StoreConfig, state: State):
            self.price = state.quote_latest_price
            self.store_config = config
            self.plan = state.plan
            self.filled_level = 0
            self.rows = list()
            self.buy_percent = None
            self.sell_percent = None
            self.buy_at = None
            self.sell_at = None
            self.has_table = self.plan.table_ready
            if self.has_table:
                self.filled_level = self.plan.current_sell_level_filled()
                self.rows = StoreBase.build_table(store_config=self.store_config, plan=self.plan)
            if self.filled_level and self.price:
                idx = self.filled_level - 1
                rate = abs(self.price - self.rows[idx].buy_at) / self.price
                self.buy_percent = rate
                self.buy_at = self.rows[idx].buy_at
            if self.filled_level < len(self.rows) and self.price:
                idx = self.filled_level
                rate = abs(self.price - self.rows[idx].sell_at) / self.price
                self.sell_percent = rate
                self.sell_at = self.rows[idx].sell_at

        def earning_forecast(self, rate: float) -> int:
            base_value = (self.plan.total_chips or 0) * (self.plan.base_price or 0.0)
            return int(base_value * (rate - 1))

    @classmethod
    def profit_tool(cls, config: StoreConfig, state: State) -> ProfitRowTool:
        return StoreBase.ProfitRowTool(config=config, state=state)


__all__ = ['StoreBase', ]
