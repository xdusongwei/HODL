import json
import zlib
import asyncio
import dataclasses
from libp2p import *
from libp2p.crypto import *
from libp2p.data_store import *
from libp2p.dht import *
from libp2p.routed_host import *
from libp2p.pubsub import *
from hodl.thread_mixin import *
from hodl.tools import *


@dataclasses.dataclass
class HostResult:
    host: Host = dataclasses.field()
    dht: DHT = dataclasses.field(default=None)


class P2pThread(ThreadMixin):
    def __init__(self, p2p_config: P2pConfig):
        self.config = p2p_config
        self.pub_create_time = TimeTools.utc_now()
        self.lock = asyncio.Lock()
        self.host: Host = None
        self.ps: PubSub = None
        self.topic: Topic = None

    def prepare(self):
        super().prepare()

    def run(self):
        super().run()

    async def make_host(
            self,
            sk: bytes,
            use_dht=False,
            dht_bootstrap=None,
            opts=None,
            dht_opts=None,
            connect_list=None,
            provide_cid=False,
    ):
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
            await asyncio.sleep(1)
            host = RoutedHost(host, dht)
            if provide_cid:
                cid = self.config.cid
                await dht.provide(cid, brdcst=True)
        if dht_bootstrap or connect_list:
            for address in (dht_bootstrap or list()) + (connect_list or list()):
                try:
                    await host.connect(address)
                except Exception as e:
                    print(f"connect {address.id} error: {e}")
        self.host = host
        self.ps = await PubSub.new_gossip(host)
        self.topic = await self.ps.join(self.config.topic)

    async def publish(self, d: dict):
        j = json.dumps(d)
        z = zlib.compress(j.encode('utf8'))
        async with self.lock:
            await self._publish(z)

    async def _publish(self, b: bytes):
        now = TimeTools.utc_now()
        if TimeTools.timedelta(self.pub_create_time, minutes=15) < now:
            self.pub_create_time = now
            if self.topic:
                await self.topic.close()
                self.topic = await self.ps.join(self.config.topic)
        await self.topic.publish(b)


__all__ = ['P2pThread', ]
