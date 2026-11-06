"""Overfitting checks for a parameter search: Deflated Sharpe Ratio and PBO (CSCV).

Statistics only: returns, Sharpe ratios and probabilities are floats here and are
reported as fixed-digit strings. They never feed back into money, fills or the
ledger, which stay Decimal in ``catos.research``.

- Deflated Sharpe Ratio (Bailey and Lopez de Prado, 2014, JPM 40(5)): the
  probability that the selected trial's true Sharpe exceeds the maximum Sharpe
  expected from N unskilled trials, corrected for sample length, skewness and
  kurtosis.
- Probability of Backtest Overfitting via combinatorially symmetric
  cross-validation (Bailey, Borwein, Lopez de Prado and Zhu, 2017): split the
  bars into S contiguous blocks, use every half as in-sample, and count how often
  the in-sample winner ranks at or below the median out of sample. The metric is
  the sum of bar returns, the same ordering as the search objective (return_pct).

N is the number of distinct parameter sets evaluated in this run only. Searches
run earlier on the same data are not counted, so N is a lower bound and the DSR
an upper bound.
"""

from dataclasses import dataclass
from decimal import localcontext
from itertools import combinations
from math import e, isfinite, log, sqrt
from statistics import NormalDist

from catos import research

EULER_GAMMA = 0.5772156649015329
NORMAL = NormalDist()
PBO_BLOCKS = 8  # C(8, 4) = 70 splits
MIN_BARS_PER_BLOCK = 50
YEAR_MS = 365 * 86_400_000
NOTICE = ("統計量以浮點計算，只供研究判讀，不是金額。N 只計本次執行評估過的不同參數組；"
          "同一份資料過去的搜尋沒有計入，所以 DSR 是上限、實際應更低。")


def bar_returns(equity_curve):
    """Simple returns between consecutive close-marked equity points (Decimal ratio, then float)."""
    with localcontext(research._CONTEXT):
        return [float(after.equity / before.equity - 1)
                for before, after in zip(equity_curve, equity_curve[1:])]


@dataclass(frozen=True)
class Moments:
    count: int
    mean: float
    std: float
    skew: float
    kurtosis: float  # non-excess: 3 for a normal distribution


def moments(returns):
    count = len(returns)
    if count < 3:
        raise ValueError("at least three returns are required")
    mean = sum(returns) / count
    deviations = [value - mean for value in returns]
    m2 = sum(d * d for d in deviations) / count
    if m2 == 0:
        return Moments(count, mean, 0.0, 0.0, 3.0)
    m3 = sum(d ** 3 for d in deviations) / count
    m4 = sum(d ** 4 for d in deviations) / count
    std = sqrt(sum(d * d for d in deviations) / (count - 1))
    return Moments(count, mean, std, m3 / m2 ** 1.5, m4 / m2 ** 2)


def sharpe(returns):
    """Per-bar Sharpe (no risk-free rate, no annualization); 0 when the series is flat."""
    stats = moments(returns)
    return stats.mean / stats.std if stats.std else 0.0


def expected_max_sharpe(variance, trials):
    """Expected maximum of `trials` unskilled Sharpe estimates with the given cross-trial variance."""
    if trials < 2 or variance <= 0:
        return 0.0
    return sqrt(variance) * ((1 - EULER_GAMMA) * NORMAL.inv_cdf(1 - 1 / trials)
                             + EULER_GAMMA * NORMAL.inv_cdf(1 - 1 / (trials * e)))


def probabilistic_sharpe(observed, benchmark, stats):
    """P(true Sharpe > benchmark) given the observed per-bar Sharpe and its return moments."""
    denominator = 1 - stats.skew * observed + (stats.kurtosis - 1) / 4 * observed ** 2
    if denominator <= 0 or stats.count < 2:
        return None
    return NORMAL.cdf((observed - benchmark) * sqrt(stats.count - 1) / sqrt(denominator))


def _average_ranks(values):
    """1-based ranks, ties get their average rank (scipy rankdata 'average')."""
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start
        while end + 1 < len(order) and values[order[end + 1]] == values[order[start]]:
            end += 1
        for position in range(start, end + 1):
            ranks[order[position]] = (start + end) / 2 + 1
        start = end + 1
    return ranks


def pbo_cscv(series, blocks=PBO_BLOCKS):
    """PBO over equal-length return series (one per candidate), or None when too short.

    Blocks are contiguous; the first ``len % blocks`` bars are dropped so every
    block has the same length. Returns the PBO, the median logit, the share of
    splits where the in-sample winner loses out of sample, and the split count.
    """
    if len(series) < 2 or blocks % 2 or blocks < 2:
        return None
    length = len(series[0])
    if any(len(item) != length for item in series):
        raise ValueError("candidate return series must have equal length")
    size = length // blocks
    if size < MIN_BARS_PER_BLOCK:
        return None
    offset = length - size * blocks
    sums = [[sum(item[offset + b * size: offset + (b + 1) * size]) for b in range(blocks)] for item in series]
    logits, losses = [], 0
    for chosen in combinations(range(blocks), blocks // 2):
        rest = [b for b in range(blocks) if b not in chosen]
        in_sample = [sum(row[b] for b in chosen) for row in sums]
        out_sample = [sum(row[b] for b in rest) for row in sums]
        winner = max(range(len(series)), key=lambda index: (in_sample[index], -index))
        relative = _average_ranks(out_sample)[winner] / (len(series) + 1)
        logits.append(log(relative / (1 - relative)))
        losses += out_sample[winner] < 0
    logits.sort()
    middle = len(logits) // 2
    median = logits[middle] if len(logits) % 2 else (logits[middle - 1] + logits[middle]) / 2
    return {"pbo": sum(value <= 0 for value in logits) / len(logits), "logit_median": median,
            "prob_oos_loss": losses / len(logits), "splits": len(logits), "blocks": blocks,
            "bars_per_block": size}


def _fmt(value, digits=4):
    if value is None:
        return None
    if not isfinite(value):
        raise ValueError("non-finite statistic")
    return f"{value:.{digits}f}"


def verdict(dsr, pbo):
    if dsr is None:
        return "樣本不足或報酬分布退化，無法計算 DSR。"
    parts = []
    if dsr >= 0.95:
        parts.append("DSR ≥ 0.95：扣掉多重試驗與非常態後，最佳參數的 Sharpe 仍顯著高於純運氣可得的最大值。")
    elif dsr >= 0.5:
        parts.append("DSR 介於 0.5 與 0.95：有跡象但不顯著，不能排除只是挑到運氣最好的一組。")
    else:
        parts.append("DSR < 0.5：最佳參數的 Sharpe 低於純運氣在這麼多組裡可期待的最大值，很可能是過擬合。")
    if pbo is not None:
        if pbo["pbo"] > 0.5:
            parts.append("PBO > 0.5：樣本內選出的冠軍，樣本外多半排在中位數以下。")
        elif pbo["pbo"] > 0.2:
            parts.append("PBO 介於 0.2 與 0.5：選參過程有一定機率選到樣本外不佳的組合。")
        else:
            parts.append("PBO ≤ 0.2：樣本內冠軍在樣本外通常仍排在前段。")
    return "".join(parts)


def search_report(candidates, best_params, timeframe_ms):
    """Overfitting summary for one search.

    candidates: {params tuple: BacktestResult} for every distinct completed trial,
    all run on the same bars and warm-up. best_params: the selected trial.
    """
    names = list(candidates)
    returns = {params: bar_returns(candidates[params].equity_curve) for params in names}
    lengths = {len(item) for item in returns.values()}
    if len(lengths) != 1:
        raise ValueError("trials must share the same evaluation bars")
    stats = {params: moments(returns[params]) for params in names}
    sharpes = {params: (item.mean / item.std if item.std else 0.0) for params, item in stats.items()}
    trials = len(names)
    mean_sr = sum(sharpes.values()) / trials
    variance = sum((value - mean_sr) ** 2 for value in sharpes.values()) / (trials - 1) if trials > 1 else 0.0
    best = sharpes[best_params]
    benchmark = expected_max_sharpe(variance, trials)
    best_stats = stats[best_params]
    dsr = probabilistic_sharpe(best, benchmark, best_stats)
    psr = probabilistic_sharpe(best, 0.0, best_stats)
    pbo = pbo_cscv([returns[params] for params in names]) if trials >= 2 else None
    per_year = sqrt(YEAR_MS / timeframe_ms)
    return {
        "method": "deflated_sharpe_bailey_lopez_de_prado_2014; pbo_cscv_bailey_et_al_2017",
        "distinct_trials": trials, "bars": best_stats.count,
        "best": {"params": [[name, value] for name, value in best_params],
                 "sharpe_per_bar": _fmt(best, 6), "sharpe_annualized": _fmt(best * per_year, 3),
                 "skew": _fmt(best_stats.skew, 3), "kurtosis": _fmt(best_stats.kurtosis, 3)},
        "trial_sharpe_variance": _fmt(variance, 8),
        "expected_max_sharpe_per_bar": _fmt(benchmark, 6),
        "expected_max_sharpe_annualized": _fmt(benchmark * per_year, 3),
        "psr_vs_zero": _fmt(psr), "dsr": _fmt(dsr),
        "pbo": None if pbo is None else {**pbo, "pbo": _fmt(pbo["pbo"]),
                                         "logit_median": _fmt(pbo["logit_median"]),
                                         "prob_oos_loss": _fmt(pbo["prob_oos_loss"])},
        "trials": [{"params": [[name, value] for name, value in params],
                    "sharpe_annualized": _fmt(sharpes[params] * per_year, 3)} for params in names],
        "verdict": verdict(dsr, pbo),
        "notice": NOTICE,
    }


def edge_selections(windows, search_space):
    """How often walk-forward picked a parameter at the edge of its searched range.

    windows: (number, selected params as (name, value) pairs or None). A choice on
    the boundary means the best value may lie outside the range, and widening the
    range is another search on the same data.
    """
    counts = {name: {"at_low": 0, "at_high": 0} for name in search_space}
    selected = [(number, dict(params)) for number, params in windows if params]
    edge_windows = 0
    for _, params in selected:
        hit = False
        for name, bounds in search_space.items():
            if params[name] == bounds["low"]:
                counts[name]["at_low"] += 1
                hit = True
            if params[name] == bounds["high"]:
                counts[name]["at_high"] += 1
                hit = True
        edge_windows += hit
    return {"windows_with_selection": len(selected), "windows_at_edge": edge_windows, "params": counts,
            "notice": "選定參數落在搜尋範圍邊界時，最佳值可能在範圍外；放寬範圍等於在同一份資料上再搜尋一次，試驗數要累計。"}
