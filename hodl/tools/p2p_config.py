from libp2p.cid import Cid
from libp2p.peer import Peer
from libp2p.main import AddrInfo


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
    def listen(self) -> list[str]:
        return self.get('listen', list())

    @property
    def protocol_prefix(self) -> str:
        return self.get('protocol_prefix', None)

    @property
    def master_pks(self) -> list[str]:
        return self.get('master_pks', list())

    @property
    def beacons(self) -> list[AddrInfo]:
        beacons = self.get('beacons', list())
        result = list()
        for beacon in beacons:
            addr = AddrInfo(
                peer_id=Peer.decode(beacon['peer']),
                addrs=beacon['addrs'],
            )
            result.append(addr)
        return result

    @property
    def topic(self) -> str:
        return self.get('topic', None)

    @property
    def cid(self) -> None | Cid:
        code: int = self.get('cid_code', None)
        key: str = self.get('cid_key', None)
        if code and key:
            return Cid(codec_type=code, key=key.encode('utf8'))
        return None


__all__ = ['P2pConfig', ]
