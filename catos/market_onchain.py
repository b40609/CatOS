"""Bounded public Ethereum token-transfer activity for the on-chain reducer.

The provider contract is intentionally narrow.  Callers supply an exact
24-hour window; this module never invents the YAOZI calendar boundary.  A
reducer input is produced only after Blockscout pagination proves the target
day and all fourteen preceding 24-hour windows complete.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import calendar
import http.client
import json
import re
import ssl

from catos.market_collectors import MarketCollectionError
from catos.market_p1 import OnchainActivity, reduce_onchain_activity


BLOCKSCOUT_ETHEREUM_HOST = "eth.blockscout.com"
ONCHAIN_SOURCE = "blockscout-ethereum-v2-token-transfers"
ONCHAIN_CONTRACT = "catos-blockscout-token-outgoing-address-v1"
DAY_MS = 86_400_000
BASELINE_DAYS = 14
_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_TX_HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
_PATH_RE = re.compile(
    r"^/api/v2/tokens/0x[0-9a-f]{40}/transfers"
    r"(?:\?block_number=[0-9]+&index=[0-9]+)?$"
)
_ZERO_ADDRESS = "0x" + "0" * 40


def _symbol(value):
    if type(value) is not str or not value.endswith("-USDT-SWAP"):
        raise ValueError("invalid_symbol")
    base = value.removesuffix("-USDT-SWAP")
    if not base or not base.isascii() or not base.isalnum():
        raise ValueError("invalid_symbol")
    return value


def _address(value):
    if type(value) is not str or _ADDRESS_RE.fullmatch(value) is None:
        raise ValueError("invalid_contract_address")
    return value.lower()


def _provider_address(value):
    if type(value) is dict:
        value = value.get("hash")
    if type(value) is not str or _ADDRESS_RE.fullmatch(value) is None:
        raise MarketCollectionError("malformed_response")
    return value.lower()


def _timestamp_ms(value):
    if type(value) is not str or not value.endswith("Z"):
        raise MarketCollectionError("malformed_response")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise MarketCollectionError("malformed_response") from None
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise MarketCollectionError("malformed_response")
    utc = parsed.astimezone(timezone.utc)
    return calendar.timegm(utc.utctimetuple()) * 1000 + utc.microsecond // 1000


def _cursor(value):
    if value is None:
        return None
    if type(value) is not dict or set(value) != {"block_number", "index"}:
        raise MarketCollectionError("malformed_response")
    block_number = value["block_number"]
    index = value["index"]
    if (type(block_number) is not int or block_number < 0
            or type(index) is not int or index < 0):
        raise MarketCollectionError("malformed_response")
    return {"block_number": block_number, "index": index}


def _cursor_key(value):
    if value is None:
        return None
    return value["block_number"], value["index"]


@dataclass(frozen=True, slots=True)
class OnchainDailyScope:
    symbol: str
    observed_at_ms: int
    chain: str
    contract_address: str
    day_start_ms: int
    day_end_ms: int

    def __post_init__(self):
        _symbol(self.symbol)
        if self.chain != "ethereum":
            raise ValueError("unsupported_onchain_chain")
        object.__setattr__(self, "contract_address", _address(self.contract_address))
        for value, name in (
            (self.observed_at_ms, "observed_at_ms"),
            (self.day_start_ms, "day_start_ms"),
            (self.day_end_ms, "day_end_ms"),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"invalid_{name}")
        if self.day_end_ms - self.day_start_ms != DAY_MS:
            raise ValueError("invalid_daily_window")
        if self.observed_at_ms < self.day_end_ms:
            raise ValueError("incomplete_daily_window")


@dataclass(frozen=True, slots=True)
class OnchainCollection:
    source: str
    symbol: str
    chain: str
    observed_at_ms: int
    status: str
    source_scope: dict
    evidence: dict
    issues: tuple[str, ...]
    activity: OnchainActivity | None

    def source_run_kwargs(self):
        return {
            "source": self.source,
            "symbol": self.symbol,
            "chain": self.chain,
            "observed_at_ms": self.observed_at_ms,
            "status": self.status,
            "source_scope": self.source_scope,
            "evidence": self.evidence,
            "issues": self.issues,
        }


class BlockscoutEthereumTokenTransferTransport:
    """Keyless fixed-host GET transport for Ethereum Blockscout token transfers."""

    def __init__(self, *, timeout_ms=8_000, max_body_bytes=1_000_000):
        if type(timeout_ms) is not int or not 1 <= timeout_ms <= 30_000:
            raise ValueError("invalid_timeout")
        if type(max_body_bytes) is not int or not 1 <= max_body_bytes <= 2_000_000:
            raise ValueError("invalid_body_limit")
        self.timeout_ms = timeout_ms
        self.max_body_bytes = max_body_bytes

    def _get(self, path):
        if type(path) is not str or _PATH_RE.fullmatch(path) is None:
            raise MarketCollectionError("source_not_allowed")
        connection = http.client.HTTPSConnection(
            BLOCKSCOUT_ETHEREUM_HOST,
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
                    "User-Agent": "catOS-public-onchain/1.0",
                },
            )
            response = connection.getresponse()
            payload = response.read(self.max_body_bytes + 1)
            if response.status != 200:
                raise MarketCollectionError(f"source_http_{response.status}")
            if len(payload) > self.max_body_bytes:
                raise MarketCollectionError("source_body_too_large")
            try:
                return json.loads(payload)
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise MarketCollectionError("malformed_response") from None
        finally:
            if response is not None:
                response.close()
            connection.close()

    def fetch_transfers(self, scope: OnchainDailyScope, cursor=None):
        if not isinstance(scope, OnchainDailyScope):
            raise ValueError("invalid_onchain_scope")
        cursor = _cursor(cursor)
        path = f"/api/v2/tokens/{scope.contract_address}/transfers"
        if cursor is not None:
            path += f"?block_number={cursor['block_number']}&index={cursor['index']}"
        return self._get(path)


def _scope_evidence(scope):
    required_start_ms = scope.day_start_ms - BASELINE_DAYS * DAY_MS
    if required_start_ms < 0:
        raise ValueError("insufficient_pre_epoch_baseline_window")
    return {
        "collection_mode": "live_public",
        "network": "ethereum",
        "token_contract": scope.contract_address,
        "provider_host": BLOCKSCOUT_ETHEREUM_HOST,
        "target_window_start_ms": scope.day_start_ms,
        "target_window_end_ms": scope.day_end_ms,
        "required_history_start_ms": required_start_ms,
        "baseline_days": BASELINE_DAYS,
        "calendar_boundary_contract": "caller_supplied_not_inferred",
        "identity_rule": "erc20_transfer_from_address",
        "beneficial_owner_aggregation": "not_available",
        "yaozi_equivalence_status": "not_claimed_source_semantics_only",
    }


def _windows(scope, senders, *, oldest_source_ms, history_exhausted):
    required_start_ms = scope.day_start_ms - BASELINE_DAYS * DAY_MS
    result = []
    for index, addresses in enumerate(senders):
        start_ms = required_start_ms + index * DAY_MS
        end_ms = start_ms + DAY_MS
        complete = bool(
            history_exhausted
            or (oldest_source_ms is not None and oldest_source_ms < start_ms)
        )
        result.append({
            "start_ms": start_ms,
            "end_ms": end_ms,
            "outgoing_distinct_lower_bound": len(addresses),
            "complete": complete,
        })
    return result


def _result(scope, *, status, evidence, issues, activity):
    return OnchainCollection(
        source=ONCHAIN_SOURCE,
        symbol=scope.symbol,
        chain=scope.chain,
        observed_at_ms=scope.observed_at_ms,
        status=status,
        source_scope=_scope_evidence(scope),
        evidence=evidence,
        issues=tuple(issues),
        activity=activity,
    )


def collect_blockscout_daily_activity(
        scope: OnchainDailyScope, transport, *, max_pages=128,
        previous: OnchainActivity | None = None):
    """Collect one complete day plus 14 complete baseline days or fail closed."""
    if not isinstance(scope, OnchainDailyScope):
        raise ValueError("invalid_onchain_scope")
    if not callable(getattr(transport, "fetch_transfers", None)):
        raise ValueError("invalid_onchain_transport")
    if type(max_pages) is not int or not 1 <= max_pages <= 512:
        raise ValueError("invalid_page_limit")
    if previous is not None and not isinstance(previous, OnchainActivity):
        raise ValueError("invalid_previous_state")

    source_scope = _scope_evidence(scope)
    required_start_ms = source_scope["required_history_start_ms"]
    senders = [set() for _ in range(BASELINE_DAYS + 1)]
    cursor = None
    seen_cursors = set()
    seen_events = set()
    latest_source_ms = None
    oldest_source_ms = None
    previous_source_ms = None
    pages_fetched = 0
    history_exhausted = False
    crossed_required_start = False
    issue = None

    for _ in range(max_pages):
        try:
            payload = transport.fetch_transfers(scope, cursor)
            pages_fetched += 1
            if type(payload) is not dict or type(payload.get("items")) is not list:
                raise MarketCollectionError("malformed_response")
            items = payload["items"]
            next_cursor = _cursor(payload.get("next_page_params"))
            if not items and next_cursor is not None:
                raise MarketCollectionError("malformed_response")

            for item in items:
                if type(item) is not dict or item.get("token_type") != "ERC-20":
                    raise MarketCollectionError("malformed_response")
                token = item.get("token")
                if type(token) is not dict:
                    raise MarketCollectionError("malformed_response")
                token_address = token.get("address_hash", token.get("address"))
                if type(token_address) is not str or _ADDRESS_RE.fullmatch(token_address) is None:
                    raise MarketCollectionError("malformed_response")
                if token_address.lower() != scope.contract_address:
                    raise MarketCollectionError("scope_mismatch")
                transaction_hash = item.get("transaction_hash")
                log_index = item.get("log_index")
                if (type(transaction_hash) is not str
                        or _TX_HASH_RE.fullmatch(transaction_hash) is None
                        or type(log_index) is not int or log_index < 0):
                    raise MarketCollectionError("malformed_response")
                event_key = transaction_hash.lower(), log_index
                if event_key in seen_events:
                    raise MarketCollectionError("duplicate_transfer")
                seen_events.add(event_key)

                source_ms = _timestamp_ms(item.get("timestamp"))
                if previous_source_ms is not None and source_ms > previous_source_ms:
                    raise MarketCollectionError("non_monotonic_source_order")
                previous_source_ms = source_ms
                if latest_source_ms is None:
                    latest_source_ms = source_ms
                oldest_source_ms = source_ms
                if source_ms < required_start_ms:
                    crossed_required_start = True
                    break
                if source_ms >= scope.day_end_ms:
                    continue

                from_address = _provider_address(item.get("from"))
                to_address = _provider_address(item.get("to"))
                if from_address == _ZERO_ADDRESS or from_address == to_address:
                    continue
                bucket = (source_ms - required_start_ms) // DAY_MS
                if not 0 <= bucket <= BASELINE_DAYS:
                    raise MarketCollectionError("scope_mismatch")
                senders[bucket].add(from_address)

            if crossed_required_start:
                break
            if next_cursor is None:
                history_exhausted = True
                break
            key = _cursor_key(next_cursor)
            if key == _cursor_key(cursor) or key in seen_cursors:
                raise MarketCollectionError("repeated_cursor")
            seen_cursors.add(key)
            cursor = next_cursor
        except MarketCollectionError as exc:
            issue = exc.code
            break
        except Exception:
            issue = "transport_error"
            break

    windows = _windows(
        scope, senders,
        oldest_source_ms=oldest_source_ms,
        history_exhausted=history_exhausted,
    )
    complete = issue is None and (crossed_required_start or history_exhausted)
    if issue is None and not complete:
        issue = "provider_page_limit_truncated"

    evidence = {
        "contract": ONCHAIN_CONTRACT,
        "coverage_status": "complete_bounded_window" if complete else issue,
        "pages_fetched": pages_fetched,
        "page_limit": max_pages,
        "required_window_complete": complete,
        "crossed_required_start": crossed_required_start,
        "provider_history_exhausted": history_exhausted,
        "latest_source_ms": latest_source_ms,
        "oldest_source_ms": oldest_source_ms,
        "window_lower_bounds": windows,
        "daily_outgoing_distinct": (
            [len(addresses) for addresses in senders] if complete else None
        ),
        "mint_sender_excluded": True,
        "self_transfer_excluded": True,
        "observation_only": True,
        "smf_eligible": False,
        "direction_signal": None,
        "yaozi_equivalence_status": "not_claimed_source_semantics_only",
    }
    if not complete:
        return _result(
            scope,
            status="issues",
            evidence=evidence,
            issues=(issue,),
            activity=None,
        )

    counts = tuple(len(addresses) for addresses in senders)
    activity = reduce_onchain_activity(
        symbol=scope.symbol,
        chain=scope.chain,
        observed_at_ms=scope.observed_at_ms,
        outgoing_distinct=counts[-1],
        previous_complete_days=counts[:-1],
        previous=previous,
    )
    return _result(
        scope,
        status="ok",
        evidence=evidence,
        issues=(),
        activity=activity,
    )


def persist_onchain_collection(store, collection: OnchainCollection):
    """Persist source evidence first; materialize activity only when complete."""
    if not isinstance(collection, OnchainCollection):
        raise ValueError("invalid_onchain_collection")
    record_run = getattr(store, "record_onchain_source_run", None)
    record_activity = getattr(store, "record_onchain_activity", None)
    if not callable(record_run) or not callable(record_activity):
        raise ValueError("invalid_onchain_store")
    record_run(**collection.source_run_kwargs())
    if collection.activity is not None:
        record_activity(collection.activity)
