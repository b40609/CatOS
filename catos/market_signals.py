"""Deterministic P0-C signal and pattern rules for the Yaozi parity layer.

Only thresholds confirmed by the research spec are executable here. Rules with
unpublished Yaozi thresholds remain explicitly disabled instead of receiving a
catOS guess. The module is pure: no network, database, notification or trading.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext

from catos import ipc, research
from catos.market_features import FeatureSet


SIGNAL_VERSION = "yaozi-l2-known-v1"
PATTERN_VERSION = "yaozi-pattern-known-v2"
CROSS_AXIS_VERSION = "yaozi-cross-axis-known-v1"
STATUS_LABEL_VERSION = "yaozi-status-label-guide-v2"

HIT = "HIT"
MISS = "MISS"
MISSING_DATA = "MISSING_DATA"
DISABLED_UNKNOWN_THRESHOLD = "DISABLED_UNKNOWN_THRESHOLD"

L2_TYPES = (
    "HIT",
    "AMBUSH",
    "ACCUMULATION",
    "HEAT",
    "MOMENTUM",
    "STRONG_MOMENTUM",
    "FUNDING_NEGATIVE_FLIP",
    "OI_SURGE",
    "EXTREME_LONG",
    "WHALE_ENTRY",
    "WHALE_EXIT",
    "TEAM_DISTRIBUTION",
    "COIL_BREAKOUT_LIGHT",
    "PURE_MOMENTUM",
)

_UNKNOWN_L2 = frozenset((
    "HIT", "AMBUSH", "ACCUMULATION", "HEAT", "OI_SURGE", "EXTREME_LONG",
    "WHALE_ENTRY", "WHALE_EXIT", "COIL_BREAKOUT_LIGHT",
))

PATTERN_TYPES = (
    "SHORT_SQUEEZE_CANDIDATE",
    "COIL_BREAKOUT",
    "PREHEAT",
    "AMBUSH",
    "FOMO",
    "TREND_REVERSAL",
    "DISTRIBUTION",
)

CROSS_AXIS_TYPES = ("ALPHA_PLUS", "ALPHA")
STATUS_LABEL_TYPES = ("OBSERVE", "DUMP_WARNING", "NEW_CANDIDATE")
SMF_GRADES = frozenset(("S", "A", "B", "C", "D"))


def _decimal(value, name):
    if value is None:
        return None
    if not isinstance(value, Decimal):
        raise ValueError(f"invalid_{name}")
    try:
        ipc.decimal_text(str(value), name, derived=True)
    except ipc.ProtocolError:
        raise ValueError(f"invalid_{name}") from None
    return value


def _optional_bool(value, name):
    if value is not None and type(value) is not bool:
        raise ValueError(f"invalid_{name}")
    return value


@dataclass(frozen=True, slots=True)
class SignalInputs:
    symbol: str
    observed_at_ms: int
    return_1h_pct: Decimal | None = None
    return_24h_pct: Decimal | None = None
    volume_24h_usd: Decimal | None = None
    market_cap_usd: Decimal | None = None
    oi_delta_5m_pct: Decimal | None = None
    oi_delta_1h_pct: Decimal | None = None
    oi_delta_4h_pct: Decimal | None = None
    volatility_percentile_15m: Decimal | None = None
    funding_previous: Decimal | None = None
    funding_current: Decimal | None = None
    trend_active: bool | None = None
    whale_exit_event: bool | None = None
    extreme_long_event: bool | None = None
    capital_flow_fomo_event: bool | None = None
    team_transfer_usd: Decimal | None = None
    team_transfer_non_exchange_to_exchange: bool | None = None
    team_distribution_cooldown_clear: bool | None = None
    volatility_high_1h: bool | None = None
    trend_strength: Decimal | None = None
    trend_strength_falling: bool | None = None
    directional_force_confirmed: bool | None = None
    prior_bullish_support: bool | None = None
    distribution_behavior: bool | None = None

    def __post_init__(self):
        if type(self.symbol) is not str or not self.symbol.endswith("-USDT-SWAP"):
            raise ValueError("invalid_symbol")
        ipc.integer(self.observed_at_ms, "observed_at_ms")
        for name in (
            "return_1h_pct", "return_24h_pct", "volume_24h_usd", "market_cap_usd",
            "oi_delta_5m_pct", "oi_delta_1h_pct", "oi_delta_4h_pct",
            "volatility_percentile_15m", "funding_previous", "funding_current",
            "team_transfer_usd", "trend_strength",
        ):
            _decimal(getattr(self, name), name)
        for name in (
            "trend_active", "whale_exit_event", "extreme_long_event",
            "capital_flow_fomo_event", "team_transfer_non_exchange_to_exchange",
            "team_distribution_cooldown_clear", "volatility_high_1h",
            "trend_strength_falling", "directional_force_confirmed",
            "prior_bullish_support", "distribution_behavior",
        ):
            _optional_bool(getattr(self, name), name)
        if self.volume_24h_usd is not None and self.volume_24h_usd < 0:
            raise ValueError("invalid_volume_24h_usd")
        if self.market_cap_usd is not None and self.market_cap_usd < 0:
            raise ValueError("invalid_market_cap_usd")
        if self.team_transfer_usd is not None and self.team_transfer_usd < 0:
            raise ValueError("invalid_team_transfer_usd")
        if (self.volatility_percentile_15m is not None
                and not Decimal("0") <= self.volatility_percentile_15m <= Decimal("100")):
            raise ValueError("invalid_volatility_percentile_15m")

    @classmethod
    def from_features(cls, features: FeatureSet, **extras):
        if not isinstance(features, FeatureSet):
            raise ValueError("invalid_feature_set")
        values = dict(
            symbol=features.symbol,
            observed_at_ms=features.observed_at_ms,
            return_1h_pct=features.return_1h_pct,
            return_24h_pct=features.return_24h_pct,
            oi_delta_5m_pct=features.oi_delta_5m_pct,
            oi_delta_1h_pct=features.oi_delta_1h_pct,
            oi_delta_4h_pct=features.oi_delta_4h_pct,
        )
        values.update(extras)
        return cls(**values)


@dataclass(frozen=True, slots=True)
class Evaluation:
    kind: str
    status: str
    evidence: tuple[tuple[str, object], ...]
    thresholds: tuple[tuple[str, object], ...]


@dataclass(frozen=True, slots=True)
class SignalBundle:
    symbol: str
    observed_at_ms: int
    signal_version: str
    pattern_version: str
    signals: tuple[Evaluation, ...]
    patterns: tuple[Evaluation, ...]

    def signal(self, kind):
        return next(item for item in self.signals if item.kind == kind)

    def pattern(self, kind):
        return next(item for item in self.patterns if item.kind == kind)


@dataclass(frozen=True, slots=True)
class CrossAxisInputs:
    pattern_strength: Decimal | None
    resonance: int | None
    bullish: bool | None
    smf_grade: str | None

    def __post_init__(self):
        _decimal(self.pattern_strength, "pattern_strength")
        if self.pattern_strength is not None and self.pattern_strength < 0:
            raise ValueError("invalid_pattern_strength")
        if self.resonance is not None and (type(self.resonance) is not int or self.resonance < 0):
            raise ValueError("invalid_resonance")
        _optional_bool(self.bullish, "bullish")
        if self.smf_grade is not None and self.smf_grade not in SMF_GRADES:
            raise ValueError("invalid_smf_grade")


@dataclass(frozen=True, slots=True)
class CrossAxisSelection:
    version: str
    evaluations: tuple[Evaluation, ...]
    selected: str | None

    def eligibility(self, kind):
        return next(item for item in self.evaluations if item.kind == kind)


@dataclass(frozen=True, slots=True)
class StatusLabelInputs:
    observe: bool | None = None
    dump_warning: bool | None = None
    new_candidate: bool | None = None
    smf_grade: str | None = None
    detailed_pattern_hit: bool | None = None
    onchain_distribution_or_whale_exit: bool | None = None
    return_24h_pct: Decimal | None = None
    distribution_behavior: bool | None = None
    first_pool_age_ms: int | None = None
    other_label_hit: bool | None = None

    def __post_init__(self):
        for name in (
            "observe", "dump_warning", "new_candidate", "detailed_pattern_hit",
            "onchain_distribution_or_whale_exit", "distribution_behavior", "other_label_hit",
        ):
            _optional_bool(getattr(self, name), name)
        if self.smf_grade is not None and self.smf_grade not in SMF_GRADES:
            raise ValueError("invalid_smf_grade")
        _decimal(self.return_24h_pct, "return_24h_pct")
        if (self.first_pool_age_ms is not None
                and (type(self.first_pool_age_ms) is not int or self.first_pool_age_ms < 0)):
            raise ValueError("invalid_first_pool_age_ms")


@dataclass(frozen=True, slots=True)
class StatusLabelBundle:
    version: str
    labels: tuple[Evaluation, ...]

    def label(self, kind):
        return next(item for item in self.labels if item.kind == kind)


def _ev(kind, status, evidence=(), thresholds=()):
    return Evaluation(kind, status, tuple(evidence), tuple(thresholds))


def _gate(value, predicate):
    if value is None:
        return None
    return bool(predicate(value))


def _and3(*values):
    if any(value is False for value in values):
        return False
    if any(value is None for value in values):
        return None
    return True


def _or3(*values):
    if any(value is True for value in values):
        return True
    if any(value is None for value in values):
        return None
    return False


def _status(value):
    if value is None:
        return MISSING_DATA
    return HIT if value else MISS


def _funding_flip(inputs):
    return _and3(
        _gate(inputs.funding_previous, lambda value: value > 0),
        _gate(inputs.funding_current, lambda value: value < 0),
        _gate(inputs.oi_delta_1h_pct, lambda value: value > 0),
    )


def _known_l2(inputs):
    result = []
    for kind in L2_TYPES:
        if kind in _UNKNOWN_L2:
            result.append(_ev(kind, DISABLED_UNKNOWN_THRESHOLD,
                              thresholds=(("yaozi_threshold", "unpublished"),)))
            continue
        if kind == "MOMENTUM":
            gate = _gate(inputs.return_24h_pct, lambda value: abs(value) >= Decimal("10"))
            result.append(_ev(kind, _status(gate),
                              (("return_24h_pct", inputs.return_24h_pct),),
                              (("abs_return_24h_pct_gte", Decimal("10")),)))
        elif kind == "STRONG_MOMENTUM":
            gate = _gate(inputs.return_24h_pct, lambda value: abs(value) >= Decimal("25"))
            result.append(_ev(kind, _status(gate),
                              (("return_24h_pct", inputs.return_24h_pct),),
                              (("abs_return_24h_pct_gte", Decimal("25")),)))
        elif kind == "FUNDING_NEGATIVE_FLIP":
            gate = _funding_flip(inputs)
            result.append(_ev(kind, _status(gate),
                              (("funding_previous", inputs.funding_previous),
                               ("funding_current", inputs.funding_current),
                               ("oi_delta_1h_pct", inputs.oi_delta_1h_pct)),
                              (("previous_funding", ">0"), ("current_funding", "<0"),
                               ("oi_direction", ">0"))))
        elif kind == "TEAM_DISTRIBUTION":
            gate = _and3(
                _gate(inputs.team_transfer_usd, lambda value: value >= Decimal("500000")),
                inputs.team_transfer_non_exchange_to_exchange,
                inputs.team_distribution_cooldown_clear,
            )
            result.append(_ev(kind, _status(gate),
                              (("transfer_usd", inputs.team_transfer_usd),
                               ("non_exchange_to_exchange", inputs.team_transfer_non_exchange_to_exchange),
                               ("cooldown_clear", inputs.team_distribution_cooldown_clear)),
                              (("single_transfer_usd_gte", Decimal("500000")),
                               ("same_symbol_cooldown_hours", 24))))
        elif kind == "PURE_MOMENTUM":
            gate = _and3(
                _gate(inputs.return_24h_pct, lambda value: value >= Decimal("10")),
                _gate(inputs.market_cap_usd, lambda value: value < Decimal("300000000")),
                _gate(inputs.volume_24h_usd, lambda value: value >= Decimal("5000000")),
            )
            result.append(_ev(kind, _status(gate),
                              (("return_24h_pct", inputs.return_24h_pct),
                               ("market_cap_usd", inputs.market_cap_usd),
                               ("volume_24h_usd", inputs.volume_24h_usd)),
                              (("return_24h_pct_gte", Decimal("10")),
                               ("market_cap_usd_lt", Decimal("300000000")),
                               ("volume_24h_usd_gte", Decimal("5000000")))))
        else:
            raise AssertionError(kind)
    return tuple(result)


def _patterns(inputs, signal_map):
    funding_flip = signal_map["FUNDING_NEGATIVE_FLIP"].status
    funding_flip_gate = (True if funding_flip == HIT else False if funding_flip == MISS else None)
    no_whale_exit = None if inputs.whale_exit_event is None else not inputs.whale_exit_event

    squeeze = _and3(
        _gate(inputs.return_24h_pct, lambda value: value >= Decimal("5")),
        _gate(inputs.oi_delta_4h_pct, lambda value: value >= Decimal("10")),
        _gate(inputs.oi_delta_1h_pct, lambda value: value >= Decimal("3")),
        no_whale_exit,
        _or3(inputs.trend_active, funding_flip_gate, inputs.extreme_long_event),
    )

    coil = _and3(
        _gate(inputs.volatility_percentile_15m, lambda value: value < Decimal("50")),
        _gate(inputs.oi_delta_5m_pct, lambda value: value >= Decimal("1.5")),
        _gate(inputs.oi_delta_1h_pct, lambda value: value >= Decimal("2.5")),
        _gate(inputs.return_1h_pct, lambda value: Decimal("-1") <= value <= Decimal("2")),
        _or3(inputs.trend_active, funding_flip_gate),
    )

    acceleration = None
    if inputs.oi_delta_5m_pct is not None and inputs.oi_delta_1h_pct is not None:
        acceleration = inputs.oi_delta_5m_pct > inputs.oi_delta_1h_pct / Decimal("12")
    preheat = _and3(
        _gate(inputs.oi_delta_1h_pct, lambda value: value >= Decimal("2")),
        _gate(inputs.oi_delta_5m_pct, lambda value: value >= Decimal("1")),
        _gate(inputs.return_1h_pct, lambda value: Decimal("1.5") <= value <= Decimal("6")),
        _gate(inputs.return_24h_pct, lambda value: Decimal("-5") <= value <= Decimal("10")),
        no_whale_exit,
        acceleration,
    )

    ambush = _and3(
        _gate(inputs.volatility_percentile_15m, lambda value: value < Decimal("35")),
        _gate(inputs.oi_delta_1h_pct, lambda value: value >= Decimal("2")),
        _gate(inputs.return_1h_pct, lambda value: abs(value) < Decimal("1.5")),
        _gate(inputs.return_24h_pct, lambda value: Decimal("-3") <= value <= Decimal("3")),
    )

    fomo_price_volume = _and3(
        _gate(inputs.return_24h_pct, lambda value: value >= Decimal("15")),
        _gate(inputs.volume_24h_usd, lambda value: value >= Decimal("1000000")),
    )
    fomo = _or3(fomo_price_volume, inputs.capital_flow_fomo_event)

    no_prior_bullish_support = (
        None if inputs.prior_bullish_support is None else not inputs.prior_bullish_support)
    trend_reversal = _and3(
        inputs.volatility_high_1h,
        _gate(inputs.trend_strength, lambda value: value >= Decimal("25")),
        inputs.trend_strength_falling,
        inputs.directional_force_confirmed,
        _gate(inputs.return_24h_pct, lambda value: value > 0),
        no_prior_bullish_support,
    )
    distribution = _or3(inputs.whale_exit_event, inputs.distribution_behavior)

    common = (
        ("return_1h_pct", inputs.return_1h_pct),
        ("return_24h_pct", inputs.return_24h_pct),
        ("oi_delta_5m_pct", inputs.oi_delta_5m_pct),
        ("oi_delta_1h_pct", inputs.oi_delta_1h_pct),
        ("oi_delta_4h_pct", inputs.oi_delta_4h_pct),
        ("volatility_percentile_15m", inputs.volatility_percentile_15m),
        ("whale_exit_event", inputs.whale_exit_event),
        ("trend_active", inputs.trend_active),
        ("funding_negative_flip_status", funding_flip),
    )
    return (
        _ev("SHORT_SQUEEZE_CANDIDATE", _status(squeeze), common,
            (("return_24h_pct_gte", Decimal("5")), ("oi_4h_pct_gte", Decimal("10")),
             ("oi_1h_pct_gte", Decimal("3")), ("requires_no_whale_exit", True))),
        _ev("COIL_BREAKOUT", _status(coil), common,
            (("volatility_percentile_15m_lt", Decimal("50")),
             ("oi_5m_pct_gte", Decimal("1.5")), ("oi_1h_pct_gte", Decimal("2.5")),
             ("return_1h_pct_range", "[-1,2]"))),
        _ev("PREHEAT", _status(preheat), common + (("oi_5m_acceleration", acceleration),),
            (("oi_1h_pct_gte", Decimal("2")), ("oi_5m_pct_gte", Decimal("1")),
             ("return_1h_pct_range", "[1.5,6]"), ("return_24h_pct_range", "[-5,10]"),
             ("oi_5m_speed_gt_1h_average", True))),
        _ev("AMBUSH", _status(ambush), common,
            (("volatility_percentile_15m_lt", Decimal("35")),
             ("oi_1h_pct_gte", Decimal("2")), ("abs_return_1h_pct_lt", Decimal("1.5")),
             ("return_24h_pct_range", "[-3,3]"))),
        _ev("FOMO", _status(fomo),
            (("return_24h_pct", inputs.return_24h_pct), ("volume_24h_usd", inputs.volume_24h_usd),
             ("capital_flow_fomo_event", inputs.capital_flow_fomo_event)),
            (("price_volume_branch", ">=15% AND >=1000000 USD"),
             ("capital_flow_branch", "FOMO event"))),
        _ev("TREND_REVERSAL", _status(trend_reversal),
            (("volatility_high_1h", inputs.volatility_high_1h),
             ("trend_strength", inputs.trend_strength),
             ("trend_strength_falling", inputs.trend_strength_falling),
             ("directional_force_confirmed", inputs.directional_force_confirmed),
             ("return_24h_pct", inputs.return_24h_pct),
             ("prior_bullish_support", inputs.prior_bullish_support)),
            (("trend_strength_gte", Decimal("25")),
             ("return_24h_direction", ">0"),
             ("volatility_high_1h_semantics", "caller_confirmed_public_condition"),
             ("directional_force_semantics", "caller_confirmed_public_condition"),
             ("prior_bullish_support_semantics", "caller_confirmed_public_condition"))),
        _ev("DISTRIBUTION", _status(distribution),
            (("whale_exit_event", inputs.whale_exit_event),
             ("distribution_behavior", inputs.distribution_behavior)),
            (("gate", "whale_exit OR caller_confirmed_distribution_behavior"),)),
    )


def evaluate_cross_axis(inputs: CrossAxisInputs) -> CrossAxisSelection:
    """Evaluate published Alpha+/Alpha cross-axis eligibility without SMF aliasing."""
    if not isinstance(inputs, CrossAxisInputs):
        raise ValueError("invalid_cross_axis_inputs")
    with localcontext(research._CONTEXT):
        alpha_plus = _and3(
            _gate(inputs.pattern_strength, lambda value: value >= Decimal("75")),
            _gate(inputs.resonance, lambda value: value >= 3),
            inputs.bullish,
            None if inputs.smf_grade is None else inputs.smf_grade not in ("C", "D"),
        )
        alpha = _and3(
            _gate(inputs.pattern_strength, lambda value: value >= Decimal("60")),
            _gate(inputs.resonance, lambda value: value >= 2),
            inputs.bullish,
            None if inputs.smf_grade is None else inputs.smf_grade != "D",
        )
    evidence = (
        ("pattern_strength", inputs.pattern_strength),
        ("resonance", inputs.resonance),
        ("bullish", inputs.bullish),
        ("smf_grade", inputs.smf_grade),
    )
    evaluations = (
        _ev("ALPHA_PLUS", _status(alpha_plus), evidence,
            (("pattern_strength_gte", Decimal("75")), ("resonance_gte", 3),
             ("requires_bullish", True), ("smf_excluded_grades", ("C", "D")))),
        _ev("ALPHA", _status(alpha), evidence,
            (("pattern_strength_gte", Decimal("60")), ("resonance_gte", 2),
             ("requires_bullish", True), ("smf_excluded_grades", ("D",)))),
    )
    selected = "ALPHA_PLUS" if alpha_plus is True else "ALPHA" if alpha is True else None
    return CrossAxisSelection(CROSS_AXIS_VERSION, evaluations, selected)


def evaluate_status_labels(inputs: StatusLabelInputs) -> StatusLabelBundle:
    """Evaluate published status-label rules while preserving source-explicit states."""
    if not isinstance(inputs, StatusLabelInputs):
        raise ValueError("invalid_status_label_inputs")
    observe_derived = _and3(
        None if inputs.smf_grade is None else inputs.smf_grade == "B",
        None if inputs.detailed_pattern_hit is None else not inputs.detailed_pattern_hit,
    )
    dump_warning_derived = _or3(
        None if inputs.smf_grade is None else inputs.smf_grade == "D",
        inputs.onchain_distribution_or_whale_exit,
        _gate(inputs.return_24h_pct, lambda value: value <= Decimal("-10")),
        _and3(
            inputs.distribution_behavior,
            None if inputs.smf_grade is None else inputs.smf_grade in ("C", "D"),
            _gate(inputs.return_24h_pct, lambda value: value <= Decimal("-5")),
        ),
    )
    new_candidate_derived = _and3(
        _gate(inputs.first_pool_age_ms, lambda value: value < 21600000),
        None if inputs.other_label_hit is None else not inputs.other_label_hit,
    )
    def evaluation(kind, explicit, derived, evidence, thresholds):
        selected = explicit if explicit is not None else derived
        mode = "source_explicit" if explicit is not None else "official_guide_derivation"
        return _ev(kind, _status(selected),
                   (("derivation_mode", mode), ("source_explicit_state", explicit), *evidence),
                   (("derivation", mode), *thresholds))

    labels = (
        evaluation("OBSERVE", inputs.observe, observe_derived,
                   (("smf_grade", inputs.smf_grade),
                    ("detailed_pattern_hit", inputs.detailed_pattern_hit)),
                   (("smf_grade_eq", "B"), ("requires_no_detailed_pattern", True))),
        evaluation("DUMP_WARNING", inputs.dump_warning, dump_warning_derived,
                   (("smf_grade", inputs.smf_grade),
                    ("onchain_distribution_or_whale_exit", inputs.onchain_distribution_or_whale_exit),
                    ("return_24h_pct", inputs.return_24h_pct),
                    ("distribution_behavior", inputs.distribution_behavior)),
                   (("smf_grade_d", True), ("onchain_distribution_or_whale_exit", True),
                    ("return_24h_pct_lte", Decimal("-10")),
                    ("distribution_branch",
                     "behavior=distribution AND smf_grade in C/D AND return_24h_pct<=-5"))),
        evaluation("NEW_CANDIDATE", inputs.new_candidate, new_candidate_derived,
                   (("first_pool_age_ms", inputs.first_pool_age_ms),
                    ("other_label_hit", inputs.other_label_hit)),
                   (("first_pool_age_ms_lt", 21600000), ("requires_no_other_label", True))),
    )
    return StatusLabelBundle(STATUS_LABEL_VERSION, labels)


def evaluate(inputs: SignalInputs) -> SignalBundle:
    if not isinstance(inputs, SignalInputs):
        raise ValueError("invalid_signal_inputs")
    with localcontext(research._CONTEXT):
        signals = _known_l2(inputs)
        signal_map = {item.kind: item for item in signals}
        patterns = _patterns(inputs, signal_map)
    return SignalBundle(inputs.symbol, inputs.observed_at_ms,
                        SIGNAL_VERSION, PATTERN_VERSION, signals, patterns)
