from pathlib import Path
from dataclasses import replace
import copy
import tempfile
import unittest

from catos.market_api import MarketIntelReader
from catos.market_intel import MarketIntelError, MarketIntelStore
from catos.market_social import (
    SOCIAL_CONTRACT,
    SOCIAL_MAPPING_CONTRACT,
    SOCIAL_SOURCE,
    SocialAssetRef,
    collect_coinpaprika_mapping,
    collect_coinpaprika_social,
    parse_coinpaprika_social,
    resolve_coinpaprika_assets,
)


BTC_PAYLOAD = {
    "id": "btc-bitcoin",
    "symbol": "BTC",
    "name": "Bitcoin",
    "links_extended": [
        {
            "url": "https://www.reddit.com/r/bitcoin",
            "type": "reddit",
            "stats": {"subscribers": 5_958_815},
        },
        {
            "url": "https://twitter.com/bitcoincoreorg",
            "type": "twitter",
            "stats": {"followers": 161_310},
        },
        {
            "url": "https://bitcoin.org/",
            "type": "website",
        },
    ],
}


class FakeTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def fetch_coin(self, coinpaprika_id):
        self.calls.append(coinpaprika_id)
        return self.payload


class FakeMappingTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def fetch_coin_list(self):
        self.calls += 1
        return self.payload


COIN_LIST = [
    {"id": "btc-bitcoin", "name": "Bitcoin", "symbol": "BTC", "rank": 1,
     "is_active": True, "type": "coin"},
    {"id": "eth-ethereum", "name": "Ethereum", "symbol": "ETH", "rank": 2,
     "is_active": True, "type": "coin"},
    {"id": "old-btc", "name": "Old BTC", "symbol": "BTC", "rank": 0,
     "is_active": False, "type": "token"},
]


class MarketSocialTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "market_intel.sqlite"
        self.store = MarketIntelStore(self.path)
        self.addCleanup(self.store.close)
        self.asset = SocialAssetRef("BTC-USDT-SWAP", "btc-bitcoin")

    def test_coin_list_resolves_only_unique_active_provider_identity_and_replays(self):
        symbols = ("ETH-USDT-SWAP", "BTC-USDT-SWAP")
        explicit = (
            SocialAssetRef("BTC-USDT-SWAP", "btc-bitcoin"),
            SocialAssetRef("ETH-USDT-SWAP", "eth-ethereum"),
        )
        first = resolve_coinpaprika_assets(symbols, COIN_LIST, explicit_assets=explicit)
        second = resolve_coinpaprika_assets(
            symbols, copy.deepcopy(COIN_LIST), explicit_assets=explicit)
        self.assertEqual(first, second)
        self.assertEqual(first.contract, SOCIAL_MAPPING_CONTRACT)
        self.assertEqual(
            [(item.symbol, item.coinpaprika_id) for item in first.assets],
            [("BTC-USDT-SWAP", "btc-bitcoin"), ("ETH-USDT-SWAP", "eth-ethereum")],
        )
        self.assertEqual(first.issues, ())

    def test_coin_list_collision_and_missing_asset_stay_unresolved(self):
        payload = COIN_LIST + [
            {"id": "btc-bitcoin-2", "name": "Bitcoin Two", "symbol": "BTC", "rank": 50,
             "is_active": True, "type": "coin"},
        ]
        coverage = resolve_coinpaprika_assets(
            ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "MISSING-USDT-SWAP"), payload,
            explicit_assets=(SocialAssetRef("ETH-USDT-SWAP", "eth-ethereum"),))
        self.assertEqual(
            [(item.symbol, item.coinpaprika_id) for item in coverage.assets],
            [("ETH-USDT-SWAP", "eth-ethereum")],
        )
        self.assertEqual(
            [(item.symbol, item.code, item.candidate_ids) for item in coverage.issues],
            [
                ("BTC-USDT-SWAP", "ambiguous_mapping", ("btc-bitcoin", "btc-bitcoin-2")),
                ("MISSING-USDT-SWAP", "missing_asset", ()),
            ],
        )

    def test_unique_symbol_without_explicit_identity_is_not_resolved(self):
        coverage = resolve_coinpaprika_assets(("ETH-USDT-SWAP",), COIN_LIST)
        self.assertEqual(coverage.assets, ())
        self.assertEqual(
            [(item.symbol, item.code, item.candidate_ids) for item in coverage.issues],
            [("ETH-USDT-SWAP", "unverified_identity", ("eth-ethereum",))],
        )

    def test_explicit_mapping_must_exist_as_current_active_same_symbol_identity(self):
        coverage = resolve_coinpaprika_assets(
            ("BTC-USDT-SWAP",), COIN_LIST,
            explicit_assets=(SocialAssetRef("BTC-USDT-SWAP", "btc-wrong"),))
        self.assertEqual(coverage.assets, ())
        self.assertEqual(coverage.issues[0].code, "identity_mismatch")
        self.assertEqual(coverage.issues[0].candidate_ids, ("btc-bitcoin",))

    def test_malformed_coin_list_fails_closed_for_entire_requested_universe(self):
        malformed = copy.deepcopy(COIN_LIST)
        malformed[0]["is_active"] = 1
        transport = FakeMappingTransport(malformed)
        coverage = collect_coinpaprika_mapping(
            ("BTC-USDT-SWAP", "ETH-USDT-SWAP"), transport)
        self.assertEqual(transport.calls, 1)
        self.assertEqual(coverage.assets, ())
        self.assertEqual(
            [(item.symbol, item.code) for item in coverage.issues],
            [("BTC-USDT-SWAP", "malformed_response"),
             ("ETH-USDT-SWAP", "malformed_response")],
        )

    def test_unresolved_asset_cannot_materialize_social_metric(self):
        payload = COIN_LIST + [
            {"id": "btc-bitcoin-2", "name": "Bitcoin Two", "symbol": "BTC", "rank": 50,
             "is_active": True, "type": "coin"},
        ]
        coverage = resolve_coinpaprika_assets(
            ("BTC-USDT-SWAP", "ETH-USDT-SWAP"), payload,
            explicit_assets=(SocialAssetRef("ETH-USDT-SWAP", "eth-ethereum"),))
        batches = [collect_coinpaprika_social(
            asset, 1_000, FakeTransport({**BTC_PAYLOAD, "id": asset.coinpaprika_id,
                                        "symbol": asset.symbol.split("-")[0]}))
                   for asset in coverage.assets]
        self.assertEqual([batch.symbol for batch in batches], ["ETH-USDT-SWAP"])
        self.assertNotIn("BTC-USDT-SWAP", [batch.symbol for batch in batches])

    def test_parser_accepts_only_numeric_social_stats_after_identity_check(self):
        batch = parse_coinpaprika_social(self.asset, BTC_PAYLOAD, 1_000)
        self.assertEqual(batch.source, SOCIAL_SOURCE)
        self.assertEqual(
            [(item.metric_kind, item.metric_value) for item in batch.metrics],
            [("reddit_subscribers", 5_958_815), ("twitter_followers", 161_310)],
        )
        self.assertEqual(batch.issues, ())

        mismatched = dict(BTC_PAYLOAD, symbol="WBTC")
        failed = collect_coinpaprika_social(self.asset, 1_000, FakeTransport(mismatched))
        self.assertEqual(failed.metrics, ())
        self.assertEqual(failed.issues, ("scope_mismatch",))

    def test_persistence_reader_and_source_coverage_keep_raw_count_semantics(self):
        batch = collect_coinpaprika_social(self.asset, 2_000, FakeTransport(BTC_PAYLOAD))
        self.store.record_social_batch(batch)
        self.store.record_social_batch(batch)

        self.assertEqual(
            self.store.connection.execute("SELECT count(*) FROM social_source_run").fetchone()[0],
            1,
        )
        self.assertEqual(
            self.store.connection.execute("SELECT count(*) FROM social_metric_snapshot").fetchone()[0],
            2,
        )

        reader = MarketIntelReader(self.path)
        social = reader.social(symbol="BTC-USDT-SWAP")
        self.assertEqual(social["contract"], SOCIAL_CONTRACT)
        self.assertEqual(social["metric_semantics"], "provider_reported_raw_counts_only")
        self.assertIsNone(social["ranking"])
        self.assertIsNone(social["social_heat"])
        self.assertIsNone(social["yaozi_heat"])
        self.assertEqual(
            {(item["metric_kind"], item["metric_value"]) for item in social["items"]},
            {("reddit_subscribers", 5_958_815), ("twitter_followers", 161_310)},
        )

        coverage = reader.source_coverage()
        social_item = next(item for item in coverage["items"] if item["domain"] == "social")
        self.assertEqual(social_item["coverage_status"], "provider_reported_counts")
        self.assertIn(
            {"capability": "social_metric", "status": "materialized_public_count_source"},
            coverage["gaps"],
        )

    def test_same_identity_with_changed_metric_conflicts(self):
        batch = collect_coinpaprika_social(self.asset, 3_000, FakeTransport(BTC_PAYLOAD))
        self.store.record_social_batch(batch)
        changed = {
            **BTC_PAYLOAD,
            "links_extended": [
                {
                    "url": "https://www.reddit.com/r/bitcoin",
                    "type": "reddit",
                    "stats": {"subscribers": 5_958_816},
                },
                BTC_PAYLOAD["links_extended"][1],
            ],
        }
        changed_batch = collect_coinpaprika_social(self.asset, 3_000, FakeTransport(changed))
        with self.assertRaisesRegex(MarketIntelError, "snapshot_conflict"):
            self.store.record_social_batch(changed_batch)

    def test_transport_failure_is_persisted_and_hides_previous_counts(self):
        self.store.record_social_batch(parse_coinpaprika_social(self.asset, BTC_PAYLOAD, 1_000))

        class OfflineTransport:
            def fetch_coin(self, coinpaprika_id):
                raise TimeoutError("upstream detail must not leak")

        failed = collect_coinpaprika_social(self.asset, 2_000, OfflineTransport())
        self.assertEqual(failed.metrics, ())
        self.assertEqual(failed.issues, ("source_transport_error",))
        self.store.record_social_batch(failed)
        result = MarketIntelReader(self.path).social(symbol=self.asset.symbol)
        self.assertEqual(result["items"], [])
        self.assertEqual(result["source_runs"][0]["status"], "issues")

    def test_link_metadata_is_empty_and_zero_is_a_real_count(self):
        payload = copy.deepcopy(BTC_PAYLOAD)
        for link in payload["links_extended"]:
            link.pop("stats", None)
        batch = parse_coinpaprika_social(self.asset, payload, 1_000)
        self.assertEqual(batch.metrics, ())
        self.store.record_social_batch(batch)
        self.assertEqual(MarketIntelReader(self.path).social()["source_runs"][0]["status"], "empty")
        payload["links_extended"][0]["stats"] = {"subscribers": 0}
        self.assertEqual(parse_coinpaprika_social(self.asset, payload, 2_000).metrics[0].metric_value, 0)

    def test_malformed_counts_types_urls_and_duplicates_fail_closed(self):
        for value in (True, -1, 1.5, "12", None, 2**63):
            with self.subTest(value=value):
                payload = copy.deepcopy(BTC_PAYLOAD)
                payload["links_extended"][0]["stats"]["subscribers"] = value
                failed = collect_coinpaprika_social(self.asset, 1_000, FakeTransport(payload))
                self.assertEqual(failed.metrics, ())
                self.assertEqual(failed.issues, ("malformed_response",))
        for field, value in (("type", []), ("url", "https://[")):
            payload = copy.deepcopy(BTC_PAYLOAD)
            payload["links_extended"][0][field] = value
            failed = collect_coinpaprika_social(self.asset, 1_000, FakeTransport(payload))
            self.assertEqual(failed.issues, ("malformed_response",))
        payload = copy.deepcopy(BTC_PAYLOAD)
        payload["links_extended"].append(payload["links_extended"][0])
        self.assertEqual(collect_coinpaprika_social(self.asset, 1_000, FakeTransport(payload)).issues,
                         ("ambiguous_metric",))

    def test_writer_rejects_invalid_batches_without_partial_rows(self):
        batch = parse_coinpaprika_social(self.asset, BTC_PAYLOAD, 1_000)
        invalid = (
            replace(batch, issues=("partial",)),
            replace(batch, symbol="BTC", provider_symbol="BTC"),
            replace(batch, asset_id="../btc-bitcoin"),
            replace(batch, metrics=(batch.metrics[0], batch.metrics[0])),
            replace(batch, metrics=(replace(batch.metrics[0], metric_kind="social_heat"),)),
            replace(batch, metrics=(replace(batch.metrics[0], metric_value=2**63),)),
            replace(batch, metrics=(replace(batch.metrics[0], source_url="javascript:bad"),)),
            replace(batch, metrics=(batch.metrics[0], replace(batch.metrics[1], symbol="ETH-USDT-SWAP"))),
        )
        for candidate in invalid:
            with self.subTest(candidate=candidate):
                with self.assertRaises(MarketIntelError):
                    self.store.record_social_batch(candidate)
                for table in ("social_source_run", "social_metric_snapshot"):
                    self.assertEqual(self.store.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
