"""R1 synthetic local-sim observations; no collector, credentials or dispatcher."""

from copy import deepcopy
from decimal import Decimal, localcontext
import hashlib
import json

from catos import ipc, okx_readonly, reconciliation_gate as gate, research, risk


def seal(report):
    report.pop("content_digest", None)
    report["content_digest"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    return report


def equity(report):
    balances = [f for f in report["facts"] if f.get("kind") == "balance"]
    if len(balances) != 1:
        raise ValueError("one qualified USDT balance required")
    details = balances[0].get("details", [])
    if len(details) != 1 or details[0].get("ccy") != "USDT" or details[0].get("liab") != "0":
        raise ValueError("synthetic R1 requires USDT-only, zero-liability balance")
    value = ipc.decimal_text(details[0].get("eq"), "period equity", derived=True)
    return value


def observation(report, account_alias):
    if (gate._report_digest(report) is None or report.get("environment") != "local-sim"
            or report.get("account_alias") != account_alias):
        raise ValueError("qualified local-sim report required")
    sources = [s for s in report["sources"] if s.get("alias") == "balance"]
    if len(sources) != 1:
        raise ValueError("one balance observation required")
    observed = sources[0]["completed_ms"]
    ipc.integer(observed, "balance observation time")
    return observed, equity(report)


def candidate(report, account_alias):
    observed, value = observation(report, account_alias)
    context = risk.DayContext.from_target_time_ms(observed)
    if value <= 0:
        raise ValueError("positive initial period equity required")
    evidence_id = "r1-" + report["content_digest"][:32]
    evidence = risk.BaselineEvidence(risk.RISK_PERIOD_CONTRACT, account_alias, "local-sim",
        risk.RISK_PERIOD_SOURCE, context.trading_day_start_ms, observed, value,
        "observed_period_equity", evidence_id, report_content_digest=report["content_digest"])
    digest = risk.compute_baseline_digest(account_alias=account_alias, environment="local-sim",
        day=context.day, equity=value, source=risk.RISK_PERIOD_SOURCE,
        evidence_id=evidence_id, evidence=evidence)
    return risk.DayBasis(context.day, value, evidence_id, account_alias, "local-sim",
                         risk.RISK_PERIOD_SOURCE, digest, evidence)


def project(report, basis, classifications):
    """Recompute C_t from complete bill facts, never reuse midnight totals."""
    if (gate._report_digest(report) is None or basis.source != risk.RISK_PERIOD_SOURCE
            or not risk.is_verified_baseline(basis, account_alias=report.get("account_alias"),
                environment=report.get("environment"), target_day=basis.day)):
        raise ValueError("verified local period and intact report required")
    output = deepcopy(report)
    start, cutoff = basis.evidence.observed_at_ms, report["window_end_ms"]
    issues = set(output["discrepancies"])
    seen, selected = {}, []
    ambiguous = False
    for fact in output["facts"]:
        if fact.get("kind") != "bill":
            continue
        bid = fact["billId"]
        if bid in seen:
            if seen[bid] != fact:
                raise ValueError("conflicting duplicate bill")
            continue
        seen[bid] = fact
        stamp = fact.get("ts")
        if type(stamp) is not int or not report["window_start_ms"] <= stamp <= cutoff:
            raise ValueError("bill outside proven window")
        if stamp < start:
            continue
        if stamp == start:
            if (fact.get("timing_evidence_id") != basis.evidence_id
                    or fact.get("timing_verified") not in ("prior_to_baseline", "after_baseline")):
                ambiguous = True
                continue
            if fact["timing_verified"] == "prior_to_baseline":
                continue
        selected.append(fact)
    # Actual unsupported activity remains blocking even before the period.
    _, all_unknown, forbidden = okx_readonly.classify_bill_flows(seen.values(), classifications)
    flows, unknown, _ = okx_readonly.classify_bill_flows(selected, classifications)
    if all_unknown:
        issues.add("unknown_external_flow")
    if forbidden:
        issues.add("unsupported_account_activity")
    if ambiguous:
        issues.add("external_flow_unavailable")
    classification_id = okx_readonly.flow_classification_id(classifications)
    output.update(day_external_flow_usdt=None if ambiguous or unknown or forbidden else str(flows),
        day_flow_start_ms=start, day_flow_cutoff_ms=cutoff, day_unknown_flow_count=len(unknown),
        flow_classification_id=classification_id, risk_period_start_ms=start,
        risk_period_basis_id=basis.evidence_id, risk_period_label="風控期間損益",
        discrepancies=sorted(issues))
    ledger = gate.DayLedgerEvidence(basis.evidence.trading_day_start_ms, basis.equity,
        basis.evidence_id, flows, classification_id, len(unknown), cutoff, basis)
    output.pop("risk_period_summary", None)
    if not (ambiguous or all_unknown or forbidden):
        output["risk_period_summary"] = summary(basis, equity(output), ledger)
    return seal(output), ledger


def summary(basis, current_equity, ledger):
    risk.decimal(current_equity, "period current equity")
    if ledger.period_basis != basis:
        raise ValueError("period ledger mismatch")
    with localcontext(research._CONTEXT):
        pnl = current_equity - basis.equity - ledger.external_flow_usdt
        return dict(label="風控期間損益", start_ms=basis.evidence.observed_at_ms,
            basis_id=basis.evidence_id, baseline_equity_usdt=str(basis.equity),
            pnl_usdt=str(pnl), return_ratio=str(pnl / basis.equity), full_day=False)


async def durable_ledger(supervisor, report, classifications):
    """Missing first evidence is retryable; this provider never latches E1."""
    target = report.get("completed_ms")
    day = risk.taipei_day(target)
    basis = await supervisor.load_day_basis(day)
    if basis is None:
        return None
    return project(report, basis, classifications)
