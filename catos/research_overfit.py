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


WIPED_OUT_NOTICE = ("權益曾跌到 0 以下或被強平（爆倉）：沒有保證金模型時，跌破 0 之後的損益只是算術延伸；"
                    "有保證金模型時，強平後權益為 0 並停止交易。"
                    "報酬率改變正負號或除以接近 0 的權益，Sharpe、PSR／DSR、PBO、bootstrap 等比率統計都沒有意義，所以不計算。")
LIQUIDATION_NOTICE = ("被強平（保證金模型）：權益跌到維持保證金加強平手續費時，以強平價平倉、扣強平手續費與清算費，"
                      "權益歸 0 並停止交易。已收盤 K 線看不出先碰高點或低點，一律假設先碰不利的一端，會高估強平。")


def first_non_positive(equity_curve):
    """Index of the first close-marked equity point <= 0 (account wiped out), or None."""
    return next((index for index, point in enumerate(equity_curve) if point.equity <= 0), None)


def bar_returns(equity_curve):
    """Simple returns between consecutive close-marked equity points (Decimal ratio, then float).

    Refuses a curve whose equity ever reaches <= 0 (see WIPED_OUT_NOTICE).
    """
    if first_non_positive(equity_curve) is not None:
        raise ValueError("equity_not_positive")
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
    # lambda == 0 (winner exactly at the OOS median) counts as overfit, as in R pbo and
    # fynance; its share is reported because with few candidates it moves PBO a lot.
    return {"pbo": sum(value <= 0 for value in logits) / len(logits), "logit_median": median,
            "prob_oos_loss": losses / len(logits), "splits": len(logits), "blocks": blocks,
            "bars_per_block": size, "logit_zero_share": sum(value == 0 for value in logits) / len(logits)}


def _fmt(value, digits=4):
    if value is None:
        return None
    if not isfinite(value):
        raise ValueError("non-finite statistic")
    return f"{value:.{digits}f}"


COARSE_TRIALS = 10  # Bailey et al. 2017 ask for many more candidates than this


def verdict(dsr, pbo, trials=None, wiped_out=0, best_wiped_out=False):
    """trials: candidates that entered PBO (wiped-out trials excluded); only used for the coarse-PBO note."""
    wiped = (f"有 {wiped_out} 組參數權益跌破 0（爆倉），它們的比率統計沒有意義，不計入 Sharpe 變異數與 PBO，"
             "但仍計入試驗數 N。") if wiped_out else ""
    if best_wiped_out:
        return "最佳參數權益跌破 0（爆倉），無法計算 DSR。" + wiped
    if dsr is None and wiped_out and trials is not None and trials < 2:
        return "沒爆倉的參數組不到 2 組，無法估計 Sharpe 變異數，DSR 不計算。" + wiped
    if dsr is None:
        return "樣本不足或報酬分布退化，無法計算 DSR。" + wiped
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
        reasons = []
        if trials is not None and trials < COARSE_TRIALS:
            reasons.append(f"只有 {trials} 組參數")
        if pbo["logit_zero_share"] >= 0.1:
            reasons.append(f"有 {pbo['logit_zero_share']:.0%} 的切法剛好落在中位數")
        if reasons:
            parts.append(f"注意：{'、'.join(reasons)}，PBO 粒度很粗；換一組試驗或改用完整格點，數字可能差很多，只能當參考。")
    return "".join(parts) + wiped


def search_report(candidates, best_params, timeframe_ms):
    """Overfitting summary for one search.

    candidates: {params tuple: BacktestResult} for every distinct completed trial,
    all run on the same bars and warm-up. best_params: the selected trial.

    A trial whose equity reaches <= 0 is wiped out: it still counts in N (it was
    tried), but its Sharpe is not computed and it is left out of the cross-trial
    Sharpe variance and of PBO. If the selected trial itself is wiped out, DSR
    and PSR are None. If fewer than two trials survive out of two or more, the
    variance cannot be estimated, so DSR is None as well (it would otherwise fall
    back to PSR against 0 and ignore N; acceptance N5, 2026-11-08).
    """
    names = list(candidates)
    lengths = {len(candidates[params].equity_curve) for params in names}
    if len(lengths) != 1:
        raise ValueError("trials must share the same evaluation bars")
    wiped = {params for params in names if first_non_positive(candidates[params].equity_curve) is not None}
    alive = [params for params in names if params not in wiped]
    returns = {params: bar_returns(candidates[params].equity_curve) for params in alive}
    stats = {params: moments(returns[params]) for params in alive}
    sharpes = {params: (item.mean / item.std if item.std else 0.0) for params, item in stats.items()}
    trials = len(names)
    mean_sr = sum(sharpes.values()) / len(alive) if alive else 0.0
    variance = (sum((value - mean_sr) ** 2 for value in sharpes.values()) / (len(alive) - 1)
                if len(alive) > 1 else 0.0)
    benchmark = expected_max_sharpe(variance, trials)
    best = sharpes.get(best_params)
    best_stats = stats.get(best_params)
    variance_known = len(alive) >= 2 or trials < 2
    dsr = None if best is None or not variance_known else probabilistic_sharpe(best, benchmark, best_stats)
    psr = None if best is None else probabilistic_sharpe(best, 0.0, best_stats)
    pbo = pbo_cscv([returns[params] for params in alive]) if len(alive) >= 2 else None
    per_year = sqrt(YEAR_MS / timeframe_ms)

    def annualized(value):
        return None if value is None else _fmt(value * per_year, 3)

    return {
        "method": "deflated_sharpe_bailey_lopez_de_prado_2014; pbo_cscv_bailey_et_al_2017",
        "distinct_trials": trials, "bars": lengths.pop() - 1,
        "wiped_out_trials": len(wiped),
        "best": {"params": [[name, value] for name, value in best_params],
                 "wiped_out": best_params in wiped,
                 "sharpe_per_bar": _fmt(best, 6), "sharpe_annualized": annualized(best),
                 "skew": None if best_stats is None else _fmt(best_stats.skew, 3),
                 "kurtosis": None if best_stats is None else _fmt(best_stats.kurtosis, 3)},
        # None when fewer than two trials survive a search: the variance is unknown, not 0 (acceptance P2).
        "trial_sharpe_variance": _fmt(variance, 8) if variance_known else None,
        "expected_max_sharpe_per_bar": _fmt(benchmark, 6) if variance_known else None,
        "expected_max_sharpe_annualized": _fmt(benchmark * per_year, 3) if variance_known else None,
        "psr_vs_zero": _fmt(psr), "dsr": _fmt(dsr),
        "pbo": None if pbo is None else {**pbo, "pbo": _fmt(pbo["pbo"]),
                                         "logit_median": _fmt(pbo["logit_median"]),
                                         "prob_oos_loss": _fmt(pbo["prob_oos_loss"]),
                                         "logit_zero_share": _fmt(pbo["logit_zero_share"])},
        "trials": [{"params": [[name, value] for name, value in params],
                    "sharpe_annualized": annualized(sharpes.get(params)),
                    "wiped_out": params in wiped} for params in names],
        "verdict": verdict(dsr, pbo, len(alive), len(wiped), best_params in wiped),
        "notice": NOTICE + (WIPED_OUT_NOTICE if wiped else ""),
    }


def edge_selections(windows, search_space):
    """How often walk-forward picked a parameter at the edge of its searched range.

    windows: (number, selected params as (name, value) pairs or None). A choice on
    the boundary means the best value may lie outside the range, and widening the
    range is another search on the same data. Parameters with at most two values
    (an on/off switch) are always on a boundary, so they are listed as excluded.
    """
    excluded = [name for name, bounds in search_space.items()
                if (bounds["high"] - bounds["low"]) // bounds["step"] + 1 <= 2]
    search_space = {name: bounds for name, bounds in search_space.items() if name not in excluded}
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
            "excluded_switch_params": excluded,
            "notice": "選定參數落在搜尋範圍邊界時，最佳值可能在範圍外；放寬範圍等於在同一份資料上再搜尋一次，試驗數要累計。"}
