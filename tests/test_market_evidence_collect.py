from pathlib import Path
import json
import tempfile
import unittest

from catos.market_collectors import ENDPOINTS
from catos.market_dex import DexScope, GeckoTerminalPool, parse_public_swap_rows
from catos.market_evidence_collect import _load_watchlist_config, collect_once, run_bounded_cadence
from catos.market_hyperliquid import (
    HyperliquidScope,
    collect_bounded_trades,
    parse_hyperliquid_trades,
)
from catos.market_intel import MarketIntelStore
from catos.market_narrative_news import (
    COINDESK_RSS_URL,
    COINGECKO_CATEGORIES_URL,
    COINGECKO_TRENDING_URL,
)


SYMBOL = "BTC-USDT-SWAP"
BUYER = "0x1111111111111111111111111111111111111111"
SELLER = "0x2222222222222222222222222222222222222222"
BASE_TOKEN = "0x" + "34" * 20
POOL_ADDRESS = "0x" + "78" * 20

CONTEXT_CATEGORIES = b'''[
  {"id":"ai-agents","name":"AI Agents","market_cap":100,"market_cap_change_24h":2.5,
   "volume_24h":20,"content":"Agents","top_3_coins_id":["alpha"]}
]'''
CONTEXT_TRENDING = b'''{"coins":[],"nfts":[],"categories":[
  {"id":244,"name":"Data Availability","slug":"data-availability",
   "data":{"market_cap":200,"total_volume":40,
   "market_cap_change_percentage_24h":{"usd":3.5}}}
]}'''
CONTEXT_RSS = b'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><item>
<title>Context story</title>
<link>https://www.coindesk.com/markets/2026/09/21/context-story</link>
<pubDate>Mon, 21 Sep 2026 02:00:00 +0000</pubDate>
<description>Context summary</description><category>Markets</category>
</item></channel></rss>'''


def okx(row):
    return {"code": "0", "data": [row]}


class OISequenceTransport:
    def __init__(self, oi_values):
        self.oi_values = list(oi_values)
        self.round = 0
        self.requests = []

    def fetch(self, request):
        self.requests.append(request.endpoint.alias)
        if request.endpoint == ENDPOINTS["okx_ticker"]:
            return okx({
                "instId": SYMBOL,
                "last": "100",
                "open24h": "95",
                "volCcy24h": "1000",
                "ts": str(1_000_000 + self.round * 300_000),
            })
        if request.endpoint == ENDPOINTS["okx_oi"]:
            value = self.oi_values[self.round]
            payload = okx({
                "instId": SYMBOL,
                "oi": value,
                "oiUsd": str(int(value) * 100),
                "ts": str(1_000_001 + self.round * 300_000),
            })
            self.round += 1
            return payload
        raise AssertionError(request.endpoint.alias)


class WatchlistConfigTests(unittest.TestCase):
    def test_watchlist_config_loads_and_deduplicates_symbols(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "watchlist.json"
            path.write_text(json.dumps({
                "symbols": [SYMBOL, SYMBOL, "ETH-USDT-SWAP"],
                "hyperliquid_symbols": [SYMBOL],
            }), encoding="utf-8")
            symbols, hyperliquid_symbols = _load_watchlist_config(path)
        self.assertEqual(symbols, (SYMBOL, "ETH-USDT-SWAP"))
        self.assertEqual(hyperliquid_symbols, (SYMBOL,))

    def test_watchlist_config_rejects_unknown_fields_and_invalid_symbols(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unknown = root / "unknown.json"
            unknown.write_text(json.dumps({"symbols": [SYMBOL], "dex_pools": []}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid_watchlist_config"):
                _load_watchlist_config(unknown)
            invalid = root / "invalid.json"
            invalid.write_text(json.dumps({"symbols": ["not a symbol"]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid_watchlist_config"):
                _load_watchlist_config(invalid)


def trade_frame(observed_at_ms, *, source_ms=None):
    source_ms = observed_at_ms - 1 if source_ms is None else source_ms
    return json.dumps({
        "channel": "trades",
        "data": [{
            "coin": "BTC",
            "side": "B",
            "px": "100.25",
            "sz": "2",
            "hash": "0xabc",
            "time": source_ms,
            "tid": 77,
            "users": [BUYER, SELLER],
        }],
    }, separators=(",", ":"))


class FakeBoundedStream:
    def __init__(self, scope, frames):
        self.scope = scope
        self.frames = tuple(frames)
        self.max_message_bytes = 262_144

    def bounded_frames(self, **_kwargs):
        return iter(self.frames)


class EvidenceCollectionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "market-intel.sqlite"

    def test_two_five_minute_rounds_materialize_exact_oi_delta_candidate(self):
        transport = OISequenceTransport(("100", "110"))
        times = iter((1_000_000, 1_000_000, 1_300_000))
        sleeps = []

        summaries = run_bounded_cadence(
            db_path=self.path,
            symbols=(SYMBOL,),
            rounds=2,
            market_transport=transport,
            clock_ms=lambda: next(times),
            sleeper=sleeps.append,
        )

        self.assertEqual(transport.requests, ["okx_ticker", "okx_oi"] * 2)
        self.assertEqual(sleeps, [300.0])
        self.assertEqual(summaries[0].oi_delta_5m_available, 0)
        self.assertEqual(summaries[1].oi_delta_5m_available, 1)
        self.assertEqual(summaries[1].oi_candidates, 1)
        store = MarketIntelStore(self.path)
        self.addCleanup(store.close)
        row = store.connection.execute(
            "SELECT oi_delta_5m_text FROM derivative_snapshot WHERE symbol=? ORDER BY observed_at_ms DESC LIMIT 1",
            (SYMBOL,),
        ).fetchone()
        self.assertEqual(row[0], "10")
        candidate = store.connection.execute(
            "SELECT evidence_json FROM public_event_candidate WHERE candidate_type='OI_POSITIVE_CHANGE'"
        ).fetchone()
        evidence = json.loads(candidate[0])
        self.assertFalse(evidence["yaozi_event_triggered"])
        self.assertEqual(evidence["threshold_status"], "unknown_unpublished")


    def test_public_context_runs_every_third_five_minute_round_and_can_run_without_watchlist(self):
        now = {"ms": 1_000}
        sleeps = []
        calls = []

        def clock():
            return now["ms"]

        def sleeper(seconds):
            sleeps.append(seconds)
            now["ms"] += int(seconds * 1000)

        def get_bytes(url):
            calls.append(url)
            if url == COINGECKO_CATEGORIES_URL:
                return CONTEXT_CATEGORIES
            if url == COINGECKO_TRENDING_URL:
                return CONTEXT_TRENDING
            if url == COINDESK_RSS_URL:
                return CONTEXT_RSS
            raise AssertionError(url)

        summaries = run_bounded_cadence(
            db_path=self.path,
            symbols=(),
            rounds=4,
            public_context=True,
            public_context_every_rounds=3,
            public_context_get_bytes=get_bytes,
            clock_ms=clock,
            sleeper=sleeper,
        )

        self.assertEqual([item.narrative_runs for item in summaries], [1, 0, 0, 1])
        self.assertEqual([item.attention_runs for item in summaries], [1, 0, 0, 1])
        self.assertEqual([item.news_runs for item in summaries], [1, 0, 0, 1])
        self.assertEqual([item.narrative_items for item in summaries], [1, 0, 0, 1])
        self.assertEqual([item.attention_items for item in summaries], [1, 0, 0, 1])
        self.assertEqual([item.news_items for item in summaries], [1, 0, 0, 1])
        self.assertEqual(sleeps, [300.0, 300.0, 300.0])
        self.assertEqual(calls, [
            COINGECKO_CATEGORIES_URL, COINGECKO_TRENDING_URL, COINDESK_RSS_URL,
            COINGECKO_CATEGORIES_URL, COINGECKO_TRENDING_URL, COINDESK_RSS_URL,
        ])
        store = MarketIntelStore(self.path)
        self.addCleanup(store.close)
        self.assertEqual(store.connection.execute(
            "SELECT count(*) FROM public_context_run").fetchone()[0], 6)
        self.assertEqual(store.connection.execute(
            "SELECT count(*) FROM narrative_snapshot").fetchone()[0], 4)
        self.assertEqual(store.connection.execute(
            "SELECT count(*) FROM news_event").fetchone()[0], 1)

    def test_bounded_hyperliquid_ignores_ack_and_deduplicates_replayed_trade(self):
        scope = HyperliquidScope(SYMBOL, 2_000_000)
        ack = json.dumps({"channel": "subscriptionResponse", "data": {}})
        frame = trade_frame(scope.observed_at_ms)
        batch = collect_bounded_trades(
            scope, stream=FakeBoundedStream(scope, (ack, frame, frame)), max_frames=3)
        self.assertEqual(len(batch.observations), 2)
        self.assertEqual(batch.issues, ())

    def test_bounded_hyperliquid_advances_anchor_to_latest_received_trade(self):
        scope = HyperliquidScope(SYMBOL, 2_000_000)
        frame = trade_frame(scope.observed_at_ms, source_ms=scope.observed_at_ms + 250)
        batch = collect_bounded_trades(
            scope, stream=FakeBoundedStream(scope, (frame,)), max_frames=1)
        self.assertEqual(batch.observed_at_ms, 2_000_250)
        self.assertEqual({item.observed_at_ms for item in batch.observations}, {2_000_250})
        self.assertEqual(batch.issues, ())

    def test_hyperliquid_and_verified_dex_candidates_remain_evidence_only(self):
        at = 4_000_000
        transport = OISequenceTransport(("100",))
        pool = GeckoTerminalPool(
            symbol=SYMBOL,
            chain="ethereum",
            network_id="eth",
            pool_address=POOL_ADDRESS,
            venue="uniswap-v3",
            base_token_address=BASE_TOKEN,
        )

        def hl_collect(scope):
            return parse_hyperliquid_trades(scope, trade_frame(scope.observed_at_ms))

        def dex_collect(item, observed_at_ms):
            self.assertEqual(item, pool)
            return parse_public_swap_rows(
                DexScope(SYMBOL, observed_at_ms, "ethereum"),
                [{
                    "symbol": SYMBOL,
                    "chain": "ethereum",
                    "venue": "uniswap-v3",
                    "router": None,
                    "wallet": BUYER,
                    "side": "BUY",
                    "base_quantity": "1",
                    "quote_notional": "2500.125",
                    "quote_currency": "USD",
                    "tx_hash": "0x" + "ab" * 32,
                    "log_index": 7,
                    "block_number": 123,
                    "source_ms": observed_at_ms - 1000,
                }],
                source=pool.source,
                coverage={
                    "status": "verified_pool_window",
                    "scope": "single_pool",
                    "base_token_address": BASE_TOKEN,
                    "window_ms": 3_600_000,
                },
            )

        summary = collect_once(
            db_path=self.path,
            symbols=(SYMBOL,),
            observed_at_ms=at,
            market_transport=transport,
            hyperliquid_symbols=(SYMBOL,),
            hyperliquid_collector=hl_collect,
            dex_pools=(pool,),
            dex_collector=dex_collect,
        )
        self.assertEqual(summary.hyperliquid_observations, 2)
        self.assertEqual(summary.hyperliquid_candidates, 1)
        self.assertEqual(summary.dex_candidates, 1)
        store = MarketIntelStore(self.path)
        self.addCleanup(store.close)
        rows = store.connection.execute(
            "SELECT candidate_type,evidence_json FROM public_event_candidate ORDER BY candidate_type"
        ).fetchall()
        evidence = {row[0]: json.loads(row[1]) for row in rows}
        self.assertIn("HYPERLIQUID_PUBLIC_TRADE_ACTIVITY", evidence)
        self.assertIn("DEX_DIRECTIONAL_FLOW", evidence)
        self.assertTrue(all(not item["yaozi_event_triggered"] for item in evidence.values()))
        self.assertEqual(
            evidence["HYPERLIQUID_PUBLIC_TRADE_ACTIVITY"]["net_flow_status"],
            "not_defined_counterparty_symmetric",
        )


if __name__ == "__main__":
    unittest.main()
