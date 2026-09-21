"""Pure P1 market-intelligence contracts and reducers.

These types contain no credentials, network clients, trading authority, or
SQLite handles. Decimal values remain Decimal until the Supervisor persists
them as TEXT.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
import hashlib

from catos import ipc, research


_CAPITAL_FLOW_GUIDE_ROWS = (
    ("inflow", "FIRST_INFLOW", "首次流入"),
    ("inflow", "MAJOR_INFLOW", "大額流入"),
    ("inflow", "CONTINUED_INFLOW", "持續流入"),
    ("inflow", "INFLOW_ACCELERATION", "流入加速"),
    ("inflow", "WHALE_BUY_CLUSTER", "鯨魚買入群"),
    ("inflow", "SMART_WALLET_ACCUMULATION", "聰明錢吸籌"),
    ("inflow", "CEX_ACCUMULATION", "CEX吸籌"),
    ("inflow", "ACCUMULATION_QUIET", "安靜吸籌"),
    ("inflow", "ALPHA_CONFIRM", "Alpha確認"),
    ("inflow", "FOMO", "量價FOMO"),
    ("outflow", "MAJOR_OUTFLOW", "大額流出"),
    ("outflow", "WHALE_SELL_CLUSTER", "鯨魚賣出群"),
    ("outflow", "SMART_WALLET_DISTRIBUTION", "聰明錢派發"),
    ("outflow", "HOLDER_REDUCTION", "持幣減少"),
    ("outflow", "FLOW_FLIP_TO_OUTFLOW", "資金轉流出"),
    ("outflow", "CEX_OUTFLOW", "CEX流出"),
    ("lifecycle", "TAKE_PROFIT_TRIGGERED", "止盈觸發"),
    ("lifecycle", "TRAILING_TAKE_PROFIT_WARNING", "移動止盈預警"),
    ("lifecycle", "INFLOW_WEAKENING", "流入轉弱"),
    ("lifecycle", "EXIT_CONFIRMED", "退場確認"),
    ("lifecycle", "BEARISH_TRACKING_STARTED", "看跌追蹤開始"),
    ("lifecycle", "BULLISH_TRACKING_ENDED", "看漲追蹤結束"),
    ("lifecycle", "TRACKING_STARTED", "追蹤開始"),
    ("lifecycle", "TRACKING_ENDED", "追蹤結束"),
    ("lifecycle", "CYCLE_RESET", "循環重置"),
    ("structural_quality", "LOW_DATA_CONFIDENCE", "數據低信度"),
    ("structural_quality", "SINGLE_VENUE_DOMINANCE", "單所主導"),
    ("structural_quality", "OI_BREAKOUT", "OI突破"),
    ("structural_quality", "NEGATIVE_FUNDING_SETUP", "負費率佈局"),
    ("structural_quality", "CROSS_VENUE_DIVERGENCE", "跨所背離"),
    ("structural_quality", "OI_SILENT_DECLINE", "OI靜默下滑"),
)


CAPITAL_FLOW_GUIDE_EVENT_TYPES = frozenset(row[1] for row in _CAPITAL_FLOW_GUIDE_ROWS)


YAOZI_OBSERVED_EVENT_TYPES = CAPITAL_FLOW_GUIDE_EVENT_TYPES | frozenset({
    "WHALE_BUY_CLUSTER",
    "WHALE_SELL_CLUSTER",
    "SMART_WALLET_ACCUMULATION",
    "SMART_WALLET_DISTRIBUTION",
    "MAJOR_OUTFLOW",
    "FIRST_INFLOW",
    "CONTINUED_INFLOW",
    "INFLOW_ACCELERATION",
    "FLOW_FLIP_TO_OUTFLOW",
    "CEX_ACCUMULATION",
    "OI_BREAKOUT",
    "CONTRACT_IGNITION",
    "SINGLE_VENUE_DOMINANCE",
    "TOP_TRADER_LONG_BUILD",
    "TOP_VS_RETAIL_DIV",
})


KNOWN_CAPITAL_FLOW_EVENT_TYPES = frozenset({
    "inflow",
    "outflow",
    "large inflow",
    "sustained inflow",
    "inflow acceleration",
    "whale buy cluster",
    "whale sell cluster",
    "smart money accumulation",
    "smart money distribution",
    "CEX accumulation",
    "CEX outflow",
    "quiet accumulation",
    "alpha confirm",
    "FOMO",
}) | YAOZI_OBSERVED_EVENT_TYPES


def capital_flow_semantic_taxonomy():
    """Return the 31 Guide-published Capital Flow semantics without inventing gates."""
    grouped = {name: [] for name in ("inflow", "outflow", "lifecycle", "structural_quality")}
    for group, event_type, guide_label in _CAPITAL_FLOW_GUIDE_ROWS:
        grouped[group].append({
            "event_type": event_type,
            "guide_label": guide_label,
            "source_status": "guide_published_semantic",
            "materialization_mode": "source_explicit_fact",
            "local_trigger_status": "not_inferred",
        })
    return {
        "contract": "yaozi-capital-flow-guide-taxonomy-v1",
        "event_kind_count": len(_CAPITAL_FLOW_GUIDE_ROWS),
        "display_only": True,
        "smf_eligible": False,
        "semantic_coverage": "complete_31_of_31",
        "trigger_coverage": "partial_source_explicit_only",
        "groups": grouped,
    }


PUBLIC_EVENT_CANDIDATE_TYPES = frozenset({
    "DEX_DIRECTIONAL_FLOW",
    "OI_POSITIVE_CHANGE",
    "HYPERLIQUID_PUBLIC_TRADE_ACTIVITY",
})


def _symbol(value: str) -> str:
    if type(value) is not str or not value.endswith("-USDT-SWAP"):
        raise ValueError("invalid_symbol")
    ipc.token(value.removesuffix("-USDT-SWAP"), "symbol base")
    return value


def _optional_decimal(value, name):
    if value is None:
        return None
    if not isinstance(value, Decimal):
        raise ValueError(f"invalid_{name}")
    try:
        return ipc.decimal_text(str(value), name, derived=True)
    except ipc.ProtocolError:
        raise ValueError(f"invalid_{name}") from None


@dataclass(frozen=True, slots=True)
class CapitalFlowEvent:
    event_id: str
    event_type: str
    symbol: str
    observed_at_ms: int
    score: Decimal | None
    cycle_state: str | None
    evidence: dict
    source_snapshot_ids: tuple[str, ...]

    def __post_init__(self):
        ipc.token(self.event_id, "event_id")
        _symbol(self.symbol)
        ipc.integer(self.observed_at_ms, "observed_at_ms")
        if self.event_type not in KNOWN_CAPITAL_FLOW_EVENT_TYPES:
            raise ValueError("unknown_capital_flow_event_type")
        _optional_decimal(self.score, "score")
        if self.cycle_state is not None:
            ipc.token(self.cycle_state, "cycle_state")
        if type(self.evidence) is not dict:
            raise ValueError("invalid_evidence")
        if type(self.source_snapshot_ids) is not tuple or any(
                type(item) is not str or not item for item in self.source_snapshot_ids):
            raise ValueError("invalid_source_snapshot_ids")


@dataclass(frozen=True, slots=True)
class PublicEventCandidate:
    """Public evidence that may contribute to a Yaozi-like event, never a trigger."""

    candidate_id: str
    candidate_type: str
    symbol: str
    observed_at_ms: int
    possible_yaozi_event_types: tuple[str, ...]
    evidence: dict
    source_snapshot_ids: tuple[str, ...]

    def __post_init__(self):
        ipc.token(self.candidate_id, "candidate_id")
        _symbol(self.symbol)
        ipc.integer(self.observed_at_ms, "observed_at_ms")
        if self.candidate_type not in PUBLIC_EVENT_CANDIDATE_TYPES:
            raise ValueError("unknown_public_event_candidate_type")
        if type(self.possible_yaozi_event_types) is not tuple or any(
                item not in YAOZI_OBSERVED_EVENT_TYPES for item in self.possible_yaozi_event_types):
            raise ValueError("invalid_possible_yaozi_event_types")
        if type(self.evidence) is not dict:
            raise ValueError("invalid_evidence")
        try:
            ipc.encode_frame({"evidence": self.evidence})
        except ipc.ProtocolError:
            raise ValueError("invalid_evidence") from None
        if type(self.source_snapshot_ids) is not tuple or not self.source_snapshot_ids or any(
                type(item) is not str or not item for item in self.source_snapshot_ids):
            raise ValueError("invalid_source_snapshot_ids")


def _bounded_source_text(value, name):
    if type(value) is not str or not value or len(value) > 512 or any(ord(char) < 32 for char in value):
        raise ValueError(f"invalid_{name}")
    return value


def _public_candidate(*, candidate_type, symbol, observed_at_ms,
                      possible_yaozi_event_types, evidence, source_snapshot_ids):
    identity = "|".join((candidate_type, symbol, str(observed_at_ms), *source_snapshot_ids))
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
    return PublicEventCandidate(
        candidate_id=f"public-candidate-{digest}",
        candidate_type=candidate_type,
        symbol=symbol,
        observed_at_ms=observed_at_ms,
        possible_yaozi_event_types=possible_yaozi_event_types,
        evidence=evidence,
        source_snapshot_ids=source_snapshot_ids,
    )


def make_public_dex_event_candidate(window) -> PublicEventCandidate | None:
    """Convert a verified DEX directional window into evidence-only candidate facts."""
    if type(window) is not dict:
        raise ValueError("invalid_dex_window")
    symbol = _symbol(window.get("symbol"))
    observed_at_ms = window.get("observed_at_ms")
    ipc.integer(observed_at_ms, "observed_at_ms")
    coverage_status = window.get("coverage_status")
    coverage_scope = window.get("coverage_scope")
    if not (
            (coverage_status == "verified_pool_window" and coverage_scope == "single_pool")
            or (coverage_status == "verified_multi_pool_window" and coverage_scope == "multi_pool")):
        return None
    if window.get("net_flow_status") != "observed_sum":
        return None
    raw_net = window.get("net_flow_text")
    if type(raw_net) is not str:
        return None
    try:
        net_flow = ipc.decimal_text(raw_net, "dex net flow", derived=True)
    except ipc.ProtocolError:
        raise ValueError("invalid_dex_window") from None
    if net_flow == 0:
        return None
    raw_source_run_ids = window.get("source_run_ids")
    if raw_source_run_ids is None:
        source_run_id = window.get("source_run_id")
        source_run_ids = () if source_run_id is None else (source_run_id,)
    elif type(raw_source_run_ids) in (list, tuple):
        source_run_ids = tuple(raw_source_run_ids)
    else:
        return None
    if not source_run_ids or any(type(value) is not str or not value for value in source_run_ids):
        return None
    direction = "INFLOW" if net_flow > 0 else "OUTFLOW"
    possible = (
        ("FIRST_INFLOW", "CONTINUED_INFLOW", "INFLOW_ACCELERATION")
        if net_flow > 0 else ("MAJOR_OUTFLOW", "FLOW_FLIP_TO_OUTFLOW")
    )
    return _public_candidate(
        candidate_type="DEX_DIRECTIONAL_FLOW",
        symbol=symbol,
        observed_at_ms=observed_at_ms,
        possible_yaozi_event_types=possible,
        evidence={
            "contract": "catos_public_event_candidate_v1",
            "source_kind": "verified_dex_flow",
            "direction": direction,
            "net_flow_text": raw_net,
            "quote_currency": window.get("quote_currency"),
            "coverage_status": coverage_status,
            "coverage_scope": coverage_scope,
            "threshold": None,
            "threshold_status": "unknown_unpublished",
            "yaozi_event_triggered": False,
        },
        source_snapshot_ids=source_run_ids,
    )


def make_oi_event_candidate(snapshot) -> PublicEventCandidate | None:
    """Preserve positive OI change as input evidence without declaring OI_BREAKOUT."""
    if type(snapshot) is not dict:
        raise ValueError("invalid_derivative_snapshot")
    symbol = _symbol(snapshot.get("symbol"))
    observed_at_ms = snapshot.get("observed_at_ms")
    ipc.integer(observed_at_ms, "observed_at_ms")
    deltas = {}
    positive = False
    for name in ("oi_delta_5m_text", "oi_delta_1h_text", "oi_delta_4h_text"):
        value = snapshot.get(name)
        if value is None:
            continue
        if type(value) is not str:
            raise ValueError("invalid_derivative_snapshot")
        try:
            parsed = ipc.decimal_text(value, name, derived=True)
        except ipc.ProtocolError:
            raise ValueError("invalid_derivative_snapshot") from None
        deltas[name] = value
        positive = positive or parsed > 0
    if not deltas or not positive:
        return None
    source_snapshot_id = f"derivative:{symbol}:{observed_at_ms}"
    return _public_candidate(
        candidate_type="OI_POSITIVE_CHANGE",
        symbol=symbol,
        observed_at_ms=observed_at_ms,
        possible_yaozi_event_types=("OI_BREAKOUT",),
        evidence={
            "contract": "catos_public_event_candidate_v1",
            "source_kind": "materialized_derivative_snapshot",
            "oi_delta": deltas,
            "threshold": None,
            "threshold_status": "unknown_unpublished",
            "yaozi_event_triggered": False,
        },
        source_snapshot_ids=(source_snapshot_id,),
    )


def make_hyperliquid_activity_candidate(batch) -> PublicEventCandidate | None:
    """Summarize public trades without inventing net flow or smart-wallet identity."""
    from catos.market_hyperliquid import HyperliquidObservationBatch

    if not isinstance(batch, HyperliquidObservationBatch):
        raise ValueError("invalid_hyperliquid_batch")
    symbol = _symbol(batch.symbol)
    ipc.integer(batch.observed_at_ms, "observed_at_ms")
    if not batch.observations:
        return None
    trades = {}
    wallets = set()
    source_ids = []
    currency = None
    for observation in batch.observations:
        if observation.symbol != symbol or observation.observed_at_ms != batch.observed_at_ms:
            raise ValueError("hyperliquid_scope_mismatch")
        if observation.position_or_flow_type != "PUBLIC_TRADE_PARTICIPANT":
            raise ValueError("invalid_hyperliquid_observation")
        tid = observation.provenance.get("tid") if type(observation.provenance) is dict else None
        if type(tid) is not int:
            raise ValueError("invalid_hyperliquid_observation")
        if currency is None:
            currency = observation.notional_currency
        elif currency != observation.notional_currency:
            raise ValueError("mixed_hyperliquid_currency")
        key = (observation.source_ms, tid)
        previous = trades.get(key)
        if previous is None:
            trades[key] = observation.notional
        elif previous != observation.notional:
            raise ValueError("conflicting_hyperliquid_trade")
        wallets.add(observation.wallet_or_trader)
        source_ids.append(observation.source_id)
    with localcontext(research._CONTEXT):
        total_notional = sum(trades.values(), Decimal("0"))
    return _public_candidate(
        candidate_type="HYPERLIQUID_PUBLIC_TRADE_ACTIVITY",
        symbol=symbol,
        observed_at_ms=batch.observed_at_ms,
        possible_yaozi_event_types=(),
        evidence={
            "contract": "catos_public_event_candidate_v1",
            "source_kind": "hyperliquid_public_trades",
            "trade_count": len(trades),
            "participant_observation_count": len(batch.observations),
            "distinct_observed_wallets": len(wallets),
            "trade_notional_total_text": str(total_notional),
            "notional_currency": currency,
            "net_flow_status": "not_defined_counterparty_symmetric",
            "smart_wallet_classification_status": "missing",
            "whale_threshold_status": "unknown_unpublished",
            "yaozi_event_triggered": False,
            "issues": [list(item) for item in batch.issues],
        },
        source_snapshot_ids=tuple(sorted(source_ids)),
    )


def make_observed_yaozi_event(*, symbol, observed_at_ms, event_type, payload,
                              source_snapshot_id, source_event_id, source_surface):
    """Preserve a black-box-observed Yaozi event without inferring its private gate.

    The caller supplies a stable source-event identity and the exact structured
    facts that were visible on the sampled surface. Numeric facts stay strings
    when their exact decimal representation matters; JSON float input is refused.
    """
    symbol = _symbol(symbol)
    ipc.integer(observed_at_ms, "observed_at_ms")
    if event_type not in YAOZI_OBSERVED_EVENT_TYPES:
        raise ValueError("unknown_yaozi_observed_event_type")
    source_snapshot_id = _bounded_source_text(source_snapshot_id, "source_snapshot_id")
    source_event_id = _bounded_source_text(source_event_id, "source_event_id")
    source_surface = _bounded_source_text(source_surface, "source_surface")
    if type(payload) is not dict:
        raise ValueError("invalid_observed_event_payload")
    try:
        ipc.encode_frame({"payload": payload})
    except ipc.ProtocolError:
        raise ValueError("invalid_observed_event_payload") from None
    identity = f"{source_snapshot_id}|{source_event_id}|{event_type}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
    return CapitalFlowEvent(
        event_id=f"yaozi-observed-{digest}",
        event_type=event_type,
        symbol=symbol,
        observed_at_ms=observed_at_ms,
        score=None,
        cycle_state=None,
        evidence={
            "contract": "yaozi_observed_event_fact_v1",
            "source": "yaozi_blackbox",
            "source_surface": source_surface,
            "source_event_type": event_type,
            "threshold_status": "unknown_unpublished",
            "threshold": None,
            "payload": payload,
        },
        source_snapshot_ids=(source_snapshot_id,),
    )


def make_dex_capital_flow_event(window) -> CapitalFlowEvent | None:
    """Materialize a catOS-native directional event from a verified DEX window.

    This does not infer Yaozi whale thresholds, cycle state, score, or Dealer FLOW.
    """
    if type(window) is not dict:
        raise ValueError("invalid_dex_window")
    symbol = _symbol(window.get("symbol"))
    observed_at_ms = window.get("observed_at_ms")
    ipc.integer(observed_at_ms, "observed_at_ms")
    coverage_status = window.get("coverage_status")
    coverage_scope = window.get("coverage_scope")
    verified = (
        (coverage_status == "verified_pool_window" and coverage_scope == "single_pool")
        or (coverage_status == "verified_multi_pool_window" and coverage_scope == "multi_pool")
    )
    if not verified:
        return None
    if window.get("net_flow_status") != "observed_sum":
        return None
    raw_net = window.get("net_flow_text")
    currency = window.get("quote_currency")
    raw_source_run_ids = window.get("source_run_ids")
    if raw_source_run_ids is None:
        source_run_id = window.get("source_run_id")
        source_run_ids = () if source_run_id is None else (source_run_id,)
    elif type(raw_source_run_ids) in (list, tuple):
        source_run_ids = tuple(raw_source_run_ids)
    else:
        return None
    if type(raw_net) is not str or type(currency) is not str or not currency:
        return None
    if not source_run_ids or any(type(value) is not str or not value for value in source_run_ids):
        return None
    try:
        net_flow = ipc.decimal_text(raw_net, "dex net flow", derived=True)
    except ipc.ProtocolError:
        raise ValueError("invalid_dex_window") from None
    if net_flow == 0:
        return None
    event_type = "inflow" if net_flow > 0 else "outflow"
    digest = hashlib.sha256("|".join(source_run_ids).encode("utf-8")).hexdigest()[:32]
    evidence = {
        "contract": ("catos_public_dex_multi_pool_window_v1"
                     if coverage_scope == "multi_pool" else "catos_public_dex_pool_window_v1"),
        "net_flow": net_flow,
        "quote_currency": currency,
        "coverage_status": coverage_status,
        "coverage_scope": coverage_scope,
        "window_start_ms": window.get("window_start_ms"),
        "window_end_ms": window.get("window_end_ms"),
        "swap_count": window.get("swap_count"),
        "whale_threshold": None,
        "dealer_flow_eligible": False,
    }
    return CapitalFlowEvent(
        event_id=f"dexflow-{digest}",
        event_type=event_type,
        symbol=symbol,
        observed_at_ms=observed_at_ms,
        score=None,
        cycle_state=None,
        evidence=evidence,
        source_snapshot_ids=source_run_ids,
    )


@dataclass(frozen=True, slots=True)
class DealerSnapshot:
    symbol: str
    observed_at_ms: int
    phase: str | None
    direction_score: Decimal | None
    direction_label: str | None
    coverage_mask: str
    axis_count: int
    position: dict | None
    flow: dict | None
    chip: dict | None

    def __post_init__(self):
        _symbol(self.symbol)
        ipc.integer(self.observed_at_ms, "observed_at_ms")
        _optional_decimal(self.direction_score, "direction_score")
        if self.phase is not None:
            ipc.token(self.phase, "phase")
        if self.direction_label is not None:
            ipc.token(self.direction_label, "direction_label")
        if self.coverage_mask not in (
                "NONE", "POSITION", "FLOW", "CHIP", "POSITION|FLOW",
                "POSITION|CHIP", "FLOW|CHIP", "POSITION|FLOW|CHIP"):
            raise ValueError("invalid_coverage_mask")
        if type(self.axis_count) is not int or not 0 <= self.axis_count <= 3:
            raise ValueError("invalid_axis_count")
        for value in (self.position, self.flow, self.chip):
            if value is not None and type(value) is not dict:
                raise ValueError("invalid_axis")


def make_dealer_snapshot(*, symbol, observed_at_ms, position=None, flow=None,
                         chip=None) -> DealerSnapshot:
    """Compose verifiable P1 axes without synthesizing Yaozi's final score."""
    position_available = bool(position and any(value is not None for value in position.values()))
    flow_available = bool(flow and any(value is not None for value in flow.values()))
    chip_available = bool(chip and any(value is not None for value in chip.values()))
    axes = tuple(name for name, available in (
        ("POSITION", position_available), ("FLOW", flow_available), ("CHIP", chip_available),
    ) if available)
    mask = "|".join(axes) if axes else "NONE"
    return DealerSnapshot(
        symbol=symbol,
        observed_at_ms=observed_at_ms,
        phase=None,
        direction_score=None,
        direction_label=None,
        coverage_mask=mask,
        axis_count=int(position_available) + int(flow_available) + int(chip_available),
        position=position if position_available else None,
        flow=flow if flow_available else None,
        chip=chip if chip_available else None,
    )


@dataclass(frozen=True, slots=True)
class OnchainActivity:
    symbol: str
    chain: str
    observed_at_ms: int
    outgoing_distinct: int
    baseline_days: int
    baseline_live: Decimal | None
    baseline_anchor: Decimal | None
    live_ratio: Decimal | None
    anchored_ratio: Decimal | None
    state: str
    first_flag_at_ms: int | None
    plateau_started_at_ms: int | None
    consecutive_days: int

    def __post_init__(self):
        _symbol(self.symbol)
        if type(self.chain) is not str or not self.chain:
            raise ValueError("invalid_chain")
        ipc.integer(self.observed_at_ms, "observed_at_ms")
        for value, name in ((self.outgoing_distinct, "outgoing_distinct"),
                            (self.baseline_days, "baseline_days"),
                            (self.consecutive_days, "consecutive_days")):
            if type(value) is not int or value < 0:
                raise ValueError(f"invalid_{name}")
        for value, name in ((self.baseline_live, "baseline_live"),
                            (self.baseline_anchor, "baseline_anchor"),
                            (self.live_ratio, "live_ratio"),
                            (self.anchored_ratio, "anchored_ratio")):
            _optional_decimal(value, name)
        if self.state not in ("NORMAL", "ELEVATED", "FLAGGED"):
            raise ValueError("invalid_onchain_state")


def _median(values: tuple[int, ...]) -> Decimal | None:
    if not values:
        return None
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("invalid_baseline_history")
    ordered = sorted(values[-14:])
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return Decimal(ordered[middle])
    with localcontext(research._CONTEXT):
        return (Decimal(ordered[middle - 1]) + Decimal(ordered[middle])) / Decimal("2")


def _ratio(value: int, baseline: Decimal | None) -> Decimal | None:
    if baseline is None or baseline <= 0:
        return None
    with localcontext(research._CONTEXT):
        return Decimal(value) / baseline


def reduce_onchain_activity(*, symbol, chain, observed_at_ms, outgoing_distinct,
                            previous_complete_days: tuple[int, ...], previous=None) -> OnchainActivity:
    """Apply only the published Address Expansion / Plateau gates.

    Baselines are per-chain and use the previous 14 complete days. Missing or
    zero baselines remain unscored rather than becoming zero-valued ratios.
    """
    _symbol(symbol)
    if type(chain) is not str or not chain:
        raise ValueError("invalid_chain")
    ipc.integer(observed_at_ms, "observed_at_ms")
    if type(outgoing_distinct) is not int or outgoing_distinct < 0:
        raise ValueError("invalid_outgoing_distinct")
    if type(previous_complete_days) is not tuple:
        raise ValueError("invalid_baseline_history")
    if previous is not None and (not isinstance(previous, OnchainActivity)
                                 or previous.symbol != symbol or previous.chain != chain):
        raise ValueError("invalid_previous_state")

    history = previous_complete_days[-14:]
    baseline_live = _median(history)
    baseline_days = len(history)
    live_ratio = _ratio(outgoing_distinct, baseline_live)
    flagged = (live_ratio is not None and live_ratio >= Decimal("3")
               and outgoing_distinct >= 5 and baseline_days >= 7)
    elevated = live_ratio is not None and live_ratio >= Decimal("2") and not flagged
    state = "FLAGGED" if flagged else "ELEVATED" if elevated else "NORMAL"

    baseline_anchor = None if previous is None else previous.baseline_anchor
    first_flag_at_ms = None if previous is None else previous.first_flag_at_ms
    if flagged and baseline_anchor is None:
        baseline_anchor = baseline_live
    if flagged and first_flag_at_ms is None:
        first_flag_at_ms = observed_at_ms
    anchored_ratio = _ratio(outgoing_distinct, baseline_anchor)

    previous_plateau = None if previous is None else previous.plateau_started_at_ms
    if previous_plateau is not None and anchored_ratio is not None and anchored_ratio >= Decimal("1.5"):
        plateau_started_at_ms = previous_plateau
    elif flagged and anchored_ratio is not None and anchored_ratio >= Decimal("3"):
        plateau_started_at_ms = observed_at_ms
    else:
        plateau_started_at_ms = None

    previous_non_normal = previous is not None and previous.state in ("ELEVATED", "FLAGGED")
    consecutive_days = (previous.consecutive_days + 1 if previous_non_normal else 1) if (
        state in ("ELEVATED", "FLAGGED")) else 0
    return OnchainActivity(
        symbol=symbol,
        chain=chain,
        observed_at_ms=observed_at_ms,
        outgoing_distinct=outgoing_distinct,
        baseline_days=baseline_days,
        baseline_live=baseline_live,
        baseline_anchor=baseline_anchor,
        live_ratio=live_ratio,
        anchored_ratio=anchored_ratio,
        state=state,
        first_flag_at_ms=first_flag_at_ms,
        plateau_started_at_ms=plateau_started_at_ms,
        consecutive_days=consecutive_days,
    )
