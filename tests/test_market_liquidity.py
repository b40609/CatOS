from decimal import Decimal
import unittest

from catos.market_collectors import CollectorScope, MarketCollectionError
from catos.market_liquidity import collect_spot_liquidity


SYMBOL = "BTC-USDT-SWAP"


class FakeTransport:
    def __init__(self, payloads):
        self.payloads = payloads
        self.requests = []

    def fetch(self, request):
        self.requests.append(request)
        payload = self.payloads[request.endpoint.alias]
        if isinstance(payload, BaseException):
            raise payload
        return payload


def _okx_book(*, deep=True):
    bids = [["100", "2", "0", "1"], ["98", "3", "0", "1"]]
    asks = [["101", "1", "0", "1"], ["103", "4", "0", "1"]]
    if not deep:
        bids[-1][0] = "99"
        asks[-1][0] = "102"
    return {"code": "0", "data": [{"ts": "1234", "bids": bids, "asks": asks}]}


def _binance_book():
    return {
        "lastUpdateId": 10,
        "bids": [["100", "5"], ["98", "2"]],
        "asks": [["101", "4"], ["103", "2"]],
    }


def _bybit_book():
    return {
        "retCode": 0,
        "retMsg": "OK",
        "result": {
            "s": "BTCUSDT",
            "ts": 1234,
            "b": [["100", "6"], ["98", "2"]],
            "a": [["101", "3"], ["103", "2"]],
        },
    }


def _gate_book():
    return {
        "id": 10,
        "current": 1235,
        "update": 1234,
        "bids": [["100", "7"], ["98", "2"]],
        "asks": [["101", "2"], ["103", "2"]],
    }


def _coinbase_book():
    return {
        "pricebook": {
            "product_id": "BTC-USDT",
            "bids": [{"price": "100", "size": "8"}, {"price": "98", "size": "2"}],
            "asks": [{"price": "101", "size": "2"}, {"price": "103", "size": "2"}],
            "time": "2026-09-21T09:56:34.236497Z",
        },
        "last": "100.5",
        "mid_market": "100.5",
        "spread_bps": "1",
        "spread_absolute": "1",
    }


def _bitget_book():
    return {
        "code": "00000",
        "msg": "success",
        "requestTime": 1235,
        "data": {
            "ts": "1234",
            "bids": [["100", "9"], ["98", "2"]],
            "asks": [["101", "2"], ["103", "2"]],
        },
    }


def _six_books(**overrides):
    payloads = {
        "okx_spot_books": _okx_book(),
        "binance_spot_depth": _binance_book(),
        "bybit_spot_orderbook": _bybit_book(),
        "gate_spot_orderbook": _gate_book(),
        "coinbase_spot_orderbook": _coinbase_book(),
        "bitget_spot_orderbook": _bitget_book(),
    }
    payloads.update(overrides)
    return payloads


class LiquidityTests(unittest.TestCase):
    def test_collects_six_spot_venues_and_computes_decimal_2pct_depth(self):
        transport = FakeTransport(_six_books())
        batch = collect_spot_liquidity(CollectorScope(SYMBOL, 2000), transport)
        self.assertEqual(batch.issues, ())
        self.assertEqual(len(batch.snapshots), 6)
        self.assertEqual(
            [(request.endpoint.alias, dict(request.params)) for request in transport.requests],
            [
                ("okx_spot_books", {"instId": "BTC-USDT", "sz": "400"}),
                ("binance_spot_depth", {"symbol": "BTCUSDT", "limit": "500"}),
                ("bybit_spot_orderbook", {"category": "spot", "symbol": "BTCUSDT", "limit": "200"}),
                ("gate_spot_orderbook", {"currency_pair": "BTC_USDT", "limit": "100", "with_id": "true"}),
                ("coinbase_spot_orderbook", {"product_id": "BTC-USDT", "limit": "100"}),
                ("bitget_spot_orderbook", {"symbol": "BTCUSDT", "type": "step0", "limit": "150"}),
            ],
        )
        okx = next(item for item in batch.snapshots if item.venue == "okx")
        self.assertEqual(okx.mid, Decimal("100.5"))
        self.assertEqual(okx.coverage["status"], "complete_2pct")
        self.assertEqual(okx.down_2pct_cost, Decimal("200"))
        self.assertEqual(okx.up_2pct_cost, Decimal("101"))
        self.assertIsInstance(okx.asymmetry, Decimal)
        self.assertFalse(okx.coverage["smf_eligible"])
        self.assertEqual(
            {item.venue for item in batch.snapshots},
            {"okx", "binance", "bybit", "gate", "coinbase", "bitget"},
        )

    def test_book_that_does_not_cross_boundary_is_lower_bound_not_full_depth(self):
        transport = FakeTransport(_six_books(okx_spot_books=_okx_book(deep=False)))
        batch = collect_spot_liquidity(CollectorScope(SYMBOL, 2000), transport)
        okx = next(item for item in batch.snapshots if item.venue == "okx")
        self.assertEqual(okx.coverage["status"], "partial_boundary_coverage")
        self.assertIsNone(okx.down_2pct_cost)
        self.assertIsNone(okx.up_2pct_cost)
        self.assertEqual(okx.down_2pct_lower_bound, Decimal("497"))
        self.assertEqual(okx.up_2pct_lower_bound, Decimal("509"))
        self.assertIsNone(okx.asymmetry)

    def test_one_source_failure_does_not_drop_other_venue(self):
        transport = FakeTransport(_six_books(okx_spot_books=MarketCollectionError("http_error")))
        batch = collect_spot_liquidity(CollectorScope(SYMBOL, 2000), transport)
        self.assertEqual(len(batch.snapshots), 5)
        self.assertEqual(
            {item.venue for item in batch.snapshots},
            {"binance", "bybit", "gate", "coinbase", "bitget"},
        )
        self.assertEqual(batch.issues, (("okx-spot-orderbook", "http_error"),))
        failed = next(run for run in batch.source_runs if run.venue == "okx")
        self.assertEqual(failed.status, "issues")
        self.assertEqual(failed.coverage["status"], "unavailable")

    def test_crossed_or_float_book_fails_closed(self):
        crossed = _okx_book()
        crossed["data"][0]["bids"][0][0] = "102"
        transport = FakeTransport(_six_books(okx_spot_books=crossed))
        batch = collect_spot_liquidity(CollectorScope(SYMBOL, 2000), transport)
        self.assertIn(("okx-spot-orderbook", "crossed_book"), batch.issues)

    def test_bybit_scope_mismatch_isolated_and_gate_integer_timestamp_is_preserved(self):
        bad_bybit = _bybit_book()
        bad_bybit["result"]["s"] = "ETHUSDT"
        transport = FakeTransport(_six_books(bybit_spot_orderbook=bad_bybit))
        batch = collect_spot_liquidity(CollectorScope(SYMBOL, 2000), transport)
        self.assertIn(("bybit-spot-orderbook", "scope_mismatch"), batch.issues)
        gate = next(item for item in batch.snapshots if item.venue == "gate")
        self.assertEqual(gate.source_ms, 1234)

    def test_coinbase_scope_mismatch_and_bitget_api_error_fail_closed(self):
        bad_coinbase = _coinbase_book()
        bad_coinbase["pricebook"]["product_id"] = "ETH-USDT"
        bad_bitget = _bitget_book()
        bad_bitget["code"] = "40001"
        batch = collect_spot_liquidity(
            CollectorScope(SYMBOL, 2000),
            FakeTransport(_six_books(
                coinbase_spot_orderbook=bad_coinbase,
                bitget_spot_orderbook=bad_bitget,
            )),
        )
        self.assertIn(("coinbase-spot-orderbook", "scope_mismatch"), batch.issues)
        self.assertIn(("bitget-spot-orderbook", "api_error"), batch.issues)
        self.assertEqual({item.venue for item in batch.snapshots}, {"okx", "binance", "bybit", "gate"})


if __name__ == "__main__":
    unittest.main()
