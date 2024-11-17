from hodl.bot import *
from hodl.tools import *
from hodl.state import *
from hodl.risk_control import *
from hodl.base_price_mixin import *
from hodl.sleep_mixin import *
from hodl.factor_mixin import *
from hodl.store import *
from hodl.storage import *
from hodl.exception_tools import *
from hodl.tools import FormatTool as FMT


@trade_strategy(strategy_name=TradeStrategyEnum.HODL)
class StoreHodl(Store, BasePriceMixin, SleepMixin, FactorMixin):
    def booting_check(self):
        trade_broker = self.broker_proxy.trade_broker
        if not trade_broker.ENABLE_BOOTING_CHECK:
            return
        try:
            self.logger.info(f'检查券商系统对接')
            self.broker_proxy.query_quote()
            self.logger.info(f'可返回行情')
            chip = self.current_chip()
            self.logger.info(f'可返回持仓')
            cash = self.current_cash()
            self.logger.info(f'可返回现金')
            assert isinstance(chip, int)
            assert isinstance(cash, float)
            self.logger.info(f'检查结束')
        except Exception as e:
            raise e

    def prepare_plan(self):
        sc, state, _ = self.args()
        # 新状态初次创建时, 因为不会更新symbol导致一些文案上的错误
        if state.quote_symbol is None:
            state.quote_symbol = sc.symbol
        if state.plan.cleanable:
            state.plan = Plan.new_plan(
                store_config=self.store_config,
            )
        state.plan.clean_orders()
        plan = state.plan

        if not plan.has_factors:
            if factors := sc.factors:
                sell_rate, buy_rate, weight = list(zip(*factors))
                plan.factor_type = 'custom'
            else:
                fear_greed_type, factors = self.auto_select_factors()
                weight = [factor[0] for factor in factors]
                sell_rate = [factor[1] for factor in factors]
                buy_rate = [factor[2] for factor in factors]
                plan.factor_type = fear_greed_type

            def _adjust_factor(sr: list[float], br: list[float], price_rate=1.0):
                sr = [FMT.adjust_precision((r - 1.0) * price_rate + 1.0, 5) for r in sr]
                br = [FMT.adjust_precision((r - 1.0) * price_rate + 1.0, 5) for r in br]
                return sr, br

            sell_rate, buy_rate = _adjust_factor(sell_rate, buy_rate, price_rate=plan.price_rate)
            plan.weight = weight
            plan.sell_rate = sell_rate
            plan.buy_rate = buy_rate
        assert plan.has_factors
        if plan.table_ready:
            self.build_table(store_config=sc, plan=plan).check_factors()

        current_enable = self.runtime_state.enable
        new_enable = self.store_config.enable
        if new_enable is True and current_enable is False:
            for order in plan.orders:
                if order.is_today:
                    continue
                state.chip_day = None
                state.chip_count = None
                state.cash_day = None
                state.cash_amount = None
                break
        self.runtime_state.enable = new_enable

    def prepare_market_status(self):
        state = self.state
        broker_name, broker_display, market_status = self.current_market_status()
        if time_str := self.store_config.closing_time:
            now_time_str = TimeTools.us_time_now().strftime('%H:%M:%S')
            if now_time_str >= time_str:
                market_status = 'CLOSING'
        state.market_status = market_status
        state.market_status_name = broker_name
        state.market_status_display = broker_display

    def prepare_quote(self):
        state = self.state

        try:
            quote = self.current_quote()
            state.quote_outdated = False
        except QuoteOutdatedError as ex:
            state.quote_outdated = True
            raise ex

        if not quote.open or quote.open <= 0:
            raise QuoteFieldError(f'{self.store_config.symbol}开盘价不正确: {quote.open}')
        if not quote.pre_close or quote.pre_close <= 0:
            raise QuoteFieldError(f'{self.store_config.symbol}昨收价不正确: {quote.pre_close}')
        state.quote_symbol = quote.symbol
        state.quote_time = quote.time.timestamp()
        state.quote_open = quote.open
        state.quote_status = quote.status
        state.quote_pre_close = quote.pre_close
        state.quote_latest_price = quote.latest_price
        state.quote_low_price = quote.day_low
        state.quote_high_price = quote.day_high
        state.quote_broker = quote.broker_name
        state.quote_broker_display = quote.broker_display

        db = self.db
        runtime_state = self.runtime_state
        quote_time = quote.time.timestamp()
        low_price = quote.day_low
        quote_day = int(TimeTools.date_to_ymd(TimeTools.from_timestamp(quote_time), join=False))

        if quote_time and low_price and db and (quote_day, low_price,) != runtime_state.low_price_compare:
            runtime_state.low_price_compare = (quote_day, low_price,)
            row = QuoteLowHistoryRow(
                broker=self.store_config.broker,
                region=self.store_config.region,
                symbol=self.store_config.symbol,
                day=quote_day,
                low_price=low_price,
                update_time=int(TimeTools.us_time_now().timestamp()),
            )
            row.save(con=db.conn)
        high_price = quote.day_high
        if quote_time and high_price and db and (quote_day, high_price,) != runtime_state.high_price_compare:
            runtime_state.high_price_compare = (quote_day, high_price,)
            row = QuoteHighHistoryRow(
                broker=self.store_config.broker,
                region=self.store_config.region,
                symbol=self.store_config.symbol,
                day=quote_day,
                high_price=high_price,
                update_time=int(TimeTools.us_time_now().timestamp()),
            )
            row.save(con=db.conn)

    def prepare_delete_state(self) -> int:
        orders = self.state.plan.orders
        total_sell = sum(order.filled_qty for order in orders if order.is_sell)
        total_buy = sum(order.filled_qty for order in orders if order.is_buy)
        if total_sell != total_buy:
            raise ValueError(f'当前计划存在买卖股票的差额')
        count = 0
        for order in orders:
            if not order.cancelable:
                continue
            self.broker_proxy.cancel_order(order=order)
            count += 1
        return count

    def prepare_chip(self):
        state = self.state
        chip_count = self.current_chip()
        state.chip_count = chip_count
        state.chip_day = TimeTools.us_day_now()

    def prepare_cash(self):
        state = self.state
        cash_amount = self.current_cash()
        state.cash_amount = cash_amount
        state.cash_day = TimeTools.us_day_now()

    def prepare_plug_in(self):
        state = self.state
        if not self.ENABLE_BROKER:
            state.trade_broker = '--'
            state.trade_broker_display = '--'
            return
        state.trade_broker = self.broker_proxy.trade_broker.BROKER_NAME
        state.trade_broker_display = self.broker_proxy.trade_broker.BROKER_DISPLAY
        if self.broker_proxy.detect_plug_in():
            text = f"""✅{state.full_name}连通已恢复"""
            state.is_plug_in = True
            self.bot.unset_alarm(AlertBot.K_TRADE_SERVICE, text=text, disable_notification=True)
        else:
            text = f"""🔌{state.full_name}连通测试失败"""
            state.is_plug_in = False
            self.bot.set_alarm(AlertBot.K_TRADE_SERVICE, text=text, disable_notification=True)
            raise PlugInError()

    def try_get_off(self):
        """
        如果没有把今天标记为收工日，
        并且发现有今天全部成交的买单，则标记今天为收工日(state.reset_day=<todayYMD>)
        :return:
        """
        state = self.state
        if state.is_today_get_off():
            return
        if state.plan.should_today_get_off:
            self.logger.info(f'判断有买单全成交，设置收工日为 {TimeTools.us_day_now()}')
            state.reset_day = TimeTools.us_day_now()

    def when_change_to_get_off(self):
        self.try_cancel_orders()
        self.try_buy_remain()
        self.set_up_earning()
        self.set_up_rework()

    def try_cancel_orders(self):
        self.logger.info(f'进入清盘环节')
        any_exception = False
        plan = self.state.plan
        orders = plan.orders
        for order in orders:
            if order.cancelable:
                self.logger.info(f'对订单{order}执行撤销')
                try:
                    self.cancel_order(order=order, wait=True)
                    self.logger.info(f'成功对订单{order}执行撤销')
                except Exception as e:
                    self.logger.exception(e)
                    self.bot.send_text(f'清盘时撤单操作失败[{e}]，请尽快手动撤销订单: {order}')
                    any_exception = True
        if not any_exception:
            assert plan.buy_order_active_count() == 0
            assert plan.sell_order_active_count() == 0

    def try_buy_remain(self):
        plan = self.state.plan
        volume = plan.total_volume_not_active(assert_zero=False)
        self.logger.info(f'清盘统计到现在买卖相差股数:{volume}')
        if volume < 0:
            raise ValueError(f'清盘计算相差股数:{volume}为负，可能因为多买')
        if volume:
            order = Order.new_config_order(
                store_config=self.store_config,
                level=0,
                direction='BUY',
                qty=volume,
                limit_price=None,
            )
            self.submit_order(
                order=order,
                wait=True,
            )
        self.logger.info(f'清盘订单全部成功完成')

    def set_up_earning(self) -> float:
        store_config, state, plan = self.args()
        symbol = store_config.symbol
        earning = plan.calc_earning()
        plan.earning = earning
        now = TimeTools.us_time_now()
        day_now = TimeTools.date_to_ymd(now)
        cash = FMT.pretty_price(earning, config=store_config, only_int=True)
        latest_order = plan.latest_today_buy_order()
        buyback_price = latest_order.avg_price
        start_date = plan.orders[0].create_timestamp
        start_date = TimeTools.from_timestamp(start_date)
        days = abs((now.date() - start_date.date()).days) + 1
        speed = earning / days
        speed = FMT.pretty_price(speed, config=store_config, only_int=True)
        buyback_text = FMT.pretty_price(buyback_price, store_config)

        earning_text = f'💰{state.full_name}在{day_now}收益{cash}, 买回价:{buyback_text}'
        if days > 1:
            earning_text += f', 持续{days}天, 平均日收益{speed}'
        self.logger.info(earning_text)
        assert earning >= 0

        plan.buy_back_price = buyback_price
        if db := self.db:
            earning_item = EarningRow(
                day=int(TimeTools.date_to_ymd(now, join=False)),
                symbol=symbol,
                currency=store_config.currency,
                days=days,
                amount=earning,
                unit=FMT.currency_to_unit(store_config.currency),
                region=store_config.region,
                broker=store_config.broker,
                buyback_price=buyback_price,
                max_level=plan.current_sell_level_filled(),
                state_version=self.state.version,
                create_time=int(TimeTools.us_time_now().timestamp()),
            )
            earning_item.save(con=db.conn)
            variable = self.runtime_state.variable
            if path := variable.earning_json_path:
                self.rewrite_earning_json(
                    db=self.db,
                    earning_json_path=path,
                    now=now,
                    weeks=variable.earning_recent_weeks,
                )
        error = self.bot.send_text(earning_text)
        if error:
            self.logger.warning(f'聊天消息发送失败: {error}')
        else:
            self.logger.info(f'聊天消息发送成功')
        return buyback_price

    def set_up_rework(self):
        store_config = self.store_config
        plan = self.state.plan
        buyback_price = plan.buy_back_price
        level = store_config.rework_level
        if not level:
            return
        if not self.enable_rework:
            return
        if level := store_config.rework_level:
            self.logger.info(f'设定清除持仓状态的价格等级为{level}')
            try:
                rework_plan = Plan.new_plan(
                    store_config=store_config,
                )
                rework_plan.base_price = self.calc_base_price()
                row = self.current_table().row_by_level(level=level)
                if row.sell_at > buyback_price:
                    price = row.sell_at
                    plan.rework_price = price
                    self.logger.info(f'设定清除持仓状态的价格为{FMT.pretty_price(price, config=store_config)}')
                else:
                    self.logger.info(f'该等级价格低于买入价，不设定清除持仓状态功能')
            except Exception as e:
                self.logger.warning(f'设置reworkPrice出现错误: {e}')

    def try_fire_orders(self):
        state = self.state
        if state.plan.earning is not None:
            state.plan = Plan.new_plan(
                store_config=self.store_config,
            )
        plan = state.plan
        if plan.base_price is None:
            price = self.calc_base_price()
            self.state.plan.base_price = price

        profit_table = self.current_table()
        state_fire = StateFire(profit_table=profit_table, market_price_rate=self.store_config.market_price_rate)
        self.try_fire_sell(fire_state=state_fire)
        self.try_fire_buy(fire_state=state_fire)

    def on_current_changed(self, current: str, new_current: str):
        if new_current == self.STATE_SLEEP and self.store_config.closing_time:
            logger = self.logger
            logger.info(f'进入定制的收盘时间段, 执行主动撤单')
            orders = self.state.plan.orders
            for order in orders:
                if not order.cancelable:
                    continue
                logger.info(f'开始撤销订单{order}')
                self.cancel_order(order=order)
                logger.info(f'撤销订单{order}成功')
        if current == self.STATE_TRADE and new_current == self.STATE_GET_OFF:
            self.when_change_to_get_off()

    def on_current(self, current: str):
        state = self.state

        try:
            if state.market_status == 'TRADING':
                self.assert_quote_time_diff()

                self.try_get_off()
                if state.is_today_get_off():
                    return

                try:
                    if not state.chip_day or state.chip_day != TimeTools.us_day_now():
                        self.prepare_chip()
                    if not state.cash_day or state.cash_day != TimeTools.us_day_now():
                        self.prepare_cash()
                    self.prepare_ta()
                except Exception as e:
                    error = PrepareError(str(e))
                    raise error

                quote_date = TimeTools.from_timestamp(state.quote_time)
                us_date = TimeTools.us_time_now()
                if quote_date.date() != us_date.date():
                    return
                if not state.quote_enable_trade:
                    return

                assert state.quote_pre_close
        except QuoteOutdatedError as e:
            raise e
        except Exception as e:
            self.logger.exception(f'更新收工状态/持仓/现金/行情时出现错误:{e}')
            raise PrepareError

        match current:
            case self.STATE_TRADE:
                self.try_fire_orders()

    def clear_error(self):
        alert_bot = self.bot
        if alert_bot:
            alert_bot.d = dict()
        if self.exception:
            self.exception = ''

    def loop_finally(self):
        self.risk_control = None
        self.after_loop()

    def run(self):
        super(Store, self).run()
        is_checked = False
        logger = self.logger
        logger.info(f'启动线程')
        TimeTools.thread_register(region=self.store_config.region)
        self.clear_error()

        while True:
            if self.ENABLE_BROKER and not is_checked:
                try:
                    self.booting_check()
                except Exception as e:
                    self.logger.exception('对接失败')
                    self.exception = e
                    return
                finally:
                    is_checked = True

            self.sleep()

            with self.thread_lock():
                try:
                    if not self.before_loop():
                        logger.info(f'循环开始前的检查要求退出')
                        break
                    if self.state.risk_control_break:
                        logger.error(f'风控标记系统禁止运行: {self.state.risk_control_detail}')
                        logger.error(
                            f'需要手动确定情况，若核对无问题可继续启动时，设置状态文件中字段riskControlBreak为false')
                        break

                    if self.ENABLE_LOG_ALIVE:
                        self.alive_logger.debug(f'开始处理循环')

                    order_checked = False
                    try:
                        self.prepare_plan()
                        self.prepare_plug_in()
                        self.prepare_market_status()
                        if self.state.market_status in {
                            'TRADING',
                            'CLOSING',
                        }:
                            self.refresh_orders()
                            order_checked = True
                        self.prepare_quote()
                    except QuoteFieldError as e:
                        if self.ENABLE_LOG_ALIVE:
                            self.alive_logger.warning(f'行情字段异常: {e}')
                        continue
                    except PlugInError:
                        continue
                    except PrepareError as e:
                        if self.ENABLE_LOG_ALIVE:
                            self.alive_logger.exception(e)
                        continue
                    except TypeError as e:
                        raise e
                    except Exception as e:
                        if self.ENABLE_LOG_ALIVE:
                            self.alive_logger.exception(f'更新状态字典/计划/市场状态/交易系统测试/订单时出现错误:{e}')
                        raise PrepareError
                    finally:
                        self.risk_control = RiskControl(
                            store_config=self.store_config,
                            margin_amount=self.margin_amount(),
                            state=self.state,
                            max_shares=self.state.plan.total_chips,
                            cash_balance_func=self.current_cash,
                            latest_price=self.state.quote_latest_price,
                            order_checked=order_checked,
                        )

                    state = self.state
                    market_status, current, new_current = state.market_status, state.current, state.current
                    enable = self.store_config.enable
                    match current:
                        case self.STATE_SLEEP:
                            # 被抑制 -> 监控中
                            if market_status == 'TRADING' and enable and not state.is_today_get_off():
                                new_current = self.STATE_TRADE
                        case self.STATE_TRADE:
                            # 监控中 -> 被抑制
                            # 监控中 -> 已套利
                            if not enable:
                                new_current = self.STATE_SLEEP
                            elif market_status != 'TRADING':
                                new_current = self.STATE_SLEEP
                            elif state.is_today_get_off():
                                new_current = self.STATE_GET_OFF
                        case self.STATE_GET_OFF:
                            # 已套利 -> 被抑制
                            if not state.is_today_get_off():
                                new_current = self.STATE_SLEEP
                        case _:
                            # 无效状态 -> 被抑制
                            new_current = self.STATE_SLEEP
                    state.current = new_current

                    if current != new_current:
                        now = FMT.pretty_dt(TimeTools.us_time_now())
                        market_status, quote_status = self.state.market_status, self.state.quote_status
                        logger.info(f'状态改变: {current} -> {new_current}')
                        logger.info(f'状态: 当前日期 {now}, 市场状态: {market_status}, 标的状态: {quote_status}')
                        self.on_current_changed(current=current, new_current=new_current)

                    self.on_current(current=new_current)

                    if self.ENABLE_LOG_ALIVE:
                        self.alive_logger.debug(f'循环执行结束')
                except RiskControlError as e:
                    self.logger.error(f'触发风控异常: {e}')
                    self.state.risk_control_break = True
                    self.state.risk_control_detail = str(e)
                    self.exception = e
                    break
                except BotError as e:
                    if e.thread_killer:
                        self.logger.exception(f'特定异常终止了执行: {e}')
                        self.exception = e
                        break
                    else:
                        self.logger.warning(f'流程异常: {e}')
                        if self.SHOW_EXCEPTION_DETAIL:
                            self.logger.exception(f'流程异常: {e}')
                except Exception as e:
                    self.logger.exception(f'异常终止了执行: {e}')
                    self.exception = e
                    break
                finally:
                    self.loop_finally()
        self.logger.info('退出处理循环，程序结束')


__all__ = ["StoreHodl"]
