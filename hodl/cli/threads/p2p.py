import json
import zlib
import struct
import asyncio
from typing import Self, Type
import msgpack
from Crypto.Cipher import AES
from libp2p import *
from libp2p.crypto import *
from libp2p.data_store import *
from libp2p.dht import *
from libp2p.peer import *
from libp2p.routed_host import *
from libp2p.pubsub import *
from hodl.store import *
from hodl.thread_mixin import *
from hodl.tools import *


class MpMessage(dict):
    @property
    def compressed(self) -> bool:
        return self.get('compressed', False)

    @property
    def encrypted(self) -> bool:
        return self.get('encrypted', False)

    def verify(self, peer_id: str = None) -> bool:
        pk = PubKey.unmarshal(self.pk)
        if peer_id:
            peer_from_pk = Peer.from_public_key(pk).string
            if peer_from_pk != peer_id:
                return False
        return pk.verify(self.bytes, self.sign)

    @property
    def sign(self) -> bytes:
        return self.get('sign')

    @property
    def pk(self) -> bytes:
        return self.get('pk')

    @property
    def bytes(self) -> bytes:
        return self.get('content')

    def unwrap(
            self,
            t: Type[dict] = dict,
            aes_key: bytes = None,
    ) -> dict:
        b = self.bytes
        if self.encrypted:
            if not aes_key:
                raise ValueError(f'加密数据需要设定密钥用来解密')
            if len(b) <= 32:
                raise ValueError(f'加密数据长度无效')
            nonce, tag, cipher_text = b[0:16], b[16:32], b[32:]
            cipher = AES.new(aes_key, AES.MODE_EAX, nonce)
            b = cipher.decrypt_and_verify(cipher_text, tag)
        if self.compressed:
            b = zlib.decompress(b)
        d = msgpack.loads(b)
        return t(d)

    @classmethod
    async def read_from_stream(cls, s: Stream) -> Self:
        _, length = await s.read_bytes(4)
        length: int = struct.unpack('<L', length)[0]
        _, b = await s.read_bytes(length)
        msg = cls.read_from_bytes(b, peer_id=s.id)
        return msg

    @classmethod
    async def write_to_stream(cls, b: bytes, s: Stream):
        length = struct.pack('<L', len(b))
        await s.write(length)
        await s.write(b)

    @classmethod
    def read_from_bytes(
            cls,
            b: bytes,
            peer_id: str = None,
    ) -> Self:
        d = msgpack.loads(b)
        msg = MpMessage(d)
        if not msg.verify(peer_id=peer_id):
            raise ValueError(f'签名验证失败')
        return msg

    @classmethod
    def make_message(
            cls,
            d: dict,
            sk: PrivKey,
            pk: PubKey,
            aes_key: bytes = None,
            *,
            compress: bool = False,
    ) -> bytes:
        b = msgpack.dumps(d)
        if compress:
            b = zlib.compress(b)
        if aes_key:
            cipher = AES.new(aes_key, AES.MODE_EAX)
            cipher_text, tag = cipher.encrypt_and_digest(b)
            nonce = cipher.nonce
            b = nonce + tag + cipher_text
        sign = sk.sign(b)
        d = {
            'compressed': bool(compress),
            'encrypted': bool(aes_key),
            'sign': sign,
            'pk': pk.marshal(),
            'content': b,
        }
        return msgpack.dumps(d)


class P2pThread(ThreadMixin):
    def __init__(self, p2p_config: P2pConfig, stores: list[Store],):
        self.config = p2p_config
        self.pub_create_time = TimeTools.utc_now()
        self.lock = asyncio.Lock()
        self.host: Host = None
        self.ps: PubSub = None
        self.topic: Topic = None
        self.stores = stores
        self.loop = asyncio.new_event_loop()
        self.topic_reset_minutes = 15
        self.sk: PrivKey = None
        self.pk: PubKey = None
        self.pub_sum = 0
        self.aes_key = None
        asyncio.set_event_loop(self.loop)

    def primary_bar(self) -> list[BarElementDesc]:
        key_type = self.pk.type.name if self.pk else '--'
        peer_id = self.host.id if self.host else '--'
        bar = [
            BarElementDesc(
                content=f'🔑{key_type}',
                tooltip=f'节点ID: {peer_id}',
            ),
        ]
        if self.topic:
            bar.append(
                BarElementDesc(
                    content=f'📻{self.config.topic}',
                    tooltip=f'topic名称',
                ),
            )
        return bar

    def secondary_bar(self) -> list[BarElementDesc]:
        bar = [
            BarElementDesc(
                content=f'🎞️{FormatTool.number_to_size(self.pub_sum)}',
                tooltip=f'topic累计发送量',
            )
        ]
        return bar

    def prepare(self):
        super().prepare()
        self.topic_reset_minutes = self.config.topic_reset_minutes
        self.aes_key = self.config.aes_key

    def run(self):
        super().run()

        async def _run():
            opts = [SecurityNoise, SecurityTls, EnableRelay, ]
            dht_opts = [Mode(DhtModeEnum.ModeAuto), ProtocolPrefix(self.config.protocol_prefix), ]
            await self.make_host(
                sk=self.config.secret_key,
                use_dht=True,
                opts=opts,
                dht_opts=dht_opts,
                dht_bootstrap=self.config.beacons,
                cid=self.config.cid,
            )
            for store in self.stores:
                store.on_state_changed.add(self.on_state_changed)
            while True:
                await asyncio.sleep(1)
        self.loop.run_until_complete(_run())

    def on_state_changed(self, store: Store):
        state = store.state
        self.loop.call_soon_threadsafe(asyncio.create_task, self.publish(state))

    async def make_host(
            self,
            sk: bytes,
            use_dht=False,
            dht_bootstrap=None,
            opts=None,
            dht_opts=None,
            connect_list=None,
            cid=None,
    ):
        dht = None
        if self.config.secret_key:
            sk = PrivKey.unmarshal(sk)
        else:
            sk, _ = crypto_generate_keypair(KeyType.Ed25519, 0)
        base_opts = [
            ListenAddrStrings(*self.config.listen),
            Identity(sk),
        ]
        if opts:
            opts = base_opts + opts
        else:
            opts = base_opts
        host = Host(*opts)
        if use_dht:
            data_store = MapDataStore()
            mutex_data_store = MutexDataStore(data_store)
            dht_opts = dht_opts or list()
            if dht_bootstrap:
                dht_opts.append(BootstrapPeers(*dht_bootstrap), )
            dht = await DHT.new(
                host,
                DataStore(mutex_data_store),
                *dht_opts,
            )
            await dht.bootstrap()
            host = RoutedHost(host, dht)
        if dht_bootstrap or connect_list:
            for address in (dht_bootstrap or list()) + (connect_list or list()):
                try:
                    await host.connect(address)
                except Exception as e:
                    print(f"connect {address.id} error: {e}")
        if dht and cid:
            try:
                await dht.provide(cid, brdcst=True)
            except Exception as e:
                print(f'注册Cid资源失败:{e}')
        self.host = host
        self.sk = sk
        self.pk = sk.get_public
        self.ps = await PubSub.new_gossip(host)
        self.topic = await self.ps.join(self.config.topic)
        self.host.set_stream_handler('/hodl/admin', self.admin)

    async def admin(self, s: Stream):
        if self.config.master_pks and s.id not in self.config.master_pks:
            resp = MpMessage.make_message(
                {
                    'type': 'unknown',
                    'code': 403,
                    'result': False,
                },
                sk=self.sk,
                pk=self.pk,
                aes_key=self.aes_key,
                compress=True,
            )
            await MpMessage.write_to_stream(resp, s)
            await s.close()
            return
        req = await MpMessage.read_from_stream(s)
        d: dict = req.unwrap(dict, aes_key=self.aes_key)
        match d.get('type'):
            case 'status':
                resp = MpMessage.make_message(
                    {
                        'type': d.get('type'),
                        'code': 200,
                        'result': True,
                        'storeCount': len(self.stores),
                    },
                    sk=self.sk,
                    pk=self.pk,
                    aes_key=self.aes_key,
                    compress=True,
                )
                await MpMessage.write_to_stream(resp, s)
            case _:
                resp = MpMessage.make_message(
                    {
                        'type': 'unknown',
                        'code': 404,
                        'result': False,
                    },
                    sk=self.sk,
                    pk=self.pk,
                    aes_key=self.aes_key,
                    compress=True,
                )
                await MpMessage.write_to_stream(resp, s)
        await s.close()

    async def publish(self, d: dict):
        if not self.topic:
            return
        j = json.dumps(d)
        z = zlib.compress(j.encode('utf8'))
        async with self.lock:
            await self._publish(z)

    async def _publish(self, b: bytes):
        now = TimeTools.utc_now()
        if TimeTools.timedelta(self.pub_create_time, minutes=self.topic_reset_minutes) < now:
            self.pub_create_time = now
            if self.topic:
                await self.topic.close()
                self.topic = await self.ps.join(self.config.topic)
        await self.topic.publish(b)
        self.pub_sum += len(b)


__all__ = [
    'MpMessage',
    'P2pThread',
]
