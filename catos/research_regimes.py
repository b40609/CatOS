"""Causal, Decimal market-regime diagnostics for in-memory research.

Rules are supplied before a run. Labels never change strategy selection. Each
equity interval belongs to the environment known at its opening, not its close.
"""

from collections import deque
from dataclasses import asdict, dataclass
from decimal import Decimal, localcontext
from hashlib import sha256
import json
from typing import Callable, Iterable, Mapping

from catos.optimization import Parameter
from catos.research import (
    BacktestConfig, BacktestResult, Candle, Performance, Strategy,
    _CONTEXT, _call, _decimal, _integer, _validate, backtest,
)
from catos.research_validation import (
    WalkForwardPlan, WalkForwardResult, _json, validation_json, walk_forward,
)


RULE_VERSION = "lagged_efficiency_true_range_v1"
REGIMES = ("UNKNOWN", "UP_LOW", "UP_HIGH", "DOWN_LOW", "DOWN_HIGH",
           "RANGE_LOW", "RANGE_HIGH")
_ASSUMPTIONS = (
    "Diagnostic rules, not a fitted model, financial policy, or deployment gate.",
    "Thresholds are explicit and fixed before evaluation; no full-sample quantiles.",
    "Each interval uses the preceding closed-bar label; unknown intervals are retained.",
    "Equity differences allocate mark-to-market PnL once, including cross-regime holdings.",
    "Fees and signed funding are already in net PnL; slippage is embedded in fills.",
    "Gross PnL adds back only fees and funding, not slippage or hypothetical exit costs.",
    "Counts are bar intervals and fills, not independent samples or round-trip win rates.",
    "No regime-level compounded returns, drawdowns, statistical significance, or pass gate.",
    "Independent OOS windows remain separate; no continuous portfolio is constructed.",
    "Input hash binds candles, config and rule, not strategy/score sources or dependencies.",
)


@dataclass(frozen=True)
class RegimeRule:
    lookback_bars: int
    trend_efficiency: Decimal
    high_volatility_bps: Decimal


@dataclass(frozen=True)
class RegimeLabel:
    close_time_ms: int
    regime: str
    efficiency: Decimal | None
    volatility_bps: Decimal | None
    reason: str | None


@dataclass(frozen=True)
class RegimeInterval:
    open_time_ms: int
    close_time_ms: int
    classification_time_ms: int | None
    regime: str
    reason: str | None
    net_pnl: Decimal
    gross_pnl: Decimal
    fees: Decimal
    funding_paid: Decimal
    fill_count: int
    funding_payment_count: int


@dataclass(frozen=True)
class RegimeSummary:
    regime: str
    bar_count: int
    positive_bars: int
    negative_bars: int
    zero_bars: int
    fill_count: int
    funding_payment_count: int
    net_pnl: Decimal
    gross_pnl: Decimal
    fees: Decimal
    funding_paid: Decimal


@dataclass(frozen=True)
class RegimeEvaluation:
    evaluation_start_ms: int
    evaluation_end_ms: int
    intervals: tuple[RegimeInterval, ...]
    summaries: tuple[RegimeSummary, ...]
    total: RegimeSummary
    core_net_rounding_residual: Decimal
    reconciled: bool


@dataclass(frozen=True)
class RegimeBacktestResult:
    schema_version: str
    input_sha256: str
    rule_version: str
    rule: RegimeRule
    labels: tuple[RegimeLabel, ...]
    backtest: BacktestResult
    evaluation: RegimeEvaluation
    assumptions: tuple[str, ...]


@dataclass(frozen=True)
class WindowRegimeEvaluation:
    number: int
    status: str
    selected_trial_number: int | None
    error: str | None
    evaluation: RegimeEvaluation | None


@dataclass(frozen=True)
class RegimeWalkForwardResult:
    schema_version: str
    input_sha256: str
    rule_version: str
    rule: RegimeRule
    labels: tuple[RegimeLabel, ...]
    validation: WalkForwardResult
    windows: tuple[WindowRegimeEvaluation, ...]
    assumptions: tuple[str, ...]


def _rule(rule):
    if not isinstance(rule, RegimeRule):
        raise TypeError("rule must be RegimeRule")
    _integer(rule.lookback_bars, "lookback_bars", minimum=1)
    _decimal(rule.trend_efficiency, "trend_efficiency", positive=True)
    if rule.trend_efficiency > Decimal(1):
        raise ValueError("trend_efficiency must be <= 1")
    _decimal(rule.high_volatility_bps, "high_volatility_bps", positive=True)


def _labels(bars, timeframe_ms, rule):
    history = deque()
    labels = []
    previous = None
    with localcontext(_CONTEXT):
        for bar in bars:
            if previous is not None:
                delta = bar.close - previous.close
                true_range = max(bar.high - bar.low, abs(bar.high - previous.close),
                                 abs(bar.low - previous.close))
                history.append((delta, true_range / previous.close * Decimal(10000)))
                if len(history) > rule.lookback_bars:
                    history.popleft()
            efficiency = volatility = None
            regime, reason = "UNKNOWN", "insufficient_history"
            if len(history) == rule.lookback_bars:
                change = sum((item[0] for item in history), Decimal(0))
                path = sum((abs(item[0]) for item in history), Decimal(0))
                efficiency = abs(change) / path if path else Decimal(0)
                volatility = sum((item[1] for item in history), Decimal(0)) / Decimal(len(history))
                trend = ("UP" if change > 0 else "DOWN") if efficiency >= rule.trend_efficiency else "RANGE"
                regime = trend + ("_HIGH" if volatility >= rule.high_volatility_bps else "_LOW")
                reason = None
            labels.append(RegimeLabel(bar.open_time_ms + timeframe_ms, regime,
                                      efficiency, volatility, reason))
            previous = bar
    return tuple(labels)


def classify_regimes(*, candles: Iterable[Candle], config: BacktestConfig,
                     rule: RegimeRule) -> tuple[RegimeLabel, ...]:
    """Label closes using L changes/TRs (L+1 bars); a prefix never uses its suffix."""
    _rule(rule)
    bars = tuple(candles)
    _call(_validate, config, bars, 0)
    return _labels(bars, config.timeframe_ms, rule)


def _summary(name, rows):
    return RegimeSummary(
        name, len(rows), sum(row.net_pnl > 0 for row in rows),
        sum(row.net_pnl < 0 for row in rows), sum(row.net_pnl == 0 for row in rows),
        sum(row.fill_count for row in rows), sum(row.funding_payment_count for row in rows),
        *(sum((getattr(row, field) for row in rows), Decimal(0))
          for field in ("net_pnl", "gross_pnl", "fees", "funding_paid")),
    )


def _attribute(result, labels):
    # Use exact additions/differences of already-rounded ledger values. The
    # ledger's 50-digit context is unchanged; grouping must not lose small terms.
    values = [getattr(view, field) for view in result.equity_curve
              for field in ("equity", "fees", "funding_paid")]
    low = min(value.as_tuple().exponent for value in values)
    high = max(value.adjusted() for value in values)
    headroom = len(str(len(values))) + 4
    context = _CONTEXT.copy()
    context.prec = max(context.prec, high - low + 1 + headroom)
    context.Emin = min(context.Emin, low)
    context.Emax = max(context.Emax, high + headroom)
    by_close = {label.close_time_ms: label for label in labels}
    fills = {}
    for trade in result.trades:
        fills[trade.time_ms] = fills.get(trade.time_ms, 0) + 1
    payments = iter(result.funding)
    payment = next(payments, None)
    rows = []
    with localcontext(context):
        for before, after in zip(result.equity_curve, result.equity_curve[1:]):
            label = by_close.get(before.time_ms)
            payment_count = 0
            # The engine settles boundary funding before the next bar's fill;
            # the first interval also owns funding exactly at evaluation start.
            while payment is not None and payment.time_ms <= after.time_ms:
                payment_count += 1
                payment = next(payments, None)
            net = after.equity - before.equity
            fee = after.fees - before.fees
            funding = after.funding_paid - before.funding_paid
            rows.append(RegimeInterval(
                before.time_ms, after.time_ms, label.close_time_ms if label else None,
                label.regime if label else "UNKNOWN",
                label.reason if label else "no_prior_closed_bar",
                net, net + fee + funding, fee, funding,
                fills.get(before.time_ms, 0), payment_count,
            ))
        summaries = tuple(_summary(name, [row for row in rows if row.regime == name])
                          for name in REGIMES)
        total = _summary("ALL", rows)
        performance = result.performance
        residual = performance.net_pnl - total.net_pnl
        if (_call(lambda: total.net_pnl + Decimal(0)) != performance.net_pnl or total.fees != performance.fees
                or total.funding_paid != performance.funding_paid
                or total.fill_count != performance.trade_count
                or total.funding_payment_count != len(result.funding)
                or any(sum((getattr(row, field) for row in summaries), Decimal(0)) != getattr(total, field)
                       for field in ("net_pnl", "gross_pnl", "fees", "funding_paid"))):
            raise ValueError("regime attribution does not reconcile with core performance")
    return RegimeEvaluation(result.evaluation_start_ms, result.evaluation_end_ms,
                            tuple(rows), summaries, total, residual, True)


def _inputs(candles, config, rule):
    _rule(rule)
    bars = tuple(candles)
    _call(_validate, config, bars, 0)
    digest = sha256(_json({"candles": bars, "config": config, "rule": rule,
                          "rule_version": RULE_VERSION}).encode("utf-8")).hexdigest()
    return bars, _labels(bars, config.timeframe_ms, rule), digest


def regime_backtest(*, strategy: Callable[[], Strategy], candles: Iterable[Candle],
                    config: BacktestConfig, rule: RegimeRule,
                    warmup_bars: int = 0) -> RegimeBacktestResult:
    """Run the existing core and attribute its own output to the bound input."""
    bars, labels, digest = _inputs(candles, config, rule)
    result = backtest(strategy=strategy, candles=bars, config=config, warmup_bars=warmup_bars)
    return RegimeBacktestResult("regime-backtest-v1", digest, RULE_VERSION, rule, labels,
                               result, _attribute(result, labels), _ASSUMPTIONS)


def regime_walk_forward(
    *, strategy_factory: Callable[[Mapping[str, int | Decimal]], Strategy],
    search_space: Mapping[str, Parameter], candles: Iterable[Candle],
    config: BacktestConfig, rule: RegimeRule,
    score: Callable[[Performance], Decimal], score_name: str,
    plan: WalkForwardPlan, max_candidates: int, max_runs: int,
    direction: str = "maximize",
) -> RegimeWalkForwardResult:
    """Annotate each independent OOS result without changing training selection.

    Classifier history may include preceding training bars, even when strategy
    warm-up is shorter. Labels are never provided to the strategy/score callback.
    """
    bars, labels, digest = _inputs(candles, config, rule)
    result = walk_forward(strategy_factory=strategy_factory, search_space=search_space,
                          candles=bars, config=config, score=score, score_name=score_name,
                          plan=plan, max_candidates=max_candidates, max_runs=max_runs,
                          direction=direction)
    windows = tuple(WindowRegimeEvaluation(
        window.number, window.status, window.training.selected_trial_number, window.error,
        _attribute(window.out_of_sample, labels) if window.out_of_sample is not None else None,
    ) for window in result.windows)
    return RegimeWalkForwardResult("regime-walk-forward-v1", digest, RULE_VERSION, rule,
                                  labels, result, windows, _ASSUMPTIONS)


def regimes_json(result: RegimeBacktestResult | RegimeWalkForwardResult) -> str:
    """Deterministic JSON with exact Decimal strings and explicit window failures."""
    if not isinstance(result, (RegimeBacktestResult, RegimeWalkForwardResult)):
        raise TypeError("result must be a regime backtest or walk-forward result")
    payload = asdict(result)
    if isinstance(result, RegimeWalkForwardResult):
        payload["validation"] = json.loads(validation_json(result.validation))
        payload["complete"] = result.validation.complete
    return _json(payload)
