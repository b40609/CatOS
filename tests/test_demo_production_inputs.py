from decimal import Decimal
import unittest

from catos import demo_production_inputs, ipc


D = Decimal


def public_row(**overrides):
    row = dict(
        instId="BTC-USDT-SWAP",
        state="live",
        ctType="linear",
        ctVal="0.01",
        ctMult="1",
        ctValCcy="BTC",
        settleCcy="USDT",
        tickSz="0.1",
        lotSz="0.01",
        minSz="0.01",
    )
    row.update(overrides)
    return row


class DemoProductionInputsTests(unittest.TestCase):
    def test_pinned_inputs_round_trip(self):
        inputs = demo_production_inputs.catosv1_demo_inputs()
        self.assertEqual(inputs.bot_id, "sma-trend-btc-usdt-swap-v1")
        ipc.token(inputs.bot_id, "bot_id")
        self.assertEqual(ipc.WorkerConfig.from_wire(inputs.config.to_wire()), inputs.config)
        self.assertEqual(inputs.config.contract.inst_id, "BTC-USDT-SWAP")
        self.assertEqual(inputs.config.contract.base_per_contract, D("0.01"))
        self.assertEqual(inputs.config.contract.tick_size, D("0.1"))
        self.assertEqual(inputs.config.contract.lot_size, D("0.01"))
        self.assertEqual(inputs.config.contract.min_size, D("0.01"))
        self.assertEqual(inputs.config.timeframe_ms, 900_000)
        self.assertEqual(inputs.config.warmup_bars, 2)
        self.assertEqual(inputs.fixture_budget, D("100"))
        self.assertEqual(inputs.risk_limits.leverage, D("3.0"))
        self.assertEqual(inputs.risk_limits.symbol_share, D("0.50"))
        self.assertEqual(inputs.risk_limits.soft_loss, D("0.10"))
        self.assertEqual(inputs.risk_limits.hard_loss, D("0.20"))

    def test_current_public_instrument_contract_is_accepted(self):
        demo_production_inputs.verify_okx_public_instrument(public_row())

    def test_public_instrument_drift_fails_closed(self):
        for field, value in (
            ("state", "suspend"),
            ("ctVal", "0.001"),
            ("tickSz", "1"),
            ("lotSz", "1"),
            ("minSz", "1"),
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(
                        demo_production_inputs.DemoProductionInputsError,
                        "instrument_metadata_mismatch"):
                    demo_production_inputs.verify_okx_public_instrument(
                        public_row(**{field: value}))


if __name__ == "__main__":
    unittest.main()
