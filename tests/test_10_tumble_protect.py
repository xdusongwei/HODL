from hodl.quote import *
from hodl.unit_test import *
from hodl.storage import *
from hodl.tools import *


class TumbleProtectTestCase(HodlTestCase):
    """
    验证各种暴跌保护机制可以按照预期设定抑制交易行为。
    """

    def test_tp_ma(self):
        config = self.config().store_configs['TEST']
        config['base_price_tumble_protect'] = True
        tickets = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=10.0, open=10.0, latest=10.0, low=10.0, high=10.0, ),
            Tick(time='23-04-11T09:30:00-04:00:00', pre_close=10.0, open=5.0, latest=5.0, low=5.0, high=5.0, ),
            Tick(time='23-04-12T09:30:00-04:00:00', pre_close=5.0, open=5.01, latest=5.01, low=5.01, high=5.01, ),
            Tick(time='23-04-13T09:30:00-04:00:00', pre_close=5.01, open=5.02, latest=5.02, low=5.02, high=5.02, ),
            Tick(time='23-04-14T09:30:00-04:00:00', pre_close=5.02, open=5.03, latest=5.03, low=5.03, high=5.03, ),
            Tick(time='23-04-15T09:30:00-04:00:00', pre_close=5.03, open=5.04, latest=5.04, low=5.04, high=5.04, ),
            Tick(time='23-04-16T09:30:00-04:00:00', pre_close=5.04, open=5.04, latest=5.04, low=5.04, high=5.04, ),
            Tick(time='23-04-17T09:30:00-04:00:00', pre_close=5.04, open=5.04, latest=5.04, low=5.04, high=5.04, ),
            Tick(time='23-04-18T09:30:00-04:00:00', pre_close=5.04, open=5.04, latest=5.04, low=5.04, high=5.04, ),
            Tick(time='23-04-19T09:30:00-04:00:00', pre_close=5.04, open=5.04, latest=5.04, low=5.04, high=5.04, ),
        ]
        db = LocalDb(':memory:')
        store = SimulationBuilder.from_config(store_config=config, db=db, ticks=tickets)
        _, state, _ = store.args()
        assert not state.ta_tumble_protect_flag
        assert state.bp_function == 'min'

        tickets = [
            Tick(time='23-04-20T09:30:00-04:00:00', pre_close=5.04, open=5.04, latest=5.04, low=5.04, high=5.04, ),
            Tick(time='23-04-20T09:31:00-04:00:00', pre_close=5.04, open=5.04, latest=5.04, low=5.04, high=5.04, ),
        ]
        store = SimulationBuilder.resume(store=store, ticks=tickets)
        _, state, _ = store.args()
        assert state.ta_tumble_protect_flag
        assert state.ta_tumble_protect_alert_price
        assert state.ta_tumble_protect_ma5 or state.ta_tumble_protect_ma10
        assert state.bp_function == 'max'
        store.call_bars()

    def test_tp_vix(self):
        class _Store(SimulationStore):
            def _query_vix(self) -> VixQuote:
                return VixQuote(
                    latest_price=30.0,
                    day_high=30.0,
                    day_low=20.0,
                    time=TimeTools.us_time_now(),
                )
        config = self.config().store_configs['TEST']
        config['vix_tumble_protect'] = 30
        tickets = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=10.0, open=10.0, latest=10.0, low=10.0, ),
            Tick(time='23-04-10T09:31:00-04:00:00', pre_close=10.0, open=10.0, latest=20.0, low=10.0, ),
        ]
        store = SimulationBuilder.from_config(store_config=config, store_type=_Store, ticks=tickets)
        _, state, plan = store.args()
        assert state.bp_function == 'max'
        assert state.ta_vix_high == 30.0
        assert len(plan.orders) == 0
        store.call_bars()

    def test_tp_rsi(self):
        config = self.config().store_configs['TEST']
        config['tumble_protect_rsi'] = True
        tickets = [
            Tick(time='23-04-10T09:30:00-04:00:00', pre_close=10.0, open=10.0, latest=10.0, low=10.0, high=10.0),
            Tick(time='23-04-11T09:30:00-04:00:00', pre_close=10.0, open=9.0, latest=9.0, low=9.0, high=9.0),
            Tick(time='23-04-12T09:30:00-04:00:00', pre_close=9.0, open=8.0, latest=8.0, low=8.0, high=8.0),
            Tick(time='23-04-13T09:30:00-04:00:00', pre_close=8.0, open=9.0, latest=9.0, low=9.0, high=9.0),
            Tick(time='23-04-13T20:00:00-04:00:00', ms='CLOSING', pre_close=8.0, open=9.0, latest=9.0, low=9.0, high=9.0),
            Tick(time='23-04-14T09:30:00-04:00:00', pre_close=9.0, open=8.0, latest=8.0, low=8.0, high=8.0),
            Tick(time='23-04-14T09:31:00-04:00:00', pre_close=9.0, open=8.0, latest=8.0, low=8.0, high=8.0),
            Tick(time='23-04-14T09:32:00-04:00:00', pre_close=9.0, open=8.0, latest=8.0, low=8.0, high=8.0),
            Tick(time='23-04-14T09:33:00-04:00:00', pre_close=9.0, open=8.0, latest=8.0, low=8.0, high=8.0),
            Tick(time='23-04-14T20:00:00-04:00:00', ms='CLOSING', pre_close=9.0, open=8.0, latest=8.0, low=8.0, high=8.0),
            Tick(time='23-04-15T09:30:00-04:00:00', pre_close=8.0, open=7.0, latest=7.0, low=7.0, high=7.0),
            Tick(time='23-04-16T09:30:00-04:00:00', pre_close=7.0, open=6.0, latest=6.0, low=6.0, high=6.0),
            Tick(time='23-04-16T09:31:00-04:00:00', pre_close=7.0, open=6.0, latest=6.0, low=6.0, high=6.0),
            Tick(time='23-04-16T09:32:00-04:00:00', pre_close=7.0, open=6.0, latest=6.0, low=6.0, high=6.0),
        ]
        db = LocalDb(':memory:')
        store = SimulationBuilder.from_config(store_config=config, db=db, ticks=tickets)
        _, state, _ = store.args()
        assert state.bp_function == 'max'
        assert state.ta_tumble_protect_rsi == config.tumble_protect_rsi_unlock_limit
        assert state.ta_tumble_protect_rsi_period == config.tumble_protect_rsi_period
        store.call_bars()

        tickets = [
            Tick(time='23-04-17T09:30:00-04:00:00', pre_close=6.0, open=10.0, latest=10.0, low=10.0, high=10.0),
            Tick(time='23-04-18T09:30:00-04:00:00', pre_close=10.0, open=15.0, latest=15.0, low=15.0, high=15.0),
            Tick(time='23-04-19T09:30:00-04:00:00', pre_close=15.0, open=20.0, latest=20.0, low=20.0, high=20.0),
        ]
        store = SimulationBuilder.resume(store=store, ticks=tickets)
        _, state, _ = store.args()
        assert state.bp_function == 'min'
        assert state.ta_tumble_protect_rsi is None
        store.call_bars()

