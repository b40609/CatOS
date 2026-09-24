"""Keyless public social-count facts for explicitly mapped CatOS assets.

CoinPaprika coin IDs are caller supplied. The provider response must echo the
expected coin ID and base symbol before any count is accepted. Link metadata
without a numeric provider-reported statistic is never promoted to a metric.
"""

from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import re
import ssl
from urllib.parse import urlsplit

from catos.market_collectors import MarketCollectionError


COINPAPRIKA_HOST = "api.coinpaprika.com"
SOCIAL_SOURCE = "coinpaprika-coin"
SOCIAL_CONTRACT = "catos-coinpaprika-social-metric-v1"
SOCIAL_MAPPING_CONTRACT = "catos-coinpaprika-identity-list-v1"

_SYMBOL_RE = re.compile(r"^(?P<base>[A-Z0-9]+)-USDT-SWAP$")
_COIN_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_PATH_RE = re.compile(r"^/v1/coins/[a-z0-9]+(?:-[a-z0-9]+)*$")
_COIN_LIST_PATH = "/v1/coins"
_METRIC_FIELDS = {
    "twitter": ("twitter_followers", "followers"),
    "reddit": ("reddit_subscribers", "subscribers"),
    "telegram": ("telegram_members", "members"),
}


def _symbol(value):
    if type(value) is not str:
        raise ValueError("invalid_symbol")
    match = _SYMBOL_RE.fullmatch(value)
    if match is None:
        raise ValueError("invalid_symbol")
    return value, match.group("base")


def _coin_id(value):
    if type(value) is not str or _COIN_ID_RE.fullmatch(value) is None:
        raise ValueError("invalid_coinpaprika_id")
    return value


def _observed_at_ms(value):
    if type(value) is not int or value < 0:
        raise ValueError("invalid_observed_at_ms")
    return value


def _source_url(value):
    if type(value) is not str or len(value) > 2048:
        raise MarketCollectionError("malformed_response")
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise MarketCollectionError("malformed_response") from None
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise MarketCollectionError("malformed_response")
    return value


@dataclass(frozen=True, slots=True)
class SocialAssetRef:
    symbol: str
    coinpaprika_id: str

    def __post_init__(self):
        _symbol(self.symbol)
        _coin_id(self.coinpaprika_id)


EXPLICIT_SOCIAL_ASSETS_V1 = (
    SocialAssetRef("AAVE-USDT-SWAP", "aave-new"),
    SocialAssetRef("BTC-USDT-SWAP", "btc-bitcoin"),
    SocialAssetRef("ETH-USDT-SWAP", "eth-ethereum"),
)

EXPLICIT_SOCIAL_ASSETS_V2 = EXPLICIT_SOCIAL_ASSETS_V1 + (
    SocialAssetRef("LDO-USDT-SWAP", "ldo-lido-dao"),
)

EXPLICIT_SOCIAL_ASSETS_V3 = EXPLICIT_SOCIAL_ASSETS_V2 + (
    SocialAssetRef("ENA-USDT-SWAP", "ena-ethena"),
    SocialAssetRef("MORPHO-USDT-SWAP", "morpho-morpho"),
    SocialAssetRef("ONDO-USDT-SWAP", "ondo-ondo"),
)

EXPLICIT_SOCIAL_ASSETS_V4 = EXPLICIT_SOCIAL_ASSETS_V3 + (
    SocialAssetRef("ETHFI-USDT-SWAP", "ethfi-etherfi"),
    SocialAssetRef("LINK-USDT-SWAP", "link-chainlink"),
    SocialAssetRef("PAXG-USDT-SWAP", "paxg-pax-gold"),
    SocialAssetRef("PENDLE-USDT-SWAP", "pendle-pendle"),
    SocialAssetRef("QNT-USDT-SWAP", "qnt-quant"),
)

EXPLICIT_SOCIAL_ASSETS_V5 = EXPLICIT_SOCIAL_ASSETS_V4 + (
    SocialAssetRef("AERO-USDT-SWAP", "aero-aerodrome-finance"),
    SocialAssetRef("CAKE-USDT-SWAP", "cake-pancakeswap"),
    SocialAssetRef("CRV-USDT-SWAP", "crv-curve-dao-token"),
    SocialAssetRef("GRT-USDT-SWAP", "grt-the-graph"),
    SocialAssetRef("VIRTUAL-USDT-SWAP", "virtual-virtual-protocol"),
)

EXPLICIT_SOCIAL_ASSETS_V6 = EXPLICIT_SOCIAL_ASSETS_V5 + (
    SocialAssetRef("COMP-USDT-SWAP", "comp-compoundd"),
    SocialAssetRef("UNI-USDT-SWAP", "uni-uniswap"),
)

EXPLICIT_SOCIAL_ASSETS_V7 = EXPLICIT_SOCIAL_ASSETS_V6 + (
    SocialAssetRef("1INCH-USDT-SWAP", "1inch-1inch"),
    SocialAssetRef("SUSHI-USDT-SWAP", "sushi-sushi"),
)

EXPLICIT_SOCIAL_ASSETS_V8 = EXPLICIT_SOCIAL_ASSETS_V7 + (
    SocialAssetRef("SNX-USDT-SWAP", "snx-synthetix-network-token"),
    SocialAssetRef("YFI-USDT-SWAP", "yfi-yearnfinance"),
    SocialAssetRef("ZRX-USDT-SWAP", "zrx-0x"),
)

EXPLICIT_SOCIAL_ASSETS_V9 = EXPLICIT_SOCIAL_ASSETS_V8 + (
    SocialAssetRef("API3-USDT-SWAP", "api3-api3"),
    SocialAssetRef("ARB-USDT-SWAP", "arb-arbitrum"),
    SocialAssetRef("BAT-USDT-SWAP", "bat-basic-attention-token"),
    SocialAssetRef("CVX-USDT-SWAP", "cvx-convex-finance"),
    SocialAssetRef("ENS-USDT-SWAP", "ens-ethereum-name-service"),
    SocialAssetRef("GMX-USDT-SWAP", "gmx-gmx"),
    SocialAssetRef("LPT-USDT-SWAP", "lpt-livepeer"),
    SocialAssetRef("OP-USDT-SWAP", "op-optimism"),
    SocialAssetRef("SPELL-USDT-SWAP", "spell-spell-token"),
    SocialAssetRef("UMA-USDT-SWAP", "uma-uma"),
)

EXPLICIT_SOCIAL_ASSETS = EXPLICIT_SOCIAL_ASSETS_V9
SOCIAL_EXPLICIT_REGISTRY_VERSION = "v9"
SOCIAL_EXPLICIT_REGISTRY_CONTRACT = "catos-social-explicit-identity-registry-v9-delta"
SOCIAL_EXPLICIT_REGISTRY_EVIDENCE = (
    "outputs/yaozi-social-explicit-identity-registry-v9-20260923.json"
)
SOCIAL_EXPLICIT_REGISTRY_COVERAGE = {
    "active_symbols": 734,
    "resolved": 34,
    "ambiguous_mapping": 242,
    "unverified_identity": 291,
    "missing_asset": 167,
}


def current_explicit_social_assets(symbols=None):
    """Return the current verified registry, optionally restricted to requested symbols."""
    if symbols is None:
        return EXPLICIT_SOCIAL_ASSETS
    if type(symbols) is not tuple or not symbols:
        raise ValueError("invalid_social_universe")
    requested = set()
    for symbol in symbols:
        _symbol(symbol)
        requested.add(symbol)
    return tuple(asset for asset in EXPLICIT_SOCIAL_ASSETS if asset.symbol in requested)


def current_social_identity_registry():
    """Describe current explicit identity readiness without implying metric materialization."""
    return {
        "version": SOCIAL_EXPLICIT_REGISTRY_VERSION,
        "contract": SOCIAL_EXPLICIT_REGISTRY_CONTRACT,
        "mapping_contract": SOCIAL_MAPPING_CONTRACT,
        "evidence_path": SOCIAL_EXPLICIT_REGISTRY_EVIDENCE,
        "explicit_identity_count": len(EXPLICIT_SOCIAL_ASSETS),
        "assets": [
            {"symbol": asset.symbol, "coinpaprika_id": asset.coinpaprika_id}
            for asset in EXPLICIT_SOCIAL_ASSETS
        ],
        "coverage": dict(SOCIAL_EXPLICIT_REGISTRY_COVERAGE),
        "coverage_basis": "baseline_derived_not_full_2026_09_23_live_distribution",
        "runtime_mapping_entrypoint": "collect_current_coinpaprika_mapping",
        "raw_metric_materialization": "separate_materialized_store",
    }


@dataclass(frozen=True, slots=True)
class SocialMappingIssue:
    symbol: str
    code: str
    candidate_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SocialMappingCoverage:
    contract: str
    assets: tuple[SocialAssetRef, ...]
    issues: tuple[SocialMappingIssue, ...]
    provider_rows: int | None
    active_provider_rows: int | None


@dataclass(frozen=True, slots=True)
class SocialMetricSnapshot:
    source: str
    symbol: str
    asset_id: str
    observed_at_ms: int
    metric_kind: str
    metric_value: int
    source_url: str


@dataclass(frozen=True, slots=True)
class SocialBatch:
    source: str
    symbol: str
    asset_id: str
    provider_symbol: str
    observed_at_ms: int
    metrics: tuple[SocialMetricSnapshot, ...]
    issues: tuple[str, ...]


class CoinPaprikaSocialTransport:
    """Bounded fixed-host transport for CoinPaprika's free coin endpoint."""

    def __init__(self, *, timeout_ms=8_000, max_body_bytes=1_000_000,
                 max_list_body_bytes=8_000_000):
        if type(timeout_ms) is not int or not 1 <= timeout_ms <= 30_000:
            raise ValueError("invalid_timeout")
        if type(max_body_bytes) is not int or not 1 <= max_body_bytes <= 2_000_000:
            raise ValueError("invalid_body_limit")
        if type(max_list_body_bytes) is not int or not 1 <= max_list_body_bytes <= 8_000_000:
            raise ValueError("invalid_list_body_limit")
        self.timeout_ms = timeout_ms
        self.max_body_bytes = max_body_bytes
        self.max_list_body_bytes = max_list_body_bytes

    def _fetch_json(self, path, max_body_bytes):
        if path != _COIN_LIST_PATH and _PATH_RE.fullmatch(path) is None:
            raise MarketCollectionError("source_not_allowed")
        connection = http.client.HTTPSConnection(
            COINPAPRIKA_HOST,
            port=443,
            timeout=self.timeout_ms / 1000,
            context=ssl.create_default_context(),
        )
        response = None
        try:
            connection.request(
                "GET", path, body=None,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                    "User-Agent": "catOS-public-social/1.0",
                },
            )
            response = connection.getresponse()
            payload = response.read(max_body_bytes + 1)
            if response.status != 200:
                raise MarketCollectionError(f"source_http_{response.status}")
            if len(payload) > max_body_bytes:
                raise MarketCollectionError("source_body_too_large")
            try:
                return json.loads(payload)
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise MarketCollectionError("malformed_response") from None
        finally:
            if response is not None:
                response.close()
            connection.close()

    def fetch_coin_list(self):
        return self._fetch_json(_COIN_LIST_PATH, self.max_list_body_bytes)

    def fetch_coin(self, coinpaprika_id):
        coinpaprika_id = _coin_id(coinpaprika_id)
        path = f"/v1/coins/{coinpaprika_id}"
        return self._fetch_json(path, self.max_body_bytes)


def resolve_coinpaprika_assets(symbols, payload, explicit_assets=()):
    """Verify caller-supplied IDs against CoinPaprika's current active identities."""
    if type(symbols) is not tuple or not symbols:
        raise ValueError("invalid_social_universe")
    if len(set(symbols)) != len(symbols):
        raise ValueError("duplicate_social_symbol")
    for symbol in symbols:
        _symbol(symbol)
    if type(explicit_assets) is not tuple:
        raise ValueError("invalid_explicit_social_mapping")
    explicit_by_symbol = {}
    for asset in explicit_assets:
        if not isinstance(asset, SocialAssetRef) or asset.symbol not in symbols:
            raise ValueError("invalid_explicit_social_mapping")
        if asset.symbol in explicit_by_symbol:
            raise ValueError("duplicate_explicit_social_mapping")
        explicit_by_symbol[asset.symbol] = asset
    if type(payload) is not list:
        raise MarketCollectionError("malformed_response")

    active_by_symbol = {}
    seen_ids = set()
    active_rows = 0
    for row in payload:
        if type(row) is not dict:
            raise MarketCollectionError("malformed_response")
        coin_id = row.get("id")
        provider_symbol = row.get("symbol")
        name = row.get("name")
        rank = row.get("rank")
        is_active = row.get("is_active")
        coin_type = row.get("type")
        if (type(coin_id) is not str or not coin_id or len(coin_id) > 128
                or any(ord(char) < 32 or ord(char) == 127 for char in coin_id)
                or coin_id in seen_ids or type(provider_symbol) is not str or not provider_symbol
                or type(name) is not str or not name or type(rank) is not int or rank < 0
                or type(is_active) is not bool or coin_type not in ("coin", "token")):
            raise MarketCollectionError("malformed_response")
        seen_ids.add(coin_id)
        if is_active:
            active_rows += 1
            active_by_symbol.setdefault(provider_symbol, []).append(coin_id)

    assets = []
    issues = []
    for symbol in sorted(symbols):
        _, base_symbol = _symbol(symbol)
        candidates = tuple(sorted(active_by_symbol.get(base_symbol, ())))
        explicit = explicit_by_symbol.get(symbol)
        if explicit is not None:
            if explicit.coinpaprika_id in candidates:
                assets.append(explicit)
            else:
                issues.append(SocialMappingIssue(symbol, "identity_mismatch", candidates))
        elif len(candidates) > 1:
            issues.append(SocialMappingIssue(symbol, "ambiguous_mapping", candidates))
        elif not candidates:
            issues.append(SocialMappingIssue(symbol, "missing_asset"))
        else:
            issues.append(SocialMappingIssue(symbol, "unverified_identity", candidates))
    return SocialMappingCoverage(
        contract=SOCIAL_MAPPING_CONTRACT,
        assets=tuple(assets),
        issues=tuple(issues),
        provider_rows=len(payload),
        active_provider_rows=active_rows,
    )


def collect_coinpaprika_mapping(symbols, transport=None, *, explicit_assets=()):
    """Fetch CoinPaprika's identity list and fail closed for unresolved assets."""
    if type(symbols) is not tuple or not symbols:
        raise ValueError("invalid_social_universe")
    for symbol in symbols:
        _symbol(symbol)
    if transport is None:
        transport = CoinPaprikaSocialTransport()
    if not callable(getattr(transport, "fetch_coin_list", None)):
        raise ValueError("invalid_social_transport")
    try:
        return resolve_coinpaprika_assets(
            symbols, transport.fetch_coin_list(), explicit_assets=explicit_assets)
    except (MarketCollectionError, OSError, http.client.HTTPException) as error:
        code = error.code if isinstance(error, MarketCollectionError) else "source_transport_error"
        return SocialMappingCoverage(
            contract=SOCIAL_MAPPING_CONTRACT,
            assets=(),
            issues=tuple(SocialMappingIssue(symbol, code) for symbol in sorted(symbols)),
            provider_rows=None,
            active_provider_rows=None,
        )


def collect_current_coinpaprika_mapping(symbols, transport=None):
    """Resolve a requested universe using the current verified explicit registry."""
    return collect_coinpaprika_mapping(
        symbols,
        transport,
        explicit_assets=current_explicit_social_assets(symbols),
    )


def parse_coinpaprika_social(asset, payload, observed_at_ms):
    """Parse raw provider counts after exact caller mapping verification."""
    if not isinstance(asset, SocialAssetRef):
        raise ValueError("invalid_social_asset")
    observed_at_ms = _observed_at_ms(observed_at_ms)
    _, base_symbol = _symbol(asset.symbol)
    if type(payload) is not dict:
        raise MarketCollectionError("malformed_response")
    if payload.get("id") != asset.coinpaprika_id or payload.get("symbol") != base_symbol:
        raise MarketCollectionError("scope_mismatch")
    links = payload.get("links_extended")
    if type(links) is not list:
        raise MarketCollectionError("malformed_response")

    metrics = []
    seen = set()
    for link in links:
        if type(link) is not dict:
            raise MarketCollectionError("malformed_response")
        provider_type = link.get("type")
        if type(provider_type) is not str:
            raise MarketCollectionError("malformed_response")
        if provider_type not in _METRIC_FIELDS:
            continue
        metric_kind, stat_field = _METRIC_FIELDS[provider_type]
        stats = link.get("stats")
        if stats is None:
            continue
        if type(stats) is not dict:
            raise MarketCollectionError("malformed_response")
        if stat_field not in stats:
            continue
        value = stats[stat_field]
        if type(value) is not int or not 0 <= value <= 2**63 - 1:
            raise MarketCollectionError("malformed_response")
        if metric_kind in seen:
            raise MarketCollectionError("ambiguous_metric")
        seen.add(metric_kind)
        metrics.append(SocialMetricSnapshot(
            source=SOCIAL_SOURCE,
            symbol=asset.symbol,
            asset_id=asset.coinpaprika_id,
            observed_at_ms=observed_at_ms,
            metric_kind=metric_kind,
            metric_value=value,
            source_url=_source_url(link.get("url")),
        ))

    metrics.sort(key=lambda item: item.metric_kind)
    return SocialBatch(
        source=SOCIAL_SOURCE,
        symbol=asset.symbol,
        asset_id=asset.coinpaprika_id,
        provider_symbol=base_symbol,
        observed_at_ms=observed_at_ms,
        metrics=tuple(metrics),
        issues=(),
    )


def collect_coinpaprika_social(asset, observed_at_ms, transport=None):
    """Collect one explicitly mapped asset; transport/parser failures fail closed."""
    if not isinstance(asset, SocialAssetRef):
        raise ValueError("invalid_social_asset")
    observed_at_ms = _observed_at_ms(observed_at_ms)
    _, base_symbol = _symbol(asset.symbol)
    if transport is None:
        transport = CoinPaprikaSocialTransport()
    if not callable(getattr(transport, "fetch_coin", None)):
        raise ValueError("invalid_social_transport")
    try:
        return parse_coinpaprika_social(
            asset,
            transport.fetch_coin(asset.coinpaprika_id),
            observed_at_ms,
        )
    except (MarketCollectionError, OSError, http.client.HTTPException) as error:
        return SocialBatch(
            source=SOCIAL_SOURCE,
            symbol=asset.symbol,
            asset_id=asset.coinpaprika_id,
            provider_symbol=base_symbol,
            observed_at_ms=observed_at_ms,
            metrics=(),
            issues=(error.code if isinstance(error, MarketCollectionError)
                    else "source_transport_error",),
        )
