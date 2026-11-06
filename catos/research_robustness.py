"""Robustness checks for one research run: per-year results, delayed fills, bootstrap.

Money stays Decimal (per-year PnL); return statistics (Sharpe, bootstrap) are
floats reported as fixed-digit strings and never feed back into the ledger.

- yearly: equity change and buy-and-hold change per UTC calendar year.
- Delayed: wraps a strategy so every target takes effect one bar later (decided
  at bar t's close, filled at bar t+2's open instead of t+1's). A real edge
  should survive one bar of delay; one that vanishes was probably timing noise
  or leaned on the exact fill bar.
- daily_returns / block_bootstrap: close-marked equity sampled at UTC day ends,
  resampled in contiguous blocks (moving-block bootstrap) to keep short-range
  dependence; reports a confidence interval for the mean daily return and the
  share of resamples whose mean is not positive.
"""

from datetime import datetime, timezone
from decimal import Decimal, localcontext
import random
from math import sqrt

from catos import research

DAY_MS = 86_400_000
ZERO = Decimal(0)


def _year(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).year


def yearly(result, bars, buy_hold_quantity):
    """Per UTC year: strategy equity change and same-quantity buy-and-hold price change.

    The equity point at a time belongs to the year of that time; a year starts
    from the previous year's last point (the initial balance for the first).
    Buy-and-hold goes from the first evaluated open in the year to the last close.
    """
    per_contract = result.config.contract.base_per_contract
    evaluated = [bar for bar in bars
                 if result.evaluation_start_ms <= bar.open_time_ms < result.evaluation_end_ms]
    rows = []
    with localcontext(research._CONTEXT):
        previous = result.equity_curve[0].equity
        for year in sorted({_year(point.time_ms - 1) for point in result.equity_curve[1:]}):
            points = [p for p in result.equity_curve[1:] if _year(p.time_ms - 1) == year]
            in_year = [bar for bar in evaluated if _year(bar.open_time_ms) == year]
            end = points[-1].equity
            hold = (buy_hold_quantity * per_contract * (in_year[-1].close - in_year[0].open)
                    if in_year else ZERO)
            rows.append({"year": year, "start_equity": previous, "end_equity": end,
                         "net_pnl": end - previous, "return_pct": (end / previous - 1) * 100,
                         "buy_hold_pnl": hold,
                         "underlying_return_pct": ((in_year[-1].close / in_year[0].open - 1) * 100
                                                   if in_year else None)})
            previous = end
    return rows


class Delayed(research.Strategy):
    """Emit each target one bar after the wrapped strategy decides it."""

    def __init__(self, inner):
        self.inner = inner
        self.pending = None

    @property
    def ready(self):
        return self.inner.ready

    def update_indicators(self, bar):
        return self.inner.update_indicators(bar)

    def on_bar(self, bar, account):
        decided = self.inner.on_bar(bar, account)
        emitted, self.pending = self.pending, decided
        return emitted


def daily_returns(result):
    """Simple returns between equity at consecutive UTC day ends (bar closes on midnight)."""
    with localcontext(research._CONTEXT):
        marks = [point for point in result.equity_curve[1:] if point.time_ms % DAY_MS == 0]
        start = result.equity_curve[0]
        series = ([start] if start.time_ms % DAY_MS == 0 else []) + marks
        return [float(after.equity / before.equity - 1) for before, after in zip(series, series[1:])]


def sharpe_annualized(returns, periods_per_year=365):
    if len(returns) < 3:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    return mean / sqrt(variance) * sqrt(periods_per_year) if variance > 0 else 0.0


def block_bootstrap(returns, *, block=20, samples=2000, seed=20261106):
    """Moving-block bootstrap of the mean daily return (fixed seed, reproducible)."""
    count = len(returns)
    if count < 2 * block:
        return None
    rng = random.Random(seed)
    starts = count - block + 1
    means = []
    for _ in range(samples):
        drawn = []
        while len(drawn) < count:
            begin = rng.randrange(starts)
            drawn.extend(returns[begin:begin + block])
        means.append(sum(drawn[:count]) / count)
    means.sort()
    return {"block_days": block, "samples": samples, "seed": seed, "days": count,
            "mean_daily_return": f"{sum(returns) / count:.6f}",
            "ci95_low": f"{means[int(0.025 * samples)]:.6f}",
            "ci95_high": f"{means[int(0.975 * samples) - 1]:.6f}",
            "share_not_positive": f"{sum(value <= 0 for value in means) / samples:.4f}"}
