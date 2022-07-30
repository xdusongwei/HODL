

class TuiConfig(dict):
    @property
    def name(self):
        return self.get('name', '')

    @property
    def manager_url(self):
        """
        manager文件的url地址，这是tui命令必要的
        """
        return self.get('manager_url')

    @property
    def profit_url(self):
        """
        profit json文件的url地址，这是tui命令必要的
        """
        return self.get('profit_url')

    @property
    def border_style(self):
        """
        tui边框的颜色
        """
        return self.get('border_style', 'yellow')

    @property
    def sleep_sound(self):
        return self.get('sleep_sound', None)

    @property
    def trading_sound(self):
        return self.get('trading_sound', None)

    @property
    def profit_width(self):
        return self.get('profit_width', None)

    @property
    def display_process_time(self):
        """
        展示持仓的处理耗时在名称后面，单位是毫秒
        """
        return self.get('display_process_time', False)

    @property
    def display_chip_rate(self):
        """
        展示持仓剩余股票的比例在名称后面，单位是百分比
        """
        return self.get('display_chip_rate', False)

    @property
    def order_filled_notification(self):
        """
        订单成交提醒，仅windows10+系统
        """
        return self.get('order_filled_notification', False)


__all__ = ['TuiConfig', ]
