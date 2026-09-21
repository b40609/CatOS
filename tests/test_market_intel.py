from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from catos import market_collectors as collectors
from catos import market_features as features
from catos import market_liquidity as liquidity
from catos import market_signals as signals
from catos.market_intel import MarketIntelError, MarketIntelStore, SCHEMA_VERSION


D = Decimal


def okx(data):
    return {"code": "0", "data": [data]}


class FakeTransport:
    def __init__(self, responses):
        self.responses = dict(responses)
        self.requests = []

    def fetch(self, request):
        self.requests.append(request)
        value = self.responses[request.endpoint.alias]
        if isinstance(value, Exception):
            raise value
        return value


def responses():
    return {
        "okx_ticker": okx({"instId": "BTC-USDT-SWAP", "last": "100.25", "open24h": "95",
                            "volCcy24h": "1234.5", "ts": "1000"}),
        "okx_oi": okx({"instId": "BTC-USDT-SWAP", "oi": "120", "oiUsd": "12000000", "ts": "1001"}),
        "okx_funding": okx({"instId": "BTC-USDT-SWAP", "fundingRate": "-0.0001", "fundingTime": "1002"}),
        "binance_ticker": {"symbol": "BTCUSDT", "lastPrice": "100.30", "quoteVolume": "999999.9",
                           "priceChangePercent": "5.60", "closeTime": 1003},
        "binance_oi": {"symbol": "BTCUSDT", "openInterest": "119.5", "time": 1004},
        "binance_premium": {"symbol": "BTCUSDT", "lastFundingRate": "-0.0002", "time": 1005},
        "binance_top_lsr": [{"symbol": "BTCUSDT", "longShortRatio": "1.5", "timestamp": 1000},
                             {"symbol": "BTCUSDT", "longShortRatio": "1.6", "timestamp": 1006}],
        "binance_taker": [{"symbol": "BTCUSDT", "buySellRatio": "1", "timestamp": 1000},
                           {"symbol": "BTCUSDT", "buySellRatio": "3", "timestamp": 1007}],
    }


class CollectorTests(unittest.TestCase):
    def test_fixed_get_allowlist_and_scope(self):
        scope = collectors.CollectorScope("BTC-USDT-SWAP", 2000)
        self.assertEqual(scope.binance_symbol, "BTCUSDT")
        with self.assertRaises(ValueError):
            collectors.CollectorScope("BTCUSDT", 2000)
        with self.assertRaises(ValueError):
            collectors.PublicRequest(collectors.Endpoint("x", "x", "evil", "/", frozenset()))
        with self.assertRaises(ValueError):
            collectors.PublicRequest(collectors.ENDPOINTS["okx_ticker"], (("url", "https://evil"),))

    def test_symbol_collection_preserves_decimal_and_combines_sources(self):
        transport = FakeTransport(responses())
        batch = collectors.collect_symbol(collectors.CollectorScope("BTC-USDT-SWAP", 2000), transport)
        self.assertEqual([item.venue for item in batch.markets], ["okx", "binance"])
        self.assertEqual(batch.markets[0].price, D("100.25"))
        self.assertEqual(batch.derivatives[0].funding, D("-0.0001"))
        self.assertEqual(batch.derivatives[1].top_position_lsr, D("1.6"))
        self.assertEqual(batch.derivatives[1].taker_buy_ratio, D("0.75"))
        self.assertEqual(batch.issues, ())
        self.assertTrue(all(request.endpoint.host in ("www.okx.com", "fapi.binance.com")
                            for request in transport.requests))

    def test_missing_supplement_is_missing_not_zero(self):
        data = responses()
        data["binance_top_lsr"] = collectors.MarketCollectionError("timeout")
        data["binance_taker"] = collectors.MarketCollectionError("timeout")
        batch = collectors.collect_symbol(collectors.CollectorScope("BTC-USDT-SWAP", 2000), FakeTransport(data))
        binance = next(item for item in batch.derivatives if item.venue == "binance")
        self.assertIsNone(binance.top_position_lsr)
        self.assertIsNone(binance.taker_buy_ratio)
        self.assertIn(("binance_top_lsr", "timeout"), batch.issues)

    def test_universe_maps_same_asset_to_catos_symbol(self):
        transport = FakeTransport({
            "okx_instruments": {"code": "0", "data": [
                {"instId": "BTC-USDT-SWAP", "quoteCcy": "USDT", "settleCcy": "USDT",
                 "ctValCcy": "BTC", "state": "live"},
                {"instId": "ETH-USD-SWAP", "quoteCcy": "USD", "settleCcy": "USD",
                 "ctValCcy": "ETH", "state": "live"}]},
            "binance_exchange_info": {"symbols": [
                {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT",
                 "contractType": "PERPETUAL", "status": "TRADING"},
                {"symbol": "ETHUSDT_2603", "baseAsset": "ETH", "quoteAsset": "USDT",
                 "contractType": "CURRENT_QUARTER", "status": "TRADING"}]},
        })
        items = collectors.collect_universe(transport, 2000)
        self.assertEqual([(x.symbol, x.venue) for x in items],
                         [("BTC-USDT-SWAP", "binance"), ("BTC-USDT-SWAP", "okx")])

    def test_feature_input_prefers_closed_okx_candles_and_marks_rest_trades_incomplete(self):
        transport = FakeTransport({
            "okx_candles": {"code": "0", "data": [
                ["1800000", "102", "104", "101", "103", "10", "20", "2060", "0"],
                ["900000", "101", "103", "100", "102", "10", "20", "2040", "1"],
                ["0", "100", "102", "99", "101", "10", "20", "2020", "1"],
            ]},
            "binance_agg_trades": [
                {"a": 10, "p": "101", "q": "2", "T": 1000, "m": False},
                {"a": 11, "p": "102", "q": "1", "T": 1100, "m": True},
            ],
        })
        batch = collectors.collect_feature_inputs(
            collectors.CollectorScope("BTC-USDT-SWAP", 2_000_000), transport,
            interval="15m", candle_limit=20, trade_limit=10)
        self.assertEqual(batch.candle_venue, "okx")
        self.assertEqual([c.open_time_ms for c in batch.candles], [0, 900000])
        self.assertEqual([t.aggressor_side for t in batch.trade_tail], ["BUY", "SELL"])
        self.assertFalse(batch.trade_window_complete)
        self.assertNotIn("binance_klines", [request.endpoint.alias for request in transport.requests])


def feature_candles():
    result = []
    for index in range(101):
        price = D(100 + index)
        open_ = price
        high = price + D("1")
        low = price - D("1")
        close = price
        if index == 100:
            open_, high, low, close = D("200"), D("206"), D("199"), D("205")
        result.append(collectors.MarketCandle(
            "okx", "BTC-USDT-SWAP", "15m", index * 900_000, 900_000,
            open_, high, low, close, D("10"), "currency", True))
    return tuple(result)


class FeatureEngineTests(unittest.TestCase):
    def test_closed_bar_features_are_decimal_and_structure_breakout_is_deterministic(self):
        candles = feature_candles()
        trades = (
            collectors.MarketTrade("binance", "BTC-USDT-SWAP", "1", 90_000_001, D("100"), D("1"), "BUY"),
            collectors.MarketTrade("binance", "BTC-USDT-SWAP", "2", 90_000_002, D("100"), D("2"), "BUY"),
            collectors.MarketTrade("binance", "BTC-USDT-SWAP", "3", 90_000_003, D("100"), D("1"), "SELL"),
        )
        window = features.TradeWindow(90_000_000, 90_060_000, trades, True)
        result = features.calculate_features(
            candles=candles, observed_at_ms=90_900_000, trade_window=window,
            oi_delta_5m_pct=D("2"), oi_delta_1h_pct=D("5"), oi_delta_4h_pct=D("10"))
        self.assertEqual(result.feature_version, features.FEATURE_VERSION)
        self.assertEqual(result.structure_state, "BREAKOUT_UP")
        self.assertEqual(result.cvd_quote, D("200"))
        self.assertEqual(result.taker_buy_ratio, D("0.75"))
        self.assertEqual(result.trade_count, 3)
        self.assertIsInstance(result.atr_pct, D)
        self.assertIsInstance(result.realized_vol_pct, D)
        self.assertIsInstance(result.bb_width_pct, D)
        self.assertIsInstance(result.bbwp_pct, D)
        self.assertIsNotNone(result.return_24h_pct)

    def test_incomplete_trade_tail_never_becomes_cvd(self):
        candles = feature_candles()
        trade = collectors.MarketTrade("binance", "BTC-USDT-SWAP", "1", 1, D("100"), D("1"), "BUY")
        result = features.calculate_features(
            candles=candles, observed_at_ms=90_900_000,
            trade_window=features.TradeWindow(0, 60_000, (trade,), False))
        self.assertIsNone(result.cvd_quote)
        self.assertIsNone(result.taker_buy_ratio)
        self.assertIsNone(result.trade_count)
        self.assertIn("trade_window_incomplete", result.issues)


class MarketIntelStoreTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "market_intel.sqlite"
        self.store = MarketIntelStore(self.path)
        self.addCleanup(lambda: self.store.close() if self.store else None)

    @staticmethod
    def _drop_liquidity_v13(connection):
        connection.execute("DROP TABLE liquidity_snapshot")
        connection.execute("DROP TABLE liquidity_source_run")

    @staticmethod
    def _drop_social_v14(connection):
        connection.execute("DROP TABLE social_metric_snapshot")
        connection.execute("DROP TABLE social_source_run")

    def test_schema_zero_to_one_wal_full_and_separate_identity(self):
        self.assertEqual(self.store.connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        self.assertEqual(self.store.connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.assertEqual(self.store.connection.execute("PRAGMA synchronous").fetchone()[0], 2)
        tables = {row[0] for row in self.store.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("market_snapshot", tables)
        self.assertIn("push_snapshot", tables)
        self.assertIn("market_candle", tables)
        self.assertIn("flow_snapshot", tables)
        self.assertIn("signal_state", tables)
        self.assertIn("public_event_candidate", tables)
        self.assertIn("cross_axis_evaluation", tables)
        self.assertIn("status_label_snapshot", tables)
        self.assertIn("liquidity_source_run", tables)
        self.assertIn("liquidity_snapshot", tables)
        self.assertIn("social_source_run", tables)
        self.assertIn("social_metric_snapshot", tables)
        self.assertNotIn("intents", tables)

    def test_record_batch_materializes_okx_primary_and_binance_supplements_as_text(self):
        batch = collectors.collect_symbol(collectors.CollectorScope("BTC-USDT-SWAP", 2000),
                                          FakeTransport(responses()))
        self.store.record_public_batch(batch)
        latest = self.store.latest("BTC-USDT-SWAP")
        self.assertEqual(latest["market"]["price_text"], "100.25")
        self.assertEqual(latest["derivative"]["oi_text"], "120")
        self.assertEqual(latest["derivative"]["funding_text"], "-0.0001")
        self.assertEqual(latest["derivative"]["top_lsr_text"], "1.6")
        self.assertEqual(latest["derivative"]["taker_buy_ratio_text"], "0.75")
        for column in ("price_text", "volume_24h_text", "change_24h_text"):
            self.assertEqual(self.store.connection.execute(
                f"SELECT typeof({column}) FROM market_snapshot").fetchone()[0], "text")

    def test_exact_replay_is_idempotent_and_changed_same_timestamp_conflicts(self):
        batch = collectors.collect_symbol(collectors.CollectorScope("BTC-USDT-SWAP", 2000),
                                          FakeTransport(responses()))
        self.store.record_public_batch(batch)
        self.store.record_public_batch(batch)
        self.assertEqual(self.store.connection.execute("SELECT count(*) FROM market_snapshot").fetchone()[0], 1)
        changed_market = replace(batch.markets[0], price=D("101"))
        changed = replace(batch, markets=(changed_market, *batch.markets[1:]))
        with self.assertRaisesRegex(MarketIntelError, "snapshot_conflict"):
            self.store.record_public_batch(changed)
        self.assertEqual(self.store.latest("BTC-USDT-SWAP")["market"]["price_text"], "100.25")

    def test_unknown_nonempty_schema_is_refused(self):
        self.store.close()
        self.store = None
        other = sqlite3.connect(self.path)
        other.execute("DROP TABLE metadata")
        other.execute("PRAGMA user_version=0")
        other.commit()
        other.close()
        with self.assertRaisesRegex(MarketIntelError, "unrecognized_nonempty_database"):
            MarketIntelStore(self.path)

    def test_schema_one_migrates_to_current_without_touching_base_tables(self):
        self.store.close()
        self.store = None
        legacy = sqlite3.connect(self.path)
        legacy.execute("DROP TABLE market_candle")
        legacy.execute("DROP TABLE flow_snapshot")
        legacy.execute("DROP TABLE signal_state")
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
        self._drop_liquidity_v13(legacy)
        self._drop_social_v14(legacy)
        legacy.execute("PRAGMA user_version=1")
        legacy.commit()
        legacy.close()
        reopened = MarketIntelStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        tables = {row[0] for row in reopened.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("market_snapshot", tables)
        self.assertIn("market_candle", tables)
        self.assertIn("flow_snapshot", tables)
        self.assertIn("signal_state", tables)

    def test_schema_six_migrates_to_current_adds_dex_coverage_and_candidates(self):
        self.store.close()
        self.store = None
        legacy = sqlite3.connect(self.path)
        legacy.execute("ALTER TABLE dex_collector_run DROP COLUMN coverage_json")
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
        self._drop_liquidity_v13(legacy)
        self._drop_social_v14(legacy)
        legacy.execute("PRAGMA user_version=6")
        legacy.commit()
        legacy.close()
        reopened = MarketIntelStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        columns = {row[1] for row in reopened.connection.execute("PRAGMA table_info(dex_collector_run)")}
        self.assertIn("coverage_json", columns)
        tables = {row[0] for row in reopened.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("public_event_candidate", tables)
        journal_tables = {row[0] for row in reopened.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'journal%'")}
        self.assertEqual(journal_tables, set())

    def test_schema_seven_migrates_to_current_adds_candidate_and_public_context(self):
        self.store.close()
        self.store = None
        legacy = sqlite3.connect(self.path)
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
        self._drop_liquidity_v13(legacy)
        self._drop_social_v14(legacy)
        legacy.execute("PRAGMA user_version=7")
        legacy.commit()
        legacy.close()
        reopened = MarketIntelStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        columns = {row[1] for row in reopened.connection.execute(
            "PRAGMA table_info(public_event_candidate)")}
        self.assertEqual(columns, {
            "candidate_id", "candidate_type", "symbol", "observed_at_ms",
            "possible_yaozi_event_types_json", "evidence_json", "source_snapshot_ids_json",
        })
        tables = {row[0] for row in reopened.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"public_context_run", "narrative_snapshot", "news_event"} <= tables)
        journal_tables = {row[0] for row in reopened.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'journal%'")}
        self.assertEqual(journal_tables, set())

    def test_schema_eight_migrates_to_current_adds_public_context_and_cross_axis(self):
        self.store.close()
        self.store = None
        legacy = sqlite3.connect(self.path)
        legacy.execute("DROP TABLE public_context_run")
        legacy.execute("DROP TABLE narrative_snapshot")
        legacy.execute("DROP TABLE news_event")
        legacy.execute("DROP TABLE cross_axis_evaluation")
        legacy.execute("DROP TABLE status_label_snapshot")
        legacy.execute("DROP TABLE option_context_run")
        legacy.execute("DROP TABLE option_summary_snapshot")
        legacy.execute("DROP TABLE option_open_interest_snapshot")
        legacy.execute("DROP TABLE onchain_source_run")
        self._drop_liquidity_v13(legacy)
        self._drop_social_v14(legacy)
        legacy.execute("PRAGMA user_version=8")
        legacy.commit()
        legacy.close()
        reopened = MarketIntelStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        tables = {row[0] for row in reopened.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"public_context_run", "narrative_snapshot", "news_event"} <= tables)
        self.assertIn("public_event_candidate", tables)
        self.assertTrue({"cross_axis_evaluation", "status_label_snapshot"} <= tables)

    def test_schema_nine_migrates_to_current_adds_cross_axis_status_and_options(self):
        self.store.close()
        self.store = None
        legacy = sqlite3.connect(self.path)
        legacy.execute("DROP TABLE cross_axis_evaluation")
        legacy.execute("DROP TABLE status_label_snapshot")
        legacy.execute("DROP TABLE option_context_run")
        legacy.execute("DROP TABLE option_summary_snapshot")
        legacy.execute("DROP TABLE option_open_interest_snapshot")
        legacy.execute("DROP TABLE onchain_source_run")
        self._drop_liquidity_v13(legacy)
        self._drop_social_v14(legacy)
        legacy.execute("PRAGMA user_version=9")
        legacy.commit()
        legacy.close()
        reopened = MarketIntelStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        tables = {row[0] for row in reopened.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"cross_axis_evaluation", "status_label_snapshot"} <= tables)
        self.assertTrue({"option_context_run", "option_summary_snapshot",
                         "option_open_interest_snapshot"} <= tables)

    def test_schema_ten_migrates_to_eleven_adds_option_tables(self):
        self.store.close()
        self.store = None
        legacy = sqlite3.connect(self.path)
        legacy.execute("DROP TABLE option_context_run")
        legacy.execute("DROP TABLE option_summary_snapshot")
        legacy.execute("DROP TABLE option_open_interest_snapshot")
        legacy.execute("DROP TABLE onchain_source_run")
        self._drop_liquidity_v13(legacy)
        self._drop_social_v14(legacy)
        legacy.execute("PRAGMA user_version=10")
        legacy.commit()
        legacy.close()
        reopened = MarketIntelStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        tables = {row[0] for row in reopened.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"option_context_run", "option_summary_snapshot",
                         "option_open_interest_snapshot"} <= tables)
        self.assertIn("onchain_source_run", tables)

    def test_schema_eleven_migrates_to_twelve_adds_onchain_source_run(self):
        self.store.close()
        self.store = None
        legacy = sqlite3.connect(self.path)
        legacy.execute("DROP TABLE onchain_source_run")
        self._drop_liquidity_v13(legacy)
        self._drop_social_v14(legacy)
        legacy.execute("PRAGMA user_version=11")
        legacy.commit()
        legacy.close()
        reopened = MarketIntelStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        columns = {row[1] for row in reopened.connection.execute(
            "PRAGMA table_info(onchain_source_run)")}
        self.assertEqual(columns, {
            "source", "symbol", "chain", "observed_at_ms", "status",
            "source_scope_json", "evidence_json", "issues_json",
        })

    def test_schema_twelve_migrates_to_current_adds_liquidity_tables(self):
        self.store.close()
        self.store = None
        legacy = sqlite3.connect(self.path)
        self._drop_liquidity_v13(legacy)
        self._drop_social_v14(legacy)
        legacy.execute("PRAGMA user_version=12")
        legacy.commit()
        legacy.close()
        reopened = MarketIntelStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        tables = {row[0] for row in reopened.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"liquidity_source_run", "liquidity_snapshot"} <= tables)

    def test_schema_thirteen_migrates_to_current_adds_social_tables(self):
        self.store.close()
        self.store = None
        legacy = sqlite3.connect(self.path)
        self._drop_social_v14(legacy)
        legacy.execute("PRAGMA user_version=13")
        legacy.commit()
        legacy.close()
        reopened = MarketIntelStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        tables = {row[0] for row in reopened.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"social_source_run", "social_metric_snapshot"} <= tables)

    def test_schema_two_migrates_to_three(self):
        self.store.close()
        self.store = None
        legacy = sqlite3.connect(self.path)
        legacy.execute("DROP TABLE signal_state")
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
        self._drop_liquidity_v13(legacy)
        self._drop_social_v14(legacy)
        legacy.execute("PRAGMA user_version=2")
        legacy.commit()
        legacy.close()
        reopened = MarketIntelStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        tables = {row[0] for row in reopened.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("signal_state", tables)

    def test_liquidity_batch_is_decimal_text_exact_replay_safe_and_conflicts_on_change(self):
        batch = liquidity.collect_spot_liquidity(
            collectors.CollectorScope("BTC-USDT-SWAP", 2_000),
            FakeTransport({
                "okx_spot_books": {
                    "code": "0",
                    "data": [{
                        "ts": "1234",
                        "bids": [["100", "2", "0", "1"], ["98", "3", "0", "1"]],
                        "asks": [["101", "1", "0", "1"], ["103", "4", "0", "1"]],
                    }],
                },
                "binance_spot_depth": {
                    "lastUpdateId": 10,
                    "bids": [["100", "5"], ["98", "2"]],
                    "asks": [["101", "4"], ["103", "2"]],
                },
                "bybit_spot_orderbook": {
                    "retCode": 0,
                    "retMsg": "OK",
                    "result": {
                        "s": "BTCUSDT", "ts": 1234,
                        "b": [["100", "6"], ["98", "2"]],
                        "a": [["101", "3"], ["103", "2"]],
                    },
                },
                "gate_spot_orderbook": {
                    "id": 10, "current": 1235, "update": 1234,
                    "bids": [["100", "7"], ["98", "2"]],
                    "asks": [["101", "2"], ["103", "2"]],
                },
                "coinbase_spot_orderbook": {
                    "pricebook": {
                        "product_id": "BTC-USDT",
                        "bids": [{"price": "100", "size": "8"}, {"price": "98", "size": "2"}],
                        "asks": [{"price": "101", "size": "2"}, {"price": "103", "size": "2"}],
                        "time": "2026-09-21T09:56:34.236497Z",
                    },
                    "last": "100.5", "mid_market": "100.5",
                    "spread_bps": "1", "spread_absolute": "1",
                },
                "bitget_spot_orderbook": {
                    "code": "00000", "msg": "success", "requestTime": 1235,
                    "data": {
                        "ts": "1234",
                        "bids": [["100", "9"], ["98", "2"]],
                        "asks": [["101", "2"], ["103", "2"]],
                    },
                },
            }),
        )
        self.store.record_liquidity_batch(batch)
        self.store.record_liquidity_batch(batch)
        self.assertEqual(
            self.store.connection.execute("SELECT count(*) FROM liquidity_source_run").fetchone()[0],
            6,
        )
        self.assertEqual(
            self.store.connection.execute("SELECT count(*) FROM liquidity_snapshot").fetchone()[0],
            6,
        )
        row = self.store.connection.execute(
            "SELECT * FROM liquidity_snapshot WHERE venue='okx'").fetchone()
        self.assertEqual(row["down_2pct_cost_text"], "200")
        self.assertEqual(row["up_2pct_cost_text"], "101")
        self.assertEqual(
            self.store.connection.execute(
                "SELECT typeof(down_2pct_cost_text) FROM liquidity_snapshot WHERE venue='okx'"
            ).fetchone()[0],
            "text",
        )
        changed_snapshot = replace(batch.snapshots[0], mid=D("999"))
        changed = replace(batch, snapshots=(changed_snapshot, *batch.snapshots[1:]))
        with self.assertRaisesRegex(MarketIntelError, "snapshot_conflict"):
            self.store.record_liquidity_batch(changed)

    def test_onchain_source_run_is_exact_replay_safe_and_conflicts_on_change(self):
        kwargs = {
            "source": "blockchair",
            "symbol": "BTC-USDT-SWAP",
            "chain": "ethereum",
            "observed_at_ms": 4_000,
            "status": "ok",
            "source_scope": {
                "collection_mode": "live_public",
                "network": "ethereum",
                "addresses": ["0x" + "12" * 20],
            },
            "evidence": {
                "coverage_status": "complete_bounded_window",
                "daily_outgoing_distinct": [1, 2, 3],
            },
            "issues": (),
        }
        self.store.record_onchain_source_run(**kwargs)
        self.store.record_onchain_source_run(**kwargs)
        row = self.store.connection.execute(
            "SELECT * FROM onchain_source_run WHERE source='blockchair'").fetchone()
        self.assertEqual(row["status"], "ok")
        self.assertEqual(json.loads(row["source_scope_json"])["collection_mode"], "live_public")
        changed = dict(kwargs)
        changed["evidence"] = {
            "coverage_status": "provider_limit_truncated",
            "daily_outgoing_distinct": [1, 2, 3],
        }
        with self.assertRaisesRegex(MarketIntelError, "snapshot_conflict"):
            self.store.record_onchain_source_run(**changed)

    def test_cross_axis_and_explicit_status_labels_are_versioned_replay_safe(self):
        cross_axis = signals.evaluate_cross_axis(
            signals.CrossAxisInputs(D("75"), 3, True, "B"))
        labels = signals.evaluate_status_labels(
            signals.StatusLabelInputs(observe=True, dump_warning=False, new_candidate=None))
        self.store.record_cross_axis(
            "BTC-USDT-SWAP", 4000, cross_axis, source_snapshot_ids=("pattern:4000", "smf:4000"))
        self.store.record_status_labels(
            "BTC-USDT-SWAP", 4000, labels, source_snapshot_ids=("surface:4000",))
        self.store.record_cross_axis(
            "BTC-USDT-SWAP", 4000, cross_axis, source_snapshot_ids=("pattern:4000", "smf:4000"))
        self.store.record_status_labels(
            "BTC-USDT-SWAP", 4000, labels, source_snapshot_ids=("surface:4000",))

        rows = self.store.connection.execute(
            "SELECT axis_type,status,selected,evidence_json,threshold_json "
            "FROM cross_axis_evaluation ORDER BY axis_type").fetchall()
        self.assertEqual(len(rows), 2)
        selected = {row[0]: row[2] for row in rows}
        self.assertEqual(selected, {"ALPHA": 0, "ALPHA_PLUS": 1})
        plus = next(row for row in rows if row[0] == "ALPHA_PLUS")
        self.assertEqual(json.loads(plus[3])["pattern_strength"], "75")
        self.assertEqual(json.loads(plus[4])["pattern_strength_gte"], "75")

        label_rows = self.store.connection.execute(
            "SELECT label_type,status,evidence_json,threshold_json "
            "FROM status_label_snapshot ORDER BY label_type").fetchall()
        self.assertEqual(len(label_rows), 3)
        observe = next(row for row in label_rows if row[0] == "OBSERVE")
        self.assertEqual(observe[1], signals.HIT)
        self.assertTrue(json.loads(observe[2])["source_explicit_state"])
        self.assertEqual(
            json.loads(observe[3])["derivation"], "source_explicit")

        changed = signals.evaluate_cross_axis(
            signals.CrossAxisInputs(D("60"), 2, True, "B"))
        with self.assertRaisesRegex(MarketIntelError, "snapshot_conflict"):
            self.store.record_cross_axis(
                "BTC-USDT-SWAP", 4000, changed,
                source_snapshot_ids=("pattern:4000", "smf:4000"))
        changed_labels = signals.evaluate_status_labels(
            signals.StatusLabelInputs(observe=False, dump_warning=False, new_candidate=None))
        with self.assertRaisesRegex(MarketIntelError, "snapshot_conflict"):
            self.store.record_status_labels(
                "BTC-USDT-SWAP", 4000, changed_labels, source_snapshot_ids=("surface:4000",))

    def test_oi_deltas_use_same_venue_history_with_bounded_lag(self):
        symbol = "BTC-USDT-SWAP"
        final = 20_000_000

        def batch(at, oi):
            market = collectors.VenueMarketSnapshot("okx", symbol, at, at, D("100"), D("10"), "currency", D("0"))
            derivative = collectors.VenueDerivativeSnapshot(
                "okx", symbol, at, at, D(oi), "contracts", D("1000"), D("0"), None, None)
            return collectors.PublicMarketBatch(symbol, at, (market,), (derivative,), ())

        for at, oi in ((final - 14_400_000, "100"), (final - 3_600_000, "120"),
                       (final - 300_000, "150"), (final, "200")):
            self.store.record_public_batch(batch(at, oi))
        row = self.store.latest(symbol)["derivative"]
        self.assertEqual(D(row["oi_delta_4h_text"]), D("100"))
        self.assertTrue(row["oi_delta_1h_text"].startswith("66.666666"))
        self.assertTrue(row["oi_delta_5m_text"].startswith("33.333333"))

    def test_candles_and_feature_snapshot_are_immutable_decimal_text(self):
        candles = feature_candles()
        self.store.record_candles(candles)
        self.store.record_candles(candles)
        self.assertEqual(self.store.connection.execute("SELECT count(*) FROM market_candle").fetchone()[0], len(candles))
        self.assertEqual(self.store.connection.execute(
            "SELECT typeof(close_text) FROM market_candle LIMIT 1").fetchone()[0], "text")
        result = features.calculate_features(candles=candles, observed_at_ms=90_900_000)
        self.store.record_feature_set(result, provenance={"candles": "okx"})
        self.store.record_feature_set(result, provenance={"candles": "okx"})
        payload = self.store.connection.execute("SELECT payload_json FROM feature_snapshot").fetchone()[0]
        self.assertIn('"structure_state":"BREAKOUT_UP"', payload)
        flow = self.store.connection.execute("SELECT * FROM flow_snapshot").fetchone()
        self.assertEqual(flow["trade_window_complete"], 0)
        self.assertIsNone(flow["cvd_quote_text"])


if __name__ == "__main__":
    unittest.main()
