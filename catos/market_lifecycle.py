"""Pure P0-D lifecycle reducers for the Yaozi parity layer.

The module intentionally does not invent unpublished Yaozi scoring formulas.
SMF and Opportunity quality are caller-supplied contracts. Flow uses only the
published component coefficients. Missing inputs remain missing and never
become numeric zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext

from catos import ipc, research


LIFECYCLE_VERSION = "yaozi-p0d-v2"

TRUE = "TRUE"
FALSE = "FALSE"
MISSING_DATA = "MISSING_DATA"

FLOW = "flow"
OPPORTUNITY = "opportunity"
RISK = "risk"

INACTIVE = "inactive"
IGNITION = "ignition"
ACCUMULATION = "accumulation"
FLOW_FADED = "flow_faded"
OPPORTUNITY_ACTIVE = "active"
OPPORTUNITY_ENDED = "ended"
RISK_HIGH = "high_risk"
RISK_WATCH = "watch"
RISK_COOLING = "cooling"
RISK_RESOLVED = "risk_resolved"


def _decimal(value, name, *, required=False):
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
    return value


def _truth(value):
    if value is None:
        return MISSING_DATA
    return TRUE if value else FALSE


def _gte(value, threshold):
    return None if value is None else value >= threshold


def _lt(value, threshold):
    return None if value is None else value < threshold


def _between(value, lower, upper):
    return None if value is None else lower <= value < upper


def smf_grade(score: Decimal | None) -> str | None:
    """Map a supplied score using the existing local grade convention.

    Yaozi's rendered guide overlaps B/C at -20 and does not specify decimal
    rounding. Keeping -20 in B preserves local compatibility; it is not proof
    of Yaozi boundary equivalence. See docs/yaozi-v1.11-handoff.md.
    """
    score = _decimal(score, "smf_score")
    if score is None:
        return None
    if not Decimal("-100") <= score <= Decimal("100"):
        raise ValueError("smf_score_out_of_range")
    if score >= Decimal("50"):
        return "S"
    if score >= Decimal("20"):
        return "A"
    if score >= Decimal("-20"):
        return "B"
    if score > Decimal("-50"):
        return "C"
    return "D"


@dataclass(frozen=True, slots=True)
class SmfSnapshot:
    symbol: str
    observed_at_ms: int
    score: Decimal | None
    grade: str | None
    model_version: str
    components: tuple[tuple[str, object], ...] | None = None
    confidence: Decimal | None = None


def make_smf_snapshot(*, symbol, observed_at_ms, score, model_version,
                      components=None, confidence=None) -> SmfSnapshot:
    if type(symbol) is not str or not symbol.endswith("-USDT-SWAP"):
        raise ValueError("invalid_symbol")
    ipc.integer(observed_at_ms, "observed_at_ms")
    if type(model_version) is not str or not model_version:
        raise ValueError("invalid_smf_model_version")
    score = _decimal(score, "smf_score")
    confidence = _decimal(confidence, "smf_confidence")
    normalized = None
    if components is not None:
        if not isinstance(components, dict) or any(type(key) is not str or not key for key in components):
            raise ValueError("invalid_smf_components")
        normalized = tuple(sorted(components.items()))
    return SmfSnapshot(symbol, observed_at_ms, score, smf_grade(score), model_version,
                       normalized, confidence)


@dataclass(frozen=True, slots=True)
class FlowComponents:
    oi_speed: Decimal | None = None
    taker: Decimal | None = None
    top_trader_lsr_slope: Decimal | None = None
    oi_quadrant: Decimal | None = None
    compression_accumulation: Decimal | None = None
    capital_flow_cycle: Decimal | None = None
    momentum_tilt: Decimal | None = None

    def __post_init__(self):
        for name in (
            "oi_speed", "taker", "top_trader_lsr_slope", "oi_quadrant",
            "compression_accumulation", "capital_flow_cycle", "momentum_tilt",
        ):
            _decimal(getattr(self, name), f"flow_{name}")

    def score(self) -> Decimal | None:
        values = (
            (self.oi_speed, Decimal("35")),
            (self.taker, Decimal("15")),
            (self.top_trader_lsr_slope, Decimal("15")),
            (self.oi_quadrant, Decimal("10")),
            (self.compression_accumulation, Decimal("10")),
            (self.capital_flow_cycle, Decimal("10")),
            (self.momentum_tilt, Decimal("10")),
        )
        if any(value is None for value, _ in values):
            return None
        with localcontext(research._CONTEXT):
            return sum((value * weight for value, weight in values), Decimal("0"))


EXIT_VERSION = "yaozi-exit-guide-v1"
EXIT = "EXIT"
HOLD = "HOLD"
STALE_EXIT_MS = 720 * 60 * 60 * 1000


def adaptive_exit_floor_pct(atr_pct: Decimal | None) -> Decimal | None:
    """Published base floor: clamp(8 * ATR%, 8%, 22%)."""
    atr_pct = _decimal(atr_pct, "atr_pct")
    if atr_pct is None:
        return None
    if atr_pct < 0:
        raise ValueError("invalid_atr_pct")
    with localcontext(research._CONTEXT):
        return min(Decimal("22"), max(Decimal("8"), atr_pct * Decimal("8")))


@dataclass(frozen=True, slots=True)
class MomentumExitInputs:
    atr_pct: Decimal | None = None
    drawdown_from_peak_pct: Decimal | None = None
    since_last_scan_ms: int | None = None
    healthy_pullback: bool | None = None
    market_risk_off: bool | None = None
    leading_exit: bool | None = None

    def __post_init__(self):
        _decimal(self.atr_pct, "atr_pct")
        _decimal(self.drawdown_from_peak_pct, "drawdown_from_peak_pct")
        if self.atr_pct is not None and self.atr_pct < 0:
            raise ValueError("invalid_atr_pct")
        if self.drawdown_from_peak_pct is not None and self.drawdown_from_peak_pct > 0:
            raise ValueError("invalid_drawdown_from_peak_pct")
        if (self.since_last_scan_ms is not None
                and (type(self.since_last_scan_ms) is not int or self.since_last_scan_ms < 0)):
            raise ValueError("invalid_since_last_scan_ms")
        for name in ("healthy_pullback", "market_risk_off", "leading_exit"):
            value = getattr(self, name)
            if value is not None and type(value) is not bool:
                raise ValueError(f"invalid_{name}")


@dataclass(frozen=True, slots=True)
class MomentumExitEvaluation:
    version: str
    decision: str
    reason: str | None
    adaptive_floor_pct: Decimal | None
    evidence: tuple[tuple[str, object], ...]


def evaluate_momentum_exit(inputs: MomentumExitInputs) -> MomentumExitEvaluation:
    """Evaluate only the Guide-published deterministic exit subset.

    Risk-off tightens the normal price floor, but the adjustment is unpublished.
    Cases whose outcome depends on that adjustment remain MISSING_DATA.
    """
    if not isinstance(inputs, MomentumExitInputs):
        raise ValueError("invalid_momentum_exit_inputs")
    floor = adaptive_exit_floor_pct(inputs.atr_pct)
    stale = None if inputs.since_last_scan_ms is None else inputs.since_last_scan_ms >= STALE_EXIT_MS
    hard_peak = (None if inputs.drawdown_from_peak_pct is None
                 else inputs.drawdown_from_peak_pct <= Decimal("-20"))
    adaptive_breach = (None if floor is None or inputs.drawdown_from_peak_pct is None
                       else inputs.drawdown_from_peak_pct <= -floor)
    evidence = (
        ("leading_exit", inputs.leading_exit),
        ("since_last_scan_ms", inputs.since_last_scan_ms),
        ("stale_gate", _truth(stale)),
        ("drawdown_from_peak_pct", inputs.drawdown_from_peak_pct),
        ("peak_hard_gate", _truth(hard_peak)),
        ("adaptive_floor_pct", floor),
        ("adaptive_breach_gate", _truth(adaptive_breach)),
        ("healthy_pullback", inputs.healthy_pullback),
        ("market_risk_off", inputs.market_risk_off),
    )
    if inputs.leading_exit is True:
        return MomentumExitEvaluation(EXIT_VERSION, EXIT, "leading_signal", floor, evidence)
    if stale is True:
        return MomentumExitEvaluation(EXIT_VERSION, EXIT, "stale_dropped", floor, evidence)
    if hard_peak is True:
        return MomentumExitEvaluation(EXIT_VERSION, EXIT, "peak_drawdown", floor, evidence)
    if adaptive_breach is True and inputs.healthy_pullback is False:
        return MomentumExitEvaluation(EXIT_VERSION, EXIT, "mfe_drawdown", floor, evidence)

    known_no_leading = inputs.leading_exit is False
    known_not_stale = stale is False
    if adaptive_breach is True and inputs.healthy_pullback is True:
        if known_no_leading and known_not_stale and inputs.market_risk_off is False:
            return MomentumExitEvaluation(EXIT_VERSION, HOLD, None, floor, evidence)
        return MomentumExitEvaluation(EXIT_VERSION, MISSING_DATA,
                                      "risk_off_or_exit_evidence_unknown", floor, evidence)
    if (adaptive_breach is False and known_no_leading and known_not_stale
            and inputs.market_risk_off is False):
        return MomentumExitEvaluation(EXIT_VERSION, HOLD, None, floor, evidence)
    return MomentumExitEvaluation(EXIT_VERSION, MISSING_DATA,
                                  "risk_off_or_exit_evidence_unknown", floor, evidence)


@dataclass(frozen=True, slots=True)
class LifecycleMemory:
    state: str = INACTIVE
    consecutive_count: int = 0

    def __post_init__(self):
        if type(self.state) is not str or not self.state:
            raise ValueError("invalid_lifecycle_state")
        if type(self.consecutive_count) is not int or self.consecutive_count < 0:
            raise ValueError("invalid_consecutive_count")


@dataclass(frozen=True, slots=True)
class ScanState:
    flow: LifecycleMemory = LifecycleMemory()
    opportunity: LifecycleMemory = LifecycleMemory()
    risk: LifecycleMemory = LifecycleMemory()


@dataclass(frozen=True, slots=True)
class ViewTransition:
    view_name: str
    observed_at_ms: int
    state: str
    score: Decimal | None
    consecutive_count: int
    event: str | None
    evidence: tuple[tuple[str, object], ...]

    def memory(self):
        return LifecycleMemory(self.state, self.consecutive_count)


@dataclass(frozen=True, slots=True)
class ScanInputs:
    symbol: str
    observed_at_ms: int
    smf_score: Decimal | None
    smf_model_version: str
    flow_components: FlowComponents
    opportunity_quality: Decimal | None
    risk_score: Decimal | None
    smf_components: dict | None = None
    smf_confidence: Decimal | None = None

    def __post_init__(self):
        if type(self.symbol) is not str or not self.symbol.endswith("-USDT-SWAP"):
            raise ValueError("invalid_symbol")
        ipc.integer(self.observed_at_ms, "observed_at_ms")
        if type(self.smf_model_version) is not str or not self.smf_model_version:
            raise ValueError("invalid_smf_model_version")
        if not isinstance(self.flow_components, FlowComponents):
            raise ValueError("invalid_flow_components")
        _decimal(self.smf_score, "smf_score")
        _decimal(self.opportunity_quality, "opportunity_quality")
        _decimal(self.risk_score, "risk_score")
        _decimal(self.smf_confidence, "smf_confidence")


@dataclass(frozen=True, slots=True)
class ScanTransition:
    symbol: str
    observed_at_ms: int
    lifecycle_version: str
    smf: SmfSnapshot
    flow: ViewTransition
    opportunity: ViewTransition
    risk: ViewTransition

    @property
    def next_state(self):
        return ScanState(self.flow.memory(), self.opportunity.memory(), self.risk.memory())


def _event(previous, current, name):
    return name if previous != current else None


def _flow_transition(previous: LifecycleMemory, observed_at_ms: int,
                     score: Decimal | None) -> ViewTransition:
    ignition_gate = _gte(score, Decimal("70"))
    accumulation_gate = _between(score, Decimal("50"), Decimal("70"))
    faded_gate = _lt(score, Decimal("35"))
    state = previous.state
    count = previous.consecutive_count
    event = None
    if score is None:
        count = 0
    elif ignition_gate:
        state, count = IGNITION, 0
        event = _event(previous.state, state, "flow_ignition")
    elif accumulation_gate:
        state, count = ACCUMULATION, 0
        event = _event(previous.state, state, "flow_accumulation")
    elif faded_gate:
        count = min(previous.consecutive_count + 1, 3)
        if count >= 3:
            state = FLOW_FADED
            event = _event(previous.state, state, "flow_faded")
    else:
        count = 0
    evidence = (
        ("evaluation_status", MISSING_DATA if score is None else "AVAILABLE"),
        ("ignition_gate", _truth(ignition_gate)),
        ("accumulation_gate", _truth(accumulation_gate)),
        ("fade_gate", _truth(faded_gate)),
        ("fade_scans_required", 3),
    )
    return ViewTransition(FLOW, observed_at_ms, state, score, count, event, evidence)


def _opportunity_transition(previous: LifecycleMemory, observed_at_ms: int,
                            quality: Decimal | None, risk: Decimal | None) -> ViewTransition:
    enter_gate = _gte(quality, Decimal("55"))
    end_gate = _lt(quality, Decimal("45"))
    risk_block_gate = _gte(risk, Decimal("60"))
    state = previous.state
    count = previous.consecutive_count
    event = None
    if quality is None:
        count = 0
    elif end_gate:
        count = min(previous.consecutive_count + 1, 3)
        if count >= 3:
            state = OPPORTUNITY_ENDED
            event = _event(previous.state, state, "opportunity_ended")
    else:
        count = 0
        if enter_gate and previous.state != OPPORTUNITY_ACTIVE and risk_block_gate is False:
            state = OPPORTUNITY_ACTIVE
            event = "opportunity_entered"
    evidence = (
        ("evaluation_status", MISSING_DATA if quality is None else "AVAILABLE"),
        ("entry_gate", _truth(enter_gate)),
        ("end_gate", _truth(end_gate)),
        ("risk_block_gate", _truth(risk_block_gate)),
        ("end_scans_required", 3),
    )
    return ViewTransition(OPPORTUNITY, observed_at_ms, state, quality, count, event, evidence)


def _risk_transition(previous: LifecycleMemory, observed_at_ms: int,
                     score: Decimal | None) -> ViewTransition:
    high_gate = _gte(score, Decimal("60"))
    watch_gate = _gte(score, Decimal("45"))
    cooling_gate = _lt(score, Decimal("45"))
    resolved_gate = _lt(score, Decimal("30"))
    state = previous.state
    count = previous.consecutive_count
    event = None
    if score is None:
        count = 0
    elif high_gate:
        state, count = RISK_HIGH, 0
        event = _event(previous.state, state, "risk_high")
    elif watch_gate:
        state, count = RISK_WATCH, 0
        event = _event(previous.state, state, "risk_watch")
    elif previous.state in (RISK_HIGH, RISK_WATCH, RISK_COOLING):
        if resolved_gate:
            count = min(previous.consecutive_count + 1, 2)
            if count >= 2:
                state = RISK_RESOLVED
                event = _event(previous.state, state, "risk_resolved")
            else:
                state = RISK_COOLING
                event = _event(previous.state, state, "risk_cooling")
        else:
            state, count = RISK_COOLING, 0
            event = _event(previous.state, state, "risk_cooling")
    else:
        count = 0
    evidence = (
        ("evaluation_status", MISSING_DATA if score is None else "AVAILABLE"),
        ("high_risk_gate", _truth(high_gate)),
        ("watch_gate", _truth(watch_gate)),
        ("cooling_gate", _truth(cooling_gate)),
        ("cooling_hysteresis", "below_45_after_active_risk"),
        ("resolved_gate", _truth(resolved_gate)),
        ("resolved_scans_required", 2),
    )
    return ViewTransition(RISK, observed_at_ms, state, score, count, event, evidence)


def transition_scan(previous: ScanState, inputs: ScanInputs) -> ScanTransition:
    """Pure deterministic reducer; caller supplies the scan timestamp explicitly."""
    if not isinstance(previous, ScanState):
        raise ValueError("invalid_scan_state")
    if not isinstance(inputs, ScanInputs):
        raise ValueError("invalid_scan_inputs")
    smf = make_smf_snapshot(
        symbol=inputs.symbol,
        observed_at_ms=inputs.observed_at_ms,
        score=inputs.smf_score,
        model_version=inputs.smf_model_version,
        components=inputs.smf_components,
        confidence=inputs.smf_confidence,
    )
    flow_score = inputs.flow_components.score()
    flow = _flow_transition(previous.flow, inputs.observed_at_ms, flow_score)
    opportunity = _opportunity_transition(
        previous.opportunity, inputs.observed_at_ms,
        inputs.opportunity_quality, inputs.risk_score,
    )
    risk = _risk_transition(previous.risk, inputs.observed_at_ms, inputs.risk_score)
    return ScanTransition(inputs.symbol, inputs.observed_at_ms, LIFECYCLE_VERSION,
                          smf, flow, opportunity, risk)
