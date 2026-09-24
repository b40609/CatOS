from pathlib import Path
from dataclasses import replace
import copy
import tempfile
import unittest

from catos.market_api import MarketIntelReader
from catos.market_intel import MarketIntelError, MarketIntelStore
from catos.market_social import (
    EXPLICIT_SOCIAL_ASSETS_V1,
    EXPLICIT_SOCIAL_ASSETS_V2,
    EXPLICIT_SOCIAL_ASSETS_V3,
    EXPLICIT_SOCIAL_ASSETS_V4,
    EXPLICIT_SOCIAL_ASSETS_V5,
    EXPLICIT_SOCIAL_ASSETS_V6,
    EXPLICIT_SOCIAL_ASSETS_V7,
    EXPLICIT_SOCIAL_ASSETS_V8,
    EXPLICIT_SOCIAL_ASSETS_V9,
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
    {"id": "aave-new", "name": "Aave", "symbol": "AAVE", "rank": 46,
     "is_active": True, "type": "token"},
    {"id": "btc-bitcoin", "name": "Bitcoin", "symbol": "BTC", "rank": 1,
     "is_active": True, "type": "coin"},
    {"id": "eth-ethereum", "name": "Ethereum", "symbol": "ETH", "rank": 2,
     "is_active": True, "type": "coin"},
    {"id": "ldo-lido-dao", "name": "Lido DAO", "symbol": "LDO", "rank": 142,
     "is_active": True, "type": "token"},
    {"id": "ena-ethena", "name": "Ethena", "symbol": "ENA", "rank": 50,
     "is_active": True, "type": "token"},
    {"id": "morpho-morpho", "name": "Morpho", "symbol": "MORPHO", "rank": 63,
     "is_active": True, "type": "token"},
    {"id": "ondo-ondo", "name": "Ondo", "symbol": "ONDO", "rank": 47,
     "is_active": True, "type": "token"},
    {"id": "ethfi-etherfi", "name": "Ether.fi", "symbol": "ETHFI", "rank": 101,
     "is_active": True, "type": "token"},
    {"id": "link-chainlink", "name": "Chainlink", "symbol": "LINK", "rank": 17,
     "is_active": True, "type": "token"},
    {"id": "paxg-pax-gold", "name": "PAX Gold", "symbol": "PAXG", "rank": 52,
     "is_active": True, "type": "token"},
    {"id": "pendle-pendle", "name": "Pendle", "symbol": "PENDLE", "rank": 130,
     "is_active": True, "type": "token"},
    {"id": "qnt-quant", "name": "Quant", "symbol": "QNT", "rank": 92,
     "is_active": True, "type": "token"},
    {"id": "aero-aerodrome-finance", "name": "Aerodrome Finance", "symbol": "AERO", "rank": 101,
     "is_active": True, "type": "token"},
    {"id": "cake-pancakeswap", "name": "PancakeSwap", "symbol": "CAKE", "rank": 94,
     "is_active": True, "type": "token"},
    {"id": "crv-curve-dao-token", "name": "Curve DAO Token", "symbol": "CRV", "rank": 113,
     "is_active": True, "type": "token"},
    {"id": "grt-the-graph", "name": "The Graph", "symbol": "GRT", "rank": 175,
     "is_active": True, "type": "token"},
    {"id": "virtual-virtual-protocol", "name": "Virtuals Protocol", "symbol": "VIRTUAL", "rank": 125,
     "is_active": True, "type": "token"},
    {"id": "comp-compoundd", "name": "Compound", "symbol": "COMP", "rank": 176,
     "is_active": True, "type": "token"},
    {"id": "comp-compound-coin", "name": "Compound Coin", "symbol": "COMP", "rank": 3886,
     "is_active": True, "type": "coin"},
    {"id": "uni-uniswap", "name": "Uniswap", "symbol": "UNI", "rank": 34,
     "is_active": True, "type": "token"},
    {"id": "uni-uni", "name": "UNI", "symbol": "UNI", "rank": 2516,
     "is_active": True, "type": "token"},
    {"id": "1inch-1inch", "name": "1INCH", "symbol": "1INCH", "rank": 228,
     "is_active": True, "type": "token"},
    {"id": "sushi-sushi", "name": "Sushi", "symbol": "SUSHI", "rank": 411,
     "is_active": True, "type": "token"},
    {"id": "snx-synthetix-network-token", "name": "Synthetix Network", "symbol": "SNX", "rank": 304,
     "is_active": True, "type": "token"},
    {"id": "yfi-yearnfinance", "name": "yearn.finance", "symbol": "YFI", "rank": 290,
     "is_active": True, "type": "token"},
    {"id": "zrx-0x", "name": "0x", "symbol": "ZRX", "rank": 299,
     "is_active": True, "type": "token"},
    {"id": "api3-api3", "name": "API3", "symbol": "API3", "rank": 500,
     "is_active": True, "type": "token"},
    {"id": "arb-arbitrum", "name": "Arbitrum", "symbol": "ARB", "rank": 79,
     "is_active": True, "type": "token"},
    {"id": "arb-arb-protocol", "name": "ARB Protocol", "symbol": "ARB", "rank": 3000,
     "is_active": True, "type": "token"},
    {"id": "arb-arbitrage-loop", "name": "Arbitrage Loop", "symbol": "ARB", "rank": 4000,
     "is_active": True, "type": "token"},
    {"id": "arb6-dotarb", "name": ".arb", "symbol": "ARB", "rank": 5000,
     "is_active": True, "type": "token"},
    {"id": "bat-basic-attention-token", "name": "Basic Attention Token", "symbol": "BAT", "rank": 216,
     "is_active": True, "type": "token"},
    {"id": "bat2-batic", "name": "Batic", "symbol": "BAT", "rank": 5000,
     "is_active": True, "type": "token"},
    {"id": "cvx-convex-finance", "name": "Convex Finance", "symbol": "CVX", "rank": 220,
     "is_active": True, "type": "token"},
    {"id": "ens-ethereum-name-service", "name": "Ethereum Name Service", "symbol": "ENS", "rank": 171,
     "is_active": True, "type": "token"},
    {"id": "gmx-gmx", "name": "GMX", "symbol": "GMX", "rank": 375,
     "is_active": True, "type": "token"},
    {"id": "gmx-gamext", "name": "GameXT", "symbol": "GMX", "rank": 5000,
     "is_active": True, "type": "token"},
    {"id": "lpt-livepeer", "name": "Livepeer", "symbol": "LPT", "rank": 400,
     "is_active": True, "type": "token"},
    {"id": "op-optimism", "name": "Optimism", "symbol": "OP", "rank": 165,
     "is_active": True, "type": "token"},
    {"id": "op-one-path", "name": "One Path", "symbol": "OP", "rank": 5000,
     "is_active": True, "type": "token"},
    {"id": "spell-spell-token", "name": "Spell Token", "symbol": "SPELL", "rank": 600,
     "is_active": True, "type": "token"},
    {"id": "spell2-the-spellcaster", "name": "The Spellcaster", "symbol": "SPELL", "rank": 5000,
     "is_active": True, "type": "token"},
    {"id": "uma-uma", "name": "UMA", "symbol": "UMA", "rank": 500,
     "is_active": True, "type": "token"},
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

    def test_evidence_backed_registry_adds_aave_without_ticker_auto_mapping(self):
        symbols = ("AAVE-USDT-SWAP", "BTC-USDT-SWAP", "ETH-USDT-SWAP")
        coverage = resolve_coinpaprika_assets(
            symbols, COIN_LIST, explicit_assets=EXPLICIT_SOCIAL_ASSETS_V1)
        self.assertEqual(
            [(item.symbol, item.coinpaprika_id) for item in coverage.assets],
            [
                ("AAVE-USDT-SWAP", "aave-new"),
                ("BTC-USDT-SWAP", "btc-bitcoin"),
                ("ETH-USDT-SWAP", "eth-ethereum"),
            ],
        )
        self.assertEqual(coverage.issues, ())

        unresolved = resolve_coinpaprika_assets(("AAVE-USDT-SWAP",), COIN_LIST)
        self.assertEqual(unresolved.assets, ())
        self.assertEqual(
            [(item.symbol, item.code, item.candidate_ids) for item in unresolved.issues],
            [("AAVE-USDT-SWAP", "unverified_identity", ("aave-new",))],
        )

    def test_v2_registry_adds_ldo_from_explicit_identity_evidence(self):
        symbols = ("AAVE-USDT-SWAP", "BTC-USDT-SWAP", "ETH-USDT-SWAP", "LDO-USDT-SWAP")
        coverage = resolve_coinpaprika_assets(
            symbols, COIN_LIST, explicit_assets=EXPLICIT_SOCIAL_ASSETS_V2)
        self.assertEqual(
            [(item.symbol, item.coinpaprika_id) for item in coverage.assets],
            [
                ("AAVE-USDT-SWAP", "aave-new"),
                ("BTC-USDT-SWAP", "btc-bitcoin"),
                ("ETH-USDT-SWAP", "eth-ethereum"),
                ("LDO-USDT-SWAP", "ldo-lido-dao"),
            ],
        )
        self.assertEqual(coverage.issues, ())

        unresolved = resolve_coinpaprika_assets(("LDO-USDT-SWAP",), COIN_LIST)
        self.assertEqual(unresolved.assets, ())
        self.assertEqual(
            [(item.symbol, item.code, item.candidate_ids) for item in unresolved.issues],
            [("LDO-USDT-SWAP", "unverified_identity", ("ldo-lido-dao",))],
        )

    def test_v3_registry_adds_contract_verified_assets_without_ticker_auto_mapping(self):
        symbols = (
            "AAVE-USDT-SWAP", "BTC-USDT-SWAP", "ENA-USDT-SWAP", "ETH-USDT-SWAP",
            "LDO-USDT-SWAP", "MORPHO-USDT-SWAP", "ONDO-USDT-SWAP",
        )
        coverage = resolve_coinpaprika_assets(
            symbols, COIN_LIST, explicit_assets=EXPLICIT_SOCIAL_ASSETS_V3)
        self.assertEqual(
            [(item.symbol, item.coinpaprika_id) for item in coverage.assets],
            [
                ("AAVE-USDT-SWAP", "aave-new"),
                ("BTC-USDT-SWAP", "btc-bitcoin"),
                ("ENA-USDT-SWAP", "ena-ethena"),
                ("ETH-USDT-SWAP", "eth-ethereum"),
                ("LDO-USDT-SWAP", "ldo-lido-dao"),
                ("MORPHO-USDT-SWAP", "morpho-morpho"),
                ("ONDO-USDT-SWAP", "ondo-ondo"),
            ],
        )
        self.assertEqual(coverage.issues, ())

        for symbol, coinpaprika_id in (
            ("ENA-USDT-SWAP", "ena-ethena"),
            ("MORPHO-USDT-SWAP", "morpho-morpho"),
            ("ONDO-USDT-SWAP", "ondo-ondo"),
        ):
            with self.subTest(symbol=symbol):
                unresolved = resolve_coinpaprika_assets((symbol,), COIN_LIST)
                self.assertEqual(unresolved.assets, ())
                self.assertEqual(
                    [(item.symbol, item.code, item.candidate_ids)
                     for item in unresolved.issues],
                    [(symbol, "unverified_identity", (coinpaprika_id,))],
                )

    def test_v4_registry_adds_more_contract_verified_assets_without_ticker_auto_mapping(self):
        symbols = (
            "AAVE-USDT-SWAP", "BTC-USDT-SWAP", "ENA-USDT-SWAP", "ETH-USDT-SWAP",
            "ETHFI-USDT-SWAP", "LDO-USDT-SWAP", "LINK-USDT-SWAP", "MORPHO-USDT-SWAP",
            "ONDO-USDT-SWAP", "PAXG-USDT-SWAP", "PENDLE-USDT-SWAP", "QNT-USDT-SWAP",
        )
        coverage = resolve_coinpaprika_assets(
            symbols, COIN_LIST, explicit_assets=EXPLICIT_SOCIAL_ASSETS_V4)
        self.assertEqual(
            [(item.symbol, item.coinpaprika_id) for item in coverage.assets],
            [
                ("AAVE-USDT-SWAP", "aave-new"),
                ("BTC-USDT-SWAP", "btc-bitcoin"),
                ("ENA-USDT-SWAP", "ena-ethena"),
                ("ETH-USDT-SWAP", "eth-ethereum"),
                ("ETHFI-USDT-SWAP", "ethfi-etherfi"),
                ("LDO-USDT-SWAP", "ldo-lido-dao"),
                ("LINK-USDT-SWAP", "link-chainlink"),
                ("MORPHO-USDT-SWAP", "morpho-morpho"),
                ("ONDO-USDT-SWAP", "ondo-ondo"),
                ("PAXG-USDT-SWAP", "paxg-pax-gold"),
                ("PENDLE-USDT-SWAP", "pendle-pendle"),
                ("QNT-USDT-SWAP", "qnt-quant"),
            ],
        )
        self.assertEqual(coverage.issues, ())

        for symbol, coinpaprika_id in (
            ("ETHFI-USDT-SWAP", "ethfi-etherfi"),
            ("LINK-USDT-SWAP", "link-chainlink"),
            ("PAXG-USDT-SWAP", "paxg-pax-gold"),
            ("PENDLE-USDT-SWAP", "pendle-pendle"),
            ("QNT-USDT-SWAP", "qnt-quant"),
        ):
            with self.subTest(symbol=symbol):
                unresolved = resolve_coinpaprika_assets((symbol,), COIN_LIST)
                self.assertEqual(unresolved.assets, ())
                self.assertEqual(
                    [(item.symbol, item.code, item.candidate_ids)
                     for item in unresolved.issues],
                    [(symbol, "unverified_identity", (coinpaprika_id,))],
                )

    def test_v5_registry_adds_chain_matched_assets_without_ticker_auto_mapping(self):
        symbols = (
            "AAVE-USDT-SWAP", "AERO-USDT-SWAP", "BTC-USDT-SWAP", "CAKE-USDT-SWAP",
            "CRV-USDT-SWAP", "ENA-USDT-SWAP", "ETH-USDT-SWAP", "ETHFI-USDT-SWAP",
            "GRT-USDT-SWAP", "LDO-USDT-SWAP", "LINK-USDT-SWAP", "MORPHO-USDT-SWAP",
            "ONDO-USDT-SWAP", "PAXG-USDT-SWAP", "PENDLE-USDT-SWAP", "QNT-USDT-SWAP",
            "VIRTUAL-USDT-SWAP",
        )
        coverage = resolve_coinpaprika_assets(
            symbols, COIN_LIST, explicit_assets=EXPLICIT_SOCIAL_ASSETS_V5)
        self.assertEqual(
            [(item.symbol, item.coinpaprika_id) for item in coverage.assets],
            [
                ("AAVE-USDT-SWAP", "aave-new"),
                ("AERO-USDT-SWAP", "aero-aerodrome-finance"),
                ("BTC-USDT-SWAP", "btc-bitcoin"),
                ("CAKE-USDT-SWAP", "cake-pancakeswap"),
                ("CRV-USDT-SWAP", "crv-curve-dao-token"),
                ("ENA-USDT-SWAP", "ena-ethena"),
                ("ETH-USDT-SWAP", "eth-ethereum"),
                ("ETHFI-USDT-SWAP", "ethfi-etherfi"),
                ("GRT-USDT-SWAP", "grt-the-graph"),
                ("LDO-USDT-SWAP", "ldo-lido-dao"),
                ("LINK-USDT-SWAP", "link-chainlink"),
                ("MORPHO-USDT-SWAP", "morpho-morpho"),
                ("ONDO-USDT-SWAP", "ondo-ondo"),
                ("PAXG-USDT-SWAP", "paxg-pax-gold"),
                ("PENDLE-USDT-SWAP", "pendle-pendle"),
                ("QNT-USDT-SWAP", "qnt-quant"),
                ("VIRTUAL-USDT-SWAP", "virtual-virtual-protocol"),
            ],
        )
        self.assertEqual(coverage.issues, ())

        for symbol, coinpaprika_id in (
            ("AERO-USDT-SWAP", "aero-aerodrome-finance"),
            ("CAKE-USDT-SWAP", "cake-pancakeswap"),
            ("CRV-USDT-SWAP", "crv-curve-dao-token"),
            ("GRT-USDT-SWAP", "grt-the-graph"),
            ("VIRTUAL-USDT-SWAP", "virtual-virtual-protocol"),
        ):
            with self.subTest(symbol=symbol):
                unresolved = resolve_coinpaprika_assets((symbol,), COIN_LIST)
                self.assertEqual(unresolved.assets, ())
                self.assertEqual(
                    [(item.symbol, item.code, item.candidate_ids)
                     for item in unresolved.issues],
                    [(symbol, "unverified_identity", (coinpaprika_id,))],
                )

    def test_v6_registry_resolves_ambiguous_uni_comp_from_chain_contract_evidence(self):
        symbols = (
            "AAVE-USDT-SWAP", "AERO-USDT-SWAP", "BTC-USDT-SWAP", "CAKE-USDT-SWAP",
            "COMP-USDT-SWAP", "CRV-USDT-SWAP", "ENA-USDT-SWAP", "ETH-USDT-SWAP",
            "ETHFI-USDT-SWAP", "GRT-USDT-SWAP", "LDO-USDT-SWAP", "LINK-USDT-SWAP",
            "MORPHO-USDT-SWAP", "ONDO-USDT-SWAP", "PAXG-USDT-SWAP",
            "PENDLE-USDT-SWAP", "QNT-USDT-SWAP", "UNI-USDT-SWAP", "VIRTUAL-USDT-SWAP",
        )
        coverage = resolve_coinpaprika_assets(
            symbols, COIN_LIST, explicit_assets=EXPLICIT_SOCIAL_ASSETS_V6)
        self.assertEqual(
            [(item.symbol, item.coinpaprika_id) for item in coverage.assets],
            [
                ("AAVE-USDT-SWAP", "aave-new"),
                ("AERO-USDT-SWAP", "aero-aerodrome-finance"),
                ("BTC-USDT-SWAP", "btc-bitcoin"),
                ("CAKE-USDT-SWAP", "cake-pancakeswap"),
                ("COMP-USDT-SWAP", "comp-compoundd"),
                ("CRV-USDT-SWAP", "crv-curve-dao-token"),
                ("ENA-USDT-SWAP", "ena-ethena"),
                ("ETH-USDT-SWAP", "eth-ethereum"),
                ("ETHFI-USDT-SWAP", "ethfi-etherfi"),
                ("GRT-USDT-SWAP", "grt-the-graph"),
                ("LDO-USDT-SWAP", "ldo-lido-dao"),
                ("LINK-USDT-SWAP", "link-chainlink"),
                ("MORPHO-USDT-SWAP", "morpho-morpho"),
                ("ONDO-USDT-SWAP", "ondo-ondo"),
                ("PAXG-USDT-SWAP", "paxg-pax-gold"),
                ("PENDLE-USDT-SWAP", "pendle-pendle"),
                ("QNT-USDT-SWAP", "qnt-quant"),
                ("UNI-USDT-SWAP", "uni-uniswap"),
                ("VIRTUAL-USDT-SWAP", "virtual-virtual-protocol"),
            ],
        )
        self.assertEqual(coverage.issues, ())

        for symbol, coinpaprika_id in (
            ("COMP-USDT-SWAP", "comp-compoundd"),
            ("UNI-USDT-SWAP", "uni-uniswap"),
        ):
            with self.subTest(symbol=symbol):
                unresolved = resolve_coinpaprika_assets((symbol,), COIN_LIST)
                self.assertEqual(unresolved.assets, ())
                self.assertEqual(
                    [(item.symbol, item.code, item.candidate_ids)
                     for item in unresolved.issues],
                    [(
                        symbol,
                        "ambiguous_mapping",
                        (("comp-compound-coin", "comp-compoundd")
                         if symbol == "COMP-USDT-SWAP"
                         else ("uni-uni", "uni-uniswap")),
                    )],
                )

    def test_v7_registry_adds_1inch_sushi_from_exact_contract_evidence(self):
        self.assertEqual(EXPLICIT_SOCIAL_ASSETS_V7[:-2], EXPLICIT_SOCIAL_ASSETS_V6)
        symbols = ("1INCH-USDT-SWAP", "SUSHI-USDT-SWAP")
        coverage = resolve_coinpaprika_assets(
            symbols, COIN_LIST, explicit_assets=EXPLICIT_SOCIAL_ASSETS_V7[-2:])
        self.assertEqual(
            [(item.symbol, item.coinpaprika_id) for item in coverage.assets],
            [
                ("1INCH-USDT-SWAP", "1inch-1inch"),
                ("SUSHI-USDT-SWAP", "sushi-sushi"),
            ],
        )
        self.assertEqual(coverage.issues, ())

        for symbol, coinpaprika_id in (
            ("1INCH-USDT-SWAP", "1inch-1inch"),
            ("SUSHI-USDT-SWAP", "sushi-sushi"),
        ):
            with self.subTest(symbol=symbol):
                unresolved = resolve_coinpaprika_assets((symbol,), COIN_LIST)
                self.assertEqual(unresolved.assets, ())
                self.assertEqual(
                    [(item.symbol, item.code, item.candidate_ids)
                     for item in unresolved.issues],
                    [(symbol, "unverified_identity", (coinpaprika_id,))],
                )

    def test_v8_registry_adds_snx_yfi_zrx_from_exact_contract_evidence(self):
        self.assertEqual(EXPLICIT_SOCIAL_ASSETS_V8[:-3], EXPLICIT_SOCIAL_ASSETS_V7)
        symbols = ("SNX-USDT-SWAP", "YFI-USDT-SWAP", "ZRX-USDT-SWAP")
        coverage = resolve_coinpaprika_assets(
            symbols, COIN_LIST, explicit_assets=EXPLICIT_SOCIAL_ASSETS_V8[-3:])
        self.assertEqual(
            [(item.symbol, item.coinpaprika_id) for item in coverage.assets],
            [
                ("SNX-USDT-SWAP", "snx-synthetix-network-token"),
                ("YFI-USDT-SWAP", "yfi-yearnfinance"),
                ("ZRX-USDT-SWAP", "zrx-0x"),
            ],
        )
        self.assertEqual(coverage.issues, ())

        for symbol, coinpaprika_id in (
            ("SNX-USDT-SWAP", "snx-synthetix-network-token"),
            ("YFI-USDT-SWAP", "yfi-yearnfinance"),
            ("ZRX-USDT-SWAP", "zrx-0x"),
        ):
            with self.subTest(symbol=symbol):
                unresolved = resolve_coinpaprika_assets((symbol,), COIN_LIST)
                self.assertEqual(unresolved.assets, ())
                self.assertEqual(
                    [(item.symbol, item.code, item.candidate_ids)
                     for item in unresolved.issues],
                    [(symbol, "unverified_identity", (coinpaprika_id,))],
                )

    def test_v9_registry_adds_contract_verified_assets_and_resolves_collisions(self):
        self.assertEqual(EXPLICIT_SOCIAL_ASSETS_V9[:-10], EXPLICIT_SOCIAL_ASSETS_V8)
        expected = (
            ("API3-USDT-SWAP", "api3-api3"),
            ("ARB-USDT-SWAP", "arb-arbitrum"),
            ("BAT-USDT-SWAP", "bat-basic-attention-token"),
            ("CVX-USDT-SWAP", "cvx-convex-finance"),
            ("ENS-USDT-SWAP", "ens-ethereum-name-service"),
            ("GMX-USDT-SWAP", "gmx-gmx"),
            ("LPT-USDT-SWAP", "lpt-livepeer"),
            ("OP-USDT-SWAP", "op-optimism"),
            ("SPELL-USDT-SWAP", "spell-spell-token"),
            ("UMA-USDT-SWAP", "uma-uma"),
        )
        symbols = tuple(symbol for symbol, _ in expected)
        coverage = resolve_coinpaprika_assets(
            symbols, COIN_LIST, explicit_assets=EXPLICIT_SOCIAL_ASSETS_V9[-10:])
        self.assertEqual(
            tuple((item.symbol, item.coinpaprika_id) for item in coverage.assets), expected)
        self.assertEqual(coverage.issues, ())

        ambiguous = {
            "ARB-USDT-SWAP": ("arb-arb-protocol", "arb-arbitrage-loop", "arb-arbitrum", "arb6-dotarb"),
            "BAT-USDT-SWAP": ("bat-basic-attention-token", "bat2-batic"),
            "GMX-USDT-SWAP": ("gmx-gamext", "gmx-gmx"),
            "OP-USDT-SWAP": ("op-one-path", "op-optimism"),
            "SPELL-USDT-SWAP": ("spell-spell-token", "spell2-the-spellcaster"),
        }
        for symbol, coinpaprika_id in expected:
            with self.subTest(symbol=symbol):
                unresolved = resolve_coinpaprika_assets((symbol,), COIN_LIST)
                self.assertEqual(unresolved.assets, ())
                issue = unresolved.issues[0]
                if symbol in ambiguous:
                    self.assertEqual(
                        (issue.symbol, issue.code, issue.candidate_ids),
                        (symbol, "ambiguous_mapping", ambiguous[symbol]),
                    )
                else:
                    self.assertEqual(
                        (issue.symbol, issue.code, issue.candidate_ids),
                        (symbol, "unverified_identity", (coinpaprika_id,)),
                    )

    def test_aave_duplicate_social_link_kind_fails_closed(self):
        asset = SocialAssetRef("AAVE-USDT-SWAP", "aave-new")
        payload = {
            "id": "aave-new",
            "symbol": "AAVE",
            "links_extended": [
                {"url": "https://twitter.com/AaveAave", "type": "twitter",
                 "stats": {"followers": 531_669}},
                {"url": "https://twitter.com/ethlend1", "type": "twitter",
                 "stats": {"followers": 9_751}},
            ],
        }
        batch = collect_coinpaprika_social(asset, 1_000, FakeTransport(payload))
        self.assertEqual(batch.metrics, ())
        self.assertEqual(batch.issues, ("ambiguous_metric",))

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
