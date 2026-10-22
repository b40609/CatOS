"""Bounded Decimal grid stability and rolling, independent-window evaluation.

Pure in-memory research only. No providers, files, databases, or live accounts.
Factories and score callbacks must be inspected, trusted, and deterministic.
"""

from dataclasses import asdict, dataclass, is_dataclass, replace
from decimal import Decimal, localcontext
from hashlib import sha256
from itertools import product
import json
from types import MappingProxyType
from typing import Callable, Iterable, Mapping

from catos.optimization import IntRange, Parameter, _validate_space
from catos.research import (
    BacktestConfig, BacktestResult, Candle, Intent, Performance, Strategy,
    _CONTEXT, _call, _integer, _validate, backtest,
)


SELECTION_RULE = "maximin_axis_neighbors_v1"
_ASSUMPTIONS = (
    "Research diagnostics only; selection is not a profitability or deployment gate.",
    "Exhaustive bounded grid; neighbors differ by one numeric step on one axis.",
    "Every existing immediate neighbor must succeed; boundary neighborhoods are one-sided.",
    "Rank by worst neighborhood score, then mean, own score, then grid order.",
    "Each training trial and OOS window starts with a fresh strategy and flat account.",
    "Warm-up updates indicators only; no pre-window intents or positions are carried.",
    "Window-end positions are marked at close, not liquidated; pending intents stay unfilled.",
    "Independent OOS windows are not a continuous tradable portfolio or equity curve.",
    "Earlier OOS bars can enter later training; inspected OOS data is no longer a fresh holdout.",
    "Caller retains strategy/score sources and input artifacts; hashes alone do not reproduce code.",
)


@dataclass(frozen=True)
class GridTrial:
    number: int
    indices: tuple[int, ...]
    params: tuple[tuple[str, int | str], ...]
    score: Decimal | None
    performance: Performance | None
    terminal_position: Decimal | None
    pending_intent: Intent | None
    error: str | None

    def strategy_params(self) -> Mapping[str, int | Decimal]:
        return MappingProxyType({name: Decimal(value) if isinstance(value, str) else value
                                 for name, value in self.params})


@dataclass(frozen=True)
class Neighborhood:
    trial_number: int
    members: tuple[int, ...]  # Includes the center; no diagonal neighbors.
    complete: bool
    worst_score: Decimal | None
    mean_score: Decimal | None


@dataclass(frozen=True)
class StabilityResult:
    schema_version: str
    input_sha256: str
    config: BacktestConfig
    warmup_bars: int
    evaluation_start_ms: int
    evaluation_end_ms: int
    axes: tuple[tuple[str, tuple[int | str, ...]], ...]
    score_name: str
    direction: str
    selection_rule: str
    trials: tuple[GridTrial, ...]
    neighborhoods: tuple[Neighborhood, ...]
    selected_trial_number: int | None
    assumptions: tuple[str, ...]

    @property
    def selected_trial(self) -> GridTrial | None:
        return None if self.selected_trial_number is None else self.trials[self.selected_trial_number]


@dataclass(frozen=True)
class WalkForwardPlan:
    train_bars: int
    test_bars: int
    windows: int
    warmup_bars: int = 0


@dataclass(frozen=True)
class WalkForwardWindow:
    number: int
    train_start_ms: int
    train_end_ms: int
    test_start_ms: int
    test_end_ms: int
    training: StabilityResult
    out_of_sample: BacktestResult | None
    error: str | None

    @property
    def status(self) -> str:
        if self.training.selected_trial is None:
            return "NO_SELECTION"
        return "COMPLETE" if self.out_of_sample is not None else "OOS_FAILED"


@dataclass(frozen=True)
class WalkForwardResult:
    schema_version: str
    input_sha256: str
    plan: WalkForwardPlan
    score_name: str
    direction: str
    max_runs: int
    required_runs: int  # Preflight upper bound, including one OOS attempt per window.
    attempted_runs: int
    unused_bars: int
    windows: tuple[WalkForwardWindow, ...]
    assumptions: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return all(window.status == "COMPLETE" for window in self.windows)


def _json(value) -> str:
    def encode(item):
        if isinstance(item, Decimal):
            if not item.is_finite():
                raise ValueError("cannot serialize a nonfinite Decimal")
            return str(item)
        if is_dataclass(item):
            return asdict(item)
        raise TypeError(f"unsupported research value: {type(item).__name__}")

    return json.dumps(value, default=encode, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def validation_json(result: StabilityResult | WalkForwardResult) -> str:
    """Return a deterministic payload with Decimal strings and explicit status."""
    if isinstance(result, WalkForwardResult):
        payload = asdict(result)
        payload["complete"] = result.complete
        for row, window in zip(payload["windows"], result.windows):
            row["status"] = window.status
    elif isinstance(result, StabilityResult):
        payload = asdict(result)
    else:
        raise TypeError("result must be a StabilityResult or WalkForwardResult")
    return _json(payload)


def _digest(bars, config) -> str:
    return sha256(_json({"candles": bars, "config": config}).encode("utf-8")).hexdigest()


def _space(search_space, max_candidates):
    _integer(max_candidates, "max_candidates", minimum=1)
    space = _call(_validate_space, search_space)
    count = 1
    for _, spec in space:
        count *= ((spec.high - spec.low) // spec.step + 1
                  if isinstance(spec, IntRange) else len(spec.values))
        if count > max_candidates:
            raise ValueError("grid exceeds max_candidates before materialization")
    if count < 2:
        raise ValueError("stability requires at least two distinct parameter combinations")
    axes = tuple((name, tuple(range(spec.low, spec.high + 1, spec.step))
                  if isinstance(spec, IntRange) else tuple(sorted(spec.values, key=Decimal)))
                 for name, spec in space)
    return axes, count


def _callbacks(strategy_factory, score, score_name, direction):
    if not callable(strategy_factory) or not callable(score):
        raise TypeError("strategy_factory and score must be callable")
    if not isinstance(score_name, str) or not score_name.strip():
        raise ValueError("score_name must document the objective")
    if direction not in ("maximize", "minimize"):
        raise ValueError("direction must be maximize or minimize")


def _neighborhoods(trials, axes, direction):
    lookup = {trial.indices: trial.number for trial in trials}
    neighborhoods, ranked = [], []
    sign = Decimal(1) if direction == "maximize" else Decimal(-1)
    with localcontext(_CONTEXT) as context:
        # A sum can exceed the ledger exponent even when every score and its
        # mean fit. Reserve enough exponent headroom for at most len(trials) terms.
        context.Emax += len(str(len(trials))) + 2
        for trial in trials:
            members = [trial.number]
            for axis, (_, values) in enumerate(axes):
                for delta in (-1, 1):
                    index = trial.indices[axis] + delta
                    if 0 <= index < len(values):
                        neighbor = list(trial.indices)
                        neighbor[axis] = index
                        members.append(lookup[tuple(neighbor)])
            complete = all(trials[number].error is None for number in members)
            worst = mean = None
            if complete:
                scores = [trials[number].score for number in members]
                worst = min(scores) if direction == "maximize" else max(scores)
                mean = sum(scores, Decimal(0)) / Decimal(len(scores))
                ranked.append(((sign * worst, sign * mean, sign * trial.score, -trial.number),
                               trial.number))
            neighborhoods.append(Neighborhood(trial.number, tuple(members), complete, worst, mean))
    selected = max(ranked)[1] if ranked else None
    return tuple(neighborhoods), selected


def _grid(strategy_factory, axes, bars, config, score, score_name, direction, warmup_bars):
    trials = []
    for indices in product(*(range(len(values)) for _, values in axes)):
        params = tuple((name, values[index]) for (name, values), index in zip(axes, indices))
        decoded = MappingProxyType({name: Decimal(value) if isinstance(value, str) else value
                                    for name, value in params})
        result = value = None
        error = None
        try:
            result = backtest(strategy=lambda: strategy_factory(decoded), candles=bars,
                              config=config, warmup_bars=warmup_bars)
            candidate = _call(score, result.performance)
            if not isinstance(candidate, Decimal):
                raise TypeError("score callback must return Decimal, never float")
            if not candidate.is_finite():
                raise ValueError("score must be finite")
            normalized = _call(lambda: candidate + Decimal(0))
            if normalized != candidate:
                raise ValueError("score exceeds the research Decimal context precision or range")
            value = candidate
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        trials.append(GridTrial(len(trials), indices, params, value,
                                result.performance if result else None,
                                result.equity_curve[-1].position if result else None,
                                result.pending_intent if result else None, error))
    neighborhoods, selected = _neighborhoods(trials, axes, direction)
    return StabilityResult("stability-v1", _digest(bars, config), config, warmup_bars,
                           bars[warmup_bars].open_time_ms,
                           bars[-1].open_time_ms + config.timeframe_ms,
                           axes, score_name, direction, SELECTION_RULE,
                           tuple(trials), neighborhoods, selected, _ASSUMPTIONS)


def parameter_stability(
    *, strategy_factory: Callable[[Mapping[str, int | Decimal]], Strategy],
    search_space: Mapping[str, Parameter], candles: Iterable[Candle],
    config: BacktestConfig, score: Callable[[Performance], Decimal], score_name: str,
    max_candidates: int, warmup_bars: int = 0, direction: str = "maximize",
) -> StabilityResult:
    """Evaluate the entire bounded grid; failed neighbors cannot look stable."""
    _callbacks(strategy_factory, score, score_name, direction)
    axes, _ = _space(search_space, max_candidates)
    bars = tuple(candles)
    _call(_validate, config, bars, warmup_bars)
    return _grid(strategy_factory, axes, bars, config, score, score_name, direction, warmup_bars)


def _window_inputs(bars, config, start, end, warmup_bars):
    selected = bars[start - warmup_bars:end]
    first = selected[0].open_time_ms
    last = selected[-1].open_time_ms + config.timeframe_ms
    events = tuple(event for event in config.funding_events if first <= event.time_ms <= last)
    return selected, replace(config, funding_events=events)


def walk_forward(
    *, strategy_factory: Callable[[Mapping[str, int | Decimal]], Strategy],
    search_space: Mapping[str, Parameter], candles: Iterable[Candle],
    config: BacktestConfig, score: Callable[[Performance], Decimal], score_name: str,
    plan: WalkForwardPlan, max_candidates: int, max_runs: int,
    direction: str = "maximize",
) -> WalkForwardResult:
    """Freeze training selections before each disjoint OOS window is executed.

    Fixed-length rolling training, fixed test length, explicit number of windows.
    Fails preflight before any strategy call if input or worst-case budget fails.
    Ordinary trial/OOS failures are retained; interruptions propagate unchanged.
    """
    _callbacks(strategy_factory, score, score_name, direction)
    if not isinstance(plan, WalkForwardPlan):
        raise TypeError("plan must be WalkForwardPlan")
    for name in ("train_bars", "test_bars", "windows"):
        _integer(getattr(plan, name), name, minimum=1)
    _integer(plan.warmup_bars, "warmup_bars")
    _integer(max_runs, "max_runs", minimum=1)
    axes, count = _space(search_space, max_candidates)
    required_runs = plan.windows * (count + 1)
    if required_runs > max_runs:
        raise ValueError("walk-forward exceeds max_runs before execution")
    bars = tuple(candles)
    required_bars = plan.warmup_bars + plan.train_bars + plan.windows * plan.test_bars
    if len(bars) < required_bars:
        raise ValueError("insufficient candles for the explicit walk-forward plan")
    _call(_validate, config, bars, 0)
    windows, attempts = [], 0
    for number in range(plan.windows):
        train_start = plan.warmup_bars + number * plan.test_bars
        test_start = train_start + plan.train_bars
        test_end = test_start + plan.test_bars
        train_bars, train_config = _window_inputs(bars, config, train_start, test_start,
                                                  plan.warmup_bars)
        training = _grid(strategy_factory, axes, train_bars, train_config, score, score_name,
                         direction, plan.warmup_bars)
        attempts += count
        # Selection is immutable and complete before any OOS strategy is created.
        selected = training.selected_trial
        result, error = None, None
        if selected is not None:
            test_bars, test_config = _window_inputs(bars, config, test_start, test_end,
                                                   plan.warmup_bars)
            attempts += 1
            try:
                result = backtest(strategy=lambda: strategy_factory(selected.strategy_params()),
                                  candles=test_bars, config=test_config,
                                  warmup_bars=plan.warmup_bars)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
        windows.append(WalkForwardWindow(number, bars[train_start].open_time_ms,
                                         bars[test_start].open_time_ms,
                                         bars[test_start].open_time_ms,
                                         bars[test_end - 1].open_time_ms + config.timeframe_ms,
                                         training, result, error))
    return WalkForwardResult("walk-forward-v1", _digest(bars, config), plan, score_name,
                             direction, max_runs, required_runs, attempts,
                             len(bars) - required_bars, tuple(windows), _ASSUMPTIONS)
