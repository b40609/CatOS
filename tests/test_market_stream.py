from decimal import Decimal
import json
import unittest

from catos.market_collectors import CollectorScope, MarketCandle, MarketCollectionError
from catos.market_features import calculate_features
from catos.market_stream import (
    BINANCE_FUTURES_STREAM_BASE,
    BinanceAggTradeStream,
    TradeStreamBuffer,
    parse_binance_agg_trade,
)


def _frame(trade_id, time_ms, *, price="100", quantity="2", maker=False, symbol="BTCUSDT"):
    return json.dumps({
        "e": "aggTrade", "E": time_ms + 1, "s": symbol, "a": trade_id,
        "p": price, "q": quantity, "f": trade_id, "l": trade_id,
        "T": time_ms, "m": maker, "nq": quantity,
    }, separators=(",", ":"))


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.scope = CollectorScope("BTC-USDT-SWAP", 10_000)

    def test_agg_trade_is_decimal_and_aggressor_side_is_preserved(self):
        buy = parse_binance_agg_trade(self.scope, _frame(10, 1_000, maker=False))
        sell = parse_binance_agg_trade(self.scope, _frame(11, 1_001, maker=True))
        self.assertEqual((buy.price, buy.base_quantity, buy.aggressor_side),
                         (Decimal("100"), Decimal("2"), "BUY"))
        self.assertEqual(sell.aggressor_side, "SELL")

    def test_scope_message_limit_and_float_json_fail_closed(self):
        with self.assertRaisesRegex(MarketCollectionError, "scope_mismatch"):
            parse_binance_agg_trade(self.scope, _frame(10, 1_000, symbol="ETHUSDT"))
        with self.assertRaisesRegex(MarketCollectionError, "stream_message_too_large"):
            parse_binance_agg_trade(
                self.scope, _frame(10, 1_000) + (" " * 2_000), max_message_bytes=1_024)
        with self.assertRaisesRegex(MarketCollectionError, "malformed_stream_message"):
            parse_binance_agg_trade(
                self.scope,
                '{"e":"aggTrade","s":"BTCUSDT","a":1,"p":100.5,"q":"1","T":1000,"m":false}',
            )


class BufferTests(unittest.TestCase):
    def setUp(self):
        self.scope = CollectorScope("BTC-USDT-SWAP", 10_000)

    def test_complete_window_requires_uninterrupted_coverage(self):
        buffer = TradeStreamBuffer(self.scope, max_trades=100, retention_ms=60_000)
        buffer.connect(1_000)
        buffer.ingest(_frame(1, 1_500, price="100", quantity="2", maker=False))
        buffer.ingest(_frame(2, 2_000, price="110", quantity="1", maker=True))
        buffer.advance_coverage(3_000)
        window = buffer.window(1_200, 2_500)
        self.assertTrue(window.complete)
        self.assertEqual([trade.trade_id for trade in window.trades], ["1", "2"])
        buffer.disconnect(3_000)

    def test_reconnect_gap_never_becomes_complete_window(self):
        buffer = TradeStreamBuffer(self.scope, max_trades=100, retention_ms=60_000)
        buffer.connect(1_000)
        buffer.ingest(_frame(1, 1_500))
        buffer.advance_coverage(1_900)
        buffer.disconnect(2_000, clean=False)
        self.assertTrue(buffer.window(1_200, 1_800).complete)
        self.assertFalse(buffer.window(1_200, 1_950).complete)
        buffer.connect(2_500)
        buffer.ingest(_frame(2, 3_000))
        buffer.advance_coverage(4_000)
        self.assertFalse(buffer.window(1_200, 3_500).complete)
        self.assertTrue(buffer.window(2_600, 3_500).complete)

    def test_reconnect_does_not_allow_global_order_regression(self):
        buffer = TradeStreamBuffer(self.scope, max_trades=100, retention_ms=60_000)
        buffer.connect(1_000)
        buffer.ingest(_frame(2, 2_000))
        buffer.advance_coverage(2_100)
        buffer.disconnect(2_100)
        buffer.connect(2_500)
        with self.assertRaisesRegex(MarketCollectionError, "stream_order_violation"):
            buffer.ingest(_frame(3, 1_900))

    def test_overflow_marks_affected_window_incomplete(self):
        buffer = TradeStreamBuffer(self.scope, max_trades=2, retention_ms=60_000)
        buffer.connect(1_000)
        for trade_id, stamp in ((1, 1_500), (2, 2_000), (3, 2_500)):
            buffer.ingest(_frame(trade_id, stamp))
        buffer.advance_coverage(3_000)
        self.assertFalse(buffer.window(1_200, 2_900).complete)
        later = buffer.window(1_600, 2_900)
        self.assertTrue(later.complete)
        self.assertEqual([trade.trade_id for trade in later.trades], ["2", "3"])

    def test_duplicate_is_idempotent_but_conflict_invalidates_segment(self):
        buffer = TradeStreamBuffer(self.scope, max_trades=100, retention_ms=60_000)
        buffer.connect(1_000)
        frame = _frame(1, 1_500)
        self.assertTrue(buffer.ingest(frame))
        self.assertFalse(buffer.ingest(frame))
        with self.assertRaisesRegex(MarketCollectionError, "trade_conflict"):
            buffer.ingest(_frame(1, 1_500, price="101"))
        buffer.advance_coverage(3_000)
        self.assertFalse(buffer.window(1_200, 2_500).complete)

    def test_complete_window_enables_cvd_while_gap_keeps_features_missing(self):
        candles = tuple(
            MarketCandle("okx", "BTC-USDT-SWAP", "15m", index * 900_000, 900_000,
                         Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100"),
                         Decimal("1"), "base", True)
            for index in range(101)
        )
        buffer = TradeStreamBuffer(self.scope, max_trades=100, retention_ms=60_000)
        start, end = 90_000_000, 90_060_000
        buffer.connect(start)
        buffer.ingest(_frame(1, start + 1_000, price="100", quantity="3", maker=False))
        buffer.ingest(_frame(2, start + 2_000, price="100", quantity="1", maker=True))
        buffer.advance_coverage(end)
        complete = calculate_features(
            candles=candles, observed_at_ms=end, trade_window=buffer.window(start, end))
        self.assertEqual(complete.cvd_quote, Decimal("200"))
        self.assertEqual(complete.taker_buy_ratio, Decimal("0.75"))

        buffer.mark_gap()
        incomplete = calculate_features(
            candles=candles, observed_at_ms=end, trade_window=buffer.window(start, end))
        self.assertIsNone(incomplete.cvd_quote)
        self.assertIn("trade_window_incomplete", incomplete.issues)


class StreamAdapterTests(unittest.TestCase):
    def test_fixed_public_url_and_bounded_connector_options(self):
        calls = []

        class FakeConnection:
            def __enter__(self):
                return iter(("one", "two"))

            def __exit__(self, exc_type, exc, tb):
                return False

        def connector(url, **kwargs):
            calls.append((url, kwargs))
            return FakeConnection()

        stream = BinanceAggTradeStream(
            CollectorScope("BTC-USDT-SWAP", 10_000), connector=connector)
        self.assertEqual(list(stream.frames()), ["one", "two"])
        self.assertEqual(stream.url, f"{BINANCE_FUTURES_STREAM_BASE}/btcusdt@aggTrade")
        url, options = calls[0]
        self.assertEqual(url, stream.url)
        self.assertIsNone(options["proxy"])
        self.assertEqual(options["max_size"], 65_536)
        self.assertEqual(options["max_queue"], 16)


if __name__ == "__main__":
    unittest.main()
