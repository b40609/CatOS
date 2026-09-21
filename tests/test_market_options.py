from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from catos.market_api import MarketIntelReader
from catos.market_intel import MarketIntelError, MarketIntelStore
from catos.market_options import (
    DERIBIT_BOOK_SUMMARY_SOURCE,
    OKX_OPEN_INTEREST_SOURCE,
    OKX_OPTION_SUMMARY_SOURCE,
    PublicOptionError,
    collect_deribit_option_source,
    collect_public_options,
    deribit_book_summary_url,
    option_open_interest_url,
    option_summary_url,
    parse_deribit_book_summary,
    parse_option_open_interest,
    parse_option_summary,
)


SUMMARY = b'''{
  "code":"0","msg":"","data":[
    {"instType":"OPTION","instFamily":"BTC-USD","instId":"BTC-USD-261225-100000-C",
     "deltaBS":"0.550000000000000001","deltaPA":"0.0000055",
     "gammaBS":"0.000012300000000001","gammaPA":"0.00000000123",
     "thetaBS":"-12.3","thetaPA":"-0.000123","vegaBS":"45.6","vegaPA":"0.000456",
     "markVol":"0.62","bidVol":"0.61","askVol":"0.63","fwdPx":"100500.25","ts":"1000"},
    {"instType":"OPTION","instFamily":"BTC-USD","instId":"BTC-USD-261225-100000-P",
     "deltaBS":"-0.45","gammaBS":"0.000011","markVol":"0.64","ts":"1000"}
  ]
}'''

OPEN_INTEREST = b'''{
  "code":"0","msg":"","data":[
    {"instType":"OPTION","instFamily":"BTC-USD","instId":"BTC-USD-261225-100000-C",
     "oi":"123.456789012345678","oiCcy":"1.23456789012345678","ts":"1001"},
    {"instType":"OPTION","instFamily":"BTC-USD","instId":"BTC-USD-261225-100000-P",
     "oi":"98.765432109876543","oiCcy":"0.98765432109876543","ts":"1001"}
  ]
}'''

DERIBIT_BOOK_SUMMARY = b'''{
  "jsonrpc":"2.0","result":[
    {"instrument_name":"BTC-25SEP26-72000-P","open_interest":2840.5,
     "mark_price":0.000374,"mark_iv":73.56,"underlying_price":84805.88,
     "creation_timestamp":1789990456009,"base_currency":"BTC","quote_currency":"BTC"},
    {"instrument_name":"BTC-26MAR27-85000-C","open_interest":8.8,
     "mark_price":0.09880579,"mark_iv":39.18,"underlying_price":86997.37,
     "creation_timestamp":1789990456011,"base_currency":"BTC","quote_currency":"BTC"}
  ],"usIn":1789990456004127,"usOut":1789990456032352,"usDiff":28225,"testnet":false
}'''


class MarketOptionsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "intel.sqlite"
        self.store = MarketIntelStore(self.path)
        self.addCleanup(self.store.close)

    def test_public_parsers_preserve_decimal_greeks_and_open_interest(self):
        summary = parse_option_summary(SUMMARY, "BTC-USD", 2_000)
        self.assertEqual(summary.source, OKX_OPTION_SUMMARY_SOURCE)
        self.assertEqual(len(summary.items), 2)
        self.assertEqual(summary.items[0].delta_bs, Decimal("0.550000000000000001"))
        self.assertEqual(summary.items[0].gamma_bs, Decimal("0.000012300000000001"))
        self.assertEqual(summary.items[0].mark_vol, Decimal("0.62"))

        open_interest = parse_option_open_interest(OPEN_INTEREST, "btc-usd", 2_000)
        self.assertEqual(open_interest.source, OKX_OPEN_INTEREST_SOURCE)
        self.assertEqual(open_interest.items[0].oi, Decimal("123.456789012345678"))
        self.assertEqual(open_interest.items[0].oi_ccy, Decimal("1.23456789012345678"))

    def test_scope_mismatch_is_recorded_per_row(self):
        bad = SUMMARY.replace(b'"instFamily":"BTC-USD"', b'"instFamily":"ETH-USD"', 1)
        batch = parse_option_summary(bad, "BTC-USD", 2_000)
        self.assertEqual(len(batch.items), 1)
        self.assertEqual(batch.issues, (("scope_mismatch", "0"),))

    def test_public_option_source_urls_are_fixed_https_okx(self):
        self.assertEqual(
            option_summary_url("btc-usd"),
            "https://www.okx.com/api/v5/public/opt-summary?instFamily=BTC-USD",
        )
        self.assertEqual(
            option_open_interest_url("BTC-USD"),
            "https://www.okx.com/api/v5/public/open-interest?instType=OPTION&instFamily=BTC-USD",
        )
        with self.assertRaisesRegex(PublicOptionError, "invalid_inst_family"):
            option_summary_url("BTC-USDT-SWAP")

    def test_deribit_book_summary_preserves_inverse_option_oi_iv_and_contract_shape(self):
        batch = parse_deribit_book_summary(DERIBIT_BOOK_SUMMARY, "BTC-USD", 2_000)
        self.assertEqual(batch.source, DERIBIT_BOOK_SUMMARY_SOURCE)
        self.assertEqual(len(batch.items), 2)
        put = next(item for item in batch.items if item.option_type == "P")
        self.assertEqual(put.expiry_code, "25SEP26")
        self.assertEqual(put.strike, Decimal("72000"))
        self.assertEqual(put.open_interest_base, Decimal("2840.5"))
        self.assertEqual(put.mark_iv, Decimal("73.56"))
        self.assertEqual(put.premium_currency, "BTC")
        self.assertEqual(put.creation_ms, 1789990456009)

        mismatched = DERIBIT_BOOK_SUMMARY.replace(
            b'"base_currency":"BTC","quote_currency":"BTC"',
            b'"base_currency":"ETH","quote_currency":"ETH"', 1)
        partial = parse_deribit_book_summary(mismatched, "BTC-USD", 2_000)
        self.assertEqual(len(partial.items), 1)
        self.assertEqual(partial.issues, (("scope_mismatch", "0"),))

    def test_deribit_url_is_fixed_and_usd_inverse_family_only(self):
        self.assertEqual(
            deribit_book_summary_url("btc-usd"),
            "https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option",
        )
        with self.assertRaisesRegex(PublicOptionError, "unsupported_deribit_family"):
            deribit_book_summary_url("BTC-USDC")

    def test_deribit_source_run_is_persisted_without_mixing_venue_snapshots(self):
        batch = collect_deribit_option_source(
            self.store, "BTC-USD", 2_500,
            get_bytes=lambda url: DERIBIT_BOOK_SUMMARY,
        )
        self.assertEqual(len(batch.items), 2)
        row = self.store.connection.execute(
            "SELECT source,status,issues_json FROM option_context_run WHERE observed_at_ms=?",
            (2_500,),
        ).fetchone()
        self.assertEqual((row[0], row[1], row[2]),
                         (DERIBIT_BOOK_SUMMARY_SOURCE, "ok", "[]"))
        self.assertEqual(
            self.store.connection.execute("SELECT count(*) FROM option_summary_snapshot").fetchone()[0],
            0,
        )
        self.assertEqual(
            self.store.connection.execute("SELECT count(*) FROM option_open_interest_snapshot").fetchone()[0],
            0,
        )

    def test_one_option_source_failure_does_not_drop_other_source(self):
        def fake_get(url):
            if "opt-summary" in url:
                raise PublicOptionError("source_unavailable")
            if "open-interest" in url:
                return OPEN_INTEREST
            raise AssertionError(url)

        summary, open_interest = collect_public_options(
            self.store, "BTC-USD", 2_000, get_bytes=fake_get)
        self.assertEqual(summary.items, ())
        self.assertEqual(summary.issues, (("source_unavailable", "fetch"),))
        self.assertEqual(len(open_interest.items), 2)
        runs = self.store.connection.execute(
            "SELECT source,status FROM option_context_run ORDER BY source").fetchall()
        self.assertEqual(
            [(row[0], row[1]) for row in runs],
            [(OKX_OPEN_INTEREST_SOURCE, "ok"), (OKX_OPTION_SUMMARY_SOURCE, "partial")],
        )

    def test_source_to_sqlite_to_reader_is_exact_and_unranked(self):
        def fake_get(url):
            if "opt-summary" in url:
                return SUMMARY
            if "open-interest" in url:
                return OPEN_INTEREST
            raise AssertionError(url)

        collect_public_options(self.store, "BTC-USD", 2_000, get_bytes=fake_get)
        collect_public_options(self.store, "BTC-USD", 2_000, get_bytes=fake_get)
        reader = MarketIntelReader(self.path)
        result = reader.options("BTC-USD")
        self.assertEqual(result["status"], "materialized")
        self.assertIsNone(result["ranking"])
        self.assertIsNone(result["signed_gex"])
        self.assertIsNone(result["gamma_aggregation"])
        self.assertEqual(result["yaozi_gamma_formula_status"], "unknown_unpublished")
        self.assertEqual(len(result["items"]), 2)
        call = result["items"][0]
        self.assertEqual(call["gamma_bs_text"], "0.000012300000000001")
        self.assertEqual(call["open_interest"]["oi_text"], "123.456789012345678")
        self.assertEqual(
            self.store.connection.execute("SELECT count(*) FROM option_summary_snapshot").fetchone()[0],
            2,
        )

        changed = SUMMARY.replace(b'"0.000012300000000001"', b'"0.000099"')
        with self.assertRaisesRegex(MarketIntelError, "snapshot_conflict"):
            summary = parse_option_summary(changed, "BTC-USD", 2_000)
            self.store.record_option_summary_batch(summary)


if __name__ == "__main__":
    unittest.main()
