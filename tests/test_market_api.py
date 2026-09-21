import json
from contextlib import redirect_stdout
from decimal import Decimal
from io import StringIO
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from catos.market_api import MarketIntelReader, create_app, inspect_database, main, serve
from catos.market_collectors import MarketCandle
from catos.market_dex import DexScope, parse_public_swap_rows
from catos.market_intel import MarketIntelStore
from catos.market_liquidity import LiquidityBatch, LiquiditySnapshot, LiquiditySourceRun
from catos.market_onchain import ONCHAIN_SOURCE
from catos.market_social import SocialAssetRef, parse_coinpaprika_social


SYMBOL = "BTC-USDT-SWAP"


class MarketApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "intel.sqlite"
        self.store = MarketIntelStore(self.path)
        self.addCleanup(self.store.close)
        self._seed()
        self.reader = MarketIntelReader(self.path)

    def _record_liquidity(self):
        complete = {
            "contract": "catos-spot-depth-2pct-v1",
            "threshold_pct": "2",
            "down_boundary_text": "98.49",
            "up_boundary_text": "102.51",
            "down_boundary_reached": True,
            "up_boundary_reached": True,
            "status": "complete_2pct",
            "book_scope": "single_venue_spot_orderbook",
            "observation_only": True,
            "smf_eligible": False,
        }
        partial = dict(complete)
        partial.update({
            "down_boundary_reached": False,
            "up_boundary_reached": False,
            "status": "partial_boundary_coverage",
        })
        batch = LiquidityBatch(
            symbol=SYMBOL,
            observed_at_ms=5_000,
            snapshots=(
                LiquiditySnapshot(
                    source="okx-spot-orderbook", venue="okx", symbol=SYMBOL,
                    pair="BTC-USDT", observed_at_ms=5_000, source_ms=4_999,
                    quote_currency="USDT", best_bid=Decimal("100"),
                    best_ask=Decimal("101"), mid=Decimal("100.5"),
                    down_2pct_cost=Decimal("200"), up_2pct_cost=Decimal("101"),
                    down_2pct_lower_bound=Decimal("200"),
                    up_2pct_lower_bound=Decimal("101"),
                    asymmetry=Decimal("0.3289036544850498338870431894"),
                    bid_levels=2, ask_levels=2, coverage=complete,
                ),
                LiquiditySnapshot(
                    source="binance-spot-orderbook", venue="binance", symbol=SYMBOL,
                    pair="BTCUSDT", observed_at_ms=5_000, source_ms=None,
                    quote_currency="USDT", best_bid=Decimal("100"),
                    best_ask=Decimal("101"), mid=Decimal("100.5"),
                    down_2pct_cost=None, up_2pct_cost=None,
                    down_2pct_lower_bound=Decimal("500"),
                    up_2pct_lower_bound=Decimal("404"), asymmetry=None,
                    bid_levels=2, ask_levels=2, coverage=partial,
                ),
            ),
            source_runs=(
                LiquiditySourceRun(
                    source="okx-spot-orderbook", venue="okx", symbol=SYMBOL,
                    pair="BTC-USDT", observed_at_ms=5_000, status="ok",
                    coverage=complete, issues=(),
                ),
                LiquiditySourceRun(
                    source="binance-spot-orderbook", venue="binance", symbol=SYMBOL,
                    pair="BTCUSDT", observed_at_ms=5_000, status="ok",
                    coverage=partial, issues=(),
                ),
            ),
            issues=(),
        )
        self.store.record_liquidity_batch(batch)

    def _seed(self):
        j = lambda value: json.dumps(value, separators=(",", ":"), sort_keys=True)
        c = self.store.connection
        c.execute(
            "INSERT INTO instrument VALUES (?,?,?,?,?,?,?)",
            (SYMBOL, SYMBOL, j(["OKX", "BINANCE"]), j([]), 1, 1000, 4000),
        )
        c.execute(
            "INSERT INTO market_snapshot VALUES (?,?,?,?,?,?,?,?,?)",
            ("m1", SYMBOL, 4000, "100", "1234567", "1.5", "8", None,
             j({"primary_market": "OKX", "issues": []})),
        )
        c.execute(
            "INSERT INTO derivative_snapshot VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (SYMBOL, 4000, "900", "1", "2", "3", "-0.0001", "1.2", "0.55", None,
             j({"oi": "OKX", "top_lsr": "BINANCE"})),
        )
        c.execute(
            "INSERT INTO feature_snapshot VALUES (?,?,?,?)",
            (SYMBOL, 4000, "feature-v1", j({"return_24h_pct": "8", "structure_state": "RANGE"})),
        )
        c.execute(
            "INSERT INTO flow_snapshot VALUES (?,?,?,?,?,?,?,?,?)",
            (SYMBOL, 4000, "250000", "0.55", 100, 3000, 4000, 1, j({"source": "fixture"})),
        )
        c.execute(
            "INSERT INTO smf_snapshot VALUES (?,?,?,?,?,?,?)",
            (SYMBOL, 4000, "55", "S", "fixture-smf-v1", None, None),
        )
        for view, state, score in (("flow", "ignition", "75"),
                                   ("opportunity", "active", "60"),
                                   ("risk", "watch", "50")):
            c.execute(
                "INSERT INTO view_state VALUES (?,?,?,?,?,?,?)",
                (SYMBOL, view, 4000, state, score, 0, j({"evaluation_status": "AVAILABLE"})),
            )
        c.execute(
            "INSERT INTO signal_hit VALUES (?,?,?,?,?,?,?,?)",
            ("s1", SYMBOL, 4000, "MOMENTUM", "signal-v1", j({"evaluation_status": "HIT"}),
             j({"abs_return_24h_pct_gte": "10"}), j(["m1"])),
        )
        l2_types = (
            "HIT", "AMBUSH", "ACCUMULATION", "HEAT", "MOMENTUM", "STRONG_MOMENTUM",
            "FUNDING_NEGATIVE_FLIP", "OI_SURGE", "EXTREME_LONG", "WHALE_ENTRY", "WHALE_EXIT",
            "TEAM_DISTRIBUTION", "COIL_BREAKOUT_LIGHT", "PURE_MOMENTUM",
        )
        disabled = {
            "HIT", "AMBUSH", "ACCUMULATION", "HEAT", "OI_SURGE", "EXTREME_LONG",
            "WHALE_ENTRY", "WHALE_EXIT", "COIL_BREAKOUT_LIGHT",
        }
        for signal_type in l2_types:
            status = "HIT" if signal_type == "MOMENTUM" else (
                "DISABLED_UNKNOWN_THRESHOLD" if signal_type in disabled else "MISS")
            c.execute(
                "INSERT INTO signal_state VALUES (?,?,?,?,?,?,?,?)",
                (SYMBOL, 4000, signal_type, status, "signal-v1",
                 j({"evaluation_status": status}), j({}), j(["m1"])),
            )
        for axis_type, selected in (("ALPHA_PLUS", 1), ("ALPHA", 0)):
            c.execute(
                "INSERT INTO cross_axis_evaluation VALUES (?,?,?,?,?,?,?,?,?)",
                (SYMBOL, 4000, axis_type, "HIT", selected, "yaozi-cross-axis-known-v1",
                 j({"pattern_strength": "75", "resonance": 3, "bullish": True, "smf_grade": "B"}),
                 j({"published_rule_only": True}), j(["m1"])),
            )
        for label_type, status, source_state in (
                ("OBSERVE", "HIT", True),
                ("DUMP_WARNING", "MISS", False),
                ("NEW_CANDIDATE", "MISSING_DATA", None)):
            c.execute(
                "INSERT INTO status_label_snapshot VALUES (?,?,?,?,?,?,?,?)",
                (SYMBOL, 4000, label_type, status, "yaozi-status-label-source-v1",
                 j({"source_explicit_state": source_state}),
                 j({"derivation": "not_reconstructed_private_gate"}), j(["surface:4000"])),
            )
        c.execute(
            "INSERT INTO pattern_hit VALUES (?,?,?,?,?,?)",
            ("p1", SYMBOL, 4000, "PREHEAT", 1, j({"evaluation_status": "HIT"})),
        )
        c.execute(
            "INSERT INTO cycle VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("c1", SYMBOL, 3000, None, "98", 4000, 1, "102", "97", "4.0816326530612244898",
             "-1.0204081632653061224", None),
        )
        c.execute(
            "INSERT INTO cycle_event VALUES (?,?,?,?,?,?,?)",
            ("e1", "c1", SYMBOL, 3000, "cycle_started", "flow", j({"price": "98"})),
        )
        c.execute(
            "INSERT INTO push_snapshot VALUES (?,?,?,?,?,?,?,?)",
            ("push1", SYMBOL, 4000, "flow_ignition", "c1",
             j({"price": "100", "active_l2": ["MOMENTUM"], "views": {"flow": {"state": "ignition"}}}),
             "feature-v1", "signal-v1"),
        )
        c.execute(
            "INSERT INTO forward_return VALUES (?,?,?,?,?,?,?,?)",
            ("push1", "24h", 86_404_000, "8", "12", "-5", "1.5", "2"),
        )
        c.execute(
            "INSERT INTO public_event_candidate VALUES (?,?,?,?,?,?,?)",
            (
                "public-candidate-fixture", "OI_POSITIVE_CHANGE", SYMBOL, 4000,
                j(["OI_BREAKOUT"]),
                j({
                    "contract": "catos_public_event_candidate_v1",
                    "threshold": None,
                    "threshold_status": "unknown_unpublished",
                    "yaozi_event_triggered": False,
                }),
                j([f"derivative:{SYMBOL}:4000"]),
            ),
        )
        c.execute(
            "INSERT INTO public_context_run VALUES (?,?,?,?,?)",
            ("coingecko-categories", "narrative", 4000, "ok", j([])),
        )
        c.execute(
            "INSERT INTO narrative_snapshot VALUES (?,?,?,?,?,?,?,?,?)",
            ("coingecko-categories", "ai-agents", 4000, "AI Agents", "1000", "12.5",
             "250", "Agent tokens", j(["alpha", "beta"])),
        )
        c.execute(
            "INSERT INTO public_context_run VALUES (?,?,?,?,?)",
            ("coingecko-trending-categories", "narrative", 4000, "ok", j([])),
        )
        c.execute(
            "INSERT INTO narrative_snapshot VALUES (?,?,?,?,?,?,?,?,?)",
            ("coingecko-trending-categories", "data-availability", 4000,
             "Data Availability", "2000", "20.5", "500", None, j([])),
        )
        c.execute(
            "INSERT INTO public_context_run VALUES (?,?,?,?,?)",
            ("coindesk-rss", "news", 4000, "ok", j([])),
        )
        c.execute(
            "INSERT INTO news_event VALUES (?,?,?,?,?,?,?,?,?)",
            ("news-fixture", "coindesk-rss", 4000, 3500, "Fixture headline",
             "https://www.coindesk.com/markets/2026/09/21/fixture", "Fixture summary",
             j(["Markets"]), j({"classification": None, "importance": None})),
        )
        c.execute(
            "INSERT INTO option_context_run VALUES (?,?,?,?,?)",
            ("okx-opt-summary", "BTC-USD", 4000, "ok", j([])),
        )
        c.execute(
            "INSERT INTO option_context_run VALUES (?,?,?,?,?)",
            ("okx-open-interest", "BTC-USD", 4000, "ok", j([])),
        )
        c.execute(
            "INSERT INTO option_summary_snapshot VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("BTC-USD", "BTC-USD-261225-100000-C", 4000, 3990,
             "0.55", "0.0000055", "0.0000123", "0.00000000123",
             "-12.3", "-0.000123", "45.6", "0.000456", "0.62", "0.61", "0.63", "100500"),
        )
        c.execute(
            "INSERT INTO option_open_interest_snapshot VALUES (?,?,?,?,?,?)",
            ("BTC-USD", "BTC-USD-261225-100000-C", 4000, 3991, "123.456", "1.23456"),
        )
        candles = []
        for interval, timeframe_ms in (
                ("15m", 900_000), ("30m", 1_800_000), ("1h", 3_600_000),
                ("4h", 14_400_000), ("1d", 86_400_000)):
            for index in range(2):
                candles.append(MarketCandle(
                    "okx", SYMBOL, interval, index * timeframe_ms, timeframe_ms,
                    Decimal("100"), Decimal("102"), Decimal("99"), Decimal("101"),
                    Decimal(str(10 + index)), "currency", True,
                ))
        self.store.record_candles(tuple(candles))

    def test_reader_is_sqlite_read_only(self):
        with self.reader._connect() as connection:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("INSERT INTO instrument VALUES ('X','X','[]','[]',0,0,0)")

    def test_single_coin_uses_materialized_data_without_recalculation(self):
        result = self.reader.single_coin(SYMBOL)
        self.assertEqual(result["market"]["price_text"], "100")
        self.assertEqual(result["smf"]["score_text"], "55")
        self.assertEqual({row["view_name"] for row in result["views"]}, {"flow", "opportunity", "risk"})
        self.assertEqual(len(result["signal_states"]), 14)
        self.assertEqual({row["axis_type"] for row in result["cross_axis"]}, {"ALPHA", "ALPHA_PLUS"})
        self.assertEqual({row["label_type"] for row in result["status_labels"]},
                         {"OBSERVE", "DUMP_WARNING", "NEW_CANDIDATE"})
        self.assertEqual(result["latest_push"]["frozen_payload_json"]["price"], "100")
        self.assertEqual(result["active_cycle"]["first_push_price_text"], "98")
        self.assertEqual(
            result["active_cycle"]["since_return_text"],
            "2.0408163265306122448979591836734693877551020408163",
        )

    def test_kline_workbench_reads_exact_five_closed_timeframes_without_recalculation(self):
        result = self.reader.kline_workbench(SYMBOL, limit=2)
        self.assertEqual(result["status"], "materialized")
        self.assertTrue(result["closed_only"])
        self.assertIsNone(result["derived_indicators"])
        self.assertEqual(result["cost_reference"]["status"], "missing")
        self.assertEqual(
            result["cost_reference"]["yaozi_equivalence_status"],
            "not_claimed_private_formula_unpublished",
        )
        self.assertEqual(
            result["cost_reference"]["holder_share_status"],
            "not_materialized_no_verified_holder_source",
        )
        self.assertEqual(result["yaozi_overlay_status"], "unknown_unpublished")
        self.assertIsNone(result["ranking"])
        self.assertEqual(
            [item["timeframe"] for item in result["timeframes"]],
            ["15m", "30m", "1h", "4h", "1d"],
        )
        for series in result["timeframes"]:
            self.assertEqual(series["status"], "materialized")
            self.assertEqual(series["available_venues"], ["okx"])
            self.assertEqual(len(series["items"]), 2)
            self.assertTrue(all(row["closed"] is True for row in series["items"]))
            self.assertEqual(
                [row["open_time_ms"] for row in series["items"]],
                sorted(row["open_time_ms"] for row in series["items"]),
            )
            self.assertTrue(all(type(row["close_text"]) is str for row in series["items"]))

        latest = self.reader.kline_workbench(SYMBOL, limit=1, timeframe="15m")
        self.assertEqual([item["timeframe"] for item in latest["timeframes"]], ["15m"])
        self.assertEqual(len(latest["timeframes"][0]["items"]), 1)
        self.assertEqual(latest["timeframes"][0]["items"][0]["open_time_ms"], 900_000)

        with self.assertRaisesRegex(ValueError, "invalid_timeframe"):
            self.reader.kline_workbench(SYMBOL, timeframe="5m")
        with self.assertRaisesRegex(ValueError, "invalid_symbol"):
            self.reader.kline_workbench("BTCUSDT")

    def test_cost_reference_uses_decimal_contiguous_same_venue_4h_candles(self):
        step = 14_400_000
        for index in range(2):
            close = Decimal("100") + Decimal(index) / Decimal("10")
            self.store.connection.execute(
                """UPDATE market_candle
                   SET open_text=?,high_text=?,low_text=?,close_text=?,volume_text='2',volume_unit='currency'
                   WHERE venue='okx' AND symbol=? AND interval='4h' AND open_time_ms=?""",
                (str(close), str(close), str(close), str(close), SYMBOL, index * step),
            )
        candles = []
        for index in range(2, 180):
            close = Decimal("100") + Decimal(index) / Decimal("10")
            candles.append(MarketCandle(
                "okx", SYMBOL, "4h", index * step, step,
                close, close, close, close, Decimal("2"), "currency", True,
            ))
        self.store.record_candles(tuple(candles))
        result = self.reader.kline_workbench(SYMBOL, limit=1, timeframe="4h")
        cost = result["cost_reference"]
        self.assertEqual(cost["status"], "materialized")
        self.assertEqual(cost["venue"], "okx")
        self.assertEqual(cost["contiguous_4h_bars"], 180)
        self.assertEqual(cost["windows"]["7d"]["bars_used"], 42)
        self.assertEqual(cost["windows"]["30d"]["bars_used"], 180)
        self.assertEqual(cost["windows"]["7d"]["cost_text"], "115.85")
        self.assertEqual(cost["windows"]["30d"]["cost_text"], "108.95")
        self.assertEqual(cost["windows"]["30d"]["volume_unit"], "currency")

    def test_cost_reference_fails_closed_on_gap_or_inconsistent_volume_basis(self):
        step = 14_400_000
        gap_candles = []
        for index in range(2, 50):
            if index == 45:
                continue
            gap_candles.append(MarketCandle(
                "binance", SYMBOL, "4h", index * step, step,
                Decimal("100"), Decimal("100"), Decimal("100"), Decimal("100"),
                Decimal("1"), "base", True,
            ))
        self.store.record_candles(tuple(gap_candles))
        gap = self.reader.kline_workbench(SYMBOL, timeframe="4h")["cost_reference"]
        self.assertEqual(gap["venue"], "binance")
        self.assertEqual(gap["windows"]["7d"]["status"], "missing")
        self.assertEqual(
            gap["windows"]["7d"]["missing_reason"],
            "insufficient_contiguous_4h_candles",
        )

        self.store.record_candles(tuple(
            MarketCandle(
                "okx", SYMBOL, "4h", index * step, step,
                Decimal("100"), Decimal("100"), Decimal("100"), Decimal("100"),
                Decimal("1"), "currency", True,
            )
            for index in range(2, 42)
        ))
        self.store.connection.execute(
            "UPDATE market_candle SET volume_unit='quote' WHERE venue='okx' AND symbol=? "
            "AND interval='4h' AND open_time_ms=?",
            (SYMBOL, 20 * step),
        )
        inconsistent = self.reader.kline_workbench(SYMBOL, timeframe="4h")["cost_reference"]
        self.assertEqual(inconsistent["venue"], "okx")
        self.assertEqual(inconsistent["windows"]["7d"]["status"], "missing")
        self.assertEqual(
            inconsistent["windows"]["7d"]["missing_reason"],
            "volume_basis_incomplete_or_inconsistent",
        )

    def test_kline_workbench_reports_explicit_missing_series(self):
        self.store.connection.execute(
            "INSERT INTO instrument VALUES (?,?,?,?,?,?,?)",
            ("ETH-USDT-SWAP", "ETH-USDT-SWAP", "[]", "[]", 1, 1000, 4000),
        )
        result = self.reader.kline_workbench("ETH-USDT-SWAP")
        self.assertEqual(result["status"], "materialized_empty")
        self.assertEqual(
            {item["status"] for item in result["timeframes"]}, {"missing"})
        self.assertEqual(
            {item["missing_reason"] for item in result["timeframes"]},
            {"no_closed_candles_materialized"},
        )

    def test_radar_is_unranked_and_momentum_exposes_materialized_components_only(self):
        radar = self.reader.radar()
        self.assertEqual(radar["status"], "materialized_unranked")
        self.assertIsNone(radar["ranking"])
        self.assertEqual(radar["items"][0]["symbol"], SYMBOL)
        momentum = self.reader.picks("momentum")
        self.assertEqual(momentum["status"], "materialized_partial")
        self.assertIsNone(momentum["ranking"])
        self.assertIsNone(momentum["items"][0]["score"])
        self.assertEqual(momentum["items"][0]["smf"]["grade"], "S")
        self.assertEqual(momentum["items"][0]["l2_state_count"], 14)
        self.assertEqual(
            next(row for row in momentum["items"][0]["cross_axis"] if row["selected"] == 1)["axis_type"],
            "ALPHA_PLUS",
        )
        self.assertEqual(
            next(row for row in momentum["items"][0]["status_labels"]
                 if row["label_type"] == "OBSERVE")["status"],
            "HIT",
        )
        self.assertEqual(momentum["items"][0]["funnel"]["status"], "not_materialized")

    def test_cross_axis_and_status_label_reader_surfaces_are_unranked_and_explicit(self):
        cross_axis = self.reader.cross_axis(symbol=SYMBOL)
        self.assertEqual(cross_axis["status"], "materialized_unranked")
        self.assertIsNone(cross_axis["ranking"])
        self.assertEqual(cross_axis["yaozi_formula_status"], "published_cross_axis_rules_only")
        selected = [row for row in cross_axis["items"] if row["selected"] == 1]
        self.assertEqual([row["axis_type"] for row in selected], ["ALPHA_PLUS"])

        labels = self.reader.status_labels(symbol=SYMBOL)
        self.assertEqual(labels["status"], "materialized")
        self.assertEqual(labels["derivation"], "caller_explicit_source_state_only")
        self.assertEqual(labels["yaozi_private_gate_status"], "unknown_unpublished")
        observe = next(row for row in labels["items"] if row["label_type"] == "OBSERVE")
        self.assertTrue(observe["evidence_json"]["source_explicit_state"])

    def test_history_exposes_versioned_flat_threshold_contract_without_guessing_source_timezone(self):
        history = self.reader.picks("history")
        self.assertEqual(history["view"], "history")
        self.assertEqual(
            [(item["threshold_pct"], item["effective_from"], item["effective_until"])
             for item in history["flat_rule_versions"]],
            [("3", None, "2026-05-07"), ("1", "2026-05-08", None)],
        )
        self.assertIsNone(history["flat_item_classification"])
        self.assertEqual(
            history["flat_item_classification_status"],
            "source_date_timezone_not_published",
        )
        self.assertEqual(history["result_semantics"]["mfe"], "captured_excursion")
        self.assertEqual(
            history["result_semantics"]["hold_until_exit"],
            "separate_realized_history_result",
        )

    def test_timeline_journey_signals_and_proof(self):
        timeline = self.reader.timeline(SYMBOL)
        self.assertIn("push_snapshot", {item["kind"] for item in timeline["items"]})
        journey = self.reader.journey(SYMBOL)
        self.assertEqual(journey["cycles"][0]["cycle"]["cycle_id"], "c1")
        self.assertEqual(journey["cycles"][0]["events"][0]["payload_json"]["price"], "98")
        signals = self.reader.signals(symbol=SYMBOL)
        self.assertEqual(signals["signals"][0]["signal_type"], "MOMENTUM")
        self.assertEqual(signals["taxonomy_contract"], "catos_source_semantic_only")
        self.assertEqual(signals["yaozi_taxonomy_mapping_status"], "unknown_unpublished")
        self.assertIn("signal", {item["family"] for item in signals["items"]})
        self.assertIn("candidate", {item["family"] for item in signals["items"]})
        proof = self.reader.proof(symbol=SYMBOL)
        self.assertEqual(proof["items"][0]["return_text"], "8")

    def test_signal_event_stream_filters_ordering_and_read_only_alert_routing(self):
        j = lambda value: json.dumps(value, separators=(",", ":"), sort_keys=True)
        c = self.store.connection
        c.execute(
            "INSERT INTO capital_flow_event VALUES (?,?,?,?,?,?,?,?)",
            ("flow-4500", "FLOW_BUILDUP", SYMBOL, 4500, None, "ACTIVE", j({"source": "fixture"}), j(["flow:4500"])),
        )
        c.execute(
            "INSERT INTO onchain_activity VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (SYMBOL, "ethereum", 3500, 12, 30, "10", "9", "1.2", "1.333333333333333333", "ELEVATED",
             3400, None, 2),
        )
        c.execute(
            "INSERT INTO cycle_event VALUES (?,?,?,?,?,?,?)",
            ("e-risk", "c1", SYMBOL, 4200, "risk_transition", "risk", j({"reason": "fixture"})),
        )

        stream = self.reader.signals(limit=100, symbol=SYMBOL)
        self.assertEqual(
            [item["observed_at_ms"] for item in stream["items"]],
            sorted((item["observed_at_ms"] for item in stream["items"]), reverse=True),
        )
        at_4000 = [item for item in stream["items"] if item["observed_at_ms"] == 4000]
        self.assertEqual(
            [(item["family"], item["source_id"]) for item in at_4000],
            sorted((item["family"], item["source_id"]) for item in at_4000),
        )

        flow = self.reader.signals(limit=10, symbol=SYMBOL, family="flow")
        self.assertEqual([item["source_id"] for item in flow["items"]], ["flow-4500"])
        self.assertEqual(flow["signals"], [])
        self.assertEqual(flow["patterns"], [])

        exact_window = self.reader.signals(limit=100, symbol=SYMBOL, since_ms=4000, until_ms=4000)
        self.assertTrue(exact_window["items"])
        self.assertEqual({item["observed_at_ms"] for item in exact_window["items"]}, {4000})

        risk_view = self.reader.signals(limit=10, symbol=SYMBOL, view="risk")
        self.assertEqual([item["source_id"] for item in risk_view["items"]], ["e-risk"])
        self.assertEqual(risk_view["items"][0]["family"], "lifecycle")
        self.assertEqual(risk_view["items"][0]["alert_route"], "risk")
        self.assertEqual(risk_view["view_filter_contract"], "explicit_cycle_event_view_name_only")

        limited = self.reader.signals(limit=2, symbol=SYMBOL)
        self.assertEqual([item["source_id"] for item in limited["items"]], ["flow-4500", "e-risk"])

        candidates = self.reader.signals(limit=10, symbol=SYMBOL, family="candidate")
        self.assertFalse(candidates["items"][0]["evidence_json"]["yaozi_event_triggered"])
        self.assertEqual(candidates["items"][0]["alert_route"], "public_evidence")

        alerts = self.reader.alerts(limit=100, symbol=SYMBOL)
        self.assertFalse(alerts["mutation_supported"])
        self.assertIsNone(alerts["unread_state"])
        self.assertEqual(alerts["unread_state_status"], "not_materialized")
        self.assertEqual(alerts["routes"]["flow"][0]["source_id"], "flow-4500")
        self.assertEqual(alerts["routes"]["risk"][0]["source_id"], "e-risk")
        self.assertEqual(alerts["routes"]["public_evidence"][0]["source_id"], "public-candidate-fixture")

        with self.assertRaisesRegex(ValueError, "invalid_signal_family"):
            self.reader.signals(family="smf_private")
        with self.assertRaisesRegex(ValueError, "invalid_signal_view"):
            self.reader.signals(view="private-view")
        with self.assertRaisesRegex(ValueError, "invalid_signal_window"):
            self.reader.signals(since_ms=5000, until_ms=4000)
        with self.assertRaisesRegex(ValueError, "invalid_signal_window"):
            self.reader.signals(since_ms=-1)

    def test_source_coverage_reads_latest_materialized_runs_without_freshness_guessing(self):
        j = lambda value: json.dumps(value, separators=(",", ":"), sort_keys=True)
        c = self.store.connection
        c.execute(
            "INSERT INTO public_context_run VALUES (?,?,?,?,?)",
            ("coingecko-categories", "narrative", 5000, "partial", j([["fixture_issue", "fetch"]])),
        )
        c.execute(
            "INSERT INTO collector_run VALUES (?,?,?)",
            (SYMBOL, 5000, j([])),
        )
        c.execute(
            "INSERT INTO venue_market_snapshot VALUES (?,?,?,?,?,?,?,?)",
            ("OKX", SYMBOL, 5000, 4990, "101", "1000000", "USDT", "1.25"),
        )
        c.execute(
            "INSERT INTO venue_derivative_snapshot VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("OKX", SYMBOL, 5000, 4990, "900", "contracts", "90000000", "0.0001", "1.1", "0.52"),
        )
        c.execute(
            "INSERT INTO option_context_run VALUES (?,?,?,?,?)",
            ("okx-open-interest", "BTC-USD", 5000, "empty", j([])),
        )
        c.execute(
            "INSERT INTO hyperliquid_collector_run VALUES (?,?,?)",
            (SYMBOL, 5000, j([])),
        )
        c.execute(
            "INSERT INTO dex_collector_run VALUES (?,?,?,?,?,?)",
            (
                SYMBOL, 5000, "ethereum", "geckoterminal:fixture", j([["fixture_warning", "row"]]),
                j({"status": "verified_pool_window", "scope": "single_pool", "pool_address": "0xabc"}),
            ),
        )
        c.execute(
            "INSERT INTO onchain_activity VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (SYMBOL, "ethereum", 5000, 12, 30, "10", "9", "1.2", "1.333333333333333333",
             "ELEVATED", 4900, None, 2),
        )
        self.store.record_onchain_source_run(
            source=ONCHAIN_SOURCE, symbol=SYMBOL, chain="ethereum", observed_at_ms=5000,
            status="ok",
            source_scope={
                "collection_mode": "live_public",
                "network": "ethereum",
                "token_contract": "0x" + "12" * 20,
                "identity_rule": "erc20_transfer_from_address",
            },
            evidence={"coverage_status": "complete_bounded_window"},
            issues=(),
        )
        self._record_liquidity()

        coverage = self.reader.source_coverage()
        self.assertEqual(coverage["contract"], "materialized_source_run_diagnostics_v1")
        self.assertEqual(coverage["freshness_status"], "not_evaluated_no_wall_clock")
        self.assertEqual(coverage["live_equivalence_status"], "not_inferred_from_persisted_run")
        self.assertEqual(
            [(item["domain"], item["source"] or "", item["scope"]) for item in coverage["items"]],
            sorted((item["domain"], item["source"] or "", item["scope"]) for item in coverage["items"]),
        )

        narrative = next(
            item for item in coverage["items"]
            if item["domain"] == "public_context" and item["source"] == "coingecko-categories")
        self.assertEqual(narrative["observed_at_ms"], 5000)
        self.assertEqual(narrative["status"], "partial")
        self.assertEqual(narrative["issues"], [["fixture_issue", "fetch"]])

        option = next(
            item for item in coverage["items"]
            if item["domain"] == "options" and item["source"] == "okx-open-interest")
        self.assertEqual(option["observed_at_ms"], 5000)
        self.assertEqual(option["status"], "empty")

        market_run = next(item for item in coverage["items"] if item["domain"] == "market_collector")
        self.assertEqual(market_run["status"], "no_recorded_issues")
        self.assertEqual(market_run["coverage_status"], "run_boundary_only")
        market_venue = next(item for item in coverage["items"] if item["domain"] == "market_venue")
        self.assertEqual(market_venue["source"], "OKX")
        self.assertEqual(market_venue["provider_identity_status"], "venue_explicit")
        derivative_venue = next(
            item for item in coverage["items"] if item["domain"] == "derivative_venue")
        self.assertEqual(derivative_venue["source"], "OKX")
        self.assertEqual(derivative_venue["status"], "snapshot_materialized")

        dex = next(item for item in coverage["items"] if item["domain"] == "dex")
        self.assertEqual(dex["status"], "issues")
        self.assertEqual(dex["coverage_status"], "verified_pool_window")
        self.assertEqual(dex["provider_identity_status"], "explicit_pool_identity")

        hyperliquid = next(item for item in coverage["items"] if item["domain"] == "hyperliquid")
        self.assertEqual(hyperliquid["status"], "no_recorded_issues")
        self.assertEqual(hyperliquid["coverage_status"], "run_boundary_only")

        onchain = next(item for item in coverage["items"] if item["domain"] == "onchain")
        self.assertEqual(onchain["source"], ONCHAIN_SOURCE)
        self.assertEqual(onchain["coverage_status"], "complete_bounded_window")
        self.assertEqual(onchain["provider_identity_status"], "explicit_live_source_scope")
        liquidity = [item for item in coverage["items"] if item["domain"] == "liquidity"]
        self.assertEqual(
            {(item["source"], item["coverage_status"]) for item in liquidity},
            {
                ("okx-spot-orderbook", "complete_2pct"),
                ("binance-spot-orderbook", "partial_boundary_coverage"),
            },
        )
        self.assertTrue(all(
            item["provider_identity_status"] == "venue_explicit_public_orderbook"
            for item in liquidity
        ))
        self.assertIn(
            {"capability": "onchain_live_provider", "status": "materialized_live_source_run"},
            coverage["gaps"],
        )
        self.assertEqual(
            self.reader.onchain(symbol=SYMBOL)["provider_status"],
            "materialized_live_source_run",
        )
        self.assertIn(
            {"capability": "social_metric", "status": "not_materialized_or_empty"},
            coverage["gaps"],
        )
        self.assertIn(
            {"capability": "multi_venue_liquidity", "status": "okx_binance_public_subset_materialized"},
            coverage["gaps"],
        )
        self.assertEqual(len(self.reader.source_coverage(limit=2)["items"]), 2)

    def test_liquidity_reader_preserves_full_depth_vs_lower_bound_semantics(self):
        self._record_liquidity()
        result = self.reader.liquidity(symbol=SYMBOL)
        self.assertEqual(result["contract"], "catos-spot-depth-2pct-v1")
        self.assertEqual(result["observed_at_ms"], 5_000)
        self.assertIsNone(result["ranking"])
        self.assertIsNone(result["signal"])
        self.assertEqual(result["coverage"]["status"], "partial_configured_venues")
        self.assertEqual(result["coverage"]["expected_venues"], ["binance", "okx"])
        self.assertEqual(result["coverage"]["complete_venues"], ["okx"])
        okx = next(item for item in result["items"] if item["venue"] == "okx")
        binance = next(item for item in result["items"] if item["venue"] == "binance")
        self.assertEqual(okx["down_2pct_cost_text"], "200")
        self.assertEqual(okx["up_2pct_cost_text"], "101")
        self.assertIsNotNone(okx["asymmetry_text"])
        self.assertEqual(okx["coverage_json"]["status"], "complete_2pct")
        self.assertIsNone(binance["down_2pct_cost_text"])
        self.assertIsNone(binance["up_2pct_cost_text"])
        self.assertEqual(binance["down_2pct_lower_bound_text"], "500")
        self.assertEqual(binance["up_2pct_lower_bound_text"], "404")
        self.assertIsNone(binance["asymmetry_text"])
        self.assertEqual(binance["coverage_json"]["status"], "partial_boundary_coverage")

    def test_signal_dex_window_is_exact_observation_and_never_dealer_flow(self):
        base = {
            "symbol": SYMBOL, "chain": "ethereum", "venue": "uniswap-v3",
            "router": "universal-router", "wallet": "0x" + "12" * 20,
            "base_quantity": "1", "quote_currency": "USDC", "block_number": 1,
        }
        rows = [
            dict(base, side="BUY", quote_notional="10.123456789012345678",
                 tx_hash="0x" + "ab" * 32, log_index=1, source_ms=3_500),
            dict(base, side="SELL", quote_notional="2.023456789012345678",
                 tx_hash="0x" + "cd" * 32, log_index=2, source_ms=3_900),
        ]
        self.store.record_dex_batch(parse_public_swap_rows(
            DexScope(SYMBOL, 4_000, "ethereum"), rows, source="mock-indexer"))
        window = self.reader.signal_dex_window(SYMBOL)
        self.assertEqual(window["net_flow_text"], "8.100000000000000000")
        self.assertEqual(window["buy_gross_text"], "10.123456789012345678")
        self.assertEqual(window["sell_gross_text"], "2.023456789012345678")
        self.assertEqual(window["quote_currency"], "USDC")
        self.assertEqual(window["swap_count"], 2)
        self.assertEqual(window["coverage_status"], "unverified_window_coverage")
        self.assertFalse(window["dealer_flow_eligible"])
        signals = self.reader.signals(symbol=SYMBOL)
        self.assertEqual(signals["dex_windows"][0]["net_flow_text"], "8.100000000000000000")
        self.assertEqual(self.reader.dealer(SYMBOL)["status"], "materialized_empty")

    def test_signal_dex_verified_multi_pool_requires_same_asset_identity(self):
        base_token = "0x" + "34" * 20
        coverage = lambda pool: {
            "status": "verified_pool_window",
            "scope": "single_pool",
            "pool_address": pool,
            "base_token_address": base_token,
        }
        common = {
            "symbol": SYMBOL, "chain": "ethereum", "router": None,
            "wallet": "0x" + "12" * 20, "base_quantity": "1",
            "quote_currency": "USD", "block_number": 1,
        }
        first = parse_public_swap_rows(
            DexScope(SYMBOL, 4_000, "ethereum"),
            [dict(common, venue="uniswap-v3", side="BUY", quote_notional="10.25",
                  tx_hash="0x" + "aa" * 32, log_index=1, source_ms=3_500)],
            source="pool-a", coverage=coverage("0x" + "56" * 20),
        )
        second = parse_public_swap_rows(
            DexScope(SYMBOL, 4_000, "ethereum"),
            [dict(common, venue="sushiswap", side="SELL", quote_notional="2.00",
                  tx_hash="0x" + "bb" * 32, log_index=2, source_ms=3_900)],
            source="pool-b", coverage=coverage("0x" + "78" * 20),
        )
        self.store.record_dex_batch(first)
        self.store.record_dex_batch(second)
        window = self.reader.signal_dex_window(SYMBOL)
        self.assertEqual(window["net_flow_text"], "8.25")
        self.assertEqual(window["coverage_status"], "verified_multi_pool_window")
        self.assertEqual(window["coverage_scope"], "multi_pool")
        self.assertEqual(window["coverage"]["base_token_address"], base_token)
        self.assertEqual(len(window["source_run_ids"]), 2)
        self.assertIsNone(window["source_run_id"])
        self.assertFalse(window["dealer_flow_eligible"])

    def test_money_flow_uses_verified_dex_then_complete_cex_fallback(self):
        end_ms = 100_000_000
        four_h = 14_400_000
        j = lambda value: json.dumps(value, separators=(",", ":"), sort_keys=True)
        self.store.connection.execute(
            "INSERT INTO market_snapshot VALUES (?,?,?,?,?,?,?,?,?)",
            ("money-flow-market", SYMBOL, end_ms, "100", "1000000", None, None,
             "1000000", j({"source": "fixture"})),
        )
        for observed_at_ms, start_ms, stop_ms, cvd in (
            (end_ms - four_h, end_ms - 2 * four_h, end_ms - four_h, "1000"),
            (end_ms, end_ms - four_h, end_ms, "4000"),
        ):
            self.store.connection.execute(
                "INSERT INTO flow_snapshot VALUES (?,?,?,?,?,?,?,?,?)",
                (SYMBOL, observed_at_ms, cvd, "0.55", 10, start_ms, stop_ms, 1,
                 j({"trade_venue": "binance"})),
            )
        base_token = "0x" + "34" * 20
        coverage = {
            "status": "verified_pool_window", "scope": "single_pool",
            "pool_address": "0x" + "56" * 20,
            "base_token_address": base_token,
            "window_ms": 3_600_000,
            "window_start_ms": end_ms - 3_600_000,
            "window_end_ms": end_ms,
        }
        common = {
            "symbol": SYMBOL, "chain": "ethereum", "venue": "uniswap-v3",
            "router": None, "wallet": "0x" + "12" * 20, "base_quantity": "1",
            "quote_currency": "USDC", "block_number": 1,
        }
        rows = [
            dict(common, side="BUY", quote_notional="1500", source_ms=end_ms - 120_000,
                 tx_hash="0x" + "aa" * 32, log_index=1),
            dict(common, side="SELL", quote_notional="200", source_ms=end_ms - 60_000,
                 tx_hash="0x" + "bb" * 32, log_index=2),
        ]
        self.store.record_dex_batch(parse_public_swap_rows(
            DexScope(SYMBOL, end_ms, "ethereum"), rows, source="pool-a", coverage=coverage))

        result = self.reader.money_flow(SYMBOL, end_ms)
        self.assertEqual(result["contract"], "yaozi-guide-money-flow-public-v1")
        self.assertFalse(result["smf_eligible"])
        five = result["windows"]["5m"]
        self.assertEqual(five["source"], "DEX")
        self.assertEqual(five["net_flow_text"], "1300")
        self.assertEqual(five["quote_currency"], "USDC")
        self.assertEqual(len(five["dex"]["large_swaps"]), 1)
        self.assertEqual(five["dex"]["large_swaps"][0]["notional_text"], "1500")
        self.assertEqual(five["dex"]["large_swaps"][0]["tx_hash"], "0x" + "aa" * 32)
        self.assertIsNone(five["delta_vs_previous_text"])

        current_four_h = result["windows"]["4h"]
        self.assertEqual(current_four_h["source"], "CEX_TAKER")
        self.assertEqual(current_four_h["net_flow_text"], "4000")
        self.assertEqual(current_four_h["delta_vs_previous_text"], "3000")
        self.assertEqual(current_four_h["delta_status"], "available")
        self.assertEqual(current_four_h["flow_market_cap_ratio_text"], "0.004")
        self.assertFalse(current_four_h["dex"]["coverage_complete"])
        self.assertEqual(result["peak_90d_status"], "calendar_day_timezone_contract_unpublished")

    def test_signal_dex_multi_pool_identity_mismatch_keeps_flow_missing(self):
        common = {
            "symbol": SYMBOL, "chain": "ethereum", "venue": "uniswap-v3", "router": None,
            "wallet": None, "base_quantity": "1", "quote_currency": "USD",
            "block_number": 1, "side": "BUY", "quote_notional": "10",
        }
        for source, tx, base_token in (
            ("pool-a", "aa", "0x" + "34" * 20),
            ("pool-b", "bb", "0x" + "56" * 20),
        ):
            batch = parse_public_swap_rows(
                DexScope(SYMBOL, 4_000, "ethereum"),
                [dict(common, tx_hash="0x" + tx * 32, log_index=1, source_ms=3_900)],
                source=source,
                coverage={
                    "status": "verified_pool_window", "scope": "single_pool",
                    "pool_address": "0x" + "78" * 20,
                    "base_token_address": base_token,
                },
            )
            self.store.record_dex_batch(batch)
        window = self.reader.signal_dex_window(SYMBOL)
        self.assertIsNone(window["net_flow_text"])
        self.assertEqual(window["net_flow_status"], "missing_asset_identity")
        self.assertEqual(window["coverage_status"], "unverified_asset_identity")
        self.assertIn("base_token_identity_mismatch", window["issues"])

    def test_signal_dex_missing_quote_or_mixed_currency_stays_null(self):
        base = {
            "symbol": SYMBOL, "chain": "ethereum", "venue": "uniswap-v3", "router": None,
            "wallet": None, "base_quantity": "1", "block_number": None, "source_ms": 3_900,
        }
        rows = [
            dict(base, side="BUY", quote_notional=None, quote_currency=None,
                 tx_hash="0x" + "ef" * 32, log_index=1),
            dict(base, side="SELL", quote_notional="2", quote_currency="USDT",
                 tx_hash="0x" + "01" * 32, log_index=2),
        ]
        self.store.record_dex_batch(parse_public_swap_rows(
            DexScope(SYMBOL, 4_000, "ethereum"), rows, source="mock-indexer"))
        window = self.reader.signal_dex_window(SYMBOL)
        self.assertIsNone(window["net_flow_text"])
        self.assertIsNone(window["quote_currency"])
        self.assertIn("missing_quote_notional", window["issues"])
        self.assertIn("missing_quote_currency", window["issues"])

    def test_source_coverage_limit_keeps_newer_dex_runs_visible(self):
        older_at = 3_000
        self.store.connection.execute(
            "INSERT INTO venue_derivative_snapshot "
            "(venue,symbol,observed_at_ms,source_ms,oi_text,oi_unit,oi_notional_usd_text,"
            "funding_text,top_lsr_text,taker_buy_ratio_text) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("binance", "ETH-USDT-SWAP", older_at, older_at, "1", "contracts", None,
             None, None, None),
        )
        self.store.connection.commit()
        batch = parse_public_swap_rows(
            DexScope(SYMBOL, 4_000, "ethereum"),
            [],
            source="pool-a",
            coverage={
                "status": "verified_pool_window",
                "scope": "single_pool",
                "pool_address": "0x" + "56" * 20,
                "base_token_address": "0x" + "34" * 20,
            },
        )
        self.store.record_dex_batch(batch)
        coverage = self.reader.source_coverage(limit=1)
        self.assertEqual(coverage["items"][0]["domain"], "dex")
        self.assertEqual(coverage["items"][0]["source"], "pool-a")

    def test_http_surface_and_not_materialized_phases(self):
        self._record_liquidity()
        self.store.record_social_batch(parse_coinpaprika_social(
            SocialAssetRef(SYMBOL, "btc-bitcoin"),
            {
                "id": "btc-bitcoin",
                "symbol": "BTC",
                "links_extended": [{
                    "url": "https://www.reddit.com/r/bitcoin",
                    "type": "reddit",
                    "stats": {"subscribers": 5_958_815},
                }],
            },
            5_000,
        ))
        client = TestClient(create_app(self.path))
        dashboard = client.get("/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("catOS Market Intel", dashboard.text)
        self.assertIn("Whale / DEX", dashboard.text)
        self.assertIn("莊家摘要", dashboard.text)
        self.assertIn("DEX 淨流 1h", dashboard.text)
        self.assertIn("Signal DEX", dashboard.text)
        self.assertIn('data-view="candidates"', dashboard.text)
        self.assertIn('data-view="narrative"', dashboard.text)
        self.assertIn('data-view="coverage"', dashboard.text)
        self.assertIn('data-view="options"', dashboard.text)
        self.assertIn("候選證據", dashboard.text)
        self.assertIn("敘事 / News", dashboard.text)
        self.assertIn("Options / Gamma", dashboard.text)
        self.assertIn("K 線工作台", dashboard.text)
        self.assertIn("CATOS COST REF", dashboard.text)
        self.assertIn("possible taxonomy", dashboard.text)
        self.assertIn("ALL FAMILIES", dashboard.text)
        self.assertIn("READ-ONLY ROUTES", dashboard.text)
        self.assertIn("SOURCE COVERAGE", dashboard.text)
        self.assertIn("LIQUIDITY ±2%", dashboard.text)
        self.assertIn("MONEY FLOW · GUIDE PUBLIC CONTRACT", dashboard.text)
        self.assertIn("SINCE", dashboard.text)
        self.assertNotIn('<span class="since">24H', dashboard.text)
        self.assertEqual(client.get(f"/intel/picks/{SYMBOL}").status_code, 200)
        candles = client.get(
            f"/intel/picks/{SYMBOL}/candles", params={"timeframe": "30m", "limit": 1}).json()
        self.assertEqual(candles["timeframes"][0]["timeframe"], "30m")
        self.assertEqual(len(candles["timeframes"][0]["items"]), 1)
        self.assertTrue(candles["timeframes"][0]["items"][0]["closed"])
        self.assertEqual(
            client.get(f"/intel/picks/{SYMBOL}/candles", params={"timeframe": "5m"}).status_code,
            422,
        )
        self.assertEqual(client.get("/intel/picks/BTCUSDT/candles").status_code, 422)
        self.assertEqual(client.get("/intel/picks/ETH-USDT-SWAP/candles").status_code, 404)
        liquidity = client.get(f"/intel/picks/{SYMBOL}/liquidity").json()
        self.assertEqual(liquidity["coverage"]["status"], "partial_configured_venues")
        self.assertEqual(len(liquidity["items"]), 2)
        self.assertEqual(client.get("/intel/picks/BTCUSDT/liquidity").status_code, 422)
        self.assertEqual(len(client.get("/intel/liquidity").json()["items"]), 2)
        money_flow = client.get(f"/intel/picks/{SYMBOL}/money-flow").json()
        self.assertEqual(money_flow["contract"], "yaozi-guide-money-flow-public-v1")
        self.assertEqual(set(money_flow["windows"]), {"5m", "1h", "4h", "24h"})
        self.assertEqual(client.get("/intel/picks/BTCUSDT/money-flow").status_code, 422)
        cross_axis = client.get("/intel/cross-axis", params={"symbol": SYMBOL}).json()
        self.assertIsNone(cross_axis["ranking"])
        self.assertEqual(
            next(row for row in cross_axis["items"] if row["selected"] == 1)["axis_type"],
            "ALPHA_PLUS",
        )
        labels = client.get("/intel/status-labels", params={"symbol": SYMBOL}).json()
        self.assertEqual(labels["yaozi_private_gate_status"], "unknown_unpublished")
        self.assertEqual(client.get("/intel/cross-axis", params={"symbol": "BTCUSDT"}).status_code, 422)
        options = client.get("/intel/options/BTC-USD").json()
        self.assertEqual(options["items"][0]["gamma_bs_text"], "0.0000123")
        self.assertEqual(options["items"][0]["open_interest"]["oi_text"], "123.456")
        self.assertIsNone(options["signed_gex"])
        self.assertEqual(options["yaozi_gamma_formula_status"], "unknown_unpublished")
        self.assertEqual(client.get("/intel/options/BTC-USDT-SWAP").status_code, 422)
        self.assertEqual(client.get("/intel/picks", params={"view": "flow"}).json()["items"][0]["state"],
                         "ignition")
        today = client.get("/intel/today").json()
        self.assertEqual(today["status"], "materialized_catos_latest")
        self.assertEqual(today["contract_version"], "catos-p0-today-v2")
        self.assertEqual(today["yaozi_contract"], "unverified")
        self.assertEqual(
            today["holdings"]["items"][0]["since_return_text"],
            "2.0408163265306122448979591836734693877551020408163",
        )
        self.assertEqual(today["views"]["momentum"]["items"][0]["l2_state_count"], 14)
        capital = client.get(f"/intel/capital-flow/{SYMBOL}").json()
        self.assertEqual(capital["status"], "materialized_empty")
        self.assertIsNone(capital["public_evidence"]["whale_threshold"])
        self.assertEqual(capital["taxonomy"]["event_kind_count"], 31)
        self.assertEqual(capital["taxonomy"]["semantic_coverage"], "complete_31_of_31")
        self.assertEqual(
            {name: len(items) for name, items in capital["taxonomy"]["groups"].items()},
            {"inflow": 10, "outflow": 6, "lifecycle": 9, "structural_quality": 6},
        )
        self.assertTrue(capital["taxonomy"]["display_only"])
        self.assertFalse(capital["taxonomy"]["smf_eligible"])
        candidates = client.get(f"/intel/event-candidates/{SYMBOL}").json()
        self.assertEqual(candidates["status"], "materialized")
        self.assertEqual(candidates["items"][0]["candidate_type"], "OI_POSITIVE_CHANGE")
        self.assertFalse(candidates["items"][0]["evidence_json"]["yaozi_event_triggered"])
        self.assertEqual(client.get("/intel/event-candidates").json()["items"][0]["symbol"], SYMBOL)
        self.assertEqual(client.get("/intel/event-candidates/BTCUSDT").status_code, 422)
        signals = client.get("/intel/signals", params={"symbol": SYMBOL, "family": "candidate"}).json()
        self.assertEqual(signals["taxonomy_contract"], "catos_source_semantic_only")
        self.assertEqual([item["family"] for item in signals["items"]], ["candidate"])
        self.assertFalse(signals["items"][0]["evidence_json"]["yaozi_event_triggered"])
        self.assertEqual(
            client.get("/intel/signals", params={"family": "private-family"}).status_code,
            422,
        )
        self.assertEqual(
            client.get("/intel/signals", params={"since_ms": 5000, "until_ms": 4000}).status_code,
            422,
        )
        alerts = client.get("/intel/alerts", params={"symbol": SYMBOL}).json()
        self.assertFalse(alerts["mutation_supported"])
        self.assertEqual(alerts["unread_state_status"], "not_materialized")
        coverage = client.get("/intel/source-coverage").json()
        self.assertEqual(coverage["contract"], "materialized_source_run_diagnostics_v1")
        self.assertEqual(coverage["freshness_status"], "not_evaluated_no_wall_clock")
        self.assertIn("public_context", {item["domain"] for item in coverage["items"]})
        self.assertIn("options", {item["domain"] for item in coverage["items"]})
        self.assertIn("social", {item["domain"] for item in coverage["items"]})
        social = client.get(f"/intel/picks/{SYMBOL}/social").json()
        self.assertEqual(social["contract"], "catos-coinpaprika-social-metric-v1")
        self.assertEqual(social["items"][0]["metric_kind"], "reddit_subscribers")
        self.assertEqual(social["items"][0]["metric_value"], 5_958_815)
        self.assertIsNone(social["social_heat"])
        self.assertEqual(client.get("/intel/picks/BTCUSDT/social").status_code, 422)
        self.assertEqual(client.get(f"/intel/dealer/{SYMBOL}").json()["status"], "materialized_empty")
        self.assertEqual(client.get("/intel/onchain").json()["status"], "materialized_empty")
        narrative = client.get("/intel/narrative").json()
        self.assertEqual(narrative["status"], "materialized")
        self.assertIsNone(narrative["ranking"])
        self.assertEqual(narrative["items"][0]["name"], "AI Agents")
        sectors = client.get("/intel/sectors").json()
        self.assertEqual(sectors["status"], "materialized_public_categories")
        self.assertIsNone(sectors["relative_strength"])
        self.assertIsNone(sectors["momentum"])
        self.assertIsNone(sectors["rotation_position"])
        self.assertEqual(sectors["yaozi_rotation_formula_status"], "unknown_unpublished")
        self.assertEqual(sectors["items"][0]["name"], "AI Agents")
        attention = client.get("/intel/narrative-attention").json()
        self.assertEqual(attention["status"], "materialized_public_attention")
        self.assertFalse(attention["ranking_persisted"])
        self.assertIsNone(attention["source_rank"])
        self.assertIsNone(attention["social_heat"])
        self.assertIsNone(attention["yaozi_heat"])
        self.assertEqual(attention["items"][0]["name"], "Data Availability")
        news = client.get("/intel/news").json()
        self.assertEqual(news["status"], "materialized")
        self.assertIsNone(news["importance"])
        self.assertEqual(news["items"][0]["title"], "Fixture headline")
        raw_flow = client.get(f"/intel/raw-flow/{SYMBOL}").json()
        self.assertIsNone(raw_flow["whale_threshold"])
        self.assertEqual(raw_flow["dex"], [])
        signal_dex = client.get(f"/intel/signal-dex/{SYMBOL}").json()
        self.assertEqual(signal_dex["status"], "materialized_empty")
        self.assertIsNone(signal_dex["net_flow_text"])
        self.assertEqual(client.get("/intel/picks", params={"view": "bogus"}).status_code, 422)

    def test_server_rejects_non_loopback_binding(self):
        with self.assertRaisesRegex(ValueError, "localhost_only"):
            serve(self.path, host="0.0.0.0")

    def test_database_preflight_reports_schema_without_mutating_database(self):
        ready = inspect_database(self.path)
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["expected_schema"], 14)
        self.assertEqual(ready["actual_schema"], 14)
        self.assertTrue(ready["read_only"])

        legacy = Path(self.directory.name) / "legacy-v12.sqlite"
        connection = sqlite3.connect(legacy)
        try:
            connection.execute(
                "CREATE TABLE metadata (id INTEGER PRIMARY KEY, format TEXT NOT NULL)")
            connection.execute("INSERT INTO metadata VALUES (1,'catos-market-intel-v1')")
            connection.execute("PRAGMA user_version=12")
            connection.commit()
        finally:
            connection.close()
        before = legacy.read_bytes()
        status = inspect_database(legacy)
        self.assertEqual(status["status"], "unsupported_schema")
        self.assertEqual(status["expected_schema"], 14)
        self.assertEqual(status["actual_schema"], 12)
        self.assertEqual(legacy.read_bytes(), before)

    def test_cli_check_is_read_only_and_start_uses_fixed_loopback_server(self):
        output = StringIO()
        with redirect_stdout(output), patch("catos.market_api.serve") as mocked_serve:
            self.assertEqual(main(["--db", str(self.path), "--check"]), 0)
        mocked_serve.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["status"], "ready")

        with patch("catos.market_api.serve") as mocked_serve:
            self.assertEqual(main(["--db", str(self.path), "--port", "8877"]), 0)
        mocked_serve.assert_called_once_with(str(self.path), port=8877)

    def test_cli_default_database_points_to_v14_product_copy(self):
        ready = {
            "path": "ignored",
            "expected_schema": 14,
            "actual_schema": 14,
            "format": "catos-market-intel-v1",
            "read_only": True,
            "status": "ready",
        }
        with patch("catos.market_api.inspect_database", return_value=ready) as inspected, \
                patch("catos.market_api.serve") as mocked_serve:
            self.assertEqual(main([]), 0)
        inspected.assert_called_once_with("outputs/catos-market-intel-v14.sqlite")
        mocked_serve.assert_called_once_with(
            "outputs/catos-market-intel-v14.sqlite", port=8765)

    def test_dashboard_labels_persisted_state_as_read_only_not_live(self):
        client = TestClient(create_app(self.path))
        dashboard = client.get("/").text
        self.assertIn("READ ONLY", dashboard)
        self.assertIn("FRESHNESS NOT INFERRED", dashboard)
        self.assertNotIn("box-shadow:0 0 8px #2ea961", dashboard)


if __name__ == "__main__":
    unittest.main()
