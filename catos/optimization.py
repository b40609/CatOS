"""Sequential in-memory Optuna controller; float is confined to search scores.

This local research controller does not create live Workers or write SQLite.
Each trial invokes the existing backtest with a fresh strategy and fixed data.
"""

from dataclasses import dataclass
from decimal import Decimal
from math import isfinite
from types import MappingProxyType
from typing import Callable, Iterable, Mapping

import optuna

from catos.research import (
    BacktestConfig, Candle, Performance, Strategy, _call, _decimal, _integer,
    _validate, backtest,
)


@dataclass(frozen=True)
class IntRange:
    low: int
    high: int
    step: int = 1


@dataclass(frozen=True)
class DecimalChoices:
    values: tuple[str, ...]


Parameter = IntRange | DecimalChoices


@dataclass(frozen=True)
class TrialRecord:
    number: int
    state: str
    # Decimal candidates are preserved as strings; never converted from float.
    params: tuple[tuple[str, int | str], ...]
    score_decimal: Decimal | None
    score_float: float | None
    performance: Performance | None
    error: str | None

    def strategy_params(self) -> Mapping[str, int | Decimal]:
        return MappingProxyType({name: Decimal(value) if isinstance(value, str) else value
                                 for name, value in self.params})


@dataclass(frozen=True)
class SearchResult:
    seed: int
    direction: str
    score_name: str
    optuna_version: str
    search_space: tuple[tuple[str, Parameter], ...]
    config: BacktestConfig
    warmup_bars: int
    trials: tuple[TrialRecord, ...]
    best_trial_number: int | None

    @property
    def best_trial(self) -> TrialRecord | None:
        if self.best_trial_number is None:
            return None
        return self.trials[self.best_trial_number]


def _validate_space(space: Mapping[str, Parameter]) -> tuple[tuple[str, Parameter], ...]:
    if not isinstance(space, Mapping) or not space:
        raise ValueError("search_space must be a nonempty mapping")
    if any(not isinstance(name, str) or not name.strip() for name in space):
        raise ValueError("parameter names must be nonempty strings")
    items = tuple(sorted(space.items()))
    for name, spec in items:
        if isinstance(spec, IntRange):
            for value in (spec.low, spec.high, spec.step):
                _integer(value, name, minimum=-(2 ** 31))
                if value > 2 ** 31 - 1:
                    raise ValueError("integer search bounds must fit signed 32-bit integers")
            if spec.step <= 0 or spec.high < spec.low or (spec.high - spec.low) % spec.step:
                raise ValueError("integer bounds must align with a positive step")
        elif isinstance(spec, DecimalChoices):
            if not isinstance(spec.values, tuple) or not spec.values:
                raise ValueError("decimal candidates must be a nonempty tuple of strings")
            parsed = []
            for value in spec.values:
                if not isinstance(value, str):
                    raise TypeError("decimal candidates must be strings, never float")
                number = Decimal(value)
                _decimal(number, name)
                parsed.append(number)
            if len(set(parsed)) != len(parsed):
                raise ValueError("decimal candidates must be numerically unique")
        else:
            raise TypeError("only IntRange and DecimalChoices are supported")
    return items


def _score_float(value: Decimal) -> float:
    if not isinstance(value, Decimal):
        raise TypeError("score callback must return a dimensionless Decimal score")
    if not value.is_finite():
        raise ValueError("score must be finite")
    converted = float(value)
    if not isfinite(converted) or (value != 0 and converted == 0.0):
        raise ValueError("score cannot be represented as a finite non-underflowing float")
    return converted


def optimize(
    *, strategy_factory: Callable[[Mapping[str, int | Decimal]], Strategy],
    search_space: Mapping[str, Parameter], candles: Iterable[Candle],
    config: BacktestConfig, score: Callable[[Performance], Decimal],
    score_name: str, n_trials: int, seed: int, warmup_bars: int = 0,
    direction: str = "maximize",
) -> SearchResult:
    """Run exactly n_trials sequential ask/tell attempts (including failures).

    score_name should document the dimensionless objective/formula. The caller
    retains the strategy source and input data for replay. Seed alone does not
    guarantee identical studies across Optuna versions. Ordinary trial failures
    are recorded as FAIL and never ranked; interruptions propagate immediately.
    """
    _integer(n_trials, "n_trials", minimum=1)
    _integer(seed, "seed")
    if seed > 2 ** 32 - 1:
        raise ValueError("seed must fit unsigned 32-bit")
    if direction not in ("maximize", "minimize"):
        raise ValueError("direction must be maximize or minimize")
    if not isinstance(score_name, str) or not score_name.strip():
        raise ValueError("score_name must document the objective")
    if not callable(strategy_factory) or not callable(score):
        raise TypeError("strategy_factory and score must be callable")
    space = _call(_validate_space, search_space)
    bars = tuple(candles)
    _call(_validate, config, bars, warmup_bars)
    study = optuna.create_study(
        study_name="catos-memory", direction=direction,
        sampler=optuna.samplers.TPESampler(seed=seed),
        storage=optuna.storages.InMemoryStorage(),
    )
    records = []
    for _ in range(n_trials):
        trial = study.ask()
        params: dict[str, int | str] = {}
        raw_score = None
        performance = None
        try:
            for name, spec in space:
                if isinstance(spec, IntRange):
                    params[name] = trial.suggest_int(name, spec.low, spec.high, step=spec.step)
                else:
                    params[name] = trial.suggest_categorical(name, spec.values)
            decoded = MappingProxyType({name: Decimal(value) if isinstance(value, str) else value
                                        for name, value in params.items()})
            result = backtest(strategy=lambda: strategy_factory(decoded), candles=bars,
                              config=config, warmup_bars=warmup_bars)
            performance = result.performance
            candidate = _call(score, performance)
            if isinstance(candidate, Decimal):
                raw_score = candidate
            converted = _score_float(candidate)
        except Exception as exc:
            study.tell(trial, state=optuna.trial.TrialState.FAIL)
            records.append(TrialRecord(trial.number, "FAIL", tuple(params.items()),
                                       raw_score, None, performance,
                                       f"{type(exc).__name__}: {exc}"))
            continue
        except BaseException:
            study.tell(trial, state=optuna.trial.TrialState.FAIL)
            raise
        study.tell(trial, converted)
        records.append(TrialRecord(trial.number, "COMPLETE", tuple(params.items()),
                                   raw_score, converted, performance, None))
    best = study.best_trial.number if any(r.state == "COMPLETE" for r in records) else None
    return SearchResult(seed, direction, score_name, optuna.__version__, space,
                        config, warmup_bars, tuple(records), best)
