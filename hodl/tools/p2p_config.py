

class P2pConfig(dict):
    @property
    def enable(self) -> bool:
        return self.get('enable', False)

    @property
    def secret_key(self) -> None | bytes:
        sk = self.get('sk', None)
        if isinstance(sk, str):
            return bytes.fromhex(sk)
        return None

    @property
    def addrs(self) -> list[str]:
        return self.get('addrs', list())

    @property
    def beacons(self) -> list[dict]:
        return self.get('beacons', list())

    @property
    def topic(self) -> str:
        return self.get('topic', None)


__all__ = ['P2pConfig', ]
