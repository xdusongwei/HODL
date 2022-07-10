

class TuiConfig(dict):
    @property
    def name(self):
        return self.get('name', '')

    @property
    def manager_url(self):
        return self.get('manager_url')

    @property
    def profit_url(self):
        return self.get('profit_url')

    @property
    def border_style(self):
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


__all__ = ['TuiConfig', ]
