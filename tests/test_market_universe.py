from pathlib import Path
import tempfile
import unittest

from catos import market_collectors as collectors
from catos.market_api import MarketIntelReader
from catos.market_universe import scan_once


class FakeTransport:
    def __init__(self, responses):
        self.responses = responses
        self.requests = []

    def fetch(self, request):
        self.requests.append(request)
        return self.responses[request.endpoint.alias]


def fixture_responses():
    return {
        "okx_instruments": {"code": "0", "data": [
            {"instId": "BTC-USDT-SWAP", "quoteCcy": "", "settleCcy": "USDT",
             "ctValCcy": "BTC", "state": "live"},
            {"instId": "ETH-USDT-SWAP", "quoteCcy": "", "settleCcy": "USDT",
             "ctValCcy": "ETH", "state": "live"},
        ]},
        "binance_exchange_info": {"symbols": [
            {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT",
             "contractType": "PERPETUAL", "status": "TRADING"},
            {"symbol": "SOLUSDT", "baseAsset": "SOL", "quoteAsset": "USDT",
             "contractType": "PERPETUAL", "status": "TRADING"},
        ]},
        "okx_tickers": {"code": "0", "data": [
            {"instId": "BTC-USDT-SWAP", "last": "115", "open24h": "100",
             "volCcy24h": "1000", "ts": "2000"},
            {"instId": "ETH-USDT-SWAP", "last": "88", "open24h": "100",
             "volCcy24h": "2000", "ts": "2001"},
        ]},
        "binance_ticker": [
            {"symbol": "BTCUSDT", "lastPrice": "116", "quoteVolume": "9999",
             "priceChangePercent": "16", "closeTime": 2002},
            {"symbol": "SOLUSDT", "lastPrice": "103", "quoteVolume": "8888",
             "priceChangePercent": "3", "closeTime": 2003},
        ],
        "binance_premium": [
            {"symbol": "BTCUSDT", "lastFundingRate": "-0.0001", "time": 2004},
            {"symbol": "SOLUSDT", "lastFundingRate": "0.0002", "time": 2005},
        ],
    }


class UniverseMarketTests(unittest.TestCase):
    def test_okx_swap_uses_settle_currency_when_quote_currency_is_blank(self):
        transport = FakeTransport({
            "okx_instruments": {"code": "0", "data": [
                {"instId": "META-USDT-SWAP", "quoteCcy": "", "settleCcy": "USDT",
                 "ctValCcy": "META", "state": "live"},
                {"instId": "BTC-USD-SWAP", "quoteCcy": "", "settleCcy": "BTC",
                 "ctValCcy": "BTC", "state": "live"},
            ]},
            "binance_exchange_info": {"symbols": []},
        })
        result = collectors.collect_universe(transport, 3000)
        self.assertEqual([(item.symbol, item.venue, item.active) for item in result], [
            ("META-USDT-SWAP", "okx", True),
        ])

    def test_bulk_collection_uses_four_public_requests_and_preserves_decimal(self):
        transport = FakeTransport(fixture_responses())
        result = collectors.collect_universe_markets(transport, 3000)
        self.assertEqual([request.endpoint.alias for request in transport.requests], [
            "okx_instruments", "binance_exchange_info", "okx_tickers", "binance_ticker",
            "binance_premium"])
        self.assertEqual(len({item.symbol for item in result.instruments if item.active}), 3)
        btc = next(batch for batch in result.batches if batch.symbol == "BTC-USDT-SWAP")
        self.assertEqual([item.venue for item in btc.markets], ["okx", "binance"])
        self.assertEqual(str(btc.markets[0].change_24h_pct), "15")
        self.assertEqual(str(btc.derivatives[0].funding), "-0.0001")
        self.assertEqual(result.issues, ())

    def test_scan_materializes_full_universe_and_only_known_momentum_rule(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        db_path = Path(directory.name) / "market_intel.sqlite"
        transport = FakeTransport(fixture_responses())
        summary = scan_once(db_path, transport=transport, observed_at_ms=3000)
        self.assertEqual(summary.active_symbols, 3)
        self.assertEqual(summary.materialized_symbols, 3)
        self.assertEqual(summary.missing_market_symbols, 0)
        self.assertEqual(summary.momentum_hits, 2)
        reader = MarketIntelReader(db_path)
        today = reader.today(1000)
        self.assertEqual(len(today["radar"]["items"]), 3)
        self.assertEqual(len(today["views"]["momentum"]["items"]), 3)
        self.assertEqual(today["views"]["flow"]["items"], [])
        self.assertEqual(reader.dealer("BTC-USDT-SWAP")["snapshot"]["coverage_mask"], "POSITION")
        states = reader.signals(1000)["signals"]
        self.assertEqual({item["symbol"] for item in states}, {"BTC-USDT-SWAP", "ETH-USDT-SWAP"})


if __name__ == "__main__":
    unittest.main()
