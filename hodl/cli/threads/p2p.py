import json
import zlib
import asyncio
from libp2p import *
from libp2p.crypto import *
from libp2p.data_store import *
from libp2p.dht import *
from libp2p.routed_host import *
from libp2p.pubsub import *
from hodl.store import *
from hodl.thread_mixin import *
from hodl.tools import *


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
        self.pk = '--'
        self.pub_sum = 0
        asyncio.set_event_loop(self.loop)

    def primary_bar(self) -> list[BarElementDesc]:
        bar = [
            BarElementDesc(
                content=f'🔑{self.pk}',
                tooltip=f'节点ID',
            ),
        ]
        if self.topic:
            bar.append(
                BarElementDesc(
                    content=f'📻{self.config.topic}',
                    tooltip=f'Topic名称',
                ),
            )
        return bar

    def secondary_bar(self) -> list[BarElementDesc]:
        bar = [
            BarElementDesc(
                content=f'🎞️{FormatTool.number_to_size(self.pub_sum)}',
                tooltip=f'Topic累计发送量',
            )
        ]
        return bar

    def prepare(self):
        super().prepare()

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
        self.ps = await PubSub.new_gossip(host)
        self.topic = await self.ps.join(self.config.topic)
        self.pk = host.id.string

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


__all__ = ['P2pThread', ]
