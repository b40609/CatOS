"""D1-Q1 quiescent-interval exact-equivalence E₀ tests. Synthetic/local only."""

from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from catos import (account_lock, account_report, demo_ledger_binding,
                   okx_collection as collection, risk)
from catos.demo_reconciliation import (
    FORMAL_ACCOUNT_ALIAS,
    FORMAL_ENVIRONMENT,
    FORMAL_INSTRUMENT,
    authorized_formal_scope,
    build_demo_quiescent_midnight_basis,
    build_formal_collection_plan,
    create_durable_day_ledger_provider,
    run_formal_reconciliation,
)
from catos.journal import Journal
from catos.supervisor import LocalSupervisor
from test_demo_reconciliation import (
    FakeClock,
    SYNTHETIC_FLOW_CLASSIFICATION,
    SequentialSyntheticTransport,
    base_formal_rows,
    btc_config,
)
from test_journal import proof


D = Decimal


def order_row(**changes):
    return dict(
        instType="SWAP", instId=FORMAL_INSTRUMENT, ordId="ORDER1",
        tdMode="cross", posSide="net", side="buy", state="canceled",
        sz="1", accFillSz="0", uTime="1700000000100",
    ) | changes


def position_row(**changes):
    return dict(
        instType="SWAP", instId=FORMAL_INSTRUMENT, posId="POS1",
        mgnMode="cross", posSide="net", pos="1", avgPx="65000",
        uTime="1700000000100",
    ) | changes


def fill_row(**changes):
    return dict(
        instId=FORMAL_INSTRUMENT, tradeId="TRADE1", ordId="ORDER1",
        fillSz="1", fillPx="65000", fee="-1", feeCcy="USDT",
        ts="1700000000100",
    ) | changes


def bill_row(**changes):
    return dict(
        billId="BILL1", type="1", subType="11", ccy="USDT",
        balChg="1", ts="1700000000100",
    ) | changes


def algo_row(**changes):
    return dict(
        instType="SWAP", instId=FORMAL_INSTRUMENT, algoId="ALGO1",
        state="live", tdMode="cross", posSide="net", side="sell",
        ordType="conditional", uTime="1700000000100", closeFraction="1",
        slTriggerPx="64000", slOrdPx="-1", slTriggerPxType="mark",
        reduceOnly=True, ordIdList=[],
    ) | changes


class DemoQuiescentE0BuilderTests(unittest.TestCase):
    START_MS = 1_700_000_000_000

    def _collect(self, mutate=None, *, delay_ms=100, cutoff_offset_ms=450):
        clock = FakeClock(self.START_MS)
        rows = base_formal_rows(inst_id=FORMAL_INSTRUMENT)
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]
        if mutate is not None:
            mutate(rows)
        cutoff_ms = self.START_MS + cutoff_offset_ms
        scope = authorized_formal_scope(cutoff_ms)
        plan = build_formal_collection_plan(scope)
        transport = SequentialSyntheticTransport(rows, clock, endpoint_delay_ms=delay_ms)
        result = collection.collect_plan(plan, transport, clock=clock)
        expected_uid = demo_ledger_binding.uid_digest("123456789")
        report = account_report.build_report(
            result,
            scope=scope,
            classifications=SYNTHETIC_FLOW_CLASSIFICATION,
            expected_uid_sha256=expected_uid,
        )
        return result, report, expected_uid, scope

    def _basis(self, mutate=None, **kwargs):
        result, report, expected_uid, _ = self._collect(mutate, **kwargs)
        return build_demo_quiescent_midnight_basis(result, report, expected_uid)

    def test_zero_event_interval_builds_verified_q1_basis(self):
        basis = self._basis()
        self.assertIsNotNone(basis)
        self.assertEqual(basis.source, risk.DEMO_QUIESCENT_BASELINE_SOURCE)
        self.assertEqual(basis.equity, D("10000"))
        self.assertEqual(basis.evidence.event_semantics,
                         risk.DEMO_QUIESCENT_BASELINE_EVENT_SEMANTICS)
        self.assertTrue(risk.is_verified_baseline(
            basis,
            account_alias=FORMAL_ACCOUNT_ALIAS,
            environment=FORMAL_ENVIRONMENT,
            target_day=basis.day,
        ))

    def test_any_usdt_or_non_usdt_bill_fails_closed(self):
        for ccy in ("USDT", "BTC"):
            with self.subTest(ccy=ccy):
                self.assertIsNone(self._basis(
                    lambda rows, ccy=ccy: rows.__setitem__(
                        "bills", [bill_row(ccy=ccy, ts=str(self.START_MS + 300))])))

    def test_fill_position_and_orders_fail_closed(self):
        cases = {
            "fill": lambda rows: rows.__setitem__(
                "fills", [fill_row(ts=str(self.START_MS + 300))]),
            "position": lambda rows: rows.__setitem__("positions", [position_row()]),
            "ordinary_pending": lambda rows: rows.__setitem__("orders_pending", [order_row(state="live")]),
            "ordinary_history": lambda rows: rows.__setitem__("orders_history", [order_row()]),
            "algo_pending": lambda rows: rows.__setitem__("algo_pending", [algo_row()]),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                self.assertIsNone(self._basis(mutate))

    def test_missing_order_history_window_provenance_fails_closed(self):
        result, _, expected_uid, scope = self._collect()
        endpoint = next(item for item in result.manifest.endpoint_manifests
                        if item.alias == "orders_history")
        broken = replace(endpoint, window_evidence=None)
        result = replace(result, manifest=replace(
            result.manifest,
            endpoint_manifests=tuple(
                broken if item.alias == "orders_history" else item
                for item in result.manifest.endpoint_manifests),
        ))
        report = account_report.build_report(
            result, scope=scope, classifications=SYNTHETIC_FLOW_CLASSIFICATION,
            expected_uid_sha256=expected_uid)
        self.assertIsNone(build_demo_quiescent_midnight_basis(result, report, expected_uid))

    def test_stale_or_too_long_collection_fails_closed(self):
        self.assertIsNone(self._basis(delay_ms=3000, cutoff_offset_ms=13500))

    def test_wrong_uid_mode_and_multicurrency_fail_closed(self):
        cases = {
            "uid": lambda rows: rows["account_config"][0].update(uid="987654321"),
            "mode": lambda rows: rows["account_config"][0].update(posMode="long_short_mode"),
            "multicurrency": lambda rows: rows["balance"][0]["details"].append(dict(
                ccy="BTC", eq="1", liab="0", availEq="1", ordFrozen="0",
                uTime="1700000000500")),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                self.assertIsNone(self._basis(mutate))

    def test_malformed_balance_never_becomes_zero_event_proof(self):
        self.assertIsNone(self._basis(
            lambda rows: rows["balance"][0]["details"][0].update(eq="NaN")))

    def test_balance_observed_after_cutoff_is_not_accepted(self):
        self.assertIsNone(self._basis(cutoff_offset_ms=0))

    def test_persisted_digest_detects_evidence_tamper(self):
        basis = self._basis()
        tampered_evidence = replace(
            basis.evidence,
            report_content_digest="f" * 64,
        )
        tampered = replace(basis, evidence=tampered_evidence)
        self.assertFalse(risk.is_verified_baseline(
            tampered,
            account_alias=FORMAL_ACCOUNT_ALIAS,
            environment=FORMAL_ENVIRONMENT,
            target_day=basis.day,
        ))
        self.assertFalse(risk.is_verified_baseline(
            replace(basis, digest="0" * 64),
            account_alias=FORMAL_ACCOUNT_ALIAS,
            environment=FORMAL_ENVIRONMENT,
            target_day=basis.day,
        ))


class DemoQuiescentE0DurableTests(unittest.IsolatedAsyncioTestCase):
    async def test_q1_commits_before_d3_and_survives_restart(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        database = root / "state.sqlite3"
        lock_patch = patch.object(account_lock, "LOCK_DIRECTORY", root / "locks")
        lock_patch.start()
        self.addCleanup(lock_patch.stop)

        journal = Journal(database, FORMAL_ACCOUNT_ALIAS, D("100"), risk_limits=risk.Limits())
        journal.register("bot", btc_config())
        journal.reconcile("bot", proof(0))
        journal.close()

        expected_uid = demo_ledger_binding.uid_digest("123456789")
        binding = demo_ledger_binding.make_binding(
            account_alias=FORMAL_ACCOUNT_ALIAS,
            expected_uid_sha256=expected_uid,
            database_path=database,
        )
        clock = FakeClock(1_700_000_000_000)
        supervisor = LocalSupervisor(
            database, account_id=FORMAL_ACCOUNT_ALIAS, bot_id="bot", config=btc_config(),
            fixture_budget=D("100"), risk_limits=risk.Limits(), day_clock=clock,
            demo_ledger_binding_proof=binding,
            expected_demo_uid_sha256=expected_uid,
        )
        await supervisor.start()

        cutoff_ms = clock.wall_ms() + 450
        rows = base_formal_rows(inst_id=FORMAL_INSTRUMENT)
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]
        transport = SequentialSyntheticTransport(rows, clock, endpoint_delay_ms=100)
        provider = create_durable_day_ledger_provider(supervisor)
        gate = await run_formal_reconciliation(
            supervisor,
            transport,
            plan=build_formal_collection_plan(authorized_formal_scope(cutoff_ms)),
            day_ledger_provider=provider,
            clock=clock,
            _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
        )
        self.assertTrue(gate.reconciled)
        self.assertFalse(gate.trade_authorized)
        basis = await supervisor.load_day_basis(risk.taipei_day(cutoff_ms))
        self.assertIsNotNone(basis)
        self.assertEqual(basis.source, risk.DEMO_QUIESCENT_BASELINE_SOURCE)
        await supervisor.close()

        restarted = LocalSupervisor(
            database, account_id=FORMAL_ACCOUNT_ALIAS, bot_id="bot", config=btc_config(),
            fixture_budget=D("100"), risk_limits=risk.Limits(), day_clock=clock,
            demo_ledger_binding_proof=binding,
            expected_demo_uid_sha256=expected_uid,
        )
        await restarted.start()
        self.addAsyncCleanup(restarted.close)
        durable = await restarted.load_day_basis(risk.taipei_day(cutoff_ms))
        self.assertTrue(risk.is_verified_baseline(
            durable,
            account_alias=FORMAL_ACCOUNT_ALIAS,
            environment=FORMAL_ENVIRONMENT,
            target_day=risk.taipei_day(cutoff_ms),
        ))
        day_start_ms = risk.taipei_day(cutoff_ms) * risk.DAY_MS - risk.TAIPEI_OFFSET_MS
        consumed = await create_durable_day_ledger_provider(restarted)(cutoff_ms, {
            "day_external_flow_usdt": "0",
            "flow_classification_id": SYNTHETIC_FLOW_CLASSIFICATION.classification_id,
            "unknown_flow_count": 0,
            "day_flow_start_ms": day_start_ms,
            "day_flow_cutoff_ms": cutoff_ms,
        })
        self.assertIsNotNone(consumed)
        self.assertEqual(consumed.baseline_equity_usdt, D("10000"))


if __name__ == "__main__":
    unittest.main()
