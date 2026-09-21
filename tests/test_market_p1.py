from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
import json
import tempfile
import unittest

from catos.market_api import MarketIntelReader
from catos.market_dex import DexScope, parse_public_swap_rows
from catos.market_intel import MarketIntelError, MarketIntelStore, SCHEMA_VERSION
from catos.market_p1 import (
    CAPITAL_FLOW_GUIDE_EVENT_TYPES,
    CapitalFlowEvent,
    capital_flow_semantic_taxonomy,
    make_dex_capital_flow_event,
    make_dealer_snapshot,
    make_hyperliquid_activity_candidate,
    make_oi_event_candidate,
    make_observed_yaozi_event,
    make_public_dex_event_candidate,
    reduce_onchain_activity,
)
from catos.market_hyperliquid import HyperliquidObservation, HyperliquidObservationBatch
from catos.market_holders import HolderScope, dealer_chip, parse_blockscout_holder_snapshot
from catos.market_p1_materialize import materialize_existing


SYMBOL = "BTC-USDT-SWAP"


class P1ContractTests(unittest.TestCase):
    def test_guide_capital_flow_taxonomy_covers_all_31_semantics_without_local_gate_inference(self):
        taxonomy = capital_flow_semantic_taxonomy()
        self.assertEqual(taxonomy["contract"], "yaozi-capital-flow-guide-taxonomy-v1")
        self.assertEqual(taxonomy["event_kind_count"], 31)
        self.assertEqual(taxonomy["semantic_coverage"], "complete_31_of_31")
        self.assertEqual(taxonomy["trigger_coverage"], "partial_source_explicit_only")
        self.assertTrue(taxonomy["display_only"])
        self.assertFalse(taxonomy["smf_eligible"])
        self.assertEqual(
            {name: len(items) for name, items in taxonomy["groups"].items()},
            {"inflow": 10, "outflow": 6, "lifecycle": 9, "structural_quality": 6},
        )
        flattened = [
            item
            for items in taxonomy["groups"].values()
            for item in items
        ]
        self.assertEqual({item["event_type"] for item in flattened}, CAPITAL_FLOW_GUIDE_EVENT_TYPES)
        self.assertEqual(len(CAPITAL_FLOW_GUIDE_EVENT_TYPES), 31)
        self.assertTrue(all(item["local_trigger_status"] == "not_inferred" for item in flattened))
        self.assertNotIn("CONTRACT_IGNITION", CAPITAL_FLOW_GUIDE_EVENT_TYPES)

    def test_source_explicit_observed_fact_accepts_guide_semantic_without_private_trigger(self):
        event = make_observed_yaozi_event(
            symbol=SYMBOL,
            observed_at_ms=1_000,
            event_type="CYCLE_RESET",
            payload={"guide_label": "循環重置"},
            source_snapshot_id="guide-surface-sample.json",
            source_event_id="BTC-CYCLE-RESET-1000",
            source_surface="capital-flow",
        )
        self.assertEqual(event.event_type, "CYCLE_RESET")
        self.assertEqual(event.evidence["threshold_status"], "unknown_unpublished")
        self.assertIsNone(event.score)

    def test_onchain_flag_plateau_retention_and_exit_are_decimal_only(self):
        history = (2, 2, 2, 2, 2, 2, 2)
        first = reduce_onchain_activity(
            symbol=SYMBOL,
            chain="ethereum",
            observed_at_ms=1_000,
            outgoing_distinct=6,
            previous_complete_days=history,
        )
        self.assertEqual(first.state, "FLAGGED")
        self.assertEqual(first.baseline_live, D("2"))
        self.assertEqual(first.live_ratio, D("3"))
        self.assertEqual(first.baseline_anchor, D("2"))
        self.assertEqual(first.anchored_ratio, D("3"))
        self.assertEqual(first.plateau_started_at_ms, 1_000)

        retained = reduce_onchain_activity(
            symbol=SYMBOL,
            chain="ethereum",
            observed_at_ms=2_000,
            outgoing_distinct=3,
            previous_complete_days=history + (6,),
            previous=first,
        )
        self.assertEqual(retained.anchored_ratio, D("1.5"))
        self.assertEqual(retained.plateau_started_at_ms, 1_000)

        exited = reduce_onchain_activity(
            symbol=SYMBOL,
            chain="ethereum",
            observed_at_ms=3_000,
            outgoing_distinct=2,
            previous_complete_days=history + (6, 3),
            previous=retained,
        )
        self.assertEqual(exited.anchored_ratio, D("1"))
        self.assertIsNone(exited.plateau_started_at_ms)

    def test_missing_or_zero_baseline_never_becomes_zero_ratio(self):
        empty = reduce_onchain_activity(
            symbol=SYMBOL, chain="base", observed_at_ms=100,
            outgoing_distinct=5, previous_complete_days=(),
        )
        self.assertIsNone(empty.baseline_live)
        self.assertIsNone(empty.live_ratio)
        zeros = reduce_onchain_activity(
            symbol=SYMBOL, chain="base", observed_at_ms=200,
            outgoing_distinct=5, previous_complete_days=(0, 0, 0, 0, 0, 0, 0),
        )
        self.assertEqual(zeros.baseline_live, D("0"))
        self.assertIsNone(zeros.live_ratio)

    def test_dealer_final_score_stays_missing(self):
        snapshot = make_dealer_snapshot(
            symbol=SYMBOL,
            observed_at_ms=100,
            position={"funding_rate": D("-0.0001")},
            flow={"independent_buyers_1h": 3, "large_buy_sell_1h": None},
        )
        self.assertEqual(snapshot.coverage_mask, "POSITION|FLOW")
        self.assertEqual(snapshot.axis_count, 2)
        self.assertIsNone(snapshot.direction_score)
        self.assertIsNone(snapshot.direction_label)
        self.assertIsNone(snapshot.chip)

    def test_dealer_chip_axis_has_independent_coverage(self):
        snapshot = make_dealer_snapshot(
            symbol=SYMBOL,
            observed_at_ms=100,
            position={"top_trader_lsr": D("1.25")},
            chip={"top10_holding_pct": D("54.0")},
        )
        self.assertEqual(snapshot.coverage_mask, "POSITION|CHIP")
        self.assertEqual(snapshot.axis_count, 2)
        self.assertIsNone(snapshot.flow)
        self.assertEqual(snapshot.chip["top10_holding_pct"], D("54.0"))

    def test_verified_single_pool_window_materializes_direction_without_private_score(self):
        event = make_dex_capital_flow_event({
            "symbol": SYMBOL,
            "observed_at_ms": 3_600_000,
            "coverage_status": "verified_pool_window",
            "coverage_scope": "single_pool",
            "net_flow_status": "observed_sum",
            "net_flow_text": "123.456789012345678901",
            "quote_currency": "USD",
            "source_run_id": "dex-run:fixture",
            "window_start_ms": 0,
            "window_end_ms": 3_600_000,
            "swap_count": 12,
        })
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "inflow")
        self.assertIsNone(event.score)
        self.assertIsNone(event.cycle_state)
        self.assertEqual(event.evidence["net_flow"], D("123.456789012345678901"))
        self.assertIsNone(event.evidence["whale_threshold"])
        self.assertFalse(event.evidence["dealer_flow_eligible"])

    def test_truncated_or_zero_dex_window_does_not_invent_capital_flow_event(self):
        base = {
            "symbol": SYMBOL,
            "observed_at_ms": 3_600_000,
            "coverage_scope": "single_pool",
            "net_flow_status": "observed_sum",
            "net_flow_text": "10",
            "quote_currency": "USD",
            "source_run_id": "dex-run:fixture",
        }
        self.assertIsNone(make_dex_capital_flow_event(
            dict(base, coverage_status="provider_limit_truncated")))
        self.assertIsNone(make_dex_capital_flow_event(
            dict(base, coverage_status="verified_pool_window", net_flow_text="0")))

    def test_verified_multi_pool_window_keeps_all_source_run_ids(self):
        event = make_dex_capital_flow_event({
            "symbol": SYMBOL,
            "observed_at_ms": 3_600_000,
            "coverage_status": "verified_multi_pool_window",
            "coverage_scope": "multi_pool",
            "net_flow_status": "observed_sum",
            "net_flow_text": "-42.125",
            "quote_currency": "USD",
            "source_run_ids": ["dex-run:pool-a", "dex-run:pool-b"],
            "window_start_ms": 0,
            "window_end_ms": 3_600_000,
            "swap_count": 7,
        })
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "outflow")
        self.assertEqual(event.source_snapshot_ids, ("dex-run:pool-a", "dex-run:pool-b"))
        self.assertEqual(event.evidence["contract"], "catos_public_dex_multi_pool_window_v1")

    def test_observed_yaozi_event_preserves_fact_and_private_gate_stays_unknown(self):
        payload = {
            "trade_count": 5,
            "notional_usd_text": "101000",
            "wallet_count": 1,
        }
        event = make_observed_yaozi_event(
            symbol=SYMBOL,
            observed_at_ms=1_000,
            event_type="WHALE_BUY_CLUSTER",
            payload=payload,
            source_snapshot_id="yaozi-blackbox-sample-2026-09-18-1920.json",
            source_event_id="AKE-1900-WHALE_BUY_CLUSTER",
            source_surface="detail",
        )
        replay = make_observed_yaozi_event(
            symbol=SYMBOL,
            observed_at_ms=1_000,
            event_type="WHALE_BUY_CLUSTER",
            payload=payload,
            source_snapshot_id="yaozi-blackbox-sample-2026-09-18-1920.json",
            source_event_id="AKE-1900-WHALE_BUY_CLUSTER",
            source_surface="detail",
        )
        self.assertEqual(event, replay)
        self.assertIsNone(event.score)
        self.assertIsNone(event.cycle_state)
        self.assertEqual(event.evidence["source_event_type"], "WHALE_BUY_CLUSTER")
        self.assertEqual(event.evidence["threshold_status"], "unknown_unpublished")
        self.assertIsNone(event.evidence["threshold"])
        self.assertEqual(event.evidence["payload"], payload)

    def test_observed_yaozi_event_rejects_unseen_type_and_float_payload(self):
        base = dict(
            symbol=SYMBOL,
            observed_at_ms=1_000,
            source_snapshot_id="sample.json",
            source_event_id="event-1",
            source_surface="detail",
        )
        with self.assertRaisesRegex(ValueError, "unknown_yaozi_observed_event_type"):
            make_observed_yaozi_event(event_type="UNSEEN_PRIVATE_EVENT", payload={}, **base)
        with self.assertRaisesRegex(ValueError, "invalid_observed_event_payload"):
            make_observed_yaozi_event(
                event_type="MAJOR_OUTFLOW", payload={"netflow_usd": -41.0}, **base)

    def test_public_dex_candidate_keeps_private_gate_untriggered(self):
        candidate = make_public_dex_event_candidate({
            "symbol": SYMBOL,
            "observed_at_ms": 3_600_000,
            "coverage_status": "verified_multi_pool_window",
            "coverage_scope": "multi_pool",
            "net_flow_status": "observed_sum",
            "net_flow_text": "125.5000",
            "quote_currency": "USD",
            "source_run_ids": ["dex-run:pool-a", "dex-run:pool-b"],
        })
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.candidate_type, "DEX_DIRECTIONAL_FLOW")
        self.assertEqual(candidate.possible_yaozi_event_types,
                         ("FIRST_INFLOW", "CONTINUED_INFLOW", "INFLOW_ACCELERATION"))
        self.assertEqual(candidate.evidence["net_flow_text"], "125.5000")
        self.assertEqual(candidate.evidence["threshold_status"], "unknown_unpublished")
        self.assertFalse(candidate.evidence["yaozi_event_triggered"])
        self.assertNotIsInstance(candidate, CapitalFlowEvent)

    def test_positive_oi_candidate_does_not_declare_breakout_hit(self):
        candidate = make_oi_event_candidate({
            "symbol": SYMBOL,
            "observed_at_ms": 7_200_000,
            "oi_delta_5m_text": "1.8000",
            "oi_delta_1h_text": "8.0000",
            "oi_delta_4h_text": None,
        })
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.candidate_type, "OI_POSITIVE_CHANGE")
        self.assertEqual(candidate.possible_yaozi_event_types, ("OI_BREAKOUT",))
        self.assertEqual(candidate.evidence["oi_delta"]["oi_delta_1h_text"], "8.0000")
        self.assertIsNone(candidate.evidence["threshold"])
        self.assertFalse(candidate.evidence["yaozi_event_triggered"])
        self.assertIsNone(make_oi_event_candidate({
            "symbol": SYMBOL,
            "observed_at_ms": 7_200_000,
            "oi_delta_5m_text": "-1",
            "oi_delta_1h_text": "0",
            "oi_delta_4h_text": None,
        }))

    def test_hyperliquid_candidate_is_counterparty_symmetric_not_smart_wallet(self):
        common = dict(
            symbol=SYMBOL,
            observed_at_ms=10_000,
            source_ms=9_000,
            notional=D("2500.125"),
            notional_currency="USDC",
            position_or_flow_type="PUBLIC_TRADE_PARTICIPANT",
            source="hyperliquid",
        )
        batch = HyperliquidObservationBatch(
            symbol=SYMBOL,
            observed_at_ms=10_000,
            observations=(
                HyperliquidObservation(
                    wallet_or_trader="0x" + "11" * 20,
                    direction="BUY",
                    source_id="hyperliquid:9000:BTC:77:buyer",
                    provenance={"tid": 77},
                    **common,
                ),
                HyperliquidObservation(
                    wallet_or_trader="0x" + "22" * 20,
                    direction="SELL",
                    source_id="hyperliquid:9000:BTC:77:seller",
                    provenance={"tid": 77},
                    **common,
                ),
            ),
            issues=(),
        )
        candidate = make_hyperliquid_activity_candidate(batch)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.candidate_type, "HYPERLIQUID_PUBLIC_TRADE_ACTIVITY")
        self.assertEqual(candidate.possible_yaozi_event_types, ())
        self.assertEqual(candidate.evidence["trade_count"], 1)
        self.assertEqual(candidate.evidence["participant_observation_count"], 2)
        self.assertEqual(candidate.evidence["trade_notional_total_text"], "2500.125")
        self.assertEqual(candidate.evidence["net_flow_status"],
                         "not_defined_counterparty_symmetric")
        self.assertEqual(candidate.evidence["smart_wallet_classification_status"], "missing")
        self.assertFalse(candidate.evidence["yaozi_event_triggered"])


class P1PersistenceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "intel.sqlite"
        self.store = MarketIntelStore(self.path)
        self.addCleanup(self.store.close)

    def test_address_holder_snapshot_materializes_source_explicit_chip_without_private_direction(self):
        scope = HolderScope(
            SYMBOL, 1_000, "ethereum", "0x" + "12" * 20,
        )
        holder = parse_blockscout_holder_snapshot(
            scope,
            {
                "address": scope.contract_address,
                "type": "ERC-20",
                "total_supply": "1000",
                "holders": "10",
            },
            {
                "items": [
                    {"address": {"hash": f"0x{index + 1:040x}"}, "value": str(value)}
                    for index, value in enumerate((100, 90, 80, 70, 60, 50, 40, 30, 20, 10))
                ],
                "next_page_params": None,
            },
        )
        snapshot = self.store.materialize_dealer_snapshot(
            SYMBOL, 1_000, chip=dealer_chip(holder),
        )
        self.assertIn("CHIP", snapshot.coverage_mask)
        self.assertEqual(snapshot.chip["top10_holding_pct"], D("55"))
        self.assertEqual(
            snapshot.chip["coverage"]["beneficial_owner_aggregation"], "not_available",
        )
        self.assertIsNone(snapshot.direction_score)
        self.assertIsNone(snapshot.direction_label)
        dealer = MarketIntelReader(self.path).dealer(SYMBOL)
        self.assertEqual(dealer["snapshot"]["chip_json"]["top10_holding_pct"], "55.00")
        self.assertEqual(
            dealer["snapshot"]["chip_json"]["coverage"]["identity_scope"],
            "direct_token_balance_address",
        )
        self.assertIsNone(dealer["snapshot"]["direction_score_text"])

    def test_schema_eight_and_capital_flow_exact_replay_conflict(self):
        self.assertEqual(
            self.store.connection.execute("PRAGMA user_version").fetchone()[0],
            SCHEMA_VERSION,
        )
        event = CapitalFlowEvent(
            event_id="capital-1",
            event_type="inflow",
            symbol=SYMBOL,
            observed_at_ms=1_000,
            score=D("12.3400"),
            cycle_state=None,
            evidence={"notional": D("1000000.123456789")},
            source_snapshot_ids=("source-1",),
        )
        self.store.record_capital_flow_event(event)
        self.store.record_capital_flow_event(event)
        row = self.store.connection.execute("SELECT * FROM capital_flow_event").fetchone()
        self.assertEqual(row["score_text"], "12.3400")
        self.assertEqual(self.store.connection.execute(
            "SELECT typeof(score_text) FROM capital_flow_event").fetchone()[0], "text")
        self.assertEqual(json.loads(row["evidence_json"])["notional"], "1000000.123456789")
        changed = CapitalFlowEvent(
            event_id="capital-1", event_type="inflow", symbol=SYMBOL,
            observed_at_ms=1_000, score=D("12.35"), cycle_state=None,
            evidence={"notional": D("1000000.123456789")}, source_snapshot_ids=("source-1",),
        )
        with self.assertRaisesRegex(MarketIntelError, "snapshot_conflict"):
            self.store.record_capital_flow_event(changed)

    def test_public_candidate_exact_replay_conflicts_on_changed_fact_and_never_becomes_hit(self):
        candidate = make_oi_event_candidate({
            "symbol": SYMBOL,
            "observed_at_ms": 1_000,
            "oi_delta_5m_text": "1.2500",
            "oi_delta_1h_text": None,
            "oi_delta_4h_text": None,
        })
        self.store.record_public_event_candidate(candidate)
        self.store.record_public_event_candidate(candidate)
        row = self.store.connection.execute("SELECT * FROM public_event_candidate").fetchone()
        self.assertEqual(row["candidate_type"], "OI_POSITIVE_CHANGE")
        self.assertEqual(json.loads(row["possible_yaozi_event_types_json"]), ["OI_BREAKOUT"])
        self.assertFalse(json.loads(row["evidence_json"])["yaozi_event_triggered"])
        self.assertEqual(self.store.connection.execute(
            "SELECT count(*) FROM capital_flow_event").fetchone()[0], 0)
        changed = replace(candidate, evidence={**candidate.evidence, "threshold_status": "changed"})
        with self.assertRaisesRegex(MarketIntelError, "snapshot_conflict"):
            self.store.record_public_event_candidate(changed)

    def test_existing_public_evidence_materializes_candidates_without_network_or_event_promotion(self):
        j = lambda value: json.dumps(value, separators=(",", ":"), sort_keys=True)
        self.store.connection.execute(
            "INSERT INTO derivative_snapshot VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (SYMBOL, 1_000, "100", "1.5", None, None, None, None, None, None, j({"oi": "okx"})),
        )
        common = dict(
            symbol=SYMBOL,
            observed_at_ms=2_000,
            source_ms=1_900,
            notional=D("2500.125"),
            notional_currency="USDC",
            position_or_flow_type="PUBLIC_TRADE_PARTICIPANT",
            source="hyperliquid",
        )
        self.store.record_hyperliquid_batch(HyperliquidObservationBatch(
            symbol=SYMBOL,
            observed_at_ms=2_000,
            observations=(
                HyperliquidObservation(
                    wallet_or_trader="0x" + "11" * 20, direction="BUY",
                    source_id="hyperliquid:1900:BTC:77:buyer", provenance={"tid": 77}, **common),
                HyperliquidObservation(
                    wallet_or_trader="0x" + "22" * 20, direction="SELL",
                    source_id="hyperliquid:1900:BTC:77:seller", provenance={"tid": 77}, **common),
            ),
            issues=(),
        ))
        tx_hash = "0x" + "ab" * 32
        self.store.record_dex_batch(parse_public_swap_rows(
            DexScope(SYMBOL, 3_000, "ethereum"),
            [{
                "symbol": SYMBOL, "chain": "ethereum", "venue": "uniswap-v3",
                "router": None, "wallet": "0x" + "33" * 20, "side": "BUY",
                "base_quantity": "1", "quote_notional": "125.50", "quote_currency": "USD",
                "tx_hash": tx_hash, "log_index": 1, "block_number": 1, "source_ms": 2_900,
            }],
            source="pool-a",
            coverage={
                "status": "verified_pool_window", "scope": "single_pool",
                "pool_address": "0x" + "44" * 20,
                "base_token_address": "0x" + "55" * 20,
            },
        ))

        first = materialize_existing(self.path)
        second = materialize_existing(self.path)
        self.assertEqual(first.public_event_candidates, 3)
        self.assertEqual(second.public_event_candidates, 3)
        rows = MarketIntelReader(self.path).event_candidates(SYMBOL)["items"]
        self.assertEqual({row["candidate_type"] for row in rows}, {
            "OI_POSITIVE_CHANGE", "HYPERLIQUID_PUBLIC_TRADE_ACTIVITY", "DEX_DIRECTIONAL_FLOW",
        })
        self.assertTrue(all(row["evidence_json"]["yaozi_event_triggered"] is False for row in rows))
        self.assertEqual(self.store.connection.execute(
            "SELECT count(*) FROM capital_flow_event").fetchone()[0], 0)

    def test_observed_yaozi_event_persists_exact_fact_without_private_score(self):
        event = make_observed_yaozi_event(
            symbol=SYMBOL,
            observed_at_ms=2_000,
            event_type="SMART_WALLET_DISTRIBUTION",
            payload={
                "top_trader_count": 4,
                "direction": "SHORT",
                "notional_usd_text": "3700000",
            },
            source_snapshot_id="yaozi-blackbox-sample-2026-09-18-1853.json",
            source_event_id="ADA-0128-SMART_WALLET_DISTRIBUTION",
            source_surface="detail",
        )
        self.store.record_capital_flow_event(event)
        self.store.record_capital_flow_event(event)
        row = self.store.connection.execute(
            "SELECT * FROM capital_flow_event WHERE event_id=?", (event.event_id,)).fetchone()
        evidence = json.loads(row["evidence_json"])
        self.assertEqual(row["event_type"], "SMART_WALLET_DISTRIBUTION")
        self.assertIsNone(row["score_text"])
        self.assertIsNone(row["cycle_state"])
        self.assertEqual(evidence["threshold_status"], "unknown_unpublished")
        self.assertEqual(evidence["payload"]["notional_usd_text"], "3700000")

    def test_dealer_materializer_keeps_missing_null_and_decimal_text(self):
        j = lambda value: json.dumps(value, separators=(",", ":"), sort_keys=True)
        c = self.store.connection
        c.execute("INSERT INTO instrument VALUES (?,?,?,?,?,?,?)",
                  (SYMBOL, SYMBOL, j(["okx"]), "[]", 1, 100, 100))
        c.execute(
            "INSERT INTO derivative_snapshot VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (SYMBOL, 1_000, "123", None, None, None, "-0.0001", "1.25", "0.55", None,
             j({"oi": "okx"})),
        )
        tx_hash = "0x" + "ab" * 32
        dex = parse_public_swap_rows(
            DexScope(SYMBOL, 1_000, "ethereum"),
            [{
                "symbol": SYMBOL,
                "chain": "ethereum",
                "venue": "uniswap-v3",
                "router": "universal-router",
                "wallet": "0x" + "12" * 20,
                "side": "BUY",
                "base_quantity": "0.125000000000000001",
                "quote_notional": "8123.456789012345678901",
                "quote_currency": "USDC",
                "tx_hash": tx_hash,
                "log_index": 7,
                "block_number": 123456,
                "source_ms": 900,
            }],
            source="mock-indexer",
        )
        self.store.record_dex_batch(dex)
        snapshot = self.store.materialize_dealer_snapshot(SYMBOL, 1_000)
        self.assertEqual(snapshot.coverage_mask, "POSITION")
        self.assertEqual(snapshot.axis_count, 1)
        self.assertEqual(snapshot.position["top_trader_lsr"], D("1.25"))
        self.assertEqual(snapshot.position["taker_buy_pct"], D("55.00"))
        self.assertIsNone(snapshot.position["retail_lsr"])
        self.assertIsNone(snapshot.flow)
        self.assertIsNone(snapshot.direction_score)
        row = c.execute("SELECT * FROM dealer_snapshot").fetchone()
        self.assertIsNone(row["direction_score_text"])
        self.assertIsNone(row["flow_json"])
        position = json.loads(row["position_json"])
        self.assertEqual(position["funding_rate"], "-0.0001")
        self.assertIsNone(position["retail_lsr"])
        reader = MarketIntelReader(self.path)
        self.assertEqual(len(reader.raw_flow(SYMBOL)["dex"]), 1)
        dealer = reader.dealer(SYMBOL)
        self.assertIsNone(dealer["snapshot"]["flow_json"])
        self.assertEqual(dealer["flow_contract"], "explicit_dealer_snapshot_only")
        self.assertEqual(dealer["signal_dex_contract"], "separate_observation_pipeline")

    def test_onchain_persistence_and_reader_are_materialized(self):
        activity = reduce_onchain_activity(
            symbol=SYMBOL, chain="ethereum", observed_at_ms=1_000,
            outgoing_distinct=6, previous_complete_days=(2, 2, 2, 2, 2, 2, 2),
        )
        self.store.record_onchain_activity(activity)
        self.store.record_onchain_activity(activity)
        reader = MarketIntelReader(self.path)
        result = reader.onchain(symbol=SYMBOL)
        self.assertEqual(result["status"], "materialized")
        self.assertEqual(result["items"][0]["live_ratio_text"], "3")
        self.assertEqual(result["items"][0]["state"], "FLAGGED")


if __name__ == "__main__":
    unittest.main()
