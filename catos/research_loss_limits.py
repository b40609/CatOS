"""Diagnostic: how many Taipei days of one backtest would hit the account Soft/Hard daily-loss limits.

Read-only over a finished BacktestResult; it changes no fill, position or PnL and
does not simulate the latch (a latched account would stop trading for the day).
Because the live latch only clears by hand, each triggered day is one manual
intervention the user would have had to make.

Day rule (R1, AGENTS.md INVARIANTS): Asia/Taipei 00:00 (UTC+08:00) days, via
risk.taipei_day; a bar belongs to the day of its open time.
Denominator: the equity at the open of the day's first evaluated bar, before
that open's fill (the previous position repriced at the open, after any funding
settled at that open).
Day low: per bar, the post-fill position valued at the bar's adverse extreme
(long: low, short: high; the same convention as the margin model), with the
balance before close-time funding; and the close equity after that funding.
Day loss = (denominator - day low) / denominator; a limit triggers when the loss
is >= the limit, the same comparison as risk.loss_reasons (loss <= -limit).
A day whose low reaches <= 0 (a liquidation, or without the margin model equity
at or below zero) counts as triggered for every limit and ends the count.
Formulas and choices: docs/research-loss-limits.md.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext

from catos import research

ZERO = Decimal("0")
HUNDRED = Decimal("100")
DAYS_PER_YEAR = Decimal("365")
MAX_LISTED_DAYS = 50
# The defaults before 2026-11-14 (risk.LEGACY_LIMITS), shown for comparison only.
LEGACY_SOFT = Decimal("0.10")
LEGACY_HARD = Decimal("0.20")
_TAIPEI = timezone(timedelta(hours=8))
_PCT = Decimal("0.0001")
_YEAR = Decimal("0.01")

NOTICE = (
    "純診斷：不改變成交、部位與損益，也不模擬鎖存；實盤觸發後當天會停止增倉或清倉，之後的數字會不同。",
    "回測沒有套用單幣曝險上限（現行預設 0.5 倍權益），部位大小照策略本身。",
    "切日依 Asia/Taipei 00:00（UTC+8）；分母是當日第一根 K 線開盤時、成交前的權益；"
    "最低權益用每根 K 線的最不利價估（多單最低價、空單最高價），會高估觸發次數。",
    "首日與末日可能只涵蓋部分時段；權益歸零（強平）的那天算觸發，之後不再計數。",
)


def _date(day):
    return (datetime(1970, 1, 1, tzinfo=_TAIPEI) + timedelta(days=day)).date().isoformat()


def _pct(ratio):
    return (ratio * HUNDRED).quantize(_PCT)


def daily_lows(result, bars):
    """[(taipei_day, basis, low, low_time_ms, wiped)] per evaluated day, up to the first wiped day.

    bars are the run's full input (warm-up first); curve[k + 1] is the close of
    evaluation bar k. Also returns the count of bars that straddle a Taipei midnight.
    """
    from catos import risk  # lazy: risk -> ipc -> strategy_registry -> research_catalog

    per_contract = result.config.contract.base_per_contract
    timeframe = result.config.timeframe_ms
    evaluation = tuple(bars)[result.warmup_bars:]
    curve = result.equity_curve
    if len(curve) != len(evaluation) + 1:
        raise ValueError("equity curve does not match the evaluation bars")
    liquidation_bar = None if result.liquidation is None else result.liquidation.bar_open_time_ms
    payments = result.funding
    cursor = 0
    days = []
    straddling = 0
    current = None  # [day, basis, low, low_time_ms, wiped]
    with localcontext(research._CONTEXT):
        for index, bar in enumerate(evaluation):
            close_time = bar.open_time_ms + timeframe
            open_paid = ZERO
            while cursor < len(payments) and payments[cursor].time_ms <= bar.open_time_ms:
                open_paid += payments[cursor].amount_paid
                cursor += 1
            close_paid = ZERO
            while cursor < len(payments) and payments[cursor].time_ms <= close_time:
                close_paid += payments[cursor].amount_paid
                cursor += 1
            day = risk.taipei_day(bar.open_time_ms)
            if risk.taipei_day(close_time - 1) != day:
                straddling += 1
            if current is None or current[0] != day:
                if current is not None:
                    days.append(tuple(current))
                before = curve[index]
                basis = (before.balance - open_paid
                         + before.position * per_contract * (bar.open - before.average_entry))
                current = [day, basis, basis, bar.open_time_ms, False]
            after = curve[index + 1]
            low = after.equity
            if after.position != ZERO:
                adverse = bar.low if after.position > ZERO else bar.high
                at_adverse = (after.balance + close_paid
                              + after.position * per_contract * (adverse - after.average_entry))
                low = min(low, at_adverse)
            if low < current[2]:
                current[2], current[3] = low, bar.open_time_ms
            if low <= ZERO or bar.open_time_ms == liquidation_bar:
                current[4] = True
                break
    if current is not None:
        days.append(tuple(current))
    return days, straddling


def _limit_summary(days, losses, limit, span_days):
    hits = [(day, loss) for (day, *_rest), loss in zip(days, losses) if loss >= limit or _rest[3]]
    with localcontext(research._CONTEXT):
        per_year = (Decimal(len(hits)) * DAYS_PER_YEAR / Decimal(span_days)).quantize(_YEAR) if span_days else None
    return {
        "limit_pct": _pct(limit), "days": len(hits), "per_year": per_year,
        "first_day": _date(hits[0][0]) if hits else None,
        "listed": [{"day": _date(day), "loss_pct": _pct(loss)} for day, loss in hits[:MAX_LISTED_DAYS]],
        "truncated": len(hits) > MAX_LISTED_DAYS,
    }


def summary(result, bars):
    """JSON-ready trigger counts for the current risk.Limits defaults and the pre-2026-11-14 ones.

    Results archived before 2026-11-14 carry key "proposed" (5%/10%, then not applied)
    where this has "legacy" (10%/20%); the UI shows each result's own labels."""
    from catos import risk

    days, straddling = daily_lows(result, bars)
    defaults = risk.Limits()
    with localcontext(research._CONTEXT):
        losses = [(basis - low) / basis if basis > ZERO else Decimal("1") for _, basis, low, _, _ in days]
    span_days = days[-1][0] - days[0][0] + 1 if days else 0
    worst = max(range(len(days)), key=lambda i: (losses[i], -i)) if days else None
    stopped = next((day for day in days if day[4]), None)
    sets = (
        ("current", "現行預設（catos/risk.py）", True, defaults.soft_loss, defaults.hard_loss),
        ("legacy", "舊預設（2026-11-14 前），只供對照", False, LEGACY_SOFT, LEGACY_HARD),
    )
    return {
        "method": "taipei_day_open_basis_adverse_extreme_v1",
        "days_evaluated": len(days),
        "span_days": span_days,
        "years": (Decimal(span_days) / DAYS_PER_YEAR).quantize(_YEAR) if span_days else None,
        "first_day": _date(days[0][0]) if days else None,
        "last_day": _date(days[-1][0]) if days else None,
        "max_daily_loss": None if worst is None else {
            "day": _date(days[worst][0]), "loss_pct": _pct(losses[worst]),
            "basis": days[worst][1], "low_equity": days[worst][2], "low_bar_open_ms": days[worst][3],
        },
        "stopped": None if stopped is None else {
            "day": _date(stopped[0]),
            "reason": "liquidation" if result.liquidation is not None else "equity_non_positive",
        },
        "straddling_bars": straddling,
        "thresholds": [
            {"key": key, "label": label, "applied_to_risk": applied,
             "soft": _limit_summary(days, losses, soft, span_days),
             "hard": _limit_summary(days, losses, hard, span_days)}
            for key, label, applied, soft, hard in sets
        ],
        "max_listed_days": MAX_LISTED_DAYS,
        "notice": list(NOTICE),
    }


def report_rows(value):
    """Rows for the HTML report table (value = summary() or its JSON form)."""
    rows = [("評估天數", f"{value['days_evaluated']} 天（{value['first_day']} 至 {value['last_day']}，台北日）")]
    worst = value["max_daily_loss"]
    if worst is not None:
        rows.append(("最大單日虧損", f"{worst['loss_pct']}%（{worst['day']}）"))
    if value["stopped"] is not None:
        rows.append(("停止計數", f"{value['stopped']['day']} 權益歸零（{value['stopped']['reason']}）"))
    for item in value["thresholds"]:
        for name in ("soft", "hard"):
            limit = item[name]
            days = "、".join(entry["day"] for entry in limit["listed"]) + ("……" if limit["truncated"] else "")
            rows.append((f"{item['label']} {name.capitalize()} {limit['limit_pct']}%",
                         f"{limit['days']} 天，每年 {limit['per_year']} 天，首次 {limit['first_day'] or '—'}"
                         + (f"；{days}" if days else "")))
    if value["straddling_bars"]:
        rows.append(("跨台北午夜的 K 線", f"{value['straddling_bars']} 根，歸入開盤所在的日"))
    rows.extend(("說明", line) for line in value["notice"])
    return rows
