from decimal import Decimal
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from catos.market_collectors import MarketCollectionError
from catos.market_dex import (
    DexScope,
    GeckoTerminalPool,
    GeckoTerminalPublicTransport,
    collect_public_swaps,
    parse_public_swap_rows,
)
from catos.market_intel import MarketIntelError, MarketIntelStore, SCHEMA_VERSION


SYMBOL = "BTC-USDT-SWAP"
TX = "0x" + "ab" * 32
WALLET = "0x" + "12" * 20
WETH = "0x" + "34" * 20
USDC = "0x" + "56" * 20


def row(**changes):
    value = {
        "symbol": SYMBOL, "chain": "ethereum", "venue": "uniswap-v3", "router": "universal-router",
        "wallet": WALLET, "side": "BUY", "base_quantity": "0.125000000000000001",
        "quote_notional": "8123.456789012345678901", "quote_currency": "USDC",
        "tx_hash": TX, "log_index": 7, "block_number": 123456, "source_ms": 9000,
    }
    value.update(changes)
    return value


class FakeTransport:
    def __init__(self, value):
        self.value = value
        self.scopes = []

    def fetch_swaps(self, scope):
        self.scopes.append(scope)
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class FakeResponse:
    def __init__(self, payload):
        self.status = 200
        self.body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    def getheader(self, _name):
        return None

    def read(self, _limit):
        return self.body

    def close(self):
        return None


class FakeConnection:
    payload = None
    last_target = None

    def __init__(self, *_args, **_kwargs):
        pass

    def request(self, method, target, body=None, headers=None):
        self.__class__.last_target = target
        self.method = method
        self.body = body
        self.headers = headers

    def getresponse(self):
        return FakeResponse(self.__class__.payload)

    def close(self):
        return None


def gecko_trade(*, tx, log_index, stamp, kind, base_amount, volume):
    if kind == "buy":
        from_token, to_token = USDC, WETH
        from_amount, to_amount = volume, base_amount
    else:
        from_token, to_token = WETH, USDC
        from_amount, to_amount = base_amount, volume
    return {
        "id": f"eth_1_{tx}_{log_index}_1",
        "type": "trade",
        "attributes": {
            "block_number": 1,
            "block_timestamp": stamp,
            "tx_hash": tx,
            "tx_from_address": WALLET,
            "kind": kind,
            "from_token_address": from_token,
            "to_token_address": to_token,
            "from_token_amount": from_amount,
            "to_token_amount": to_amount,
            "volume_in_usd": volume,
        },
    }


class DexParserTests(unittest.TestCase):
    def setUp(self):
        self.scope = DexScope(SYMBOL, 10_000, "ethereum")

    def test_exact_decimal_and_identity_are_preserved(self):
        batch = parse_public_swap_rows(self.scope, [row()], source="mock-indexer")
        obs = batch.observations[0]
        self.assertEqual(obs.base_quantity, Decimal("0.125000000000000001"))
        self.assertEqual(obs.quote_notional, Decimal("8123.456789012345678901"))
        self.assertEqual(obs.source_id, f"dex:ethereum:{TX}:7")
        self.assertEqual(obs.wallet, WALLET)

    def test_missing_optional_values_stay_missing_not_zero(self):
        batch = parse_public_swap_rows(
            self.scope, [row(wallet=None, quote_notional=None, quote_currency=None)], source="mock-indexer")
        obs = batch.observations[0]
        self.assertIsNone(obs.wallet)
        self.assertIsNone(obs.quote_notional)
        self.assertIsNone(obs.quote_currency)
        self.assertTrue(obs.provenance["wallet_missing"])
        self.assertTrue(obs.provenance["quote_notional_missing"])

    def test_missing_side_is_issue_and_scope_mismatch_fails_closed(self):
        batch = parse_public_swap_rows(self.scope, [row(side=None)], source="mock-indexer")
        self.assertEqual(batch.observations, ())
        self.assertEqual(batch.issues, (("dex_swaps", "missing_side"),))
        with self.assertRaisesRegex(MarketCollectionError, "scope_mismatch"):
            parse_public_swap_rows(self.scope, [row(symbol="ETH-USDT-SWAP")], source="mock-indexer")

    def test_mock_transport_failure_is_explicit_empty_batch(self):
        transport = FakeTransport(MarketCollectionError("timeout"))
        batch = collect_public_swaps(self.scope, transport, source="mock-indexer")
        self.assertEqual(batch.observations, ())
        self.assertEqual(batch.issues, (("dex_swaps", "timeout"),))

    def test_geckoterminal_keyless_adapter_maps_exact_values_and_proves_pool_window(self):
        pool = GeckoTerminalPool(
            symbol=SYMBOL, chain="ethereum", network_id="eth",
            pool_address="0x" + "78" * 20, venue="uniswap-v3", base_token_address=WETH)
        scope = DexScope(SYMBOL, 3_601_000, "ethereum")
        FakeConnection.payload = {"data": [
            gecko_trade(tx="0x" + "aa" * 32, log_index=7,
                        stamp="1970-01-01T01:00:00Z", kind="buy",
                        base_amount="0.123456789012345678", volume="321.123456789012345678"),
            gecko_trade(tx="0x" + "bb" * 32, log_index=8,
                        stamp="1970-01-01T00:00:01Z", kind="sell",
                        base_amount="0.023456789012345678", volume="21.123456789012345678"),
        ]}
        with patch("catos.market_dex.http.client.HTTPSConnection", FakeConnection):
            transport = GeckoTerminalPublicTransport((pool,))
            batch = collect_public_swaps(scope, transport, source=pool.source)
        self.assertEqual(FakeConnection.last_target,
                         f"/api/v2/networks/eth/pools/{pool.pool_address}/trades")
        self.assertEqual(batch.coverage["status"], "verified_pool_window")
        self.assertEqual(batch.coverage["scope"], "single_pool")
        self.assertEqual(batch.coverage["base_token_address"], WETH)
        self.assertEqual(batch.observations[0].base_quantity, Decimal("0.123456789012345678"))
        self.assertEqual(batch.observations[0].quote_notional, Decimal("321.123456789012345678"))
        self.assertEqual(batch.observations[0].quote_currency, "USD")
        self.assertEqual(batch.observations[1].side, "SELL")

    def test_geckoterminal_short_response_not_reaching_window_stays_unverified(self):
        pool = GeckoTerminalPool(
            symbol=SYMBOL, chain="ethereum", network_id="eth",
            pool_address="0x" + "78" * 20, venue="uniswap-v3", base_token_address=WETH)
        FakeConnection.payload = {"data": [
            gecko_trade(tx="0x" + "cc" * 32, log_index=1,
                        stamp="1970-01-01T00:59:00Z", kind="buy",
                        base_amount="1", volume="10"),
        ]}
        with patch("catos.market_dex.http.client.HTTPSConnection", FakeConnection):
            batch = collect_public_swaps(
                DexScope(SYMBOL, 3_600_000, "ethereum"),
                GeckoTerminalPublicTransport((pool,)), source=pool.source)
        self.assertEqual(batch.coverage["status"], "unverified_window_coverage")


class DexPersistenceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "intel.sqlite"
        self.store = MarketIntelStore(self.path)
        self.addCleanup(self.store.close)

    def test_schema_five_and_idempotent_text_persistence(self):
        self.assertEqual(
            self.store.connection.execute("PRAGMA user_version").fetchone()[0],
            SCHEMA_VERSION,
        )
        batch = parse_public_swap_rows(DexScope(SYMBOL, 10_000, "ethereum"), [row()], source="mock-indexer")
        self.store.record_dex_batch(batch)
        self.store.record_dex_batch(batch)
        record = self.store.connection.execute("SELECT * FROM dex_swap_observation").fetchone()
        self.assertEqual(record["base_quantity_text"], "0.125000000000000001")
        self.assertEqual(record["quote_notional_text"], "8123.456789012345678901")
        self.assertEqual(self.store.connection.execute(
            "SELECT typeof(quote_notional_text) FROM dex_swap_observation").fetchone()[0], "text")
        run = self.store.connection.execute("SELECT coverage_json FROM dex_collector_run").fetchone()
        self.assertEqual(json.loads(run["coverage_json"])["status"], "unverified_window_coverage")

    def test_replayed_swap_under_later_collection_anchor_is_idempotent(self):
        first = parse_public_swap_rows(
            DexScope(SYMBOL, 10_000, "ethereum"), [row()], source="mock-indexer")
        replay = parse_public_swap_rows(
            DexScope(SYMBOL, 11_000, "ethereum"), [row()], source="mock-indexer")
        self.store.record_dex_batch(first)
        self.store.record_dex_batch(replay)
        record = self.store.connection.execute("SELECT * FROM dex_swap_observation").fetchone()
        self.assertEqual(record["observed_at_ms"], 10_000)
        self.assertEqual(self.store.connection.execute(
            "SELECT count(*) FROM dex_collector_run").fetchone()[0], 2)

    def test_changed_same_identity_conflicts(self):
        first = parse_public_swap_rows(DexScope(SYMBOL, 10_000, "ethereum"), [row()], source="mock-indexer")
        changed = parse_public_swap_rows(
            DexScope(SYMBOL, 10_000, "ethereum"), [row(base_quantity="0.5")], source="mock-indexer")
        self.store.record_dex_batch(first)
        with self.assertRaisesRegex(MarketIntelError, "snapshot_conflict"):
            self.store.record_dex_batch(changed)


if __name__ == "__main__":
    unittest.main()
