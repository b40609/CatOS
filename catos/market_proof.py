"""Pure P0-E cycle, push-freeze and 24h proof contracts.

Unknown Yaozi cycle-entry gates are deliberately not inferred here. A caller
must provide an explicit cycle directive. All prices and derived percentages
use Decimal; timestamps are caller supplied so replay is deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext
import hashlib

from catos import ipc, research


PROOF_VERSION = "yaozi-p0e-v1"
HORIZON_24H = "24h"
HORIZON_24H_MS = 86_400_000

HISTORY_FLAT_RULE_CHANGE_DATE = date(2026, 5, 8)
HISTORY_FLAT_RULE_PRE = "yaozi-history-flat-pre-2026-05-08-v1"
HISTORY_FLAT_RULE_POST = "yaozi-history-flat-from-2026-05-08-v1"

CYCLE_START = "START"
CYCLE_NONE = "NONE"
CYCLE_OBSERVE = "OBSERVE"
CYCLE_PUSH = "PUSH"
CYCLE_END = "END"


@dataclass(frozen=True, slots=True)
class HistoryFlatRule:
    version: str
    threshold_pct: Decimal
    effective_from: date | None
    effective_until: date | None


def history_flat_rule_versions() -> tuple[HistoryFlatRule, HistoryFlatRule]:
    return (
        HistoryFlatRule(
            HISTORY_FLAT_RULE_PRE,
            Decimal("3"),
            None,
            date(2026, 5, 7),
        ),
        HistoryFlatRule(
            HISTORY_FLAT_RULE_POST,
            Decimal("1"),
            HISTORY_FLAT_RULE_CHANGE_DATE,
            None,
        ),
    )


def history_flat_rule_for_date(history_date: date) -> HistoryFlatRule:
    """Return the published History flat-threshold version for an explicit source date.

    The public spec confirms the date boundary but does not state which timezone
    should be used to derive that date from an epoch timestamp. Callers must
    therefore supply the already-normalized source date instead of this module
    silently assuming UTC or a local timezone.
    """
    if type(history_date) is not date:
        raise ValueError("invalid_history_date")
    before, after = history_flat_rule_versions()
    return before if history_date < HISTORY_FLAT_RULE_CHANGE_DATE else after


def _decimal(value, name, *, required=False, positive=False):
    if value is None:
        if required:
            raise ValueError(f"missing_{name}")
        return None
    if not isinstance(value, Decimal):
        raise ValueError(f"invalid_{name}")
    try:
        ipc.decimal_text(str(value), name, derived=True)
    except ipc.ProtocolError:
        raise ValueError(f"invalid_{name}") from None
    if positive and value <= 0:
        raise ValueError(f"invalid_{name}")
    return value


def _symbol(value):
    if type(value) is not str or not value.endswith("-USDT-SWAP"):
        raise ValueError("invalid_symbol")
    return value


def _token(value, name):
    if type(value) is not str or not value:
        raise ValueError(f"invalid_{name}")
    return value


def _pct(price, reference):
    with localcontext(research._CONTEXT):
        return (price - reference) * Decimal("100") / reference


@dataclass(frozen=True, slots=True)
class CycleState:
    cycle_id: str
    symbol: str
    started_at_ms: int
    first_push_price: Decimal
    latest_push_at_ms: int
    push_count: int
    peak_price: Decimal
    trough_price: Decimal
    mfe_pct: Decimal
    mae_pct: Decimal
    ended_at_ms: int | None = None
    end_reason: str | None = None

    def __post_init__(self):
        _token(self.cycle_id, "cycle_id")
        _symbol(self.symbol)
        ipc.integer(self.started_at_ms, "started_at_ms")
        ipc.integer(self.latest_push_at_ms, "latest_push_at_ms")
        if self.ended_at_ms is not None:
            ipc.integer(self.ended_at_ms, "ended_at_ms")
        for name in ("first_push_price", "peak_price", "trough_price"):
            _decimal(getattr(self, name), name, required=True, positive=True)
        _decimal(self.mfe_pct, "mfe_pct", required=True)
        _decimal(self.mae_pct, "mae_pct", required=True)
        if type(self.push_count) is not int or self.push_count < 1:
            raise ValueError("invalid_push_count")
        if self.peak_price < self.trough_price:
            raise ValueError("invalid_cycle_range")
        if (self.ended_at_ms is None) != (self.end_reason is None):
            raise ValueError("invalid_cycle_terminal_state")

    @property
    def active(self):
        return self.ended_at_ms is None


@dataclass(frozen=True, slots=True)
class CycleDirective:
    action: str
    push_type: str | None = None
    view_name: str | None = None
    end_reason: str | None = None

    def __post_init__(self):
        if self.action not in (CYCLE_NONE, CYCLE_START, CYCLE_OBSERVE, CYCLE_PUSH, CYCLE_END):
            raise ValueError("invalid_cycle_action")
        if self.push_type is not None:
            _token(self.push_type, "push_type")
        if self.view_name is not None:
            _token(self.view_name, "view_name")
        if self.end_reason is not None:
            _token(self.end_reason, "end_reason")
        if self.action in (CYCLE_START, CYCLE_PUSH) and self.push_type is None:
            raise ValueError("push_type_required")
        if self.action == CYCLE_END and self.end_reason is None:
            raise ValueError("end_reason_required")
        if self.action != CYCLE_END and self.end_reason is not None:
            raise ValueError("unexpected_end_reason")


@dataclass(frozen=True, slots=True)
class CycleEvent:
    event_id: str
    cycle_id: str
    symbol: str
    observed_at_ms: int
    event_type: str
    view_name: str | None
    payload: tuple[tuple[str, object], ...]


@dataclass(frozen=True, slots=True)
class CycleTransition:
    before: CycleState | None
    after: CycleState | None
    event: CycleEvent | None


def _cycle_id(symbol, observed_at_ms, push_type):
    raw = f"cycle:{symbol}:{observed_at_ms}:{push_type}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cycle_event(cycle, observed_at_ms, event_type, view_name, payload):
    raw = f"cycle-event:{cycle.cycle_id}:{observed_at_ms}:{event_type}:{view_name or ''}"
    return CycleEvent(
        hashlib.sha256(raw.encode("utf-8")).hexdigest(), cycle.cycle_id, cycle.symbol,
        observed_at_ms, event_type, view_name, tuple(sorted(payload.items())),
    )


def transition_cycle(previous: CycleState | None, *, symbol: str,
                     observed_at_ms: int, price: Decimal,
                     directive: CycleDirective) -> CycleTransition:
    """Apply one explicit cycle directive without guessing private entry gates."""
    _symbol(symbol)
    ipc.integer(observed_at_ms, "observed_at_ms")
    price = _decimal(price, "cycle_price", required=True, positive=True)
    if not isinstance(directive, CycleDirective):
        raise ValueError("invalid_cycle_directive")

    if directive.action == CYCLE_NONE and previous is None:
        return CycleTransition(None, None, None)

    if directive.action == CYCLE_START:
        if previous is not None and previous.active:
            raise ValueError("cycle_already_active")
        cycle = CycleState(
            _cycle_id(symbol, observed_at_ms, directive.push_type), symbol,
            observed_at_ms, price, observed_at_ms, 1, price, price,
            Decimal("0"), Decimal("0"),
        )
        event = _cycle_event(cycle, observed_at_ms, "cycle_started", directive.view_name,
                             {"push_type": directive.push_type, "price": price})
        return CycleTransition(previous, cycle, event)

    if previous is None or not previous.active:
        raise ValueError("active_cycle_required")
    if previous.symbol != symbol:
        raise ValueError("cycle_symbol_mismatch")
    if observed_at_ms < previous.started_at_ms:
        raise ValueError("cycle_time_regression")

    peak = max(previous.peak_price, price)
    trough = min(previous.trough_price, price)
    mfe = max(Decimal("0"), _pct(peak, previous.first_push_price))
    mae = min(Decimal("0"), _pct(trough, previous.first_push_price))
    if directive.action in (CYCLE_NONE, CYCLE_OBSERVE):
        cycle = CycleState(
            previous.cycle_id, symbol, previous.started_at_ms, previous.first_push_price,
            previous.latest_push_at_ms, previous.push_count, peak, trough, mfe, mae,
        )
        return CycleTransition(previous, cycle, None)
    if directive.action == CYCLE_PUSH:
        cycle = CycleState(
            previous.cycle_id, symbol, previous.started_at_ms, previous.first_push_price,
            observed_at_ms, previous.push_count + 1, peak, trough, mfe, mae,
        )
        event = _cycle_event(cycle, observed_at_ms, "cycle_push", directive.view_name,
                             {"push_type": directive.push_type, "price": price})
        return CycleTransition(previous, cycle, event)

    cycle = CycleState(
        previous.cycle_id, symbol, previous.started_at_ms, previous.first_push_price,
        previous.latest_push_at_ms, previous.push_count, peak, trough, mfe, mae,
        observed_at_ms, directive.end_reason,
    )
    event = _cycle_event(cycle, observed_at_ms, "cycle_ended", directive.view_name,
                         {"end_reason": directive.end_reason, "price": price})
    return CycleTransition(previous, cycle, event)


@dataclass(frozen=True, slots=True)
class FrozenPush:
    push_id: str
    symbol: str
    pushed_at_ms: int
    push_type: str
    cycle_id: str | None
    price: Decimal
    active_l2: tuple[str, ...]
    patterns: tuple[tuple[str, str], ...]
    smf: tuple[tuple[str, object], ...]
    views: tuple[tuple[str, object], ...]
    feature_version: str
    signal_version: str
    source_freshness: tuple[tuple[str, object], ...]
    market_regime: tuple[tuple[str, object], ...]
    pre_entry_volatility: Decimal | None
    proof_version: str = PROOF_VERSION


def freeze_push_snapshot(*, symbol, pushed_at_ms, push_type, cycle_id, price,
                         active_l2, patterns, smf, views, feature_version,
                         signal_version, source_freshness, market_regime,
                         pre_entry_volatility) -> FrozenPush:
    """Freeze all evidence needed to evaluate a push later without survivor bias."""
    _symbol(symbol)
    ipc.integer(pushed_at_ms, "pushed_at_ms")
    _token(push_type, "push_type")
    if cycle_id is not None:
        _token(cycle_id, "cycle_id")
    price = _decimal(price, "push_price", required=True, positive=True)
    pre_entry_volatility = _decimal(pre_entry_volatility, "pre_entry_volatility")
    if type(active_l2) is not tuple or any(type(value) is not str or not value for value in active_l2):
        raise ValueError("invalid_active_l2")
    for name, value in (("patterns", patterns), ("smf", smf), ("views", views),
                        ("source_freshness", source_freshness), ("market_regime", market_regime)):
        if not isinstance(value, dict):
            raise ValueError(f"invalid_{name}")
    _token(feature_version, "feature_version")
    _token(signal_version, "signal_version")
    identity = f"push:{symbol}:{pushed_at_ms}:{push_type}:{cycle_id or ''}"
    return FrozenPush(
        hashlib.sha256(identity.encode("utf-8")).hexdigest(), symbol, pushed_at_ms,
        push_type, cycle_id, price, tuple(sorted(active_l2)), tuple(sorted(patterns.items())),
        tuple(sorted(smf.items())), tuple(sorted(views.items())), feature_version, signal_version,
        tuple(sorted(source_freshness.items())), tuple(sorted(market_regime.items())),
        pre_entry_volatility,
    )


@dataclass(frozen=True, slots=True)
class PricePoint:
    observed_at_ms: int
    price: Decimal

    def __post_init__(self):
        ipc.integer(self.observed_at_ms, "observed_at_ms")
        _decimal(self.price, "proof_price", required=True, positive=True)


@dataclass(frozen=True, slots=True)
class ProofResult:
    push_id: str
    horizon: str
    measured_at_ms: int
    return_pct: Decimal
    mfe_pct: Decimal
    mae_pct: Decimal
    market_baseline_pct: Decimal | None
    vol_matched_baseline_pct: Decimal | None


def evaluate_24h(*, push: FrozenPush, measured_at_ms: int, terminal_price: Decimal,
                 path: tuple[PricePoint, ...], market_baseline_pct=None,
                 vol_matched_baseline_pct=None) -> ProofResult:
    """Evaluate raw upside/downside excursion over the explicit 24h proof window."""
    if not isinstance(push, FrozenPush):
        raise ValueError("invalid_push")
    ipc.integer(measured_at_ms, "measured_at_ms")
    terminal_price = _decimal(terminal_price, "terminal_price", required=True, positive=True)
    market_baseline_pct = _decimal(market_baseline_pct, "market_baseline_pct")
    vol_matched_baseline_pct = _decimal(vol_matched_baseline_pct, "vol_matched_baseline_pct")
    target_ms = push.pushed_at_ms + HORIZON_24H_MS
    if measured_at_ms < target_ms:
        raise ValueError("proof_not_due")
    if type(path) is not tuple or not path:
        raise ValueError("proof_path_required")
    if any(not isinstance(point, PricePoint) for point in path):
        raise ValueError("invalid_proof_path")
    if any(point.observed_at_ms <= push.pushed_at_ms or point.observed_at_ms > target_ms for point in path):
        raise ValueError("proof_path_outside_window")
    if any(left.observed_at_ms >= right.observed_at_ms for left, right in zip(path, path[1:])):
        raise ValueError("proof_path_not_ordered")
    returns = tuple(_pct(point.price, push.price) for point in path)
    terminal_return = _pct(terminal_price, push.price)
    return ProofResult(
        push.push_id, HORIZON_24H, measured_at_ms, terminal_return,
        max((Decimal("0"), *returns)), min((Decimal("0"), *returns)),
        market_baseline_pct, vol_matched_baseline_pct,
    )
