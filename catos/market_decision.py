"""Deterministic read-model aggregation for the Yaozi decision surface.

The module only combines already-materialized public facts. It does not infer
unpublished Yaozi formulas, convert unavailable data to zero, or create trading
authority.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext

from catos import research


DIRECTION_DOMAINS = ("price", "derivatives", "capital_flow")
_BULLISH = "bullish"
_BEARISH = "bearish"
_NO_DIRECTION = "no_direction"
_UNAVAILABLE = "unavailable"
_CONFLICT = "conflict"


def _decimal(value):
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _decimal_text(value):
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _ratio_text(numerator, denominator, *, places="0.0001"):
    if not denominator:
        return None
    with localcontext(research._CONTEXT):
        value = Decimal(numerator) / Decimal(denominator)
        return _decimal_text(value.quantize(Decimal(places)))


def _confidence_text(coverage, agreement):
    with localcontext(research._CONTEXT):
        value = coverage * agreement * Decimal("100")
        return _decimal_text(value.quantize(Decimal("0.01")))


def _signed_direction(value):
    parsed = _decimal(value)
    if parsed is None:
        return _UNAVAILABLE
    if parsed > 0:
        return _BULLISH
    if parsed < 0:
        return _BEARISH
    return _NO_DIRECTION


def _signal(axis, direction, *, observed_at_ms, facts, refs):
    return {
        "axis": axis,
        "direction": direction,
        "observed_at_ms": observed_at_ms,
        "facts": facts,
        "evidence_refs": refs,
    }


def _combine_symbol_signals(symbol, signals):
    available = [item for item in signals if item["direction"] != _UNAVAILABLE]
    directional = [item["direction"] for item in available
                   if item["direction"] in (_BULLISH, _BEARISH)]
    if not available:
        status = _UNAVAILABLE
    elif _BULLISH in directional and _BEARISH in directional:
        status = _CONFLICT
    elif _BULLISH in directional:
        status = _BULLISH
    elif _BEARISH in directional:
        status = _BEARISH
    else:
        status = _NO_DIRECTION
    return {
        "symbol": symbol,
        "status": status,
        "available_axis_count": len(available),
        "signals": signals,
    }


def _price_assessment(symbol, market):
    if market is None:
        return _combine_symbol_signals(symbol, [])
    observed_at_ms = market["observed_at_ms"]
    ref = {
        "surface": f"/intel/picks/{symbol}",
        "table": "market_snapshot",
        "observed_at_ms": observed_at_ms,
    }
    signals = []
    for axis, field in (("price_change_1h", "change_1h_text"),
                        ("price_change_24h", "change_24h_text")):
        value = market.get(field)
        signals.append(_signal(
            axis, _signed_direction(value), observed_at_ms=observed_at_ms,
            facts={field: value}, refs=[ref],
        ))
    return _combine_symbol_signals(symbol, signals)


def _derivative_assessment(symbol, derivative, market):
    if derivative is None:
        return _combine_symbol_signals(symbol, [])
    observed_at_ms = derivative["observed_at_ms"]
    derivative_ref = {
        "surface": f"/intel/picks/{symbol}",
        "table": "derivative_snapshot",
        "observed_at_ms": observed_at_ms,
    }
    taker = _decimal(derivative.get("taker_buy_ratio_text"))
    if taker is None:
        taker_direction = _UNAVAILABLE
    elif taker > Decimal("0.5"):
        taker_direction = _BULLISH
    elif taker < Decimal("0.5"):
        taker_direction = _BEARISH
    else:
        taker_direction = _NO_DIRECTION
    signals = [_signal(
        "taker_buy_ratio", taker_direction, observed_at_ms=observed_at_ms,
        facts={"taker_buy_ratio_text": derivative.get("taker_buy_ratio_text"),
               "neutral_point": "0.5"}, refs=[derivative_ref],
    )]

    oi_delta = _decimal(derivative.get("oi_delta_1h_text"))
    price_change = None if market is None else _decimal(market.get("change_1h_text"))
    if oi_delta is None or price_change is None:
        oi_price_direction = _UNAVAILABLE
        reason = "missing_oi_or_price_change"
    elif oi_delta <= 0 or price_change == 0:
        oi_price_direction = _NO_DIRECTION
        reason = "oi_not_expanding_or_price_flat"
    else:
        oi_price_direction = _BULLISH if price_change > 0 else _BEARISH
        reason = "oi_expanding_with_price_direction"
    refs = [derivative_ref]
    if market is not None:
        refs.append({
            "surface": f"/intel/picks/{symbol}",
            "table": "market_snapshot",
            "observed_at_ms": market["observed_at_ms"],
        })
    signals.append(_signal(
        "oi_x_price_1h", oi_price_direction, observed_at_ms=observed_at_ms,
        facts={
            "oi_delta_1h_text": derivative.get("oi_delta_1h_text"),
            "price_change_1h_text": None if market is None else market.get("change_1h_text"),
            "reason": reason,
        },
        refs=refs,
    ))
    return _combine_symbol_signals(symbol, signals)


def _capital_flow_assessment(symbol, flow, events):
    signals = []
    if flow is not None:
        complete = flow.get("trade_window_complete") == 1
        cvd = flow.get("cvd_quote_text")
        direction = _signed_direction(cvd) if complete else _UNAVAILABLE
        signals.append(_signal(
            "cex_cvd", direction, observed_at_ms=flow["observed_at_ms"],
            facts={
                "cvd_quote_text": cvd,
                "trade_window_complete": bool(complete),
            },
            refs=[{
                "surface": f"/intel/picks/{symbol}/money-flow",
                "table": "flow_snapshot",
                "observed_at_ms": flow["observed_at_ms"],
            }],
        ))
    for event in events:
        event_type = event.get("event_type")
        direction = _BULLISH if event_type == "inflow" else _BEARISH
        signals.append(_signal(
            "verified_dex_flow", direction, observed_at_ms=event["observed_at_ms"],
            facts={
                "event_type": event_type,
                "score_text": event.get("score_text"),
                "evidence": event.get("evidence_json"),
            },
            refs=[{
                "surface": f"/intel/capital-flow/{symbol}",
                "table": "capital_flow_event",
                "event_id": event.get("event_id"),
                "observed_at_ms": event["observed_at_ms"],
            }],
        ))
    return _combine_symbol_signals(symbol, signals)


def _domain_summary(name, items):
    counts = {_BULLISH: 0, _BEARISH: 0, _CONFLICT: 0, _NO_DIRECTION: 0, _UNAVAILABLE: 0}
    for item in items:
        counts[item["status"]] += 1
    available = len(items) - counts[_UNAVAILABLE]
    if available == 0:
        direction = _UNAVAILABLE
    elif counts[_BULLISH] > counts[_BEARISH]:
        direction = _BULLISH
    elif counts[_BEARISH] > counts[_BULLISH]:
        direction = _BEARISH
    else:
        direction = _NO_DIRECTION
    return {
        "domain": name,
        "direction": direction,
        "symbol_count": len(items),
        "available_symbol_count": available,
        "bullish_count": counts[_BULLISH],
        "bearish_count": counts[_BEARISH],
        "conflict_count": counts[_CONFLICT],
        "no_direction_count": counts[_NO_DIRECTION],
        "unavailable_count": counts[_UNAVAILABLE],
        "agreement_ratio_text": _ratio_text(
            max(counts[_BULLISH], counts[_BEARISH]), available),
        "items": items,
    }


def _source_domain_status(items, names, *, materialized_fallback=False):
    matched = [item for item in items if item.get("domain") in names]
    if not matched:
        return "materialized" if materialized_fallback else _UNAVAILABLE
    statuses = {item.get("status") for item in matched}
    if any(item.get("issues") for item in matched):
        return "partial"
    if statuses <= {"ok", "snapshot_materialized", "no_recorded_issues"}:
        return "materialized"
    if statuses <= {"empty"}:
        return _UNAVAILABLE
    return "partial"


def _latest_observed(items):
    values = [item.get("observed_at_ms") for item in items
              if type(item.get("observed_at_ms")) is int]
    return max(values) if values else None


def _rank_views(view_rows, view_name, states, limit):
    rows = [row for row in view_rows
            if row.get("view_name") == view_name and row.get("state") in states]

    def key(row):
        score = _decimal(row.get("score_text"))
        return (Decimal("-Infinity") if score is None else score,
                row.get("observed_at_ms") or 0, row.get("symbol") or "")

    rows.sort(key=key, reverse=True)
    result = []
    for rank, row in enumerate(rows[:limit], 1):
        result.append({
            "rank": rank,
            "symbol": row["symbol"],
            "state": row["state"],
            "score_text": row.get("score_text"),
            "observed_at_ms": row["observed_at_ms"],
            "evidence": row.get("evidence_json"),
            "evidence_refs": [{
                "surface": f'/intel/picks?view={view_name}',
                "table": "view_state",
                "view_name": view_name,
                "observed_at_ms": row["observed_at_ms"],
            }],
        })
    return result


def _watchlist(domain_items, view_rows, limit):
    by_symbol = {}
    for domain, items in domain_items.items():
        for item in items:
            slot = by_symbol.setdefault(item["symbol"], {
                "domain_status": {}, "conflict_count": 0,
            })
            slot["domain_status"][domain] = item["status"]
            if item["status"] == _CONFLICT:
                slot["conflict_count"] += 1
    for row in view_rows:
        slot = by_symbol.setdefault(row["symbol"], {"domain_status": {}, "conflict_count": 0})
        slot[row["view_name"]] = row

    ranked = []
    for symbol, facts in by_symbol.items():
        risk = facts.get("risk")
        opportunity = facts.get("opportunity")
        reasons = []
        if risk is not None and risk.get("state") == "high_risk":
            priority = 1
            reasons.append("high_risk")
        elif opportunity is not None and opportunity.get("state") == "active":
            priority = 2
            reasons.append("active_opportunity")
        elif facts["conflict_count"]:
            priority = 3
            reasons.append("direction_conflict")
        elif risk is not None and risk.get("state") in {"watch", "cooling"}:
            priority = 4
            reasons.append(f'risk_{risk.get("state")}')
        else:
            directions = [value for value in facts["domain_status"].values()
                          if value in (_BULLISH, _BEARISH)]
            if len(directions) < 2 or len(set(directions)) != 1:
                continue
            priority = 5
            reasons.append(f'multi_domain_{directions[0]}')
        score_candidates = [
            _decimal(None if risk is None else risk.get("score_text")),
            _decimal(None if opportunity is None else opportunity.get("score_text")),
        ]
        score = max((value for value in score_candidates if value is not None),
                    default=Decimal("-Infinity"))
        ranked.append((priority, -score if score.is_finite() else Decimal("Infinity"), symbol, {
            "symbol": symbol,
            "priority_level": priority,
            "priority_reasons": reasons,
            "direction_domains": facts["domain_status"],
            "risk": None if risk is None else {
                "state": risk.get("state"), "score_text": risk.get("score_text"),
                "observed_at_ms": risk.get("observed_at_ms"),
            },
            "opportunity": None if opportunity is None else {
                "state": opportunity.get("state"), "score_text": opportunity.get("score_text"),
                "observed_at_ms": opportunity.get("observed_at_ms"),
            },
        }))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    result = []
    for rank, (_, _, _, item) in enumerate(ranked[:limit], 1):
        item["rank"] = rank
        result.append(item)
    return result


def build_decision_surface(*, market_rows, derivative_rows, flow_rows,
                           capital_flow_rows, view_rows, source_coverage, limit=20):
    """Build the v0.2 decision surface from persisted facts only."""
    market_by_symbol = {row["symbol"]: row for row in market_rows}
    derivative_by_symbol = {row["symbol"]: row for row in derivative_rows}
    flow_by_symbol = {row["symbol"]: row for row in flow_rows}
    events_by_symbol = {}
    for row in capital_flow_rows:
        events_by_symbol.setdefault(row["symbol"], []).append(row)
    symbols = sorted(set(market_by_symbol) | set(derivative_by_symbol)
                     | set(flow_by_symbol) | set(events_by_symbol))

    domain_items = {
        "price": [_price_assessment(symbol, market_by_symbol.get(symbol)) for symbol in symbols],
        "derivatives": [
            _derivative_assessment(symbol, derivative_by_symbol.get(symbol), market_by_symbol.get(symbol))
            for symbol in symbols
        ],
        "capital_flow": [
            _capital_flow_assessment(
                symbol, flow_by_symbol.get(symbol), events_by_symbol.get(symbol, ()))
            for symbol in symbols
        ],
    }
    domains = {name: _domain_summary(name, domain_items[name]) for name in DIRECTION_DOMAINS}
    available_domains = [item for item in domains.values() if item["direction"] != _UNAVAILABLE]
    bullish_domains = [item for item in available_domains if item["direction"] == _BULLISH]
    bearish_domains = [item for item in available_domains if item["direction"] == _BEARISH]
    majority_count = max(len(bullish_domains), len(bearish_domains))
    if len(available_domains) < 2:
        direction = _UNAVAILABLE
    elif majority_count < 2 or len(bullish_domains) == len(bearish_domains):
        direction = _NO_DIRECTION
    else:
        direction = _BULLISH if len(bullish_domains) > len(bearish_domains) else _BEARISH

    coverage_ratio = Decimal(len(available_domains)) / Decimal(len(DIRECTION_DOMAINS))
    agreement_ratio = (Decimal(0) if not available_domains else
                       Decimal(majority_count) / Decimal(len(available_domains)))
    confidence = {
        "score_text": _confidence_text(coverage_ratio, agreement_ratio),
        "coverage_ratio_text": _decimal_text(coverage_ratio.quantize(Decimal("0.0001"))),
        "agreement_ratio_text": _decimal_text(agreement_ratio.quantize(Decimal("0.0001"))),
        "available_direction_domains": len(available_domains),
        "configured_direction_domains": len(DIRECTION_DOMAINS),
        "contract": "direction_domain_coverage_x_agreement_v1",
    }

    price = domains["price"]
    price_directional = price["bullish_count"] + price["bearish_count"]
    matching_price = price["bullish_count"] if direction == _BULLISH else price["bearish_count"]
    breadth_ratio_text = _ratio_text(matching_price, price_directional)
    if direction == _UNAVAILABLE:
        regime = "undetermined"
    elif direction == _NO_DIRECTION:
        regime = ("fragmented" if bullish_domains and bearish_domains else "range_or_weak_signal")
    elif price_directional >= 3 and breadth_ratio_text is not None and Decimal(breadth_ratio_text) >= Decimal("0.6"):
        regime = f"broad_{direction}"
    else:
        regime = f"selective_{direction}"

    evidence_for = []
    evidence_against = []
    if direction in (_BULLISH, _BEARISH):
        opposite = _BEARISH if direction == _BULLISH else _BULLISH
        for summary in domains.values():
            compact = {key: summary[key] for key in (
                "domain", "direction", "available_symbol_count", "bullish_count",
                "bearish_count", "conflict_count", "agreement_ratio_text")}
            if summary["direction"] == direction:
                evidence_for.append(compact)
            elif summary["direction"] == opposite:
                evidence_against.append(compact)

    conflicts = []
    if bullish_domains and bearish_domains:
        conflicts.append({
            "type": "cross_domain_disagreement",
            "bullish_domains": [item["domain"] for item in bullish_domains],
            "bearish_domains": [item["domain"] for item in bearish_domains],
        })
    for summary in domains.values():
        if summary["conflict_count"]:
            conflicts.append({
                "type": "within_domain_symbol_conflict",
                "domain": summary["domain"],
                "conflict_count": summary["conflict_count"],
            })

    coverage_items = list(source_coverage.get("items") or ())
    source_domains = {
        "spot": _source_domain_status(
            coverage_items, {"market_collector", "market_venue"},
            materialized_fallback=domains["price"]["available_symbol_count"] > 0),
        "perp": _source_domain_status(
            coverage_items, {"derivative_venue"},
            materialized_fallback=domains["derivatives"]["available_symbol_count"] > 0),
        "capital_flow": _source_domain_status(
            coverage_items, {"dex", "hyperliquid"},
            materialized_fallback=domains["capital_flow"]["available_symbol_count"] > 0),
        "options": _source_domain_status(coverage_items, {"options"}),
        "onchain": _source_domain_status(coverage_items, {"onchain"}),
        "liquidity": _source_domain_status(coverage_items, {"liquidity"}),
        "social": _source_domain_status(coverage_items, {"social"}),
        "narrative": _source_domain_status(coverage_items, {"public_context"}),
    }
    freshness_by_domain = {}
    for name in source_domains:
        names = {
            "spot": {"market_collector", "market_venue"},
            "perp": {"derivative_venue"},
            "capital_flow": {"dex", "hyperliquid"},
            "options": {"options"},
            "onchain": {"onchain"},
            "liquidity": {"liquidity"},
            "social": {"social"},
            "narrative": {"public_context"},
        }[name]
        freshness_by_domain[name] = _latest_observed(
            [item for item in coverage_items if item.get("domain") in names])
    raw_latest = [_latest_observed(rows) for rows in (
        market_rows, derivative_rows, flow_rows, capital_flow_rows, view_rows)]
    latest_materialized = max((value for value in raw_latest if value is not None), default=None)
    direction_domain_observed_at_ms = {}
    for name, items in domain_items.items():
        timestamps = [
            signal.get("observed_at_ms")
            for item in items if item["status"] != _UNAVAILABLE
            for signal in item["signals"]
            if type(signal.get("observed_at_ms")) is int
        ]
        direction_domain_observed_at_ms[name] = max(timestamps) if timestamps else None
    direction_domain_times = [
        value for value in direction_domain_observed_at_ms.values()
        if value is not None
    ]
    direction_evidence_span_ms = (
        max(direction_domain_times) - min(direction_domain_times)
        if len(direction_domain_times) >= 2 else None
    )

    unavailable = [
        {"capability": "dealer_direction", "reason": "private_formula_unknown_unpublished"},
        {"capability": "options_direction", "reason": "signed_gex_and_dealer_sign_unknown_unpublished"},
        {"capability": "onchain_direction", "reason": "current_contract_is_activity_anomaly_not_direction"},
        {"capability": "liquidity_direction", "reason": "current_contract_is_depth_description_only"},
        {"capability": "social_direction", "reason": "raw_counts_only_private_heat_unknown_unpublished"},
        {"capability": "wall_clock_freshness", "reason": "freshness_policy_not_defined"},
    ]
    for name, summary in domains.items():
        if summary["direction"] == _UNAVAILABLE:
            unavailable.append({"capability": f"direction_domain:{name}", "reason": "no_materialized_direction_evidence"})

    top_opportunities = _rank_views(view_rows, "opportunity", {"active"}, limit)
    top_risks = _rank_views(view_rows, "risk", {"high_risk", "watch", "cooling"}, limit)

    return {
        "surface": "decision_surface",
        "contract_version": "catos-decision-surface-v0.2",
        "status": "materialized" if symbols else "materialized_empty",
        "market_regime": regime,
        "direction": direction,
        "confidence": confidence,
        "evidence_for": evidence_for,
        "evidence_against": evidence_against,
        "conflicts": conflicts,
        "freshness": {
            "status": "not_evaluated_no_wall_clock_policy",
            "latest_materialized_at_ms": latest_materialized,
            "by_domain": freshness_by_domain,
            "timing_contract": "catos-decision-timing-diagnostics-v0.5",
            "time_alignment_status": "not_evaluated_no_skew_policy",
            "by_direction_domain_observed_at_ms": direction_domain_observed_at_ms,
            "direction_evidence_domain_count": len(direction_domain_times),
            "oldest_direction_evidence_at_ms": (
                min(direction_domain_times) if direction_domain_times else None
            ),
            "latest_direction_evidence_at_ms": (
                max(direction_domain_times) if direction_domain_times else None
            ),
            "direction_evidence_span_ms": direction_evidence_span_ms,
        },
        "data_quality": {
            "direction_domains": {name: {
                "direction": summary["direction"],
                "available_symbol_count": summary["available_symbol_count"],
                "unavailable_count": summary["unavailable_count"],
                "conflict_count": summary["conflict_count"],
            } for name, summary in domains.items()},
            "source_domains": source_domains,
            "source_run_item_count": len(coverage_items),
            "source_run_issue_item_count": sum(bool(item.get("issues")) for item in coverage_items),
            "live_equivalence_status": source_coverage.get("live_equivalence_status"),
        },
        "breadth": {
            "price_directional_symbol_count": price_directional,
            "matching_direction_symbol_count": matching_price if direction in (_BULLISH, _BEARISH) else 0,
            "matching_ratio_text": breadth_ratio_text if direction in (_BULLISH, _BEARISH) else None,
            "broad_threshold_ratio_text": "0.6",
            "broad_minimum_symbol_count": 3,
        },
        "top_opportunities": top_opportunities,
        "top_risks": top_risks,
        "watchlist": {
            "ranking_contract": "risk_then_opportunity_then_conflict_then_multi_domain_v1",
            "items": _watchlist(domain_items, view_rows, limit),
        },
        "domains": domains,
        "unavailable": unavailable,
        "private_formula_status": "not_inferred",
        "trading_authority": False,
    }


def build_symbol_decision(decision_surface, symbol):
    """Project the market decision surface into one traceable symbol decision."""
    domain_items = {}
    for name in DIRECTION_DOMAINS:
        summary = (decision_surface.get("domains") or {}).get(name) or {}
        item = next(
            (row for row in summary.get("items") or () if row.get("symbol") == symbol),
            None,
        )
        domain_items[name] = item or {
            "symbol": symbol,
            "status": _UNAVAILABLE,
            "available_axis_count": 0,
            "signals": [],
        }

    available = [
        (name, item) for name, item in domain_items.items()
        if item["status"] != _UNAVAILABLE
    ]
    bullish = [name for name, item in available if item["status"] == _BULLISH]
    bearish = [name for name, item in available if item["status"] == _BEARISH]
    majority_count = max(len(bullish), len(bearish))
    if len(available) < 2:
        direction = _UNAVAILABLE
    elif majority_count < 2 or len(bullish) == len(bearish):
        direction = _NO_DIRECTION
    else:
        direction = _BULLISH if len(bullish) > len(bearish) else _BEARISH

    coverage_ratio = Decimal(len(available)) / Decimal(len(DIRECTION_DOMAINS))
    agreement_ratio = (Decimal(0) if not available else
                       Decimal(majority_count) / Decimal(len(available)))
    confidence = {
        "score_text": _confidence_text(coverage_ratio, agreement_ratio),
        "coverage_ratio_text": _decimal_text(coverage_ratio.quantize(Decimal("0.0001"))),
        "agreement_ratio_text": _decimal_text(agreement_ratio.quantize(Decimal("0.0001"))),
        "available_direction_domains": len(available),
        "configured_direction_domains": len(DIRECTION_DOMAINS),
        "contract": "direction_domain_coverage_x_agreement_v1",
    }

    opposite = _BEARISH if direction == _BULLISH else _BULLISH
    evidence_for = []
    evidence_against = []
    if direction in (_BULLISH, _BEARISH):
        for name, item in domain_items.items():
            compact = {
                "domain": name,
                "status": item["status"],
                "available_axis_count": item["available_axis_count"],
                "signals": item["signals"],
            }
            if item["status"] == direction:
                evidence_for.append(compact)
            elif item["status"] == opposite:
                evidence_against.append(compact)

    conflicts = []
    if bullish and bearish:
        conflicts.append({
            "type": "cross_domain_disagreement",
            "bullish_domains": bullish,
            "bearish_domains": bearish,
        })
    for name, item in domain_items.items():
        if item["status"] == _CONFLICT:
            conflicts.append({
                "type": "within_symbol_domain_conflict",
                "domain": name,
                "signals": item["signals"],
            })

    def ranked_item(name):
        return next(
            (row for row in decision_surface.get(name) or () if row.get("symbol") == symbol),
            None,
        )

    watch = next(
        (row for row in ((decision_surface.get("watchlist") or {}).get("items") or ())
         if row.get("symbol") == symbol),
        None,
    )
    opportunity = ranked_item("top_opportunities")
    risk = ranked_item("top_risks")

    observed = []
    domain_observed_at_ms = {}
    for name, item in domain_items.items():
        timestamps = [
            signal.get("observed_at_ms") for signal in item["signals"]
            if type(signal.get("observed_at_ms")) is int
        ]
        domain_observed_at_ms[name] = max(timestamps) if timestamps else None
        observed.extend(timestamps)
    for item in (opportunity, risk):
        if item is not None and type(item.get("observed_at_ms")) is int:
            observed.append(item["observed_at_ms"])
    latest_materialized = max(observed) if observed else None
    direction_domain_times = [
        domain_observed_at_ms[name]
        for name, item in domain_items.items()
        if item["status"] != _UNAVAILABLE and domain_observed_at_ms[name] is not None
    ]
    direction_evidence_span_ms = (
        max(direction_domain_times) - min(direction_domain_times)
        if len(direction_domain_times) >= 2 else None
    )

    market_direction = decision_surface.get("direction")
    if direction in (_BULLISH, _BEARISH) and market_direction in (_BULLISH, _BEARISH):
        market_alignment = "aligned" if direction == market_direction else "opposed"
    else:
        market_alignment = "not_evaluated"

    return {
        "surface": "symbol_decision",
        "contract_version": "catos-symbol-decision-v0.3",
        "status": "materialized" if available or opportunity or risk or watch else "materialized_empty",
        "symbol": symbol,
        "direction": direction,
        "confidence": confidence,
        "evidence_for": evidence_for,
        "evidence_against": evidence_against,
        "conflicts": conflicts,
        "domains": domain_items,
        "actionability": {
            "top_opportunity": opportunity,
            "top_risk": risk,
            "watchlist": watch,
        },
        "market_context": {
            "direction": market_direction,
            "market_regime": decision_surface.get("market_regime"),
            "alignment": market_alignment,
        },
        "freshness": {
            "status": (decision_surface.get("freshness") or {}).get("status"),
            "latest_materialized_at_ms": latest_materialized,
            "timing_contract": "catos-decision-timing-diagnostics-v0.5",
            "time_alignment_status": "not_evaluated_no_skew_policy",
            "by_domain_observed_at_ms": domain_observed_at_ms,
            "direction_evidence_domain_count": len(direction_domain_times),
            "oldest_direction_evidence_at_ms": (
                min(direction_domain_times) if direction_domain_times else None
            ),
            "latest_direction_evidence_at_ms": (
                max(direction_domain_times) if direction_domain_times else None
            ),
            "direction_evidence_span_ms": direction_evidence_span_ms,
        },
        "private_formula_status": "not_inferred",
        "trading_authority": False,
    }


def build_decision_compare(decision_surface, limit=20):
    """Project the existing watchlist rank into a side-by-side comparison surface."""
    watchlist = decision_surface.get("watchlist") or {}
    watch_items = list(watchlist.get("items") or ())[:limit]
    items = []
    for watch in watch_items:
        symbol = watch["symbol"]
        symbol_decision = build_symbol_decision(decision_surface, symbol)
        actionability = symbol_decision["actionability"]
        items.append({
            "watch_rank": watch.get("rank"),
            "symbol": symbol,
            "priority_level": watch.get("priority_level"),
            "priority_reasons": watch.get("priority_reasons") or [],
            "direction": symbol_decision["direction"],
            "confidence": symbol_decision["confidence"],
            "domains": {
                name: symbol_decision["domains"][name]["status"]
                for name in DIRECTION_DOMAINS
            },
            "conflicts": symbol_decision["conflicts"],
            "opportunity": actionability["top_opportunity"],
            "risk": actionability["top_risk"],
            "market_alignment": symbol_decision["market_context"]["alignment"],
            "latest_materialized_at_ms": symbol_decision["freshness"]["latest_materialized_at_ms"],
            "direction_evidence_span_ms": symbol_decision["freshness"]["direction_evidence_span_ms"],
        })

    return {
        "surface": "decision_compare",
        "contract_version": "catos-decision-compare-v0.4",
        "status": "materialized" if items else "materialized_empty",
        "ordering_contract": watchlist.get("ranking_contract"),
        "ordering_source": "decision_surface.watchlist.items",
        "comparison_score": None,
        "items": items,
        "market_context": {
            "direction": decision_surface.get("direction"),
            "market_regime": decision_surface.get("market_regime"),
        },
        "freshness": {
            "status": (decision_surface.get("freshness") or {}).get("status"),
            "timing_contract": "catos-decision-timing-diagnostics-v0.5",
            "time_alignment_status": "not_evaluated_no_skew_policy",
        },
        "private_formula_status": "not_inferred",
        "trading_authority": False,
    }
