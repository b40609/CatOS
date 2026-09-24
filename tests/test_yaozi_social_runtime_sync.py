from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from catos.market_api import create_app
from catos.market_intel import MarketIntelStore
from catos.market_social import (
    EXPLICIT_SOCIAL_ASSETS,
    EXPLICIT_SOCIAL_ASSETS_V9,
    collect_current_coinpaprika_mapping,
    current_social_identity_registry,
)


class FakeMappingTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def fetch_coin_list(self):
        self.calls += 1
        return self.payload


class YaoziSocialRuntimeSyncTests(unittest.TestCase):
    def test_current_runtime_mapping_uses_v9_registry_and_resolves_ambiguous_symbol(self):
        self.assertIs(EXPLICIT_SOCIAL_ASSETS, EXPLICIT_SOCIAL_ASSETS_V9)
        payload = [
            {"id": "arb-arb-protocol", "name": "ARB Protocol", "symbol": "ARB", "rank": 0,
             "is_active": True, "type": "token"},
            {"id": "arb-arbitrum", "name": "Arbitrum", "symbol": "ARB", "rank": 37,
             "is_active": True, "type": "token"},
            {"id": "api3-api3", "name": "API3", "symbol": "API3", "rank": 241,
             "is_active": True, "type": "token"},
        ]
        transport = FakeMappingTransport(payload)
        coverage = collect_current_coinpaprika_mapping(
            ("ARB-USDT-SWAP", "API3-USDT-SWAP"), transport)

        self.assertEqual(transport.calls, 1)
        self.assertEqual(
            [(item.symbol, item.coinpaprika_id) for item in coverage.assets],
            [("API3-USDT-SWAP", "api3-api3"), ("ARB-USDT-SWAP", "arb-arbitrum")],
        )
        self.assertEqual(coverage.issues, ())

    def test_registry_status_and_web_surface_expose_v9_without_fabricating_metrics(self):
        registry = current_social_identity_registry()
        self.assertEqual(registry["version"], "v9")
        self.assertEqual(registry["explicit_identity_count"], 34)
        self.assertEqual(
            registry["coverage"],
            {
                "active_symbols": 734,
                "resolved": 34,
                "ambiguous_mapping": 242,
                "unverified_identity": 291,
                "missing_asset": 167,
            },
        )
        self.assertEqual(
            registry["coverage_basis"],
            "baseline_derived_not_full_2026_09_23_live_distribution",
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intel.sqlite"
            store = MarketIntelStore(path)
            store.close()
            client = TestClient(create_app(path))
            social = client.get("/intel/social?limit=1000").json()

            self.assertEqual(social["status"], "materialized_empty")
            self.assertEqual(social["items"], [])
            self.assertEqual(social["source_runs"], [])
            self.assertEqual(social["identity_registry"]["version"], "v9")
            self.assertEqual(social["identity_registry"]["explicit_identity_count"], 34)
            self.assertIsNone(social["social_heat"])
            self.assertIsNone(social["yaozi_heat"])

            dashboard = client.get("/dashboard").text
            self.assertIn("registry=${esc(registry.version??'—')}", dashboard)
            self.assertIn("屬 baseline-derived，不是 2026-09-23 完整 live distribution", dashboard)
            self.assertIn("identity readiness 與 raw metric materialization 分開", dashboard)
            self.assertIn("registry ready 不代表已有 numeric social stats", dashboard)


if __name__ == "__main__":
    unittest.main()
