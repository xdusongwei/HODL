

class TuiConfig(dict):
    @property
    def manager_url(self):
        """
        manager文件的url地址，这是tui命令必要的
        """
        return self.get('manager_url')

    @property
    def earning_url(self):
        return self.get('earning_url')

    @property
    def period_seconds(self) -> int:
        return self.get('period_seconds', 4)

    @property
    def show_broker_display(self) -> bool:
        return self.get('show_broker_display', True)


__all__ = ['TuiConfig', ]
