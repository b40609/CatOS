"""Explicitly authorized one-shot Demo balance cleanup.

This operator maintenance tool is deliberately narrower than the application
runtime: fixed Demo host, fixed demo-adjust-balance endpoint, fixed removable
currencies (BTC/ETH/OKB), one POST at most, no retries, no trading orders, and
no persistence of credentials, raw payloads, identifiers, or monetary values.
USDT is never adjusted.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import http.client
import json
import ssl
import sys
import time

from catos.okx_collection import RunScope
from catos.okx_http import (
    DemoReadTransport,
    GLOBAL_DEMO_HOST,
    HTTPOptions,
    HTTPSGetSender,
    WireRequest,
    _ResponseSocket,
    _connect_tls,
    _json_body,
)
from tools.demo_subaccount_evidence import (
    EXPECTED_DEMO_UID,
    collect as collect_identity,
    load_designated_demo_credentials,
)


TARGET_CCYS = ("BTC", "ETH", "OKB")
BALANCE_TARGET = "/api/v5/account/balance?ccy=BTC,ETH,OKB,USDT"
ADJUST_TARGET = "/api/v5/account/demo-adjust-balance"
MAX_BODY_BYTES = 200_000
TIMEOUT_MS = 10_000


def _decimal_text(value, name):
    if type(value) is not str or not value or len(value) > 128:
        raise ValueError(name)
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError(name) from None
    if not number.is_finite():
        raise ValueError(name)
    return number


def _zero_or_na(value, name):
    if value in (None, ""):
        return True
    return _decimal_text(value, name) == 0


def plan_reductions(balance_row):
    """Return fixed-currency Demo reductions after strict free-balance checks."""
    if type(balance_row) is not dict or type(balance_row.get("details")) is not list:
        raise ValueError("invalid_balance")
    details = balance_row["details"]
    by_ccy = {}
    for item in details:
        if type(item) is not dict or type(item.get("ccy")) is not str:
            raise ValueError("invalid_balance")
        ccy = item["ccy"]
        if ccy in by_ccy:
            raise ValueError("duplicate_currency")
        by_ccy[ccy] = item
    if "USDT" not in by_ccy:
        raise ValueError("usdt_missing")

    reductions = []
    for ccy in TARGET_CCYS:
        item = by_ccy.get(ccy)
        if item is None:
            continue
        eq = _decimal_text(item.get("eq"), "eq")
        if eq < 0:
            raise ValueError("negative_equity")
        if eq == 0:
            continue
        avail = _decimal_text(item.get("availBal"), "availBal")
        cash = _decimal_text(item.get("cashBal"), "cashBal")
        if avail != eq or cash != eq:
            raise ValueError("balance_not_fully_available")
        if not _zero_or_na(item.get("liab"), "liab"):
            raise ValueError("liability_present")
        if not _zero_or_na(item.get("frozenBal"), "frozenBal"):
            raise ValueError("frozen_balance_present")
        if not _zero_or_na(item.get("ordFrozen"), "ordFrozen"):
            raise ValueError("order_frozen_present")
        reductions.append({"ccy": ccy, "amt": format(eq, "f")})
    return tuple(reductions)


@dataclass(frozen=True, repr=False)
class PostRequest:
    host: str
    target: str
    body: bytes
    headers: tuple[tuple[str, str], ...]
    timeout_ms: int = TIMEOUT_MS
    max_body_bytes: int = MAX_BODY_BYTES

    def __repr__(self):
        return "PostRequest(POST, <private>)"


@dataclass(frozen=True, repr=False)
class PostResponse:
    status: int
    body: bytes

    def __repr__(self):
        return f"PostResponse(status={self.status}, <private>)"


def _post_headers(credentials, target, body, wall_ms):
    if target != ADJUST_TARGET or type(wall_ms) is not int:
        raise ValueError("invalid_post")
    timestamp = (datetime(1970, 1, 1, tzinfo=timezone.utc)
                 + timedelta(milliseconds=wall_ms)).isoformat(
                     timespec="milliseconds").replace("+00:00", "Z")
    body_text = body.decode("ascii")
    signature = base64.b64encode(hmac.new(
        credentials.secret.encode("ascii"),
        (timestamp + "POST" + target + body_text).encode("ascii"),
        hashlib.sha256,
    ).digest()).decode("ascii")
    return tuple({
        "Accept": "application/json",
        "Accept-Encoding": "identity",
        "Content-Type": "application/json",
        "x-simulated-trading": "1",
        "OK-ACCESS-KEY": credentials.api_key,
        "OK-ACCESS-PASSPHRASE": credentials.passphrase,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-SIGN": signature,
    }.items())


class HTTPSPostSender:
    """One fixed Demo POST over verified TLS; no redirects or retries."""

    def send(self, request):
        if (not isinstance(request, PostRequest)
                or request.host != GLOBAL_DEMO_HOST
                or request.target != ADJUST_TARGET
                or not request.body or len(request.body) > 8192
                or dict(request.headers).get("x-simulated-trading") != "1"):
            raise ValueError("invalid_post_request")
        deadline = time.monotonic() + request.timeout_ms / 1000
        conn = None
        response = None
        try:
            context = ssl.create_default_context()
            conn = http.client.HTTPSConnection(
                request.host, port=443, timeout=request.timeout_ms / 1000, context=context)
            conn.sock = _connect_tls(request.host, context, deadline)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            conn.sock.settimeout(remaining)
            conn.request("POST", request.target, body=request.body, headers=dict(request.headers))
            response = http.client.HTTPResponse(_ResponseSocket(conn.sock, deadline), method="POST")
            response.begin()
            if response.status != 200:
                return PostResponse(response.status, b"")
            content_length = response.getheader("content-length")
            if content_length is not None:
                if (not content_length.isascii() or not content_length.isdigit()
                        or int(content_length) > request.max_body_bytes):
                    raise ValueError("body_limit")
            body = response.read(request.max_body_bytes + 1)
            if len(body) > request.max_body_bytes:
                raise ValueError("body_limit")
            return PostResponse(response.status, body)
        except Exception:
            raise ValueError("post_failed") from None
        finally:
            if response is not None:
                response.close()
            if conn is not None:
                conn.close()


def _balance_once(credentials, sender):
    now = time.time_ns() // 1_000_000
    scope = RunScope("catOSv1", "demo", "BTC-USDT-SWAP", now - 1, now,
                     2, 1, TIMEOUT_MS, 30_000)
    signer = DemoReadTransport(scope, HTTPOptions(host=GLOBAL_DEMO_HOST), credentials,
                               sender=sender)
    response = sender.send(WireRequest(
        GLOBAL_DEMO_HOST, BALANCE_TARGET,
        signer._headers(BALANCE_TARGET, "balance"), TIMEOUT_MS, MAX_BODY_BYTES))
    if response.status != 200:
        raise ValueError("balance_http")
    body = _json_body(response.body, MAX_BODY_BYTES)
    if body.get("code") != "0" or type(body.get("data")) is not list or len(body["data"]) != 1:
        raise ValueError("balance_api")
    return body["data"][0]


def _verify_cleared(balance_row):
    details = balance_row.get("details") if type(balance_row) is dict else None
    if type(details) is not list:
        return False
    found = {item.get("ccy"): item for item in details if type(item) is dict}
    for ccy in TARGET_CCYS:
        item = found.get(ccy)
        if item is None:
            continue
        try:
            if _decimal_text(item.get("eq"), "eq") != 0:
                return False
        except ValueError:
            return False
    return True


def execute(credentials, *, get_sender, post_sender, pause=time.sleep):
    identity = collect_identity(
        credentials, EXPECTED_DEMO_UID, sender=get_sender, pause=pause)
    checks = identity.get("checks", {})
    required = (
        "expected_uid", "dedicated_subaccount", "net_mode", "account_mode_contract",
        "permission_contract", "known_role", "no_remote_position_records",
        "no_remote_ordinary_orders", "no_remote_algos",
    )
    if identity.get("collection_complete") is not True or not all(checks.get(k) is True for k in required):
        return {"status": "preflight_failed", "post_attempted": False,
                "reconciled": False, "trade_authorized": False}

    before = _balance_once(credentials, get_sender)
    try:
        reductions = plan_reductions(before)
    except ValueError:
        return {"status": "balance_not_safe_to_reduce", "post_attempted": False,
                "reconciled": False, "trade_authorized": False}
    if not reductions:
        return {"status": "already_single_usdt", "post_attempted": False,
                "cleared_currencies": [], "reconciled": False, "trade_authorized": False}

    body = json.dumps({"type": "reduce", "adjustments": list(reductions)},
                      ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    headers = _post_headers(credentials, ADJUST_TARGET, body, time.time_ns() // 1_000_000)
    response = post_sender.send(PostRequest(GLOBAL_DEMO_HOST, ADJUST_TARGET, body, headers))
    if response.status != 200:
        return {"status": "post_http_failed", "post_attempted": True,
                "reconciled": False, "trade_authorized": False}
    try:
        payload = _json_body(response.body, MAX_BODY_BYTES)
        if payload.get("code") != "0" or type(payload.get("data")) is not list or len(payload["data"]) != 1:
            raise ValueError()
    except Exception:
        return {"status": "post_api_failed", "post_attempted": True,
                "reconciled": False, "trade_authorized": False}

    after = _balance_once(credentials, get_sender)
    if not _verify_cleared(after):
        return {"status": "post_verify_failed", "post_attempted": True,
                "reconciled": False, "trade_authorized": False}
    return {"status": "cleared", "post_attempted": True,
            "cleared_currencies": [item["ccy"] for item in reductions],
            "reconciled": False, "trade_authorized": False}


def main():
    if len(sys.argv) != 2 or sys.argv[1] != "--execute-authorized":
        return 2
    try:
        credentials = load_designated_demo_credentials()
        result = execute(credentials, get_sender=HTTPSGetSender(), post_sender=HTTPSPostSender())
    except Exception:
        result = {"status": "fixed_error", "post_attempted": False,
                  "reconciled": False, "trade_authorized": False}
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result.get("status") in ("cleared", "already_single_usdt") else 2


if __name__ == "__main__":
    raise SystemExit(main())
