from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from catos.market_api import MarketIntelReader
from catos.market_intel import MarketIntelStore
from catos.market_narrative_news import (
    COINDESK_RSS_URL,
    COINGECKO_CATEGORIES_URL,
    COINGECKO_TRENDING_URL,
    PublicContextError,
    _MAX_SOURCE_BYTES,
    _http_get,
    collect_public_context,
    parse_coindesk_rss,
    parse_coingecko_categories,
    parse_coingecko_trending_categories,
)


CATEGORIES = b'''[
  {"id":"ai-agents","name":"AI Agents","market_cap":123456789.123456789,
   "market_cap_change_24h":-2.500000000000001,"volume_24h":999.000000000000001,
   "content":"Agent tokens","top_3_coins_id":["alpha","beta"]},
  {"id":"defi","name":"Decentralized Finance","market_cap":500,
   "market_cap_change_24h":3.25,"volume_24h":120,"content":null,
   "top_3_coins_id":["gamma"]}
]'''

TRENDING = b'''{
  "coins":[],"nfts":[],"categories":[
    {"id":244,"name":"Data Availability","slug":"data-availability",
     "market_cap_1h_change":3.1530813588985613,
     "data":{"market_cap":6741561451.703885,"total_volume":2280246266.7819567,
       "market_cap_change_percentage_24h":{"usd":20.35030083042584}}},
    {"id":10673,"name":"Chain Abstraction","slug":"chain-abstraction",
     "market_cap_1h_change":1.962571608478456,
     "data":{"market_cap":15397421317.913319,"total_volume":2661327040.0982385,
       "market_cap_change_percentage_24h":{"usd":11.912369594365474}}}
  ]
}'''

RSS = b'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Second story</title>
    <link>https://www.coindesk.com/markets/2026/09/21/second-story</link>
    <pubDate>Mon, 21 Sep 2026 02:00:00 +0000</pubDate>
    <description>Second summary</description>
    <category>Markets</category>
  </item>
  <item>
    <title>First story</title>
    <link>https://www.coindesk.com/business/2026/09/20/first-story</link>
    <pubDate>Sun, 20 Sep 2026 12:00:00 +0000</pubDate>
    <description>First summary</description>
    <category>Business</category><category>Crypto</category>
  </item>
</channel></rss>'''


class NarrativeNewsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "intel.sqlite"
        self.store = MarketIntelStore(self.path)
        self.addCleanup(self.store.close)

    def test_parsers_preserve_decimal_and_source_facts_without_ranking(self):
        narratives = parse_coingecko_categories(CATEGORIES, 1_000)
        self.assertEqual([item.narrative_id for item in narratives.items], ["ai-agents", "defi"])
        self.assertEqual(
            narratives.items[0].market_cap,
            Decimal("123456789.123456789"),
        )
        self.assertEqual(
            narratives.items[0].market_cap_change_24h,
            Decimal("-2.500000000000001"),
        )
        attention = parse_coingecko_trending_categories(TRENDING, 1_000)
        self.assertEqual(
            [item.narrative_id for item in attention.items],
            ["data-availability", "chain-abstraction"],
        )
        self.assertEqual(attention.items[0].market_cap, Decimal("6741561451.703885"))
        self.assertEqual(
            attention.items[0].market_cap_change_24h,
            Decimal("20.35030083042584"),
        )
        news = parse_coindesk_rss(RSS, 1_000)
        self.assertEqual([item.title for item in news.items], ["Second story", "First story"])
        self.assertEqual(news.items[1].categories, ("Business", "Crypto"))

    def test_http_source_size_is_bounded(self):
        class Response:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return False
            def read(self, size):
                self.requested = size
                return b"x" * size

        response = Response()
        with patch("catos.market_narrative_news.urlopen", return_value=response):
            with self.assertRaisesRegex(PublicContextError, "source_too_large"):
                _http_get(COINGECKO_CATEGORIES_URL)
        self.assertEqual(response.requested, _MAX_SOURCE_BYTES + 1)

    def test_one_public_source_failure_is_recorded_without_dropping_the_other_source(self):
        def fake_get(url):
            if url == COINGECKO_CATEGORIES_URL:
                return CATEGORIES
            if url == COINGECKO_TRENDING_URL:
                return TRENDING
            if url == COINDESK_RSS_URL:
                raise PublicContextError("source_unavailable")
            raise AssertionError(url)

        narratives, attention, news = collect_public_context(self.store, 1_000, get_bytes=fake_get)
        self.assertEqual(len(narratives.items), 2)
        self.assertEqual(len(attention.items), 2)
        self.assertEqual(news.items, ())
        self.assertEqual(news.issues, (("source_unavailable", "fetch"),))
        self.assertEqual(self.store.connection.execute(
            "SELECT count(*) FROM narrative_snapshot").fetchone()[0], 4)
        self.assertEqual(self.store.connection.execute(
            "SELECT count(*) FROM news_event").fetchone()[0], 0)
        self.assertEqual(self.store.connection.execute(
            "SELECT count(*) FROM public_context_run").fetchone()[0], 3)

    def test_public_source_to_sqlite_to_reader_is_deterministic(self):
        calls = []

        def fake_get(url):
            calls.append(url)
            if url == COINGECKO_CATEGORIES_URL:
                return CATEGORIES
            if url == COINGECKO_TRENDING_URL:
                return TRENDING
            if url == COINDESK_RSS_URL:
                return RSS
            raise AssertionError(url)

        collect_public_context(self.store, 1_000, get_bytes=fake_get)
        self.assertEqual(
            calls,
            [COINGECKO_CATEGORIES_URL, COINGECKO_TRENDING_URL, COINDESK_RSS_URL],
        )
        reader = MarketIntelReader(self.path)
        narrative = reader.narrative()
        self.assertEqual(narrative["status"], "materialized")
        self.assertIsNone(narrative["ranking"])
        self.assertEqual(narrative["yaozi_formula_status"], "unknown_unpublished")
        self.assertEqual(narrative["items"][0]["top_assets_json"], ["alpha", "beta"])
        sectors = reader.sectors()
        self.assertEqual(sectors["status"], "materialized_public_categories")
        self.assertIsNone(sectors["ranking"])
        self.assertIsNone(sectors["relative_strength"])
        self.assertIsNone(sectors["momentum"])
        self.assertIsNone(sectors["rotation_position"])
        self.assertEqual(sectors["yaozi_rotation_formula_status"], "unknown_unpublished")
        self.assertEqual(
            sectors["metric_semantics"],
            "source_reported_market_cap_change_not_standardized_rotation",
        )
        self.assertEqual(sectors["items"][0]["name"], "AI Agents")
        self.assertIsNone(sectors["items"][0]["relative_strength"])
        attention = reader.narrative_attention()
        self.assertEqual(attention["status"], "materialized_public_attention")
        self.assertFalse(attention["ranking_persisted"])
        self.assertIsNone(attention["source_rank"])
        self.assertIsNone(attention["social_heat"])
        self.assertIsNone(attention["yaozi_heat"])
        self.assertEqual(
            {item["narrative_id"] for item in attention["items"]},
            {"data-availability", "chain-abstraction"},
        )
        news = reader.news()
        self.assertEqual(news["status"], "materialized")
        self.assertIsNone(news["ranking"])
        self.assertIsNone(news["importance"])
        self.assertEqual(news["items"][0]["title"], "Second story")

        collect_public_context(self.store, 2_000, get_bytes=fake_get)
        self.assertEqual(
            self.store.connection.execute("SELECT count(*) FROM news_event").fetchone()[0],
            2,
        )
        self.assertEqual(
            self.store.connection.execute("SELECT count(*) FROM narrative_snapshot").fetchone()[0],
            8,
        )

        revised_rss = RSS.replace(b"Second story", b"Second story updated")

        def revised_get(url):
            if url == COINGECKO_CATEGORIES_URL:
                return CATEGORIES
            if url == COINGECKO_TRENDING_URL:
                return TRENDING
            if url == COINDESK_RSS_URL:
                return revised_rss
            raise AssertionError(url)

        collect_public_context(self.store, 3_000, get_bytes=revised_get)
        self.assertEqual(
            self.store.connection.execute("SELECT count(*) FROM news_event").fetchone()[0],
            3,
        )
        latest_news = reader.news()
        self.assertEqual(len(latest_news["items"]), 2)
        self.assertEqual(latest_news["items"][0]["title"], "Second story updated")


if __name__ == "__main__":
    unittest.main()
