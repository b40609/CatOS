"""I-a offline OKX evidence checks. No transport, credentials, writer or trade gate.

Caller-supplied coverage assertions are fixture metadata, not exchange guarantees.
Raw payloads and evidence must remain available to the future Supervisor adapter.
"""

from dataclasses import dataclass
from decimal import Decimal, localcontext

from catos import ipc, research


def number(row, field):
    return ipc.decimal_text(row.get(field), field, derived=True)


def text(row, field):
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing {field}")
    return value


def rows(payload):
    if payload.get("code") != "0" or not isinstance(payload.get("data"), list):
        raise ValueError("unsuccessful or malformed response")
    if len(payload["data"]) > 1000 or any(not isinstance(r, dict) for r in payload["data"]):
        raise ValueError("invalid offline response rows")
    return payload["data"]


@dataclass(frozen=True)
class Evidence:
    account: str
    environment: str
    source: str
    evidence_id: str
    source_ms: int
    received_ms: int
    complete: bool

    def __post_init__(self):
        for field in ("account", "environment", "source", "evidence_id"):
            text(vars(self), field)
        for field in ("source_ms", "received_ms"):
            ipc.integer(getattr(self, field), field)
        if type(self.complete) is not bool:
            raise ValueError("complete must be explicit bool")


def evidence_issues(evidence, *, account, environment, now_ms, max_age_ms, max_skew_ms):
    """Explicit test parameters only; no production freshness defaults."""
    for name, value in (("now", now_ms), ("age", max_age_ms), ("skew", max_skew_ms)):
        ipc.integer(value, name)
    issues = set()
    if not evidence:
        return frozenset({"missing_evidence"})
    for e in evidence:
        if (e.account, e.environment) != (account, environment):
            issues.add("scope_mismatch")
        if not e.complete:
            issues.add("incomplete_coverage")
        if e.source_ms > e.received_ms + max_skew_ms or e.received_ms > now_ms:
            issues.add("clock_mismatch")
        if now_ms - min(e.source_ms, e.received_ms) > max_age_ms:
            issues.add("stale")
    if max(e.source_ms for e in evidence) - min(e.source_ms for e in evidence) > max_skew_ms:
        issues.add("snapshot_skew")
    return frozenset(issues)


def usdt_equity(payload):
    """Narrow fixture profile: single USDT equity, no liabilities/other assets.

    Does not establish account eligibility or margin sufficiency. Never uses USD
    totalEq/adjEq as USDT. Unsupported balance profiles fail closed for this decoder.
    """
    data = rows(payload)
    if len(data) != 1 or not isinstance(data[0].get("details"), list):
        raise ValueError("one account balance required")
    details = data[0]["details"]
    if len(details) != 1 or details[0].get("ccy") != "USDT":
        raise ValueError("unsupported collateral profile")
    if number(details[0], "liab") != 0:
        raise ValueError("unsupported liabilities")
    verified = number(details[0], "eq")
    return verified, verified  # P3a: E_verified, E_risk; no equity buffer.


@dataclass(frozen=True)
class Order:
    symbol: str
    order_id: str
    client_id: str
    side: str
    state: str
    size: Decimal
    filled: Decimal
    updated_ms: int


def order(row):
    if row.get("instType") != "SWAP" or not text(row, "instId").endswith("-USDT-SWAP"):
        raise ValueError("unsupported instrument")
    if row.get("tdMode") != "cross" or row.get("posSide") != "net":
        raise ValueError("unsupported position mode")
    if row.get("side") not in ("buy", "sell"):
        raise ValueError("invalid side")
    if row.get("state") not in ("live", "partially_filled", "filled", "canceled", "mmp_canceled"):
        raise ValueError("unknown order state")
    size, filled = number(row, "sz"), number(row, "accFillSz")
    if not 0 <= filled <= size or size <= 0:
        raise ValueError("invalid order quantities")
    stamp = text(row, "uTime")
    if not stamp.isascii() or not stamp.isdigit():
        raise ValueError("invalid order timestamp")
    client_id = row.get("clOrdId", "")
    if not isinstance(client_id, str):
        raise ValueError("invalid client id")
    return Order(row["instId"], text(row, "ordId"), client_id, row["side"],
                 row["state"], size, filled, int(stamp))


def merge_orders(observations):
    """Dedup by exchange ID, retaining timestamp conflicts as unresolved evidence."""
    merged, issues = {}, set()
    for item in observations:
        old = merged.get(item.order_id)
        if old is not None:
            if (old.symbol, old.client_id, old.side) != (item.symbol, item.client_id, item.side):
                issues.add("order_identity_conflict")
            if old.updated_ms == item.updated_ms and old != item:
                issues.add("same_time_conflict")
            if old.updated_ms > item.updated_ms:
                issues.add("out_of_order")
                continue
            if item.filled < old.filled:
                issues.add("cumulative_regression")
        merged[item.order_id] = item
    return merged, frozenset(issues)


def fill_totals(fill_rows):
    """Quantity by order and signed fees by currency; tradeId scoped to symbol."""
    seen, quantities, fees = {}, {}, {}
    with localcontext(research._CONTEXT):
        for row in fill_rows:
            key = text(row, "instId"), text(row, "tradeId")
            value = (text(row, "ordId"), number(row, "fillSz"),
                     number(row, "fillPx"), number(row, "fee"), text(row, "feeCcy"))
            if value[1] <= 0 or value[2] <= 0:
                raise ValueError("invalid fill")
            if key in seen:
                if seen[key] != value:
                    raise ValueError("conflicting duplicate fill")
                continue
            seen[key] = value
            oid, quantity, _, fee, currency = value
            quantities[oid] = quantities.get(oid, Decimal(0)) + quantity
            fees[currency] = fees.get(currency, Decimal(0)) + fee
    return quantities, fees


def reconcile(orders, fill_rows, *, owned_order_ids, unresolved_local_ids, evidence_problems):
    """Return discrepancies only, never a trade authorization or G complete report.

    Historical fills need the matching historical order rows in this audit window.
    Ownership must come from durable local attribution, never tag/clOrdId guessing.
    """
    merged, conflicts = merge_orders(orders)
    quantities, fees = fill_totals(fill_rows)
    issues = set(evidence_problems) | set(conflicts)
    for oid, item in merged.items():
        if oid not in owned_order_ids:
            issues.add("foreign_order")
        if quantities.get(oid, Decimal(0)) != item.filled:
            issues.add("fill_gap")
        if item.state == "filled" and item.filled != item.size:
            issues.add("invalid_terminal")
    if quantities.keys() - merged.keys():
        issues.add("orphan_fill")
    if unresolved_local_ids:
        issues.add("local_unknown")  # absence from a response cannot clear UNKNOWN.
    return frozenset(issues), fees


def external_flows(bill_rows, classifications):
    """Explicit (type, subType) whitelist: external / internal. Unknowns retained.

    No shipped production whitelist; this function does not rebuild E_0 or change it.
    """
    seen, total, unknown = {}, Decimal(0), set()
    with localcontext(research._CONTEXT):
        for row in bill_rows:
            bid = text(row, "billId")
            value = (text(row, "type"), text(row, "subType"),
                     text(row, "ccy"), number(row, "balChg"))
            if bid in seen:
                if seen[bid] != value:
                    raise ValueError("conflicting duplicate bill")
                continue
            seen[bid] = value
            category = classifications.get(value[:2])
            if category not in ("external", "internal") or value[2] != "USDT":
                unknown.add(bid)
            elif category == "external":
                total += value[3]
    return total, frozenset(unknown)
