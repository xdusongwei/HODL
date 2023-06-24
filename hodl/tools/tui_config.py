

class TuiConfig(dict):
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
    def period_seconds(self) -> int:
        return self.get('period_seconds', 4)


__all__ = ['TuiConfig', ]
