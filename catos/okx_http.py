"""I-b-3 restricted, single-run Demo GET adapter. Importing performs no I/O.

Credentials are explicit in-memory inputs. This module never loads credentials,
uses environment proxies, writes files, mutates an account or follows redirects.
Constructing a real sender is NOT authorization to collect a real account.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import hashlib
import hmac
import http.client
import io
import json
import re
import socket
import ssl
import time
from typing import Callable, Protocol
from urllib.parse import urlencode

from catos import bounded_pagination as pages
from catos.okx_collection import ENDPOINTS, PageRequest, PageResponse, RunScope, TransportError


# Only the Global documentation profile is implemented. No regional fallback.
GLOBAL_DEMO_HOST = "openapi.okx.com"
_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_SYMBOL = re.compile(r"[A-Z0-9]{1,32}-USDT-SWAP\Z")
_PUBLIC = frozenset(("public_time", "public_instruments", "mark_price"))
_PAGED = {"orders_pending": "ordId", "orders_history": "ordId",
          "fills": "billId", "fills_history": "billId", "bills": "billId",
          "bills_archive": "billId", "algo_pending": "algoId", "algo_history": "algoId"}
_WINDOWED = frozenset(("orders_history", "fills", "fills_history", "bills", "bills_archive"))
_TARGETED = frozenset(("account_instruments", "public_instruments", "mark_price",
                       "orders_history", "fills", "fills_history", "order", "order_algo"))
_ALGO_TYPES = ("conditional,oco", "trigger", "move_order_stop", "iceberg", "twap", "chase", "smart_iceberg")
_ALGO_STATES = ("effective", "canceled", "order_failed")


def _identifier(value):
    if type(value) is not str or not _ID.fullmatch(value):
        raise ValueError("invalid_identifier")
    return value


def _positive(value, name, maximum):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError("invalid_" + name)
    return value


@dataclass(frozen=True, repr=False)
class MemoryCredentials:
    api_key: str
    secret: str
    passphrase: str

    def __post_init__(self):
        for value in (self.api_key, self.secret, self.passphrase):
            if type(value) is not str or not 1 <= len(value) <= 512 or any(not 33 <= ord(c) <= 126 for c in value):
                raise ValueError("invalid_credentials")

    def __repr__(self):
        return "MemoryCredentials(<redacted>)"


@dataclass(frozen=True)
class HTTPOptions:
    # Explicit choice: not inferred from residence, IP, credentials or config.
    host: str
    page_size: int = 100
    max_body_bytes: int = 2_000_000
    # Sequential global spacing is intentionally conservative for this tiny run.
    min_interval_ms: int = 500

    def __post_init__(self):
        if self.host != GLOBAL_DEMO_HOST:
            raise ValueError("unsupported_host_profile")
        _positive(self.page_size, "page_size", 100)
        _positive(self.max_body_bytes, "body_limit", 2_000_000)
        if type(self.min_interval_ms) is not int or not 500 <= self.min_interval_ms <= 60000:
            raise ValueError("invalid_min_interval")


@dataclass(frozen=True, repr=False)
class WireRequest:
    host: str
    target: str
    headers: tuple[tuple[str, str], ...]
    timeout_ms: int
    max_body_bytes: int

    def __repr__(self):
        return "WireRequest(GET, <private>)"


@dataclass(frozen=True, repr=False)
class WireResponse:
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes

    def __repr__(self):
        return f"WireResponse(status={self.status}, <private>)"


class Sender(Protocol):
    def send(self, request: WireRequest) -> WireResponse:
        """Exactly one GET attempt, no retries, redirects or output of raw data."""


def _wire_guard(request):
    if request.host != GLOBAL_DEMO_HOST or type(request.target) is not str:
        raise ValueError("invalid_wire_target")
    path = request.target.split("?", 1)[0]
    if path not in {e.path for e in ENDPOINTS.values()} or any(ord(c) <= 32 or ord(c) >= 127 for c in request.target):
        raise ValueError("invalid_wire_target")
    if len(request.target) > 4096 or "#" in request.target:
        raise ValueError("invalid_wire_target")
    allowed = {"Accept", "Accept-Encoding", "x-simulated-trading", "OK-ACCESS-KEY",
               "OK-ACCESS-SIGN", "OK-ACCESS-TIMESTAMP", "OK-ACCESS-PASSPHRASE"}
    if len(dict(request.headers)) != len(request.headers):
        raise ValueError("invalid_wire_headers")
    for key, value in request.headers:
        if key not in allowed or type(value) is not str or len(value) > 512 or any(not 32 <= ord(c) <= 126 for c in value):
            raise ValueError("invalid_wire_headers")
    if dict(request.headers).get("x-simulated-trading") != "1":
        raise ValueError("demo_header_required")
    _positive(request.timeout_ms, "timeout", 2**31 - 1)
    _positive(request.max_body_bytes, "body_limit", 2_000_000)


class _DeadlineReader(io.RawIOBase):
    """Refresh remaining time before each socket read, including HTTP headers."""

    def __init__(self, sock, deadline):
        self.sock, self.deadline = sock, deadline

    def readable(self):
        return True

    def readinto(self, buffer):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        self.sock.settimeout(remaining)
        return self.sock.recv_into(buffer)


class _ResponseSocket:
    def __init__(self, sock, deadline):
        self.sock, self.deadline = sock, deadline

    def makefile(self, mode):
        if mode != "rb":
            raise ValueError("invalid_socket_mode")
        return io.BufferedReader(_DeadlineReader(self.sock, self.deadline))


class HTTPSGetSender:
    """Direct verified TLS on port 443, no proxy/cookies/redirect machinery.

    Standard OS DNS lookup is not forcibly cancellable. Subsequent socket I/O
    shares an absolute deadline; a late DNS return is rejected before HTTP send.
    No claim of an OS-hard wall-clock bound during DNS resolution is made.
    """

    def send(self, request):
        _wire_guard(request)
        deadline = time.monotonic() + request.timeout_ms / 1000
        conn = None
        response = None
        try:
            context = ssl.create_default_context()
            conn = http.client.HTTPSConnection(request.host, port=443,
                timeout=request.timeout_ms / 1000, context=context)
            conn.sock = _connect_tls(request.host, context, deadline)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            conn.sock.settimeout(remaining)
            conn.request("GET", request.target, body=None, headers=dict(request.headers))
            response = http.client.HTTPResponse(_ResponseSocket(conn.sock, deadline), method="GET")
            response.begin()
            if time.monotonic() >= deadline:
                raise TimeoutError()
            # Error bodies and redirects are never retained/read for retry logic.
            headers = tuple((k.lower(), v) for k, v in response.getheaders()
                            if k.lower() in ("retry-after", "content-length", "content-encoding", "content-type"))
            if response.status != 200:
                return WireResponse(response.status, headers, b"")
            encodings = [v.lower() for k, v in headers if k == "content-encoding"]
            if encodings and encodings != ["identity"]:
                raise TransportError("unsupported_content_encoding")
            sizes = [v for k, v in headers if k == "content-length"]
            if sizes and (len(sizes) != 1 or not sizes[0].isascii() or not sizes[0].isdigit()
                          or len(sizes[0]) > 12 or int(sizes[0]) > request.max_body_bytes):
                raise TransportError("body_limit_exceeded")
            body = bytearray()
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError()
                chunk = response.read1(min(65536, request.max_body_bytes + 1 - len(body)))
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > request.max_body_bytes:
                    raise TransportError("body_limit_exceeded")
            if sizes and len(body) != int(sizes[0]):
                raise TransportError("truncated_body")
            if time.monotonic() >= deadline:
                raise TimeoutError()
            return WireResponse(response.status, headers, bytes(body))
        except TimeoutError:
            raise TransportError("timeout") from None
        except TransportError:
            raise
        except Exception:
            # No request, headers, exception strings, or response bodies in errors.
            raise TransportError("transport_error") from None
        finally:
            if response is not None:
                response.close()
            if conn is not None:
                conn.close()


def _connect_tls(host, context, deadline):
    """One OS DNS resolution; TCP and TLS each receive the remaining deadline."""
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    for family, socktype, protocol, _, address in addresses:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        sock = socket.socket(family, socktype, protocol)
        try:
            sock.settimeout(remaining)
            sock.connect(address)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            sock.settimeout(remaining)
            secured = context.wrap_socket(sock, server_hostname=host)
            if time.monotonic() >= deadline:
                secured.close()
                raise TimeoutError()
            return secured
        except (TimeoutError, ssl.SSLError):
            sock.close()
            raise
        except OSError:
            sock.close()
    raise OSError("connection_failed")


def _json_body(body, maximum):
    if type(body) is not bytes or len(body) > maximum:
        raise TransportError("body_limit_exceeded")
    def reject_number(_):
        raise ValueError("non_integer_json_number")
    def pairs(items):
        obj = {}
        for k, v in items:
            if k in obj:
                raise ValueError("duplicate_json_key")
            obj[k] = v
        return obj
    try:
        result = json.loads(body.decode("utf-8"), parse_float=reject_number,
                            parse_constant=reject_number, object_pairs_hook=pairs)
        # Reuse I-b-1's depth/node/encoded-size checks before returning raw data.
        pages._encode(result, pages.Limits(1, 1, 1, 1, max_json_bytes=maximum))
        if type(result) is not dict or type(result.get("code")) is not str:
            raise ValueError("invalid_envelope")
        return result
    except (ValueError, TypeError, RecursionError):
        raise TransportError("malformed_response") from None


def _retry_after(headers, now_ms):
    values = [v for k, v in headers if k.lower() == "retry-after"]
    if not values:
        return 0
    if len(values) != 1 or type(values[0]) is not str or len(values[0]) > 128:
        raise TransportError("invalid_retry_after")
    value = values[0].strip()
    try:
        if value.isascii() and value.isdigit():
            if len(value) > 8:
                raise ValueError()
            return int(value) * 1000
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            raise ValueError()
        delta = parsed.astimezone(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
        stamp = (delta.days * 86400 + delta.seconds) * 1000
        return max(0, stamp - now_ms)
    except (ValueError, TypeError, OverflowError):
        raise TransportError("invalid_retry_after") from None


def _partitions(alias):
    if alias == "algo_pending":
        return tuple((("ordType", kind),) for kind in _ALGO_TYPES)
    if alias == "algo_history":
        return tuple((("ordType", kind), ("state", state))
                     for kind in _ALGO_TYPES for state in _ALGO_STATES)
    return ((),)


class DemoReadTransport:
    """One sequential bounded run; create a fresh object for the next run.

    Sender/clock/sleep injection is for trusted local test code. It is not a
    sandbox or a plugin boundary. Audit output contains no IDs or raw payloads.
    """

    def __init__(self, scope: RunScope, options: HTTPOptions, credentials: MemoryCredentials,
                 *, sender: Sender, known_order_ids=frozenset(), known_algo_ids=frozenset(),
                 order_id: str | None = None, algo_id: str | None = None,
                 wall_ms: Callable[[], int] | None = None,
                 monotonic_ms: Callable[[], int] | None = None,
                 sleep_ms: Callable[[int], None] | None = None):
        if not isinstance(scope, RunScope) or not isinstance(options, HTTPOptions) or not isinstance(credentials, MemoryCredentials):
            raise ValueError("invalid_transport_configuration")
        if not _SYMBOL.fullmatch(scope.instrument) or not callable(getattr(sender, "send", None)):
            raise ValueError("invalid_transport_configuration")
        self.scope, self.options = scope, options
        self._credentials, self._sender = credentials, sender
        self._known_orders = {_identifier(v) for v in known_order_ids}
        self._known_algos = {_identifier(v) for v in known_algo_ids}
        self._order_id = None if order_id is None else _identifier(order_id)
        self._algo_id = None if algo_id is None else _identifier(algo_id)
        self._wall = wall_ms or (lambda: time.time_ns() // 1_000_000)
        self._mono = monotonic_ms or (lambda: time.monotonic_ns() // 1_000_000)
        self._sleep = sleep_ms or (lambda ms: time.sleep(ms / 1000))
        self._started = None
        self._last_attempt = None
        self._attempts = 0
        self._state = {}
        self._seen_page_ids = {}
        self._audit = []

    def audit(self):
        """Defensive copy of operational evidence; JSON-ready and ID-free."""
        return {"version": "i-b-3.v1", "host_profile": "global_demo",
                "wire_attempts": self._attempts, "attempts": [dict(v) for v in self._audit]}

    def select_detail(self, alias, identifier):
        """Select one already-known target ID before starting its detail source.

        Callers may select an ID learned from an earlier collection source. This
        neither fetches data nor adds IDs to the known set; no arbitrary ID query.
        """
        identifier = _identifier(identifier)
        if alias in self._state:
            raise ValueError("detail_source_already_started")
        if alias == "order" and identifier in self._known_orders:
            self._order_id = identifier
        elif alias == "order_algo" and identifier in self._known_algos:
            self._algo_id = identifier
        else:
            raise ValueError("detail_id_not_authorized")

    def _query(self, request):
        alias = request.endpoint.alias
        parts = _partitions(alias)
        partition, after = 0, None
        if request.cursor is not None:
            try:
                cursor = json.loads(request.cursor)
                if type(cursor) is not dict or set(cursor) != {"partition", "after"}:
                    raise ValueError()
                partition, after = cursor["partition"], cursor["after"]
                if type(partition) is not int or not 0 <= partition < len(parts):
                    raise ValueError()
                if after is not None:
                    _identifier(after)
            except (ValueError, TypeError):
                raise TransportError("invalid_cursor") from None
        params = dict(parts[partition])
        if alias not in ("account_config", "balance", "bills", "bills_archive", "public_time", "order_algo"):
            params["instType"] = "SWAP"
        # Detail /trade/order accepts instId+ordId, not instType.
        if alias == "order":
            params.pop("instType", None)
        if alias in _TARGETED and alias != "order_algo":
            params["instId"] = self.scope.instrument
        if alias in _WINDOWED:
            params.update(begin=str(self.scope.window_start_ms), end=str(self.scope.window_end_ms))
        if alias in _PAGED:
            params["limit"] = str(self.options.page_size)
            if after is not None:
                params["after"] = after
        elif request.cursor is not None:
            raise TransportError("unexpected_cursor")
        for selected, known, target, key in ((self._order_id, self._known_orders, "order", "ordId"),
                                            (self._algo_id, self._known_algos, "order_algo", "algoId")):
            if alias == target:
                if selected is None or selected not in known:
                    raise TransportError("detail_id_not_authorized")
                params[key] = selected
        return params, partition, parts

    def _headers(self, target, alias):
        result = {"Accept": "application/json", "Accept-Encoding": "identity", "x-simulated-trading": "1"}
        if alias in _PUBLIC:
            return tuple(result.items())
        stamp_ms = self._wall()
        if type(stamp_ms) is not int or not 0 <= stamp_ms <= 253402300799999:
            raise TransportError("invalid_clock")
        timestamp = (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=stamp_ms)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        signature = base64.b64encode(hmac.new(self._credentials.secret.encode("ascii"),
            (timestamp + "GET" + target).encode("ascii"), hashlib.sha256).digest()).decode("ascii")
        result.update({"OK-ACCESS-KEY": self._credentials.api_key,
                       "OK-ACCESS-PASSPHRASE": self._credentials.passphrase,
                       "OK-ACCESS-TIMESTAMP": timestamp, "OK-ACCESS-SIGN": signature})
        return tuple(result.items())

    def fetch(self, request):
        if not isinstance(request, PageRequest) or request.scope != self.scope:
            raise TransportError("scope_mismatch")
        if request.endpoint != ENDPOINTS.get(request.endpoint.alias):
            raise TransportError("invalid_endpoint")
        alias = request.endpoint.alias
        expected_page, expected_cursor, ended = self._state.get(alias, (1, None, False))
        if ended or (request.page_number, request.cursor) != (expected_page, expected_cursor):
            raise TransportError("page_sequence_mismatch")
        params, partition, partitions = self._query(request)
        now = self._mono()
        if self._started is None:
            self._started = now
        deadline = min(now + request.timeout_ms, self._started + self.scope.max_runtime_ms)
        if self._attempts >= self.scope.max_requests:
            raise TransportError("request_budget_exhausted")
        wait = 0 if self._last_attempt is None else max(0, self._last_attempt + self.options.min_interval_ms - now)
        if now + wait >= deadline:
            raise TransportError("timeout")
        if wait:
            self._sleep(wait)
            if self._mono() < now + wait:
                raise TransportError("interrupted")
        remaining = deadline - self._mono()
        if remaining <= 0:
            raise TransportError("timeout")
        target = request.endpoint.path + ("?" + urlencode(sorted(params.items())) if params else "")
        wire = WireRequest(self.options.host, target, self._headers(target, alias), remaining, self.options.max_body_bytes)
        _wire_guard(wire)
        self._attempts += 1
        self._last_attempt = self._mono()
        entry = {"endpoint": alias, "page_number": request.page_number, "partition": partition,
                 "ord_type": params.get("ordType"), "state": params.get("state"),
                 "started_ms": self._wall(), "wait_ms": wait, "outcome": "transport_error"}
        self._audit.append(entry)
        try:
            response = self._sender.send(wire)
            if self._mono() >= deadline:
                raise TransportError("timeout")
            if not isinstance(response, WireResponse) or type(response.status) is not int:
                raise TransportError("malformed_response")
            if 300 <= response.status <= 399:
                raise TransportError("redirect_rejected")
            if response.status == 429:
                raise pages.RetryableRateLimit(_retry_after(response.headers, self._wall()))
            if response.status != 200:
                raise TransportError("http_error")
            payload = _json_body(response.body, self.options.max_body_bytes)
            if payload["code"] == "50011":
                raise pages.RetryableRateLimit(_retry_after(response.headers, self._wall()))
            if payload["code"] != "0":
                raise TransportError("api_error")
            data = payload.get("data")
            if type(data) is not list or any(type(row) is not dict for row in data):
                raise TransportError("malformed_response")
            if alias in ("account_config", "balance", "order", "order_algo", "public_time", "account_instruments", "public_instruments", "mark_price") and len(data) != 1:
                raise TransportError("unexpected_cardinality")
            if alias in _PAGED and len(data) > self.options.page_size:
                raise TransportError("unexpected_page_size")
            for row in data:
                if alias in _TARGETED and row.get("instId") != self.scope.instrument:
                    raise TransportError("instrument_scope_mismatch")
                if alias in ("positions", "orders_pending", "algo_pending", "algo_history") and row.get("instType") != "SWAP":
                    raise TransportError("instrument_scope_mismatch")
                if alias == "order" and row.get("ordId") != self._order_id:
                    raise TransportError("detail_identity_mismatch")
                if alias == "order_algo" and row.get("algoId") != self._algo_id:
                    raise TransportError("detail_identity_mismatch")
                if alias.startswith("algo_") and (row.get("ordType") not in params["ordType"].split(",")
                        or (alias == "algo_history" and row.get("state") != params["state"])):
                    raise TransportError("partition_mismatch")
            next_cursor = None
            page_ids = ()
            if alias in _PAGED:
                if data:
                    ids = [_identifier(row.get(_PAGED[alias])) for row in data]
                    page_ids = tuple(ids)
                    seen_ids = self._seen_page_ids.get((alias, partition), set())
                    if len(set(ids)) != len(ids) or params.get("after") in ids or seen_ids.intersection(ids):
                        raise TransportError("nonprogressing_page")
                    next_cursor = json.dumps({"partition": partition, "after": ids[-1]}, separators=(",", ":"))
                elif partition + 1 < len(partitions):
                    next_cursor = json.dumps({"partition": partition + 1, "after": None}, separators=(",", ":"))
            # IDs only enter the in-memory detail allowlist from accepted target rows.
            new_orders, new_algos = set(), set()
            for row in data:
                if row.get("instId") != self.scope.instrument:
                    continue
                if alias in ("orders_pending", "orders_history", "order", "fills", "fills_history") and row.get("ordId"):
                    new_orders.add(_identifier(row["ordId"]))
                if alias in ("algo_pending", "algo_history", "order_algo"):
                    new_algos.add(_identifier(row.get("algoId")))
                    children = row.get("ordIdList", [])
                    if type(children) is not list:
                        raise TransportError("malformed_response")
                    new_orders.update(_identifier(v) for v in children)
            received = self._wall()
            if self._mono() >= deadline:
                raise TransportError("timeout")
            answer = PageResponse(self.scope.account_alias, self.scope.environment, received, payload, next_cursor)
            self._known_orders.update(new_orders)
            self._known_algos.update(new_algos)
            if page_ids:
                self._seen_page_ids.setdefault((alias, partition), set()).update(page_ids)
            self._state[alias] = (expected_page + 1, next_cursor, next_cursor is None)
            entry["outcome"] = "accepted"
            entry["bytes"] = len(response.body)
            return answer
        except pages.RetryableRateLimit:
            entry["outcome"] = "rate_limited"
            raise
        except TransportError as exc:
            # Protect against arbitrary errors from an injected trusted test sender.
            allowed = {"timeout", "redirect_rejected", "http_error", "api_error", "malformed_response",
                       "unexpected_cardinality", "unexpected_page_size", "instrument_scope_mismatch",
                       "detail_identity_mismatch", "partition_mismatch", "nonprogressing_page",
                       "body_limit_exceeded", "truncated_body", "unsupported_content_encoding",
                       "invalid_retry_after", "transport_error"}
            code = exc.issue if exc.issue in allowed else "transport_error"
            entry["outcome"] = code
            raise TransportError(code) from None
        except Exception:
            entry["outcome"] = "malformed_response"
            raise TransportError("malformed_response") from None
        finally:
            entry["completed_ms"] = self._wall()
