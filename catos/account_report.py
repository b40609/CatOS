"""I-b-2 offline account facts and private, pseudonymized discrepancy report.

Only accepts I-b-1 in-memory evidence. No persistence or trading authorization.
Unknown/malformed fields never become zero. These decoders implement the local
I-a contract; separate transport validation does not verify every live response.
"""

from decimal import Decimal
import hashlib
import json
import re

from catos import ipc, okx_readonly as ia
from catos.okx_collection import ENDPOINTS, CollectionResult, RunScope


_TOKEN = re.compile(r"[A-Za-z0-9_,.-]{1,128}\Z")
_IDS = {"uid": "user", "mainUid": "user", "ordId": "order",
        "clOrdId": "client", "algoId": "algo", "algoClOrdId": "algo_client",
        "posId": "position", "tradeId": "trade", "billId": "bill"}
_GROUP = {"orders_pending": "order", "orders_history": "order", "order": "order",
          "fills": "fill", "fills_history": "fill", "bills": "bill",
          "bills_archive": "bill", "algo_pending": "algo", "algo_history": "algo",
          "order_algo": "algo"}


def _text(row, field):
    value = ia.text(row, field)
    if not _TOKEN.fullmatch(value):
        raise ValueError("invalid text")
    return value


def _stamp(row, field):
    value = ia.text(row, field)
    if not value.isascii() or not value.isdigit() or len(value) > 19:
        raise ValueError("invalid timestamp")
    return ipc.integer(int(value), field)


class _BalanceFieldError(ValueError):
    _FIELDS = frozenset(("totalEq", "adjEq", "uTime", "details", "details[]",
                         "details[].ccy", "details[].uTime", "details[].eq",
                         "details[].liab", "details[].availEq", "details[].ordFrozen"))
    _REASONS = frozenset(("missing", "invalid_decimal", "invalid_timestamp",
                          "invalid_structure", "invalid_text", "duplicate_currency"))

    def __init__(self, field, reason):
        if field not in self._FIELDS or reason not in self._REASONS:
            raise ValueError("invalid balance diagnostic")
        super().__init__("invalid balance field")
        self.field = field
        self.reason = reason


def _balance_value(row, name, parser, reason, prefix=""):
    if row.get(name) is None or row.get(name) == "":
        raise _BalanceFieldError(prefix + name, "missing")
    try:
        return parser(row, name)
    except (ValueError, TypeError, AttributeError):
        raise _BalanceFieldError(prefix + name, reason) from None


def decode_row(alias, row):
    """Allowlisted normalized fact; financial fields are Decimal, time is ms.

    Invalid records raise a fixed error at the report boundary, without raw data.
    Unsupported modes remain facts so foreign responsibilities are not hidden.
    """
    if type(row) is not dict:
        raise ValueError("invalid row")
    kind = _GROUP.get(alias, alias)
    fact = {"kind": kind}
    def texts(*names):
        for name in names:
            fact[name] = _text(row, name)
    def nums(*names):
        for name in names:
            fact[name] = ia.number(row, name)
    def stamp(name):
        fact[name] = _stamp(row, name)
    if kind == "account_config":
        texts("uid", "mainUid", "acctLv", "posMode", "roleType", "perm")
        fact["is_subaccount"] = fact["uid"] != fact["mainUid"]
    elif kind in ("account_instruments", "public_instruments"):
        texts("instType", "instId", "ctType", "settleCcy", "ctValCcy", "state")
        nums("ctVal", "ctMult", "tickSz", "lotSz", "minSz")
        if any(fact[n] <= 0 for n in ("ctVal", "ctMult", "tickSz", "lotSz", "minSz")):
            raise ValueError("invalid instrument quantity")
    elif kind == "balance":
        for name in ("totalEq", "adjEq"):
            fact[name] = _balance_value(row, name, ia.number, "invalid_decimal")
        fact["uTime"] = _balance_value(row, "uTime", _stamp, "invalid_timestamp")
        fact["aggregate_currency"] = "USD"
        details = row.get("details")
        if details is None or details == []:
            raise _BalanceFieldError("details", "missing")
        if type(details) is not list:
            raise _BalanceFieldError("details", "invalid_structure")
        fact["details"] = []
        for detail in details:
            if type(detail) is not dict:
                raise _BalanceFieldError("details[]", "invalid_structure")
            item = {"ccy": _balance_value(detail, "ccy", _text, "invalid_text", "details[]."),
                    "uTime": _balance_value(detail, "uTime", _stamp, "invalid_timestamp", "details[].")}
            item.update({n: _balance_value(detail, n, ia.number, "invalid_decimal", "details[].")
                         for n in ("eq", "liab", "availEq", "ordFrozen")})
            fact["details"].append(item)
        if len({d["ccy"] for d in fact["details"]}) != len(details):
            raise _BalanceFieldError("details[].ccy", "duplicate_currency")
    elif kind == "positions":
        texts("instType", "instId", "posId", "mgnMode", "posSide")
        nums("pos")
        stamp("uTime")
        fact["avgPx"] = None if fact["pos"] == 0 and row.get("avgPx") == "" else ia.number(row, "avgPx")
        if fact["pos"] != 0 and fact["avgPx"] <= 0:
            raise ValueError("invalid average cost")
    elif kind == "order":
        texts("instType", "instId", "ordId", "tdMode", "posSide", "side", "state")
        nums("sz", "accFillSz")
        stamp("uTime")
        if not 0 <= fact["accFillSz"] <= fact["sz"] or fact["sz"] <= 0:
            raise ValueError("invalid order quantity")
        if row.get("clOrdId"):
            texts("clOrdId")
    elif kind == "fill":
        texts("instId", "tradeId", "ordId", "feeCcy")
        nums("fillSz", "fillPx", "fee")
        stamp("ts")
        if fact["fillSz"] <= 0 or fact["fillPx"] <= 0:
            raise ValueError("invalid fill")
    elif kind == "bill":
        texts("billId", "type", "subType", "ccy")
        nums("balChg")
        stamp("ts")
    elif kind == "algo":
        texts("instType", "instId", "algoId", "state", "tdMode", "posSide", "side", "ordType")
        stamp("uTime")
        for name in ("closeFraction", "slTriggerPx", "slOrdPx"):
            fact[name] = None if row.get(name) in (None, "") else ia.number(row, name)
        fact["slTriggerPxType"] = _text(row, "slTriggerPxType") if row.get("slTriggerPxType") else None
        fact["reduceOnly"] = row.get("reduceOnly")
        # OKX algo REST documents this field as a String; retain bool fixtures.
        if type(fact["reduceOnly"]) is str and fact["reduceOnly"] in ("true", "false"):
            fact["reduceOnly"] = fact["reduceOnly"] == "true"
        if type(fact["reduceOnly"]) is not bool:
            raise ValueError("invalid reduceOnly")
        if row.get("algoClOrdId"):
            texts("algoClOrdId")
        children = row.get("ordIdList")
        if type(children) is not list or any(type(v) is not str or not _TOKEN.fullmatch(v) for v in children):
            raise ValueError("missing child evidence")
        fact["ordIdList"] = list(dict.fromkeys(children))
    elif kind == "public_time":
        stamp("ts")
    elif kind == "mark_price":
        texts("instType", "instId")
        nums("markPx")
        stamp("ts")
        if fact["markPx"] <= 0:
            raise ValueError("invalid mark")
    else:
        raise ValueError("unsupported source")
    return fact


def build_report(result, *, scope, owned_order_ids=frozenset(),
                 owned_algo_ids=frozenset(), owned_positions=None,
                 unresolved_local_ids=frozenset(), classifications=None):
    """Return JSON-ready private report. Attribution is caller's durable evidence.

    owned_positions maps (instId, posId) to the locally verified signed Decimal
    quantity. Window is inclusive [start_ms, end_ms] for fills/bills only. Order
    and algo timestamps are last updates, NOT snapshot freshness or fill windows.
    All output IDs use a fresh per-report sequential namespace, never raw hashes.
    """
    if not isinstance(result, CollectionResult) or not isinstance(scope, RunScope):
        raise ValueError("invalid report input")
    owned_positions = dict(owned_positions or {})
    if any(type(v) is not Decimal or not v.is_finite() for v in owned_positions.values()):
        raise ValueError("local positions require finite Decimal")
    classifications = dict(classifications or {})
    m = result.manifest
    issues, facts, sources = set(), [], []
    record_diagnostics = []
    aliases = [e.alias for e in m.endpoint_manifests]
    if ((m.account_alias, m.environment, m.instrument, m.window_start_ms, m.window_end_ms) !=
        (scope.account_alias, scope.environment, scope.instrument, scope.window_start_ms, scope.window_end_ms)):
        raise ValueError("scope_mismatch")
    if not aliases or len(set(aliases)) != len(aliases) or any(a not in ENDPOINTS for a in aliases):
        raise ValueError("invalid_manifest")
    pages = {}
    for page in result.pages:
        if type(page.page_number) is not int or page.page_number <= 0:
            issues.add("page_chain_invalid")
            continue
        key = page.endpoint_alias, page.page_number
        if key in pages:
            raise ValueError("duplicate_page")
        pages[key] = page
    expected = {(e.alias, p.page_number) for e in m.endpoint_manifests for p in e.pages
                if type(p.page_number) is int and p.page_number > 0}
    if set(pages) != expected:
        issues.add("page_evidence_gap")
    if not m.complete or not all(e.complete for e in m.endpoint_manifests):
        issues.add("incomplete_collection")
    if (type(m.complete) is not bool or any(type(e.complete) is not bool for e in m.endpoint_manifests)
            or m.complete != all(e.complete for e in m.endpoint_manifests)):
        issues.add("manifest_completion_mismatch")
    for e in m.endpoint_manifests:
        if e.complete and (not e.pages or e.pages[-1].next_cursor is not None or e.issue != ""):
            issues.add("manifest_completion_mismatch")
        sources.append({"alias": e.alias, "started_ms": e.started_ms,
                        "completed_ms": e.completed_ms, "requests": e.requests,
                        "source_time_semantics": "transport_supplied_not_verified_snapshot",
                        "record_time_semantics": ("event_ms" if _GROUP.get(e.alias) in ("fill", "bill")
                                                  else "last_update_or_reference_ms_not_snapshot"),
                        "complete": e.complete, "issue": "collection_failed" if e.issue else "",
                        "pages": []})
        seen_pages, seen_cursors = set(), set()
        previous_next = None
        for number, ev in enumerate(e.pages, 1):
            valid_number = type(ev.page_number) is int and ev.page_number > 0
            valid_request = ev.request_cursor is None or (type(ev.request_cursor) is str and bool(ev.request_cursor))
            valid_next = ev.next_cursor is None or (type(ev.next_cursor) is str and bool(ev.next_cursor))
            if (not valid_number or ev.page_number != number or not valid_request or not valid_next
                    or ev.request_cursor != previous_next or (number > 1 and previous_next is None)
                    or (valid_next and ev.next_cursor is not None and ev.next_cursor in seen_cursors)):
                issues.add("page_chain_invalid")
            previous_next = ev.next_cursor if valid_next else None
            if valid_next and ev.next_cursor is not None:
                seen_cursors.add(ev.next_cursor)
            sources[-1]["pages"].append({"page_number": ev.page_number if valid_number else None,
                "request_cursor": ev.request_cursor if valid_request else None,
                "next_cursor": ev.next_cursor if valid_next else None,
                "source_ms": ev.source_ms, "received_ms": ev.received_ms,
                "digest": ev.digest})
            if not valid_number or ev.page_number in seen_pages:
                continue
            seen_pages.add(ev.page_number)
            page = pages.get((e.alias, ev.page_number))
            if page is None:
                continue
            if (hashlib.sha256(page.payload_json.encode("utf-8")).hexdigest() != ev.digest
                    or page.request_cursor != ev.request_cursor):
                issues.add("page_evidence_mismatch")
                continue
            try:
                data = ia.rows(json.loads(page.payload_json))
            except (ValueError, TypeError, AttributeError):
                issues.add("malformed_page")
                continue
            if e.alias in ("account_config", "balance") and len(data) != 1:
                issues.add("singleton_cardinality")
            for index, row in enumerate(data):
                try:
                    fact = decode_row(e.alias, row)
                except _BalanceFieldError as exc:
                    issues.add("invalid_record:" + e.alias)
                    record_diagnostics.append({"alias": e.alias, "page": ev.page_number, "row": index,
                                               "field": exc.field, "reason": exc.reason})
                    continue
                except (ValueError, TypeError, AttributeError):
                    issues.add("invalid_record:" + e.alias)
                    continue
                fact["source"] = {"alias": e.alias, "page": ev.page_number, "row": index}
                facts.append(fact)

    collection_complete = (m.complete is True and all(e.complete is True for e in m.endpoint_manifests)
                           and not {"page_evidence_gap", "page_evidence_mismatch", "malformed_page",
                                    "page_chain_invalid", "manifest_completion_mismatch"} & issues)
    by_kind = {}
    # Each identity retains all content versions and their own source lists.
    seen = {}
    unique = []
    for f in facts:
        kind = f["kind"]
        identity = {"order": (f.get("ordId"),), "fill": (f.get("instId"), f.get("tradeId")),
                    "bill": (f.get("billId"),), "algo": (f.get("algoId"),),
                    "positions": (f.get("instId"), f.get("posId"))}.get(kind)
        body = {k: v for k, v in f.items() if k != "source"}
        if identity is not None:
            key = (kind, identity)
            versions = seen.setdefault(key, [])
            matching_sources = next((sources_for_version for previous, sources_for_version in versions
                                     if previous == body), None)
            if matching_sources is not None:
                matching_sources.append(f["source"])
                continue
            if versions:
                issues.add("conflicting_observation:" + kind)
            f["observations"] = [f["source"]]
            versions.append((body, f["observations"]))
        unique.append(f)
        by_kind.setdefault(kind, []).append(f)
        if "instId" in f:
            if not f["instId"].endswith("-USDT-SWAP") or f.get("instType", "SWAP") != "SWAP":
                issues.add("unsupported_instrument")
            if kind not in ("positions", "order", "algo") and f["instId"] != scope.instrument:
                issues.add("instrument_scope_mismatch")
        if "posSide" in f and f["posSide"] != "net":
            issues.add("mode_mismatch")
        if f.get("mgnMode", f.get("tdMode", "cross")) != "cross":
            issues.add("mode_mismatch")
        if kind in ("fill", "bill") and not scope.window_start_ms <= f["ts"] <= scope.window_end_ms:
            issues.add("outside_window:" + kind)
        if kind == "account_config":
            if f["posMode"] != "net_mode" or f["acctLv"] not in ("2", "3"):
                issues.add("mode_mismatch")
            if not f["is_subaccount"]:
                issues.add("not_subaccount")
        if kind in ("account_instruments", "public_instruments"):
            if (f["ctType"], f["settleCcy"], f["ctValCcy"], f["state"]) != ("linear", "USDT", scope.instrument.split("-")[0], "live"):
                issues.add("unsupported_contract")
        if kind == "positions" and f["pos"] != 0:
            key = (f["instId"], f["posId"])
            if key not in owned_positions:
                issues.add("foreign_position")
            elif owned_positions[key] != f["pos"]:
                issues.add("position_mismatch")
        if kind == "order":
            if f["ordId"] not in owned_order_ids:
                issues.add("foreign_order")
            if f["state"] not in ("live", "partially_filled", "filled", "canceled", "mmp_canceled"):
                issues.add("unknown_order_state")
            if f["side"] not in ("buy", "sell"):
                issues.add("invalid_side")
            if f["state"] == "filled" and f["sz"] != f["accFillSz"]:
                issues.add("invalid_terminal")
        if kind == "algo":
            if f["algoId"] not in owned_algo_ids:
                issues.add("foreign_algo")
            if f["state"] not in ("live", "pause", "effective", "canceled", "order_failed"):
                issues.add("unknown_algo_state")
            if f["side"] not in ("buy", "sell"):
                issues.add("invalid_side")
            if (f["closeFraction"] != Decimal(1) or f["slTriggerPxType"] != "mark"
                    or f["slOrdPx"] != Decimal(-1) or not f["reduceOnly"]
                    or f["slTriggerPx"] is None or f["slTriggerPx"] <= 0
                    or f["ordType"] not in ("conditional", "oco")):
                issues.add("p6_protection_unverified")

    required = {"account_config", "balance", "positions", "orders_pending", "algo_pending", "account_instruments"}
    if required - set(aliases):
        issues.add("missing_governance_source")
    for kind in ("account_config", "balance", "account_instruments"):
        if len(by_kind.get(kind, [])) != 1:
            issues.add("missing_or_ambiguous:" + kind)
    positions = {(f["instId"], f["posId"]): f["pos"] for f in by_kind.get("positions", [])}
    if any(positions.get(k) != v for k, v in owned_positions.items()):
        issues.add("local_position_unverified")
    orders = {f["ordId"]: f for f in by_kind.get("order", [])}
    fills = by_kind.get("fill", [])
    # 无效证据链、事件身份冲突或超出窗口时不计算合计；合法部分采集保留已观测小计。
    fees, flows = None, None
    fill_valid = (bool(set(aliases) & {"fills", "fills_history"}) and
                  not any(i in issues for i in ("invalid_record:fills", "invalid_record:fills_history",
                      "conflicting_observation:fill", "outside_window:fill", "malformed_page",
                      "page_evidence_gap", "page_evidence_mismatch", "page_chain_invalid",
                      "manifest_completion_mismatch")))
    if fill_valid:
        try:
            quantities, fees = ia.fill_totals([_decimal_strings(f) for f in fills])
            for oid, f in orders.items():
                if quantities.get(oid, Decimal(0)) != f["accFillSz"]:
                    issues.add("fill_window_gap")
            if quantities.keys() - orders.keys():
                issues.add("orphan_fill")
        except ValueError:
            issues.add("fill_conflict")
    bill_valid = (bool(set(aliases) & {"bills", "bills_archive"}) and
                  not any(i in issues for i in ("invalid_record:bills", "invalid_record:bills_archive",
                      "conflicting_observation:bill", "outside_window:bill", "malformed_page",
                      "page_evidence_gap", "page_evidence_mismatch", "page_chain_invalid",
                      "manifest_completion_mismatch")))
    if bill_valid:
        flows, unknown = ia.external_flows([_decimal_strings(f) for f in by_kind.get("bill", [])], classifications)
        if unknown:
            issues.add("unknown_external_flow")
            flows = None
    for f in by_kind.get("algo", []):
        if f["state"] == "effective":
            issues.add("p6_triggered_not_reconciled")
            if not f["ordIdList"] or any(oid not in orders for oid in f["ordIdList"]):
                issues.add("p6_child_order_gap")
    if unresolved_local_ids:
        issues.add("local_unknown")
    if not fill_valid:
        issues.add("fill_totals_unavailable")
    if not bill_valid:
        issues.add("external_flow_unavailable")
    # No invented freshness threshold, E_0, collateral conversion or trade gate.
    issues.update(("freshness_unverified", "window_coverage_unverified", "day_baseline_unverified"))
    for f in by_kind.get("balance", []):
        details = f["details"]
        if len(details) != 1 or details[0]["ccy"] != "USDT" or details[0]["liab"] != 0:
            issues.add("unsupported_collateral")
    report = {"version": "i-b-2.v1", "account_alias": scope.account_alias,
        "environment": scope.environment, "instrument": scope.instrument,
        "window_start_ms": scope.window_start_ms, "window_end_ms": scope.window_end_ms,
        "started_ms": m.started_ms, "completed_ms": m.completed_ms,
        "collection_complete": collection_complete,
        "reconciled": False, "trade_authorized": False, "sources": sources,
        "facts": unique, "discrepancies": sorted(issues), "record_diagnostics": record_diagnostics,
        "observed_signed_fees_by_currency": fees, "observed_external_flow_usdt": flows}
    return _private_output(report)


def _decimal_strings(value):
    if isinstance(value, Decimal):
        return str(value)
    if type(value) is dict:
        return {k: _decimal_strings(v) for k, v in value.items()}
    if type(value) is list:
        return [_decimal_strings(v) for v in value]
    return value


def _private_output(report):
    names = {}
    def alias(kind, value):
        key = kind, value
        if key not in names:
            names[key] = f"{kind}_{1 + sum(k[0] == kind for k in names)}"
        return names[key]
    def visit(value, key=""):
        if value is None:
            return None
        if key in _IDS:
            return alias(_IDS[key], value)
        if key in ("request_cursor", "next_cursor"):
            return alias("cursor", value)
        if key == "digest":
            # Raw response hash is not exported: it can fingerprint private input.
            return alias("evidence", value)
        if key == "ordIdList":
            return [alias("order", item) for item in value]
        if isinstance(value, Decimal):
            return str(value)
        if type(value) is dict:
            return {k: visit(v, k) for k, v in value.items()}
        if type(value) is list:
            return [visit(v) for v in value]
        return value
    output = visit(report)
    output["content_digest"] = hashlib.sha256(json.dumps(output, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    return output
