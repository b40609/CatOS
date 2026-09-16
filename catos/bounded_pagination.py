"""Pure offline bounded pagination with explicit completeness evidence."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time
from typing import Any, Callable, Protocol


DEFAULT_MAX_JSON_DEPTH = 32
DEFAULT_MAX_JSON_NODES = 100_000
DEFAULT_MAX_JSON_BYTES = 2_000_000


class FetchError(Exception):
    def __init__(self, issue: str):
        if not isinstance(issue, str) or not issue:
            raise ValueError("fetch error issue must be non-empty text")
        super().__init__(issue)
        self.issue = issue


class TransportError(FetchError):
    def __init__(self, issue: str = "transport_error"):
        super().__init__(issue)


class RetryableRateLimit(FetchError):
    """Only an explicit rate-limit response is eligible for bounded retry."""

    def __init__(self, retry_after_ms: int = 0):
        if type(retry_after_ms) is not int or retry_after_ms < 0:
            raise ValueError("invalid retry delay")
        super().__init__("rate_limited")
        self.retry_after_ms = retry_after_ms


@dataclass(frozen=True)
class RetryPolicy:
    max_retries_per_page: int = 0
    base_delay_ms: int = 1000
    max_delay_ms: int = 10000

    def __post_init__(self):
        if type(self.max_retries_per_page) is not int or not 0 <= self.max_retries_per_page <= 5:
            raise ValueError("retry count must be in 0..5")
        if (type(self.base_delay_ms) is not int or type(self.max_delay_ms) is not int
                or not 1 <= self.base_delay_ms <= self.max_delay_ms <= 60000):
            raise ValueError("invalid retry delay bounds")


class RateLimited(TransportError):
    def __init__(self):
        super().__init__("rate_limited")


class Interrupted(TransportError):
    def __init__(self):
        super().__init__("interrupted")


@dataclass(frozen=True)
class Limits:
    max_requests: int
    max_pages: int
    request_timeout_ms: int
    max_runtime_ms: int
    max_json_depth: int = DEFAULT_MAX_JSON_DEPTH
    max_json_nodes: int = DEFAULT_MAX_JSON_NODES
    max_json_bytes: int = DEFAULT_MAX_JSON_BYTES

    def __post_init__(self) -> None:
        for name in (
            "max_requests",
            "max_pages",
            "request_timeout_ms",
            "max_runtime_ms",
            "max_json_depth",
            "max_json_nodes",
            "max_json_bytes",
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class Page:
    payload: dict[str, Any]
    source_ms: int
    next_cursor: str | None = None


@dataclass(frozen=True)
class Evidence:
    page_number: int
    request_cursor: str | None
    next_cursor: str | None
    source_ms: int
    received_ms: int
    digest: str


@dataclass(frozen=True)
class Result:
    payloads_json: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    requests: int
    complete: bool
    issue: str


class Clock(Protocol):
    def wall_ms(self) -> int: ...

    def monotonic_ms(self) -> int: ...


class _Clock:
    @staticmethod
    def wall_ms() -> int:
        return time.time_ns() // 1_000_000

    @staticmethod
    def monotonic_ms() -> int:
        return time.monotonic_ns() // 1_000_000


class _PayloadProblem(ValueError):
    def __init__(self, issue: str):
        super().__init__(issue)
        self.issue = issue


def _json(value: Any, limits: Limits, *, depth: int = 0, nodes: list[int] | None = None) -> None:
    if nodes is None:
        nodes = [0, 0]
    nodes[0] += 1
    if nodes[0] > limits.max_json_nodes:
        raise _PayloadProblem("page_node_limit_exceeded")
    if depth > limits.max_json_depth:
        raise _PayloadProblem("page_depth_limit_exceeded")
    if value is None or type(value) in (bool, int):
        return
    if isinstance(value, str):
        nodes[1] += len(value.encode("utf-8"))
        if nodes[1] > limits.max_json_bytes:
            raise _PayloadProblem("page_byte_limit_exceeded")
        return
    if isinstance(value, list):
        for item in value:
            _json(item, limits, depth=depth + 1, nodes=nodes)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise _PayloadProblem("malformed_page")
            nodes[1] += len(key.encode("utf-8"))
            if nodes[1] > limits.max_json_bytes:
                raise _PayloadProblem("page_byte_limit_exceeded")
            _json(item, limits, depth=depth + 1, nodes=nodes)
        return
    raise _PayloadProblem("malformed_page")


def _encode(payload: object, limits: Limits) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise _PayloadProblem("malformed_page")
    _json(payload, limits)
    parts, size = [], 0
    digest = hashlib.sha256()
    encoder = json.JSONEncoder(ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    for part in encoder.iterencode(payload):
        encoded = part.encode('utf-8')
        size += len(encoded)
        if size > limits.max_json_bytes:
            raise _PayloadProblem('page_byte_limit_exceeded')
        parts.append(part)
        digest.update(encoded)
    return ''.join(parts), digest.hexdigest()


def collect(
    fetch: Callable[[str | None, int], Page],
    limits: Limits,
    *,
    clock: Clock | None = None,
    retry_policy: RetryPolicy = RetryPolicy(),
    sleep_ms: Callable[[int], None] | None = None,
) -> Result:
    if not isinstance(retry_policy, RetryPolicy):
        raise ValueError("invalid retry policy")
    pause = sleep_ms or (lambda ms: time.sleep(ms / 1000))
    active_clock = clock or _Clock()
    started = active_clock.monotonic_ms()
    cursor: str | None = None
    seen: set[str] = set()
    payloads: list[str] = []
    evidence: list[Evidence] = []
    requests = 0
    issue = ""

    for page_number in range(1, limits.max_pages + 1):
        if requests >= limits.max_requests:
            issue = "request_budget_exhausted"
            break
        elapsed = active_clock.monotonic_ms() - started
        if elapsed >= limits.max_runtime_ms:
            issue = "runtime_budget_exhausted"
            break

        retries = 0
        while True:
            remaining_runtime_ms = limits.max_runtime_ms - (active_clock.monotonic_ms() - started)
            if requests >= limits.max_requests:
                issue = "request_budget_exhausted"
                break
            if remaining_runtime_ms <= 0:
                issue = "runtime_budget_exhausted"
                break
            effective_timeout_ms = min(limits.request_timeout_ms, remaining_runtime_ms)
            call_started = active_clock.monotonic_ms()
            requests += 1
            try:
                page = fetch(cursor, effective_timeout_ms)
                break
            except RetryableRateLimit as exc:
                if active_clock.monotonic_ms() - call_started >= effective_timeout_ms:
                    issue = "timeout"
                    break
                if retries >= retry_policy.max_retries_per_page:
                    issue = "rate_limited"
                    break
                if requests >= limits.max_requests:
                    issue = "request_budget_exhausted"
                    break
                delay = max(exc.retry_after_ms, min(retry_policy.max_delay_ms,
                            retry_policy.base_delay_ms * 2 ** retries))
                # Never shorten a server's Retry-After to fit a local cap.
                if delay > retry_policy.max_delay_ms:
                    issue = "rate_limited"
                    break
                remaining = limits.max_runtime_ms - (active_clock.monotonic_ms() - started)
                if delay >= remaining:
                    issue = "runtime_budget_exhausted"
                    break
                resume_at = active_clock.monotonic_ms() + delay
                pause(delay)
                if active_clock.monotonic_ms() < resume_at:
                    issue = "interrupted"
                    break
                retries += 1
            except TimeoutError:
                issue = "timeout"
                break
            except FetchError as exc:
                issue = exc.issue
                break
            except OSError:
                issue = "transport_error"
                break
        if issue:
            break

        if active_clock.monotonic_ms() - call_started > effective_timeout_ms:
            issue = "timeout"
            break
        try:
            if not isinstance(page, Page) or type(page.source_ms) is not int or page.source_ms < 0:
                raise _PayloadProblem("malformed_page")
            if page.next_cursor is not None and (not isinstance(page.next_cursor, str) or not page.next_cursor):
                raise _PayloadProblem("malformed_page")
            if page.next_cursor is not None and len(page.next_cursor.encode('utf-8')) > limits.max_json_bytes:
                raise _PayloadProblem('page_byte_limit_exceeded')
            payload_text, digest = _encode(page.payload, limits)
        except _PayloadProblem as exc:
            issue = exc.issue
            break
        except (ValueError, RecursionError):
            issue = 'malformed_page'
            break

        payloads.append(payload_text)
        evidence.append(Evidence(
            page_number=page_number,
            request_cursor=cursor,
            next_cursor=page.next_cursor,
            source_ms=page.source_ms,
            received_ms=active_clock.wall_ms(),
            digest=digest,
        ))
        if active_clock.monotonic_ms() - started >= limits.max_runtime_ms:
            issue = "runtime_budget_exhausted"
            break
        if page.next_cursor is None:
            return Result(tuple(payloads), tuple(evidence), requests, True, "")
        if page.next_cursor == cursor or page.next_cursor in seen:
            issue = "repeated_cursor"
            break
        seen.add(page.next_cursor)
        cursor = page.next_cursor

    if not issue:
        issue = "page_limit_exhausted"
    return Result(tuple(payloads), tuple(evidence), requests, False, issue)
