from rich.align import Align
from rich.console import Group
from rich.text import Text
from textual.widget import Widget
from textual.reactive import reactive
from hodl.store import *
from hodl.tools import *
from hodl.state import *
from hodl.store_base import *


def default_style(state: State):
    return 'white' if state.market_status == 'TRADING' else 'grey50'


class StorePanel(Widget):
    pairs_list: reactive[list[tuple[dict, dict, StoreConfig, State]]] = reactive(list)
    tui_config = VariableTools().tui_config

    def render(self):
        parts = list()
        for item in self.pairs_list:
            item: tuple[dict, dict, StoreConfig, State] = item
            thread, store, config, state = item
            default_color = default_style(state)
            text = Text(style=default_color)
            if self.tui_config.show_broker_display:
                text.append(f'[{state.trade_broker_display}]{config.symbol} {config.name}\n')
            else:
                text.append(f'[{config.region}]{config.symbol} {config.name}\n')

            tags = list()
            factor_type = state.plan.factor_type
            match factor_type:
                case 'custom':
                    tags.append('自定义')
                case 'fear':
                    tags.append('🙈恐慌')
                case 'neutral':
                    tags.append('😐中性')
                case 'greed':
                    tags.append('☺️贪婪')
                case _:
                    tags.append('未知')
            args = list()
            args.append('昨收')
            args.append('开盘')
            if config.base_price_last_buy:
                args.append('买回')
            if config.base_price_day_low:
                args.append('日低')
            tags.append(f'{state.bp_function}({",".join(args)})')
            text.append(f'策略: {"|".join(tags)}\n')
            state_bar = StoreBase.state_bar(
                thread_alive=not thread.get('dead'),
                config=config,
                state=state,
            )
            text.append(' '.join(elem.content for elem in state_bar) + '\n')
            parts.append(text)
        return Align.left(Group(*parts))


class StatusPanel(Widget):
    pairs_list: reactive[list[tuple[dict, dict, StoreConfig, State]]] = reactive(list)

    def render(self):
        parts = list()
        for item in self.pairs_list:
            item: tuple[dict, dict, StoreConfig, State] = item
            thread, store, config, state = item
            default_color = default_style(state)
            dt = f'{FormatTool.pretty_dt(state.quote_time, region=config.region, with_year=FormatTool)[:-10]}'
            latest = FormatTool.pretty_price(state.quote_latest_price, config=config)
            rate = FormatTool.factor_to_percent(state.quote_rate, fmt='{:+.2%}')

            color = 'green'
            if state.quote_latest_price and state.quote_pre_close:
                if state.quote_latest_price < state.quote_pre_close:
                    color = 'red'
            text = Text(style=default_color)
            text.append(f'[{config.region}]{config.symbol} {dt}\n')
            text.append(f'报价: ')
            text.append(f'{latest} {rate}\n', style=color)
            buff_bar = StoreBase.buff_bar(
                config=config,
                state=state,
                process_time=store.get('processTime'),
            )
            text.append('状态: ' + ''.join(elem.content for elem in buff_bar) + '\n')
            parts.append(text)
        return Align.left(Group(*parts))


class PlanPanel(Widget):
    pairs_list: reactive[list[tuple[dict, dict, StoreConfig, State]]] = reactive(list)

    @classmethod
    def cash_to_emoji(cls, n: int):
        icon = '🪙'
        if n >= 500:
            icon = '💰'
        if n >= 1000:
            icon = '💵'
        if n >= 2000:
            icon = '💎'
        return icon

    def render(self):
        parts = list()
        for item in self.pairs_list:
            item: tuple[dict, dict, StoreConfig, State] = item
            thread, store, config, state = item
            default_color = default_style(state)
            base_price = FormatTool.pretty_price(state.plan.base_price, config=config)
            profit_tool = Store.ProfitRowTool(config=config, state=state)
            text = Text(style=default_color)
            id_title = f'[{config.region}]{config.symbol}'
            if profit_tool.has_table and profit_tool.filled_level:
                total_rate = profit_tool.rows.row_by_level(profit_tool.filled_level).total_rate
                earning = profit_tool.earning_forecast(rate=total_rate)
                earning_text = FormatTool.pretty_price(earning, config=config, only_int=True)
                level = f'{profit_tool.filled_level}/{len(profit_tool.rows)}'
                text.append(f'{id_title}#{level} ')
                text.append(f'⏳{earning_text}\n', style='bright_green')
            else:
                text.append(id_title)
                if earning := state.plan.earning:
                    icon = self.cash_to_emoji(earning)
                    earning_text = FormatTool.pretty_price(earning, config=config, only_int=True)
                    earning_text = f' {icon}{earning_text}'
                    text.append(f'{earning_text}', style='bright_green')
                    if rework_price := state.plan.rework_price:
                        rework_price = FormatTool.pretty_price(rework_price, config=config)
                        text.append(f' 🔁{rework_price}')
                    text.append(f'\n')
                else:
                    text.append(' ')
                    tp_text = ''
                    if state.ta_tumble_protect_flag:
                        tp_text += '⚠️MA'
                    if state.ta_tumble_protect_rsi:
                        tp_text += '🚫RSI'
                    if state.plan.base_price is not None:
                        text.append(f'⚓️{base_price}')
                    text.append(f'{tp_text}\n')

            sell_at = sell_percent = buy_at = buy_percent = None
            sell_percent_color = buy_percent_color = 'red'
            if profit_tool.has_table:
                sell_at = profit_tool.sell_at
                sell_percent = profit_tool.sell_percent
                if sell_percent is not None:
                    if sell_percent < 0.10:
                        sell_percent_color = 'orange3'
                    if sell_percent < 0.05:
                        sell_percent_color = 'yellow1'
                    if sell_percent < 0.01:
                        sell_percent_color = 'bright_green'
                buy_at = profit_tool.buy_at
                buy_percent = profit_tool.buy_percent
                if buy_percent is not None:
                    if buy_percent < 0.10:
                        buy_percent_color = 'orange3'
                    if buy_percent < 0.05:
                        buy_percent_color = 'yellow1'
                    if buy_percent < 0.01:
                        buy_percent_color = 'bright_green'
            sell_percent = FormatTool.factor_to_percent(sell_percent, fmt='{:.1%}')
            buy_percent = FormatTool.factor_to_percent(buy_percent, fmt='{:.1%}')

            aim_icon = ''
            for order in state.plan.orders:
                if not order.is_waiting_filling:
                    continue
                if not order.is_sell:
                    continue
                if order.level != profit_tool.filled_level + 1:
                    continue
                aim_icon = '🎯'
                break
            text.append(f'卖出价: {aim_icon}{FormatTool.pretty_price(sell_at, config=config)}')
            if profit_tool.sell_percent is not None:
                text.append(f' 距离')
                text.append(sell_percent, style=sell_percent_color)
            text.append('\n')

            aim_icon = ''
            for order in state.plan.orders:
                if not order.is_waiting_filling:
                    continue
                if not order.is_buy:
                    continue
                if order.level != profit_tool.filled_level:
                    continue
                aim_icon = '🎯'
                break
            text.append(f'买回价: {aim_icon}{FormatTool.pretty_price(buy_at, config=config)}')
            if profit_tool.buy_percent is not None:
                text.append(f' 距离')
                text.append(buy_percent, style=buy_percent_color)
            text.append('\n')

            parts.append(text)
        return Align.left(Group(*parts))


__all__ = ['StorePanel', 'StatusPanel', 'PlanPanel', ]
