"""Isolated synthetic self-tests; never contact a provider or product DB."""

from dataclasses import replace
from decimal import localcontext
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from catos.dcm import DAY, HOUR, D, DCMFrame, DCMParams, DCMStrategy, levels
from catos.dcm_public_data import Collector, ENDPOINTS, SYMBOL, TIMEFRAMES, public_get
from catos.dcm_study import load_snapshot, rank_training, round_trips, select_families, study, summarize
from catos.research import AccountView, BacktestConfig, Candle, ContractSpec, FundingEvent, _CONTEXT, backtest


def flat(position="0", time=0):
    return AccountView(time, D(position), D("100"), D("1000"), D(0), D(0), D("1000"), D(0), D(0))


def bar(time=0, close="111", low="109", high="113", opening=None):
    return Candle(time, D(opening or close), D(high), D(low), D(close))


def configured(candidate, strength="0.05", regime=1, compressed=True):
    params = DCMParams(candidate, HOUR, ma_days=2, short_days=2, atr_days=2, compression_days=2)
    instance = DCMStrategy(params)
    instance.frame = DCMFrame(0, -DAY, D(110), D(100), D(90), D(95), D(100), D(10), D(strength), regime, compressed)
    instance.previous_close = D(109)
    return instance


def synthetic_bars(days=16, step=HOUR):
    bars = []
    for index in range(days * DAY // step):
        day, offset = divmod(index * step, DAY)
        # Deterministic trends and spikes, all on a 0.1 tick. No random search.
        base = D(100 + day * 8)
        close = base + (D(8) if offset >= 12 * HOUR else D(0))
        opening = bars[-1].close if bars else base
        bars.append(Candle(index * step, opening, max(opening, close) + D(2), min(opening, close) - D(2), close))
    return tuple(bars)


class DCMRuleTests(unittest.TestCase):
    def test_source_formula_and_cap_are_preserved(self):
        with localcontext(_CONTEXT):
            dh, dc, dl = levels(D(110), D(100), D(108), False)
            self.assertEqual(dc, D(106))
            self.assertGreater(dh, D(110))
            self.assertLess(dl, D(100))
            wide = levels(D(200), D(50), D(100), True)
            self.assertEqual((wide[0], wide[2]), (D("109.5"), D("90.5")))

    def test_daily_context_excludes_current_day_final_close(self):
        params = DCMParams("A", HOUR, ma_days=2, short_days=2, atr_days=2, compression_days=2)
        instance = DCMStrategy(params)
        bars = synthetic_bars(5)
        for item in bars[:4 * 24]:
            instance.update_indicators(item)
        self.assertTrue(instance.ready)
        instance.update_indicators(bars[4 * 24])
        frozen = instance.frame
        self.assertEqual(frozen.reference_day_ms, 3 * DAY)
        for index in range(4 * 24 + 1, 5 * 24):
            instance.update_indicators(bar(index * HOUR, "1000", "1000", "1000"))
            self.assertEqual(instance.frame, frozen)
        self.assertIsNone(instance.event)
        self.assertEqual(instance.trace, [])

    def test_partial_first_day_never_becomes_reference_day(self):
        params = DCMParams("A", HOUR, ma_days=2, short_days=2, atr_days=2, compression_days=2)
        instance = DCMStrategy(params)
        for item in synthetic_bars(4)[1:]:
            instance.update_indicators(item)
        self.assertEqual(len(instance.days), 3)
        self.assertEqual(instance.days[0].day_ms, DAY)
        self.assertFalse(instance.ready)

    def test_gap_unconfirmed_and_alignment_are_rejected(self):
        instance = configured("A")
        instance.update_indicators(bar())
        with self.assertRaisesRegex(ValueError, "contiguous"):
            instance.update_indicators(bar(2 * HOUR))
        with self.assertRaises(ValueError):
            configured("A").update_indicators(replace(bar(), closed=False))
        with self.assertRaises(ValueError):
            configured("A").update_indicators(bar(1))

    def test_direct_breakout_and_compression_condition(self):
        self.assertEqual(configured("A").on_bar(bar(), flat()), D(1))
        self.assertEqual(configured("F").on_bar(bar(), flat()), D(1))
        self.assertIsNone(configured("F", compressed=False).on_bar(bar(), flat()))
        self.assertIsNone(configured("A", regime=-1).on_bar(bar(), flat()))

    def test_retest_requires_a_later_bar_and_frozen_levels(self):
        instance = configured("B")
        self.assertIsNone(instance.on_bar(bar(), flat()))
        self.assertIsNotNone(instance.event)
        instance.frame = replace(instance.frame, day_ms=DAY, dh=D(210), dc=D(200), dl=D(190))
        instance.previous_close = D(111)
        self.assertEqual(instance.on_bar(bar(HOUR, "112", "110", "114"), flat()), D(1))
        self.assertEqual(instance.trace[-1]["dh"], "110")
        self.assertEqual(instance.trace[-1]["decision_time_ms"], 2 * HOUR)

    def test_retest_can_expire_or_fail_without_entry(self):
        for stamp, close, reason in ((14 * HOUR, "111", "expired"), (HOUR, "107", "invalidated")):
            instance = configured("B")
            instance.on_bar(bar(), flat())
            instance.previous_close = D(111)
            self.assertIsNone(instance.on_bar(bar(stamp, close, "106", "113"), flat()))
            self.assertIsNone(instance.event)
            self.assertTrue(any(reason in item["reason"] for item in instance.trace))

    def test_failed_breakout_and_strong_trend_counterexample(self):
        instance = configured("D")
        self.assertIsNone(instance.on_bar(bar(), flat()))
        instance.previous_close = D(111)
        self.assertEqual(instance.on_bar(bar(HOUR, "108", "107", "112"), flat()), D(-1))
        self.assertEqual(instance._target, D(100))
        strong = configured("D", strength="0.2")
        strong.on_bar(bar(), flat())
        self.assertIsNone(strong.event)

    def test_pullback_and_neutral_rejection_are_distinct(self):
        pullback = configured("C")
        pullback.previous_close = D(99)
        self.assertEqual(pullback.on_bar(bar(0, "101", "99", "102"), flat()), D(1))
        neutral = configured("E", strength="0", regime=0)
        self.assertEqual(neutral.on_bar(bar(0, "92", "88", "93"), flat()), D(1))
        self.assertEqual(neutral._target, D(100))
        self.assertIsNone(configured("E").on_bar(bar(0, "92", "88", "93"), flat()))

    def test_short_symmetry_and_target_exit(self):
        short = configured("A", strength="-0.05", regime=-1)
        short.frame = replace(short.frame, ma=D(100))
        short.previous_close = D(91)
        self.assertEqual(short.on_bar(bar(0, "89", "88", "92"), flat()), D(-1))
        reversal = configured("D")
        reversal.on_bar(bar(), flat())
        reversal.previous_close = D(111)
        reversal.on_bar(bar(HOUR, "108", "107", "112"), flat())
        self.assertEqual(reversal.on_bar(bar(2 * HOUR, "99", "98", "109"), flat("-1")), D(0))
        self.assertEqual(reversal.trace[-1]["reason"], "exit:DC-target")

    def test_overnight_is_allowed_and_time_exit_is_closed_bar(self):
        instance = configured("E", strength="0", regime=0)
        instance.on_bar(bar(23 * HOUR, "92", "88", "93"), flat())
        self.assertIsNone(instance.on_bar(bar(25 * HOUR, "93", "92", "94"), flat("1")))
        self.assertEqual(instance.on_bar(bar(72 * HOUR, "93", "92", "94"), flat("1")), D(0))

    def test_core_execution_and_prefix_causality(self):
        bars = synthetic_bars(16)
        cfg = BacktestConfig(ContractSpec(SYMBOL, D("0.01"), D("0.1"), D(1), D(1)),
                             HOUR, D(1000), D("0.001"), D(2), ())
        p = DCMParams("A", HOUR, ma_days=2, short_days=2, atr_days=2, compression_days=2)
        original, changed = DCMStrategy(p), DCMStrategy(p)
        boundary = 10 * DAY
        mutated = tuple(item if item.open_time_ms < boundary else
                        replace(item, open=D(500), high=D(500), low=D(500), close=D(500)) for item in bars)
        first = backtest(strategy=lambda: original, candles=bars, config=cfg, warmup_bars=4 * 24)
        second = backtest(strategy=lambda: changed, candles=mutated, config=cfg, warmup_bars=4 * 24)
        self.assertTrue(first.trades)
        self.assertEqual([item for item in first.trades if item.time_ms < boundary],
                         [item for item in second.trades if item.time_ms < boundary])
        self.assertEqual([item for item in original.trace if item["decision_time_ms"] <= boundary],
                         [item for item in changed.trace if item["decision_time_ms"] <= boundary])
        for fill in first.trades:
            source = next(item for item in bars if item.open_time_ms == fill.time_ms)
            self.assertEqual(fill.time_ms, fill.decision_time_ms)
            self.assertGreaterEqual(fill.price, source.open) if fill.quantity > 0 else self.assertLessEqual(fill.price, source.open)
        self.assertTrue(all(item["decision_time_ms"] > 4 * DAY for item in original.trace))

    def test_invalid_parameter_types_are_rejected(self):
        for changes in ({"quantity": 1.0}, {"capped": 1}, {"ma_days": True}, {"timeframe_ms": 7 * HOUR}):
            with self.assertRaises((ValueError, TypeError)):
                replace(DCMParams("A", HOUR), **changes)

    def test_flat_complete_market_remains_ready_without_entries(self):
        p = DCMParams("A", HOUR, ma_days=2, short_days=2, atr_days=2, compression_days=2)
        instance = DCMStrategy(p)
        bars = tuple(bar(i * HOUR, "100", "100", "100") for i in range(6 * 24))
        cfg = BacktestConfig(ContractSpec(SYMBOL, D("0.01"), D("0.1"), D(1), D(1)),
                             HOUR, D(1000), D("0.001"), D(2), ())
        result = backtest(strategy=lambda: instance, candles=bars, config=cfg, warmup_bars=4 * 24)
        self.assertTrue(instance.ready)
        self.assertEqual(instance.frame.atr, D(0))
        self.assertEqual(result.trades, ())


class FakeProvider:
    """Public API-shaped local fixture; no socket or provider access."""

    def __init__(self, days=70):
        self.end = 100 * DAY
        self.start = self.end - days * DAY
        self.calls = []
        self.tables = {}
        for label, step in TIMEFRAMES.items():
            self.tables[("candles", label)] = [[str(item.open_time_ms), str(item.open), str(item.high), str(item.low),
                                                str(item.close), "10", "0.1", "10", "1"]
                                               for item in synthetic_bars(101, step)]
        self.tables[("marks", "1H")] = [[str(stamp), "100", "101", "99", "100", "1"]
                                          for stamp in range(0, self.end + HOUR, HOUR)]
        self.tables[("funding", None)] = [{"fundingTime": str(stamp), "realizedRate": "0.0001", "instId": SYMBOL}
                                         for stamp in range(0, self.end + HOUR, 8 * HOUR)]

    def __call__(self, endpoint, params):
        kind = next(key for key, path in ENDPOINTS.items() if path == endpoint)
        self.calls.append((kind, dict(params)))
        if kind == "time":
            data = [{"ts": str(self.end + DAY + 5 * HOUR)}]
        elif kind == "instrument":
            data = [{"instId": SYMBOL, "ctType": "linear", "settleCcy": "USDT", "ctValCcy": "BTC",
                     "ctVal": "0.01", "ctMult": "1", "tickSz": "0.1", "lotSz": "1", "minSz": "1"}]
        else:
            table = self.tables[(kind, params.get("bar"))]
            stamp = lambda row: int(row["fundingTime"] if kind == "funding" else row[0])
            data = sorted((row for row in table if stamp(row) < int(params["after"])), key=stamp, reverse=True)[:100]
        return {"code": "0", "data": data}


class SnapshotStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.provider = FakeProvider()
        cls.snapshot = cls.root / "snapshot"
        manifest = Collector(cls.snapshot, cls.provider, pause=lambda _: None, progress=lambda *a, **k: None).collect(70)
        manifest["kind"] = "synthetic"
        (cls.snapshot / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_fixed_public_get_allowlist_rejects_arbitrary_endpoints(self):
        with patch("catos.dcm_public_data.urlopen") as mocked:
            for endpoint, params in (("https://evil.example", {}), (ENDPOINTS["funding"], {"secret": "x"}),
                                     (ENDPOINTS["candles"], {"instId": "OTHER-USDT-SWAP"})):
                with self.assertRaises(ValueError):
                    public_get(endpoint, params)
            mocked.assert_not_called()

    def test_snapshot_is_complete_hashed_and_only_public_requests(self):
        manifest, datasets = load_snapshot(self.snapshot)
        self.assertEqual(manifest["kind"], "synthetic")
        self.assertEqual({len(bars) for bars, _ in datasets.values()}, {70 * 96, 70 * 24, 70 * 6})
        for kind, params in self.provider.calls:
            self.assertIn(kind, ENDPOINTS)
            self.assertFalse(set(params) & {"apikey", "secretkey", "passphrase"})
        self.assertTrue(manifest["funding_events"])
        self.assertIn("proxy", manifest["funding_mark_model"])

    def test_existing_output_is_never_overwritten(self):
        with self.assertRaises(FileExistsError):
            Collector(self.snapshot, self.provider, pause=lambda _: None).collect(70)
        with self.assertRaises(ValueError):
            study(self.snapshot, self.snapshot / "output")

    def test_bad_pagination_stops_and_saves_failure(self):
        provider = FakeProvider()
        original = provider.__call__

        def bad(endpoint, params):
            value = original(endpoint, params)
            if endpoint == ENDPOINTS["marks"]:
                value["data"][0][0] = params["after"]
            return value

        output = self.root / "bad-pagination"
        with self.assertRaisesRegex(ValueError, "older"):
            Collector(output, bad, pause=lambda _: None).collect(70)
        self.assertTrue((output / "collection-failed.json").exists())
        self.assertFalse((output / "manifest.json").exists())

    def test_hash_tampering_and_path_escape_are_rejected(self):
        with self.assertRaises(ValueError):
            from catos.dcm_study import safe_file
            safe_file(self.snapshot, "../outside.csv")
        target = self.snapshot / "15m.csv"
        original = target.read_bytes()
        try:
            target.write_bytes(original + b"\n")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                load_snapshot(self.snapshot)
        finally:
            target.write_bytes(original)

    def test_full_matrix_replay_and_selection_precedes_holdout(self):
        reports = []
        for label in ("first", "replay"):
            report = study(self.snapshot, self.root / label, progress=lambda *a, **k: None)
            reports.append(report)
            selection = json.loads((self.root / label / "selection-before-holdout.json").read_text(encoding="utf-8"))
            self.assertEqual(selection["selection_run_count"], 144)
            self.assertFalse(selection["holdout_used_for_selection"])
            self.assertEqual(len(report["runs"]), 150)
            self.assertFalse([row for row in report["runs"] if "error" in row])
            self.assertEqual({row["candidate"] for row in report["runs"]}, set("ABCDEF"))
            self.assertEqual({row["bar"] for row in report["runs"]}, set(TIMEFRAMES))
            self.assertEqual({row["key"] for row in report["runs"] if row["phase"] == "holdout"}, set(selection["shortlist"]))
            self.assertEqual(len({key.split('-')[0] for key in selection["shortlist"]}), 3)
            text = (self.root / label / "report.html").read_text(encoding="utf-8")
            self.assertIn("合成行為驗證", text)
            self.assertIn("未平部位", text)
            self.assertEqual(report["preregistration"]["optimization_trials"], 0)
            from catos.dcm_public_data import digest
            for name, expected in report["preregistration"]["source_hashes"].items():
                self.assertEqual(digest(self.root / label / "sources" / name), expected)
        self.assertEqual(reports[0], reports[1])

    def test_round_trip_funding_at_entry_and_exit_boundaries(self):
        from catos.research import Strategy

        class Script(Strategy):
            def update_indicators(self, bar):
                pass

            def on_bar(self, bar, account):
                return D(1) if bar.open_time_ms == 0 else D(0) if bar.open_time_ms == HOUR else None

        cfg = BacktestConfig(ContractSpec(SYMBOL, D(1), D(1), D(1), D(1)), HOUR, D(1000), D("0.01"), D(0),
                             (FundingEvent(HOUR, D("0.01"), D(100)), FundingEvent(2 * HOUR, D("0.01"), D(110))))
        bars = (bar(0, "100", "100", "100"), bar(HOUR, "110", "100", "110", "100"),
                bar(2 * HOUR, "110", "110", "110"))
        result = backtest(strategy=Script, candles=bars, config=cfg)
        with localcontext(_CONTEXT):
            trips, entry = round_trips(result)
            summary = summarize(result)
        self.assertIsNone(entry)
        self.assertEqual(trips[0]["funding_paid"], D("1.1"))
        self.assertEqual(trips[0]["net_pnl"], D("6.8"))
        self.assertEqual(summary["closed_net_pnl"], result.performance.net_pnl)
        self.assertEqual(summary["open_component_net_pnl"], D(0))

    def test_rank_uses_both_training_phases_and_cost_stress(self):
        rows = [{"key": "A", "summary": {"performance": {"net_pnl": D(value)}, "completed_trades": 6}}
                for value in ("10", "9", "8", "-1")]
        ranking = rank_training(rows)
        self.assertEqual(ranking[0]["robust_min_net_pnl"], D(-1))
        self.assertFalse(ranking[0]["qualifying"])

    def test_cap_duplicates_cannot_fill_all_holdout_slots(self):
        ranking = [{"key": key, "robust_min_net_pnl": D(1)} for key in
                   ("A-15m-cap", "A-15m-uncapped", "A-1H-cap", "B-1H-cap", "D-1H-cap")]
        self.assertEqual(select_families(ranking), ["A-15m-cap", "B-1H-cap", "D-1H-cap"])


if __name__ == "__main__":
    unittest.main()
