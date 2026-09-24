"""Explicitly authorized, read-only identity/empty-responsibility evidence slice.

No DB, runtime gate, raw payload persistence, retries, or trade capabilities.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlencode

from catos import demo_collection
from catos.okx_collection import RunScope
from catos.okx_http import (
    DemoReadTransport, GLOBAL_DEMO_HOST, HTTPOptions, HTTPSGetSender,
    WireRequest, _json_body,
)

ALGO_TYPES = ("conditional,oco", "trigger", "move_order_stop", "iceberg",
              "twap", "chase", "smart_iceberg")
EXPECTED_DEMO_UID = "888708418616582747"


def load_designated_demo_credentials():
    """Select exactly one Demo-labelled block from the designated local file."""
    path = Path(r"C:\Users\user\Desktop\OKX_API.txt")
    if path.resolve(strict=True) != path.absolute():
        raise ValueError("credential_path_redirected")
    raw = path.read_bytes()
    if not 0 < len(raw) <= demo_collection.MAX_CREDENTIAL_BYTES:
        raise ValueError("credential_file_size_invalid")
    source = raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
    return parse_explicit_demo_block(source)


def parse_explicit_demo_block(source):
    """Reject ambiguous sections; never return or display the Live credential."""
    blocks = []
    block = None
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        assignment = re.fullmatch(r"([^:=：]+?)\s*[:=：]\s*(.+)", stripped)
        if assignment:
            if block is None:
                raise ValueError("unlabelled_credentials")
            key = re.sub(r"[ _-]", "", assignment.group(1)).lower()
            if key in ("apikey", "secretkey", "passphrase"):
                if key in block[1]:
                    raise ValueError("duplicate_credential_field")
                block[1][key] = assignment.group(2).strip()
        else:
            block = (stripped, {})
            blocks.append(block)
    demo = [fields for heading, fields in blocks
            if re.search(r"\bdemo\b|模擬|模拟", heading, re.I)
            and not re.search(r"\blive\b|實盤|正式", heading, re.I)]
    if len(demo) != 1 or set(demo[0]) != {"apikey", "secretkey", "passphrase"}:
        raise ValueError("demo_block_ambiguous")
    return demo_collection.parse_credentials("\n".join(
        f"{key}={demo[0][key]}" for key in ("apikey", "secretkey", "passphrase")))


def collect(credentials, expected_uid, *, sender, pause=time.sleep):
    start = time.monotonic()
    now = time.time_ns() // 1_000_000
    scope = RunScope("catOSv1", "demo", "BTC-USDT-SWAP", now - 1, now,
                     10, 1, 10000, 120000)
    signer = DemoReadTransport(scope, HTTPOptions(host=GLOBAL_DEMO_HOST),
                               credentials, sender=sender)
    result = {
        "version": "dedicated-demo-evidence.v1", "started_ms": now,
        "environment": "demo", "account_alias": "catOSv1",
        "checks": {}, "requests": [], "collection_complete": False,
        "local_unknown": "unverified_local_ledger_not_loaded",
        "reconciled": False, "trade_authorized": False,
        "coverage": "account-wide positions/orders-pending; seven existing algo partitions; no instType/instId filter",
        "semantics": "bounded sequential observations; nonempty response fails empty-account check; no attribution or UNKNOWN clearance",
        "limits": {"max_requests": 10, "request_timeout_ms": 10000,
                   "max_runtime_ms": 120000, "max_body_bytes": 2000000,
                   "retries": 0},
    }

    def get(alias, path, params=None):
        if len(result["requests"]) >= 10 or time.monotonic() - start >= 110:
            raise ValueError("budget")
        if result["requests"]:
            pause(0.5)
        target = path + ("?" + urlencode(params) if params else "")
        audit = {"endpoint": alias, "partition": (params or {}).get("ordType"),
                 "started_ms": time.time_ns() // 1_000_000, "accepted": False}
        result["requests"].append(audit)
        response = sender.send(WireRequest(GLOBAL_DEMO_HOST, target,
            signer._headers(target, alias), 10000, 2000000))
        if response.status != 200:
            raise ValueError("http")
        body = _json_body(response.body, 2000000)
        if body.get("code") != "0" or type(body.get("data")) is not list:
            raise ValueError("api")
        rows = body["data"]
        if any(type(row) is not dict for row in rows):
            raise ValueError("row")
        audit.update(accepted=True, row_count=len(rows),
                     completed_ms=time.time_ns() // 1_000_000)
        return rows

    try:
        rows = get("account_config", "/api/v5/account/config")
        if len(rows) != 1:
            raise ValueError("config")
        config = rows[0]
        checks = result["checks"]
        checks["expected_uid"] = config.get("uid") == expected_uid
        checks["dedicated_subaccount"] = (
            type(config.get("uid")) is str and bool(config["uid"])
            and type(config.get("mainUid")) is str and bool(config["mainUid"])
            and config["uid"] != config["mainUid"])
        checks["net_mode"] = config.get("posMode") == "net_mode"
        checks["account_mode_contract"] = config.get("acctLv") in ("2", "3")
        permissions = config.get("perm", "").split(",")
        checks["permission_contract"] = (
            "read_only" in permissions and len(set(permissions)) == len(permissions)
            and set(permissions) <= {"read_only", "trade"})
        checks["known_role"] = config.get("roleType") in ("0", "1", "2")
        if not all(checks.values()):
            result["status"] = "config_gate_failed"
            return result
        checks["no_remote_position_records"] = not get("positions", "/api/v5/account/positions")
        checks["no_remote_ordinary_orders"] = not get(
            "orders_pending", "/api/v5/trade/orders-pending", {"limit": "100"})
        algo_empty = []
        for kind in ALGO_TYPES:
            algo_empty.append(not get("algo_pending", "/api/v5/trade/orders-algo-pending",
                                      {"ordType": kind, "limit": "100"}))
        checks["no_remote_algos"] = all(algo_empty)
        result["collection_complete"] = True
        result["status"] = "remote_checks_pass_local_unknown_unverified" if all(checks.values()) else "remote_responsibility_not_empty"
    except Exception:
        # Never expose exception text, response messages, identifiers or credentials.
        result["status"] = "incomplete_fixed_error"
    finally:
        result["completed_ms"] = time.time_ns() // 1_000_000
    return result


def main():
    if len(sys.argv) != 2 or sys.argv[1] != "--execute-authorized":
        return 2
    try:
        credentials = load_designated_demo_credentials()
        result = collect(credentials, EXPECTED_DEMO_UID, sender=HTTPSGetSender())
    except Exception:
        result = {"status": "credential_setup_failed", "wire_requests": 0,
                  "reconciled": False, "trade_authorized": False}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
