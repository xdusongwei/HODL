import json


class DictWrapper:
    def __init__(self, d: dict = None):
        if d is None:
            d = dict()
        self.d = d

    def copy(self):
        d = json.loads(json.dumps(self.d))
        return self.__class__(d)

    def change_d(self, wrapper: 'DictWrapper'):
        d = json.loads(json.dumps(wrapper.d))
        self.d.clear()
        self.d.update(d)


__all__ = ['DictWrapper', ]
