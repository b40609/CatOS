from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from catos.market_collectors import MarketCollectionError
from catos.market_hyperliquid import (
    HYPERLIQUID_STREAM_URL,
    HyperliquidScope,
    HyperliquidTradeStream,
    issue_batch,
    parse_hyperliquid_trades,
)
from catos.market_intel import MarketIntelError, MarketIntelStore, SCHEMA_VERSION


BUYER = "0x1111111111111111111111111111111111111111"
SELLER = "0x2222222222222222222222222222222222222222"


def trade_frame(*, price="12345.678901", size="0.12345678", time_ms=9_000,
                tid=123456789, users=None, coin="BTC"):
    if users is None:
        users = [BUYER, SELLER]
    return json.dumps({
        "channel": "trades",
        "data": [{
            "coin": coin,
            "side": "B",
            "px": price,
            "sz": size,
            "hash": "0xabc",
            "time": time_ms,
            "tid": tid,
            "users": users,
        }],
    }, separators=(",", ":"))


class HyperliquidParserTests(unittest.TestCase):
    def setUp(self):
        self.scope = HyperliquidScope("BTC-USDT-SWAP", 10_000)

    def test_public_trade_becomes_two_exact_participant_observations(self):
        batch = parse_hyperliquid_trades(self.scope, trade_frame())
        self.assertEqual(batch.issues, ())
        self.assertEqual(len(batch.observations), 2)
        buy, sell = batch.observations
        expected = Decimal("12345.678901") * Decimal("0.12345678")
        self.assertEqual((buy.wallet_or_trader, buy.direction), (BUYER, "BUY"))
        self.assertEqual((sell.wallet_or_trader, sell.direction), (SELLER, "SELL"))
        self.assertEqual(buy.notional, expected)
        self.assertEqual(buy.notional_currency, "USDC")
        self.assertEqual(buy.position_or_flow_type, "PUBLIC_TRADE_PARTICIPANT")
        self.assertEqual(buy.source_id, "hyperliquid:9000:BTC:123456789:buyer")
        self.assertEqual(sell.source_id, "hyperliquid:9000:BTC:123456789:seller")
        self.assertNotIn("is_whale", buy.provenance)

    def test_missing_users_is_issue_and_never_fabricates_zero_or_wallet(self):
        frame = trade_frame(users=[])
        payload = json.loads(frame)
        payload["data"][0].pop("users")
        batch = parse_hyperliquid_trades(self.scope, json.dumps(payload, separators=(",", ":")))
        self.assertEqual(batch.observations, ())
        self.assertEqual(batch.issues, (("hyperliquid_trades", "missing_users"),))

    def test_missing_price_is_issue_not_zero(self):
        payload = json.loads(trade_frame())
        payload["data"][0].pop("px")
        batch = parse_hyperliquid_trades(self.scope, json.dumps(payload, separators=(",", ":")))
        self.assertEqual(batch.observations, ())
        self.assertEqual(batch.issues, (("hyperliquid_trades", "missing_price"),))

    def test_json_float_scope_mismatch_and_future_source_fail_closed(self):
        with self.assertRaisesRegex(MarketCollectionError, "malformed_stream_message"):
            parse_hyperliquid_trades(
                self.scope,
                '{"channel":"trades","data":[{"coin":"BTC","px":100.5,"sz":"1"}]}'
            )
        with self.assertRaisesRegex(MarketCollectionError, "scope_mismatch"):
            parse_hyperliquid_trades(self.scope, trade_frame(coin="ETH"))
        future = parse_hyperliquid_trades(self.scope, trade_frame(time_ms=10_001))
        self.assertEqual(future.observations, ())
        self.assertEqual(future.issues, (("hyperliquid_trades", "source_time_after_observed"),))

    def test_source_failure_is_explicit_empty_batch(self):
        batch = issue_batch(self.scope, "stream_transport_error")
        self.assertEqual(batch.observations, ())
        self.assertEqual(batch.issues, (("hyperliquid_trades", "stream_transport_error"),))


class HyperliquidAdapterTests(unittest.TestCase):
    def test_fixed_public_url_subscription_and_no_auth_surface(self):
        calls = []
        sent = []

        class FakeConnection:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def send(self, value):
                sent.append(value)

            def __iter__(self):
                return iter((trade_frame(),))

        def connector(url, **kwargs):
            calls.append((url, kwargs))
            return FakeConnection()

        stream = HyperliquidTradeStream(HyperliquidScope("BTC-USDT-SWAP", 10_000), connector=connector)
        self.assertEqual(list(stream.frames()), [trade_frame()])
        self.assertEqual(stream.url, HYPERLIQUID_STREAM_URL)
        self.assertEqual(json.loads(sent[0]), {
            "method": "subscribe", "subscription": {"type": "trades", "coin": "BTC"}})
        url, options = calls[0]
        self.assertEqual(url, HYPERLIQUID_STREAM_URL)
        self.assertIsNone(options["proxy"])
        self.assertIsNone(options["compression"])
        self.assertEqual(options["max_queue"], 16)
        self.assertFalse(any("key" in key.lower() or "secret" in key.lower() for key in options))


class HyperliquidPersistenceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "market_intel.sqlite"
        self.store = MarketIntelStore(self.path)
        self.addCleanup(lambda: self.store.close() if self.store is not None else None)

    def test_current_schema_and_decimal_text_persistence_are_idempotent(self):
        self.assertEqual(
            self.store.connection.execute("PRAGMA user_version").fetchone()[0],
            SCHEMA_VERSION,
        )
        batch = parse_hyperliquid_trades(HyperliquidScope("BTC-USDT-SWAP", 10_000), trade_frame())
        self.store.record_hyperliquid_batch(batch)
        self.store.record_hyperliquid_batch(batch)
        rows = self.store.connection.execute(
            "SELECT * FROM hyperliquid_observation ORDER BY direction").fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["notional_text"], str(batch.observations[0].notional))
        self.assertEqual(self.store.connection.execute(
            "SELECT typeof(notional_text) FROM hyperliquid_observation LIMIT 1").fetchone()[0], "text")
        self.assertEqual(self.store.connection.execute(
            "SELECT count(*) FROM hyperliquid_collector_run").fetchone()[0], 1)

    def test_replayed_trade_under_later_collection_anchor_is_idempotent(self):
        first = parse_hyperliquid_trades(HyperliquidScope("BTC-USDT-SWAP", 10_000), trade_frame())
        replay = parse_hyperliquid_trades(HyperliquidScope("BTC-USDT-SWAP", 11_000), trade_frame())
        self.store.record_hyperliquid_batch(first)
        self.store.record_hyperliquid_batch(replay)
        self.assertEqual(self.store.connection.execute(
            "SELECT count(*) FROM hyperliquid_observation").fetchone()[0], 2)
        self.assertEqual(self.store.connection.execute(
            "SELECT count(*) FROM hyperliquid_collector_run").fetchone()[0], 2)
        observed = self.store.connection.execute(
            "SELECT DISTINCT observed_at_ms FROM hyperliquid_observation").fetchall()
        self.assertEqual([row[0] for row in observed], [10_000])

    def test_empty_failure_batch_persists_issue_without_fake_observation(self):
        batch = issue_batch(HyperliquidScope("BTC-USDT-SWAP", 10_000), "stream_transport_error")
        self.store.record_hyperliquid_batch(batch)
        self.assertEqual(self.store.connection.execute(
            "SELECT count(*) FROM hyperliquid_observation").fetchone()[0], 0)
        issues = self.store.connection.execute(
            "SELECT issues_json FROM hyperliquid_collector_run").fetchone()[0]
        self.assertEqual(json.loads(issues), [["hyperliquid_trades", "stream_transport_error"]])

    def test_same_source_id_with_changed_fact_conflicts(self):
        batch = parse_hyperliquid_trades(HyperliquidScope("BTC-USDT-SWAP", 10_000), trade_frame())
        self.store.record_hyperliquid_batch(batch)
        changed = replace(batch.observations[0], notional=Decimal("1"))
        changed_batch = replace(batch, observations=(changed, batch.observations[1]))
        with self.assertRaisesRegex(MarketIntelError, "snapshot_conflict"):
            self.store.record_hyperliquid_batch(changed_batch)

    def test_schema_three_migrates_to_current_without_financial_journal_tables(self):
        self.store.close()
        self.store = None
        legacy = sqlite3.connect(self.path)
        legacy.execute("DROP TABLE hyperliquid_observation")
        legacy.execute("DROP TABLE hyperliquid_collector_run")
        legacy.execute("DROP TABLE dex_swap_observation")
        legacy.execute("DROP TABLE dex_collector_run")
        legacy.execute("DROP TABLE capital_flow_event")
        legacy.execute("DROP TABLE dealer_snapshot")
        legacy.execute("DROP TABLE onchain_activity")
        legacy.execute("DROP TABLE public_event_candidate")
        legacy.execute("DROP TABLE public_context_run")
        legacy.execute("DROP TABLE narrative_snapshot")
        legacy.execute("DROP TABLE news_event")
        legacy.execute("DROP TABLE cross_axis_evaluation")
        legacy.execute("DROP TABLE status_label_snapshot")
        legacy.execute("DROP TABLE option_context_run")
        legacy.execute("DROP TABLE option_summary_snapshot")
        legacy.execute("DROP TABLE option_open_interest_snapshot")
        legacy.execute("DROP TABLE onchain_source_run")
        legacy.execute("DROP TABLE liquidity_snapshot")
        legacy.execute("DROP TABLE liquidity_source_run")
        legacy.execute("PRAGMA user_version=3")
        legacy.commit()
        legacy.close()
        reopened = MarketIntelStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        tables = {row[0] for row in reopened.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("hyperliquid_observation", tables)
        self.assertIn("hyperliquid_collector_run", tables)
        self.assertNotIn("journal", tables)
        self.assertNotIn("intents", tables)


if __name__ == "__main__":
    unittest.main()
