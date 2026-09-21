"""Deterministic P0-E scan orchestration.

The caller owns timing and data acquisition. This module composes pure reducers,
commits market-intelligence evidence, then invokes notification as a downstream
side effect only after the commit succeeds.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from catos.market_lifecycle import ScanInputs, ScanState, ScanTransition, transition_scan
from catos.market_proof import (
    CYCLE_PUSH, CYCLE_START, CycleDirective, CycleState, CycleTransition, FrozenPush,
    freeze_push_snapshot, transition_cycle,
)


SCAN_INTERVAL_MS = 60_000


@dataclass(frozen=True, slots=True)
class ScanRun:
    lifecycle: ScanTransition
    cycle: CycleTransition
    push: FrozenPush | None
    next_scan_at_ms: int


@dataclass(frozen=True, slots=True)
class PushCandidate:
    push_type: str
    active_l2: tuple[str, ...]
    patterns: dict
    feature_version: str
    signal_version: str
    source_freshness: dict
    market_regime: dict
    pre_entry_volatility: Decimal | None = None


class MarketScanOrchestrator:
    def __init__(self, store, notifier=None):
        self.store = store
        self.notifier = notifier

    def run(self, *, previous_scan: ScanState, inputs: ScanInputs,
            previous_cycle: CycleState | None, price, cycle_directive: CycleDirective,
            push_candidate: PushCandidate | None = None) -> ScanRun:
        lifecycle = transition_scan(previous_scan, inputs)
        cycle = transition_cycle(
            previous_cycle, symbol=inputs.symbol, observed_at_ms=inputs.observed_at_ms,
            price=price, directive=cycle_directive,
        )
        if cycle_directive.action in (CYCLE_START, CYCLE_PUSH) and push_candidate is None:
            raise ValueError("cycle_push_snapshot_required")
        if push_candidate is not None and not isinstance(push_candidate, PushCandidate):
            raise ValueError("invalid_push_candidate")
        if (push_candidate is not None and cycle_directive.action in (CYCLE_START, CYCLE_PUSH)
                and push_candidate.push_type != cycle_directive.push_type):
            raise ValueError("push_type_mismatch")
        push = None
        if push_candidate is not None:
            smf = {
                "score": lifecycle.smf.score,
                "grade": lifecycle.smf.grade,
                "model_version": lifecycle.smf.model_version,
                "confidence": lifecycle.smf.confidence,
            }
            views = {
                item.view_name: {
                    "state": item.state,
                    "score": item.score,
                    "consecutive_count": item.consecutive_count,
                }
                for item in (lifecycle.flow, lifecycle.opportunity, lifecycle.risk)
            }
            push = freeze_push_snapshot(
                symbol=inputs.symbol, pushed_at_ms=inputs.observed_at_ms,
                push_type=push_candidate.push_type,
                cycle_id=None if cycle.after is None else cycle.after.cycle_id,
                price=price, active_l2=push_candidate.active_l2, patterns=push_candidate.patterns,
                smf=smf, views=views, feature_version=push_candidate.feature_version,
                signal_version=push_candidate.signal_version,
                source_freshness=push_candidate.source_freshness,
                market_regime=push_candidate.market_regime,
                pre_entry_volatility=push_candidate.pre_entry_volatility,
            )
        inserted = self.store.record_p0e_scan(lifecycle, cycle, push)
        if push is not None and inserted and self.notifier is not None:
            self.notifier(push)
        return ScanRun(lifecycle, cycle, push, inputs.observed_at_ms + SCAN_INTERVAL_MS)
