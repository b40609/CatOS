"""I-b-1 offline OKX collection contract and bounded pagination driver.

No HTTP implementation, credential access, persistence or trading capability
belongs in this module. Optional rate-limit retry is counted by the page driver.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from types import MappingProxyType
from typing import Any, Callable, Protocol

from catos import bounded_pagination as pagination


COLLECTOR_VERSION = "i-b-1.v1"
SNAPSHOT_SEMANTICS_CONTRACT = "s1-bounded-sequential.v1"
WINDOW_COVERAGE_CONTRACT = "w1-exact-window-pagination.v1"
WINDOWED_EVENT_ENDPOINTS = frozenset(("orders_history", "fills", "fills_history", "bills", "bills_archive"))


@dataclass(frozen=True)
class EndpointSpec:
    alias: str
    path: str
    source_time_semantics: str = "transport-supplied; decode semantics in I-b-2"
    method: str = "GET"

    def __post_init__(self) -> None:
        if not isinstance(self.alias, str) or not self.alias:
            raise ValueError("endpoint alias must be non-empty text")
        if not isinstance(self.path, str) or not self.path.startswith("/api/v5/") or "://" in self.path:
            raise ValueError("endpoint path must be a fixed OKX API path")
        if self.method != "GET":
            raise ValueError("I-b-1 permits GET endpoints only")


def _endpoint(alias: str, path: str) -> EndpointSpec:
    if not path.startswith("/api/v5/"):
        raise ValueError("endpoint path must be an OKX API path")
    return EndpointSpec(alias=alias, path=path)


ENDPOINTS = MappingProxyType({
    "account_subtypes": _endpoint("account_subtypes", "/api/v5/account/subtypes"),
    "account_config": _endpoint("account_config", "/api/v5/account/config"),
    "account_instruments": _endpoint("account_instruments", "/api/v5/account/instruments"),
    "balance": _endpoint("balance", "/api/v5/account/balance"),
    "positions": _endpoint("positions", "/api/v5/account/positions"),
    "orders_pending": _endpoint("orders_pending", "/api/v5/trade/orders-pending"),
    "order": _endpoint("order", "/api/v5/trade/order"),
    "orders_history": _endpoint("orders_history", "/api/v5/trade/orders-history"),
    "fills": _endpoint("fills", "/api/v5/trade/fills"),
    "fills_history": _endpoint("fills_history", "/api/v5/trade/fills-history"),
    "bills": _endpoint("bills", "/api/v5/account/bills"),
    "bills_archive": _endpoint("bills_archive", "/api/v5/account/bills-archive"),
    "algo_pending": _endpoint("algo_pending", "/api/v5/trade/orders-algo-pending"),
    "algo_history": _endpoint("algo_history", "/api/v5/trade/orders-algo-history"),
    "order_algo": _endpoint("order_algo", "/api/v5/trade/order-algo"),
    "public_time": _endpoint("public_time", "/api/v5/public/time"),
    "public_instruments": _endpoint("public_instruments", "/api/v5/public/instruments"),
    "mark_price": _endpoint("mark_price", "/api/v5/public/mark-price"),
})


def _nonempty_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(f"{field} must be non-empty normalized text")
    return value


def _positive_int(value: object, field: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _timestamp_ms(value: object, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a non-negative integer millisecond timestamp")
    return value


@dataclass(frozen=True)
class RunScope:
    account_alias: str
    environment: str
    instrument: str
    window_start_ms: int
    window_end_ms: int
    max_requests: int
    max_pages_per_endpoint: int
    request_timeout_ms: int
    max_runtime_ms: int

    def __post_init__(self) -> None:
        _nonempty_text(self.account_alias, "account_alias")
        if self.environment != "demo":
            raise ValueError("I-b scope currently permits only the selected demo environment")
        instrument = _nonempty_text(self.instrument, "instrument")
        if not instrument.endswith("-USDT-SWAP"):
            raise ValueError("instrument must be an explicit USDT-SWAP contract")
        start = _timestamp_ms(self.window_start_ms, "window_start_ms")
        end = _timestamp_ms(self.window_end_ms, "window_end_ms")
        if start >= end:
            raise ValueError("collection window must have start < end")
        _positive_int(self.max_requests, "max_requests")
        _positive_int(self.max_pages_per_endpoint, "max_pages_per_endpoint")
        _positive_int(self.request_timeout_ms, "request_timeout_ms")
        _positive_int(self.max_runtime_ms, "max_runtime_ms")


@dataclass(frozen=True)
class CollectionPlan:
    scope: RunScope
    endpoint_aliases: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.scope, RunScope):
            raise ValueError("scope must be RunScope")
        if type(self.endpoint_aliases) is not tuple or not self.endpoint_aliases:
            raise ValueError("at least one endpoint is required")
        if any(type(alias) is not str for alias in self.endpoint_aliases):
            raise ValueError('endpoint aliases must be strings')
        if len(set(self.endpoint_aliases)) != len(self.endpoint_aliases):
            raise ValueError("duplicate endpoint aliases are not allowed")
        unknown = [alias for alias in self.endpoint_aliases if alias not in ENDPOINTS]
        if unknown:
            raise ValueError(f"endpoint is not allowlisted: {unknown[0]}")


@dataclass(frozen=True)
class PageRequest:
    endpoint: EndpointSpec
    scope: RunScope
    page_number: int
    cursor: str | None
    timeout_ms: int

    def __post_init__(self) -> None:
        if not isinstance(self.scope, RunScope):
            raise ValueError("scope must be RunScope")
        allowed = ENDPOINTS.get(getattr(self.endpoint, "alias", None))
        if allowed is None or self.endpoint != allowed or self.endpoint.method != "GET":
            raise ValueError("endpoint must match the fixed GET allowlist")
        if type(self.page_number) is not int or self.page_number <= 0:
            raise ValueError("page number must be positive")
        if type(self.timeout_ms) is not int or self.timeout_ms <= 0:
            raise ValueError("timeout must be positive")
        if self.page_number > self.scope.max_pages_per_endpoint or self.timeout_ms > min(self.scope.request_timeout_ms, self.scope.max_runtime_ms):
            raise ValueError('request exceeds scope budget')
        if self.cursor is not None and (not isinstance(self.cursor, str) or not self.cursor):
            raise ValueError("cursor must be non-empty text when present")


@dataclass(frozen=True)
class WindowRequestEvidence:
    begin_ms: int
    end_ms: int
    event_time_field: str = "ts"
    cursor_semantics: str = "after_bill_id"

    def __post_init__(self) -> None:
        begin = _timestamp_ms(self.begin_ms, "window evidence begin_ms")
        end = _timestamp_ms(self.end_ms, "window evidence end_ms")
        if begin >= end:
            raise ValueError("window evidence must have begin < end")
        if (self.event_time_field, self.cursor_semantics) not in {
                ("ts", "after_bill_id"),
                ("cTime", "after_order_id"),
        }:
            raise ValueError("unsupported window evidence semantics")


@dataclass(frozen=True)
class PageResponse:
    account_alias: str
    environment: str
    source_ms: int
    payload: dict[str, Any]
    next_cursor: str | None = None
    window_evidence: WindowRequestEvidence | None = None

    def __post_init__(self) -> None:
        _nonempty_text(self.account_alias, "account_alias")
        _nonempty_text(self.environment, "environment")
        _timestamp_ms(self.source_ms, "source_ms")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be a JSON object")
        if self.next_cursor is not None and (not isinstance(self.next_cursor, str) or not self.next_cursor):
            raise ValueError("next cursor must be non-empty text when present")
        if self.window_evidence is not None and not isinstance(self.window_evidence, WindowRequestEvidence):
            raise ValueError("invalid window request evidence")


class PageTransport(Protocol):
    def fetch(self, request: PageRequest) -> PageResponse:
        """Return one page while honoring request.timeout_ms."""


class TransportError(pagination.TransportError):
    """Expected transport failure that makes the current endpoint incomplete."""


class RateLimited(TransportError):
    """Transport observed an HTTP 429 or equivalent rate-limit rejection."""

    def __init__(self):
        super().__init__("rate_limited")


class CollectionInterrupted(TransportError):
    """Explicit cooperative interruption from a transport or caller."""

    def __init__(self):
        super().__init__("interrupted")


@dataclass(frozen=True)
class CollectedPage:
    endpoint_alias: str
    page_number: int
    payload_json: str
    request_cursor: str | None


@dataclass(frozen=True)
class PageEvidence:
    page_number: int
    request_cursor: str | None
    next_cursor: str | None
    source_ms: int
    received_ms: int
    digest: str


@dataclass(frozen=True)
class EndpointManifest:
    alias: str
    path: str
    source_time_semantics: str
    started_ms: int | None
    completed_ms: int
    requests: int
    complete: bool
    issue: str
    pages: tuple[pagination.Evidence, ...]
    window_evidence: WindowRequestEvidence | None = None


@dataclass(frozen=True)
class RunManifest:
    collector_version: str
    account_alias: str
    environment: str
    instrument: str
    window_start_ms: int
    window_end_ms: int
    started_ms: int
    completed_ms: int
    requests: int
    complete: bool
    endpoint_manifests: tuple[EndpointManifest, ...]


@dataclass(frozen=True)
class CollectionResult:
    pages: tuple[CollectedPage, ...]
    manifest: RunManifest


class _Clock:
    @staticmethod
    def wall_ms() -> int:
        return time.time_ns() // 1_000_000

    @staticmethod
    def monotonic_ms() -> int:
        return time.monotonic_ns() // 1_000_000


def collect_plan(
    plan: CollectionPlan,
    transport: PageTransport,
    *,
    clock: pagination.Clock | None = None,
    retry_policy: pagination.RetryPolicy = pagination.RetryPolicy(),
    sleep_ms: Callable[[int], None] | None = None,
    stop_on_incomplete: tuple[str, ...] = (),
) -> CollectionResult:
    if not isinstance(plan, CollectionPlan):
        raise ValueError("plan must be CollectionPlan")
    if not callable(getattr(transport, "fetch", None)):
        raise ValueError("transport must provide fetch")
    if (type(stop_on_incomplete) is not tuple
            or any(type(alias) is not str or alias not in plan.endpoint_aliases for alias in stop_on_incomplete)):
        raise ValueError("stop_on_incomplete must name selected sources")

    active_clock = clock or _Clock()
    run_started_ms = active_clock.wall_ms()
    run_started_mono = active_clock.monotonic_ms()
    collected: list[CollectedPage] = []
    manifests: list[EndpointManifest] = []
    requests = 0
    stop_issue = ""

    for alias in plan.endpoint_aliases:
        spec = ENDPOINTS[alias]
        accepted_window_evidence: list[WindowRequestEvidence | None] = []
        remaining_ms = plan.scope.max_runtime_ms - (active_clock.monotonic_ms() - run_started_mono)
        if not stop_issue:
            if requests >= plan.scope.max_requests:
                stop_issue = 'request_budget_exhausted'
            elif remaining_ms <= 0:
                stop_issue = 'runtime_budget_exhausted'
        if stop_issue:
            manifests.append(EndpointManifest(alias, spec.path, spec.source_time_semantics,
                None, active_clock.wall_ms(), 0, False, 'not_started:' + stop_issue, ()))
            continue

        endpoint_started = active_clock.wall_ms()
        page_number = 0

        def fetch(cursor: str | None, timeout_ms: int) -> pagination.Page:
            nonlocal page_number
            remaining = plan.scope.max_runtime_ms - (active_clock.monotonic_ms() - run_started_mono)
            if remaining <= 0:
                raise pagination.FetchError('runtime_budget_exhausted')
            request = PageRequest(spec, plan.scope, page_number + 1, cursor, min(timeout_ms, remaining))
            response = transport.fetch(request)
            if not isinstance(response, PageResponse):
                raise pagination.FetchError('malformed_response')
            if (response.account_alias, response.environment) != (plan.scope.account_alias, plan.scope.environment):
                raise pagination.FetchError('scope_mismatch')
            # This is only envelope validation, not account/financial decoding.
            if response.payload.get('code') != '0':
                raise pagination.FetchError('api_error')
            if not isinstance(response.payload.get('data'), list):
                raise pagination.FetchError('malformed_response')
            accepted_window_evidence.append(response.window_evidence)
            page_number += 1
            return pagination.Page(response.payload, response.source_ms, response.next_cursor)

        result = pagination.collect(fetch, pagination.Limits(
            max_requests=plan.scope.max_requests - requests,
            max_pages=plan.scope.max_pages_per_endpoint,
            request_timeout_ms=plan.scope.request_timeout_ms,
            max_runtime_ms=remaining_ms), clock=active_clock,
            retry_policy=retry_policy, sleep_ms=sleep_ms)
        requests += result.requests
        collected.extend(CollectedPage(alias, evidence.page_number, payload, evidence.request_cursor)
                         for payload, evidence in zip(result.payloads_json, result.evidence))
        window_evidence = None
        if (alias in WINDOWED_EVENT_ENDPOINTS and result.evidence
                and len(accepted_window_evidence) == len(result.evidence)
                and accepted_window_evidence[0] is not None
                and all(item == accepted_window_evidence[0] for item in accepted_window_evidence)):
            window_evidence = accepted_window_evidence[0]
        manifests.append(EndpointManifest(alias, spec.path, spec.source_time_semantics,
            endpoint_started, active_clock.wall_ms(), result.requests, result.complete,
            result.issue, result.evidence, window_evidence))
        if result.issue in ('scope_mismatch', 'rate_limited', 'interrupted'):
            stop_issue = result.issue
        elif alias in stop_on_incomplete and not result.complete:
            stop_issue = 'required_source_incomplete'

    return CollectionResult(tuple(collected), RunManifest(
        COLLECTOR_VERSION, plan.scope.account_alias, plan.scope.environment,
        plan.scope.instrument, plan.scope.window_start_ms, plan.scope.window_end_ms,
        run_started_ms, active_clock.wall_ms(), requests,
        all(item.complete for item in manifests), tuple(manifests)))
