"""Provider-neutral public DEX swap observations for P1-B market intelligence.

The module defines the normalized boundary only. It owns no credentials and
does not choose or contact an external provider by itself. A Supervisor-owned
transport supplies public swap rows; tests use an in-memory mock transport.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import http.client
import json
import re
import ssl
from typing import Protocol

from catos import ipc
from catos.market_collectors import CollectorScope, MarketCollectionError


_CHAIN = re.compile(r"[a-z0-9_-]{1,32}\Z")
_NAME = re.compile(r"[A-Za-z0-9_.:-]{1,96}\Z")
_TX = re.compile(r"0x[0-9a-fA-F]{32,128}\Z")
_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")
_GECKO_NETWORK = re.compile(r"[a-z0-9-]{1,32}\Z")
_GECKO_TRADE_ID = re.compile(r".+_(0x[0-9a-fA-F]{64})_([0-9]+)_[0-9]+\Z")
_GECKO_HOST = "api.geckoterminal.com"
_GECKO_MAX_TRADES = 300
_WINDOW_MS = 3_600_000


@dataclass(frozen=True, slots=True)
class DexScope:
    symbol: str
    observed_at_ms: int
    chain: str

    def __post_init__(self):
        CollectorScope(self.symbol, self.observed_at_ms)
        if type(self.chain) is not str or not _CHAIN.fullmatch(self.chain):
            raise ValueError("invalid_chain")


@dataclass(frozen=True, slots=True)
class DexSwapObservation:
    source_id: str
    symbol: str
    observed_at_ms: int
    source_ms: int
    chain: str
    venue: str
    router: str | None
    wallet: str | None
    side: str
    base_quantity: Decimal
    quote_notional: Decimal | None
    quote_currency: str | None
    tx_hash: str
    log_index: int
    block_number: int | None
    source: str
    provenance: dict


@dataclass(frozen=True, slots=True)
class DexSwapBatch:
    symbol: str
    observed_at_ms: int
    chain: str
    source: str
    observations: tuple[DexSwapObservation, ...]
    issues: tuple[tuple[str, str], ...]
    coverage: dict


@dataclass(frozen=True, slots=True)
class DexProviderPayload:
    rows: list[dict]
    coverage: dict


@dataclass(frozen=True, slots=True)
class GeckoTerminalPool:
    symbol: str
    chain: str
    network_id: str
    pool_address: str
    venue: str
    base_token_address: str

    def __post_init__(self):
        DexScope(self.symbol, 0, self.chain)
        if type(self.network_id) is not str or not _GECKO_NETWORK.fullmatch(self.network_id):
            raise ValueError("invalid_network_id")
        if type(self.pool_address) is not str or not _ADDRESS.fullmatch(self.pool_address):
            raise ValueError("invalid_pool_address")
        if type(self.base_token_address) is not str or not _ADDRESS.fullmatch(self.base_token_address):
            raise ValueError("invalid_base_token_address")
        if type(self.venue) is not str or not _NAME.fullmatch(self.venue):
            raise ValueError("invalid_venue")

    @property
    def source(self):
        return f"geckoterminal:{self.pool_address.lower()}"


class PublicDexTransport(Protocol):
    def fetch_swaps(self, scope: DexScope):
        """Return public swap rows for exactly the requested scope."""


def _decode_json(body):
    if type(body) is not bytes:
        raise MarketCollectionError("malformed_response")

    def duplicate_guard(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate")
            result[key] = value
        return result

    def forbidden(_):
        raise ValueError("float")

    try:
        return json.loads(body.decode("utf-8"), object_pairs_hook=duplicate_guard,
                          parse_float=forbidden, parse_constant=forbidden)
    except (UnicodeError, ValueError, json.JSONDecodeError, RecursionError):
        raise MarketCollectionError("malformed_response") from None


def _iso_ms(value):
    if type(value) is not str or len(value) > 64:
        raise MarketCollectionError("malformed_response")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise MarketCollectionError("malformed_response") from None
    if stamp.tzinfo is None:
        raise MarketCollectionError("malformed_response")
    stamp = stamp.astimezone(timezone.utc)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = stamp - epoch
    return delta.days * 86_400_000 + delta.seconds * 1_000 + delta.microseconds // 1_000


class GeckoTerminalPublicTransport:
    """Keyless fixed-host GET transport for explicitly configured GeckoTerminal pools."""

    def __init__(self, pools, *, timeout_ms=5_000, max_body_bytes=2_000_000):
        if type(pools) is not tuple or not pools or any(not isinstance(item, GeckoTerminalPool) for item in pools):
            raise ValueError("invalid_pool_configuration")
        if type(timeout_ms) is not int or not 1 <= timeout_ms <= 30_000:
            raise ValueError("invalid_timeout")
        if type(max_body_bytes) is not int or not 1 <= max_body_bytes <= 2_000_000:
            raise ValueError("invalid_body_limit")
        self.pools = {(item.symbol, item.chain): item for item in pools}
        if len(self.pools) != len(pools):
            raise ValueError("duplicate_pool_scope")
        self.timeout_ms = timeout_ms
        self.max_body_bytes = max_body_bytes

    def source_for(self, scope: DexScope):
        pool = self.pools.get((scope.symbol, scope.chain))
        if pool is None:
            raise MarketCollectionError("unsupported_scope")
        return pool.source

    def fetch_swaps(self, scope: DexScope):
        if not isinstance(scope, DexScope):
            raise MarketCollectionError("invalid_request")
        pool = self.pools.get((scope.symbol, scope.chain))
        if pool is None:
            raise MarketCollectionError("unsupported_scope")
        target = f"/api/v2/networks/{pool.network_id}/pools/{pool.pool_address.lower()}/trades"
        connection = http.client.HTTPSConnection(
            _GECKO_HOST, port=443, timeout=self.timeout_ms / 1000,
            context=ssl.create_default_context())
        response = None
        try:
            connection.request("GET", target, body=None,
                               headers={"Accept": "application/json", "Accept-Encoding": "identity"})
            response = connection.getresponse()
            if response.status != 200:
                raise MarketCollectionError("http_error")
            encoding = response.getheader("Content-Encoding")
            if encoding and encoding.lower() != "identity":
                raise MarketCollectionError("unsupported_content_encoding")
            body = response.read(self.max_body_bytes + 1)
            if len(body) > self.max_body_bytes:
                raise MarketCollectionError("body_limit_exceeded")
            payload = _decode_json(body)
        except MarketCollectionError:
            raise
        except Exception:
            raise MarketCollectionError("transport_error") from None
        finally:
            if response is not None:
                response.close()
            connection.close()

        data = payload.get("data") if type(payload) is dict else None
        if type(data) is not list or len(data) > _GECKO_MAX_TRADES:
            raise MarketCollectionError("malformed_response")
        rows = []
        source_times = []
        for item in data:
            if type(item) is not dict or item.get("type") != "trade" or type(item.get("attributes")) is not dict:
                raise MarketCollectionError("malformed_response")
            match = _GECKO_TRADE_ID.fullmatch(str(item.get("id", "")))
            if match is None:
                raise MarketCollectionError("missing_identity")
            attrs = item["attributes"]
            tx_hash = attrs.get("tx_hash")
            if type(tx_hash) is not str or tx_hash.lower() != match.group(1).lower():
                raise MarketCollectionError("missing_identity")
            source_ms = _iso_ms(attrs.get("block_timestamp"))
            if source_ms > scope.observed_at_ms:
                continue
            side = attrs.get("kind")
            from_token = attrs.get("from_token_address")
            to_token = attrs.get("to_token_address")
            if side == "buy":
                if type(to_token) is not str or to_token.lower() != pool.base_token_address.lower():
                    raise MarketCollectionError("scope_mismatch")
                base_quantity = attrs.get("to_token_amount")
                normalized_side = "BUY"
            elif side == "sell":
                if type(from_token) is not str or from_token.lower() != pool.base_token_address.lower():
                    raise MarketCollectionError("scope_mismatch")
                base_quantity = attrs.get("from_token_amount")
                normalized_side = "SELL"
            else:
                raise MarketCollectionError("missing_side")
            rows.append({
                "symbol": scope.symbol,
                "chain": scope.chain,
                "venue": pool.venue,
                "router": None,
                "wallet": attrs.get("tx_from_address"),
                "side": normalized_side,
                "base_quantity": base_quantity,
                "quote_notional": attrs.get("volume_in_usd"),
                "quote_currency": "USD",
                "tx_hash": tx_hash,
                "log_index": int(match.group(2)),
                "block_number": attrs.get("block_number"),
                "source_ms": source_ms,
            })
            source_times.append(source_ms)
        oldest = min(source_times) if source_times else None
        newest = max(source_times) if source_times else None
        start_ms = max(0, scope.observed_at_ms - _WINDOW_MS)
        verified = oldest is not None and oldest <= start_ms
        if verified:
            coverage_status = "verified_pool_window"
            proof = "oldest_returned_at_or_before_window_start"
        elif len(data) == _GECKO_MAX_TRADES:
            coverage_status = "provider_limit_truncated"
            proof = "latest_300_does_not_reach_window_start"
        else:
            coverage_status = "unverified_window_coverage"
            proof = "provider_response_does_not_prove_window_start"
        coverage = {
            "status": coverage_status,
            "scope": "single_pool",
            "provider": "geckoterminal",
            "pool_address": pool.pool_address.lower(),
            "base_token_address": pool.base_token_address.lower(),
            "window_ms": _WINDOW_MS,
            "window_start_ms": start_ms,
            "window_end_ms": scope.observed_at_ms,
            "provider_limit": _GECKO_MAX_TRADES,
            "response_count": len(data),
            "accepted_count": len(rows),
            "oldest_source_ms": oldest,
            "newest_source_ms": newest,
            "proof": proof,
        }
        return DexProviderPayload(rows, coverage)


def _decimal(value, name, *, positive=False):
    if value is None:
        return None
    if type(value) is not str:
        raise MarketCollectionError("malformed_swap")
    try:
        result = ipc.decimal_text(value, name, derived=True)
    except ipc.ProtocolError:
        raise MarketCollectionError("malformed_swap") from None
    if positive and result <= 0:
        raise MarketCollectionError("malformed_swap")
    return result


def _integer(value, name, *, optional=False):
    if value is None and optional:
        return None
    try:
        return ipc.integer(value, name)
    except ipc.ProtocolError:
        raise MarketCollectionError("malformed_swap") from None


def _optional_address(value):
    if value is None:
        return None
    if type(value) is not str or not _ADDRESS.fullmatch(value):
        raise MarketCollectionError("malformed_swap")
    return value.lower()


def parse_public_swap_rows(scope: DexScope, payload, *, source: str, coverage=None) -> DexSwapBatch:
    """Normalize a provider adapter payload without inventing missing values."""
    if not isinstance(scope, DexScope):
        raise ValueError("invalid_scope")
    if type(source) is not str or not _NAME.fullmatch(source):
        raise ValueError("invalid_source")
    if type(payload) is not list:
        raise MarketCollectionError("malformed_response")
    if coverage is None:
        coverage = {
            "status": "unverified_window_coverage",
            "scope": "unknown",
            "window_ms": _WINDOW_MS,
        }
    if type(coverage) is not dict:
        raise ValueError("invalid_coverage")

    observations = []
    issues = []
    seen = {}
    for row in payload:
        if type(row) is not dict:
            issues.append(("dex_swaps", "malformed_swap"))
            continue
        try:
            if row.get("symbol") != scope.symbol or row.get("chain") != scope.chain:
                raise MarketCollectionError("scope_mismatch")
            venue = row.get("venue")
            router = row.get("router")
            if type(venue) is not str or not _NAME.fullmatch(venue):
                raise MarketCollectionError("malformed_swap")
            if router is not None and (type(router) is not str or not _NAME.fullmatch(router)):
                raise MarketCollectionError("malformed_swap")
            side = row.get("side")
            if side not in ("BUY", "SELL"):
                raise MarketCollectionError("missing_side" if side is None else "malformed_swap")
            tx_hash = row.get("tx_hash")
            if type(tx_hash) is not str or not _TX.fullmatch(tx_hash):
                raise MarketCollectionError("missing_identity" if tx_hash is None else "malformed_swap")
            log_index = _integer(row.get("log_index"), "log_index")
            source_ms = _integer(row.get("source_ms"), "source_ms")
            if source_ms > scope.observed_at_ms:
                raise MarketCollectionError("source_time_after_observed")
            base_quantity = _decimal(row.get("base_quantity"), "base_quantity", positive=True)
            if base_quantity is None:
                raise MarketCollectionError("missing_base_quantity")
            quote_notional = _decimal(row.get("quote_notional"), "quote_notional", positive=True)
            quote_currency = row.get("quote_currency")
            if quote_currency is not None and (
                    type(quote_currency) is not str or not _NAME.fullmatch(quote_currency)):
                raise MarketCollectionError("malformed_swap")
            block_number = _integer(row.get("block_number"), "block_number", optional=True)
            wallet = _optional_address(row.get("wallet"))
            source_id = f"dex:{scope.chain}:{tx_hash.lower()}:{log_index}"
            provenance = {
                "source": source,
                "identity_rule": "chain_tx_hash_log_index",
                "quote_notional_missing": quote_notional is None,
                "wallet_missing": wallet is None,
            }
            observation = DexSwapObservation(
                source_id, scope.symbol, scope.observed_at_ms, source_ms, scope.chain,
                venue, router, wallet, side, base_quantity, quote_notional,
                quote_currency, tx_hash.lower(), log_index, block_number, source, provenance)
        except MarketCollectionError as exc:
            if exc.code == "scope_mismatch":
                raise
            issues.append(("dex_swaps", exc.code))
            continue
        existing = seen.get(source_id)
        if existing is None:
            seen[source_id] = observation
            observations.append(observation)
        elif existing != observation:
            raise MarketCollectionError("swap_conflict")
    return DexSwapBatch(
        scope.symbol, scope.observed_at_ms, scope.chain, source,
        tuple(observations), tuple(issues), coverage)


def collect_public_swaps(scope: DexScope, transport: PublicDexTransport, *, source: str) -> DexSwapBatch:
    """Supervisor-owned collection seam; transport is mocked in P1-B tests."""
    if not isinstance(scope, DexScope) or not callable(getattr(transport, "fetch_swaps", None)):
        raise ValueError("invalid_collector_configuration")
    try:
        payload = transport.fetch_swaps(scope)
    except MarketCollectionError as exc:
        return DexSwapBatch(scope.symbol, scope.observed_at_ms, scope.chain, source, (),
                            (("dex_swaps", exc.code),), {
                                "status": "unavailable",
                                "scope": "unknown",
                                "window_ms": _WINDOW_MS,
                            })
    if isinstance(payload, DexProviderPayload):
        return parse_public_swap_rows(scope, payload.rows, source=source, coverage=payload.coverage)
    return parse_public_swap_rows(scope, payload, source=source)
