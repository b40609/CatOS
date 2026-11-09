"""Exact cost attribution for one research backtest, plus a buy-and-hold baseline.

Everything here is derived from a finished ``BacktestResult`` and the same bars;
nothing changes how a run trades. All money is Decimal in the research context.

price_pnl = net_pnl + fees + slippage + funding_paid: the result valued at each
fill bar's open instead of the fill price, before fees, slippage (including
adverse tick rounding) and funding. Tests check it against an independent re-run
with zero fee and zero slippage, which fills exactly at the open.

The funding scenario is an assumption, never ledger data: when a dataset's real
funding starts after the evaluation start (OKX keeps about three months), the
uncovered funding times are charged at a fixed rate on the position the engine
held at each time, marked at that bar's open, mirroring ``research._Ledger.fund``.
It is exact for strategies whose targets do not depend on balance or equity
(fixed contract quantity: SMA, Donchian, DCM daily). For equity-sized strategies
(sizing "vol_target") the assumed funding would have changed equity and later
sizes, so the scenario keeps the actual positions and is only an approximation;
results say so with EQUITY_SIZED_NOTICE.
"""

from dataclasses import dataclass, replace
from decimal import Decimal, localcontext

from catos import research

ZERO = Decimal(0)
BPS = Decimal(10_000)
HUNDRED = Decimal(100)
# A label, not a market estimate: 0.01% per 8 hours, longs pay and shorts receive.
ASSUMED_FUNDING_RATE = Decimal("0.0001")
ASSUMED_FUNDING_INTERVAL_MS = 28_800_000
SCENARIO_NOTICE = ("假設情境，不是實際帳務：資金費歷史未涵蓋的期間，以每 {hours} 小時 {rate}% 固定費率、"
                   "多單支付／空單收取，按當時部位與 K 線開盤價估算。")


EQUITY_SIZED_NOTICE = "部位依權益調整的策略，假設資金費會改變權益與之後的張數，這裡沿用實際部位，只是近似值。"


@dataclass(frozen=True)
class BuyHold:
    quantity: Decimal
    entry_open: Decimal
    exit_close: Decimal
    pnl: Decimal
    underlying_return_pct: Decimal


@dataclass(frozen=True)
class FundingScenario:
    rate: Decimal
    interval_ms: int
    uncovered_start_ms: int
    uncovered_end_ms: int
    events: int
    assumed_paid: Decimal  # positive is a debit
    net_pnl_with_assumption: Decimal
    notice: str


@dataclass(frozen=True)
class CostBreakdown:
    price_pnl: Decimal
    fees: Decimal
    slippage: Decimal
    funding_paid: Decimal
    net_pnl: Decimal
    traded_notional: Decimal
    fill_count: int
    cost_bps_per_side: Decimal | None
    break_even_bps_per_side: Decimal | None
    buy_hold: BuyHold
    funding_scenario: FundingScenario | None


def _scenario(result, bars, uncovered_end_ms, rate, interval_ms):
    start, end = result.evaluation_start_ms, min(result.evaluation_end_ms, uncovered_end_ms)
    first = -(-start // interval_ms) * interval_ms
    opens = {bar.open_time_ms: bar.open for bar in bars}
    per_contract = result.config.contract.base_per_contract
    trades = result.trades
    index, position, paid, events = 0, ZERO, ZERO, 0
    times = list(range(first, end, interval_ms))
    # The engine also settles an event exactly at the last bar's close (the
    # evaluation end) when the data has one there, e.g. a walk-forward window cut
    # from a longer dataset; mirror it while that time is still uncovered.
    last = result.evaluation_end_ms
    if last < uncovered_end_ms and last % interval_ms == 0 and last in opens:
        times.append(last)
    # The engine settles a funding time before the fill at the same bar open, so
    # the position at time t is the one left by fills strictly before t.
    for time_ms in times:
        while index < len(trades) and trades[index].time_ms < time_ms:
            position = trades[index].position_after
            index += 1
        if time_ms not in opens:
            raise ValueError("funding_scenario_time_without_candle")
        paid += position * per_contract * opens[time_ms] * rate
        events += 1
    hours = Decimal(interval_ms) / Decimal(3_600_000)
    notice = SCENARIO_NOTICE.format(hours=hours.normalize(), rate=(rate * HUNDRED).normalize())
    return FundingScenario(rate, interval_ms, start, end, events, paid,
                           result.performance.net_pnl - paid, notice)


def cost_breakdown(result, bars, quantity, funding_from_ms=None, *,
                   rate=ASSUMED_FUNDING_RATE, interval_ms=ASSUMED_FUNDING_INTERVAL_MS, equity_sized=False):
    """Attribution of one run.

    bars: the candles the run used (warm-up included); quantity: the strategy's
    contract quantity, reused for the buy-and-hold baseline. funding_from_ms: the
    dataset's first real funding time; None means no scenario (complete funding,
    or a synthetic dataset that states funding is explicitly empty).
    """
    if not isinstance(result, research.BacktestResult):
        raise TypeError("result must be BacktestResult")
    with localcontext(research._CONTEXT):
        opens = {bar.open_time_ms: bar.open for bar in bars}
        per_contract = result.config.contract.base_per_contract
        slippage = notional = ZERO
        for trade in result.trades:
            if trade.time_ms not in opens:
                raise ValueError("trade_time_without_candle")
            size = abs(trade.quantity) * per_contract
            slippage += abs(trade.price - opens[trade.time_ms]) * size
            notional += size * trade.price
        performance = result.performance
        price_pnl = performance.net_pnl + performance.fees + slippage + performance.funding_paid
        cost_bps = break_even = None
        if notional:
            cost_bps = (performance.fees + slippage) / notional * BPS
            break_even = (price_pnl - performance.funding_paid) / notional * BPS
        evaluated = [bar for bar in bars if result.evaluation_start_ms <= bar.open_time_ms < result.evaluation_end_ms]
        entry, exit_ = evaluated[0].open, evaluated[-1].close
        buy_hold = BuyHold(quantity, entry, exit_, quantity * per_contract * (exit_ - entry),
                           (exit_ / entry - 1) * HUNDRED)
        scenario = None
        if funding_from_ms is not None and funding_from_ms > result.evaluation_start_ms:
            scenario = _scenario(result, bars, funding_from_ms, rate, interval_ms)
            if not scenario.events:
                scenario = None
            elif equity_sized:
                # Sizes follow equity, which the assumed funding would have changed slightly.
                scenario = replace(scenario, notice=scenario.notice + EQUITY_SIZED_NOTICE)
        return CostBreakdown(price_pnl, performance.fees, slippage, performance.funding_paid,
                             performance.net_pnl, notional, len(result.trades), cost_bps, break_even,
                             buy_hold, scenario)


def total(breakdowns):
    """Sum of independent runs (walk-forward OOS windows); ratios recomputed on the sums.

    The buy-and-hold baseline is summed per window (each window re-enters at its
    own first open), matching how the windows themselves are evaluated.
    """
    rows = [row for row in breakdowns if row is not None]
    if not rows:
        return None
    with localcontext(research._CONTEXT):
        def add(field):
            return sum((getattr(row, field) for row in rows), ZERO)
        notional, fees, slippage = add("traded_notional"), add("fees"), add("slippage")
        price_pnl, funding = add("price_pnl"), add("funding_paid")
        scenarios = [row.funding_scenario for row in rows if row.funding_scenario is not None]
        return {
            "windows": len(rows), "price_pnl": price_pnl, "fees": fees, "slippage": slippage,
            "funding_paid": funding, "net_pnl": add("net_pnl"), "traded_notional": notional,
            "fill_count": sum(row.fill_count for row in rows),
            "cost_bps_per_side": (fees + slippage) / notional * BPS if notional else None,
            "break_even_bps_per_side": (price_pnl - funding) / notional * BPS if notional else None,
            "buy_hold_pnl": sum((row.buy_hold.pnl for row in rows), ZERO),
            "assumed_funding_paid": sum((item.assumed_paid for item in scenarios), ZERO) if scenarios else None,
            "assumed_funding_events": sum(item.events for item in scenarios) if scenarios else None,
        }


REPORT_ROWS = (
    ("price_pnl", "價格損益（成本前，以成交 K 線開盤價計）"), ("fees", "手續費"),
    ("slippage", "滑價（含價格取整）"), ("funding_paid", "資金費（資料集實際，正為支出）"),
    ("net_pnl", "淨損益"), ("traded_notional", "成交名目"), ("fill_count", "成交筆數"),
    ("cost_bps_per_side", "每邊成本 bps（手續費＋滑價）"),
    ("break_even_bps_per_side", "每邊兩平成本 bps（淨損益為 0 時可承受的手續費＋滑價）"),
)
