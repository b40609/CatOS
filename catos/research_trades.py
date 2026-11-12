"""Round trips and win-rate statistics for one research backtest (Decimal, exact).

A round trip opens when the position leaves zero and closes when it returns to
zero; a reversal closes one trip and opens the next in the same fill. Every
fill's realized PnL, every fee and every funding payment belongs to exactly one
trip, so the closed trips plus the open one (with its unrealized PnL) add up to
the run's net PnL; that identity is checked, not assumed. Sums use a 120-digit
context; the engine's own 50-digit running balance can differ from the exact sum
by a rounding residual (non-terminating average entries after scaling in, or a
reversal fee split such as 3.17/7.89), so the check allows |residual| <= 1e-30
USDT and reports it.

- A reversal fill's fee is split by quantity: the closing part goes to the old
  trip, the opening part to the new one.
- Funding settles before a fill at the same timestamp (the engine's order), so a
  payment at time t belongs to the trip that was open just before t.
- A liquidation (margin model) closes the last trip; its clearance cost (net of
  any security-fund cover, Performance.liquidation_cost) is charged to that trip.
- Win rate counts closed trips with positive net PnL (after fees and funding);
  zero-PnL trips are neither wins nor losses. The open trip is reported apart.
"""

from dataclasses import dataclass
from decimal import Decimal, localcontext

from catos import research

ZERO = Decimal(0)
HOUR_MS = 3_600_000
TOLERANCE = Decimal("1e-30")
_WIDE = research._CONTEXT.copy()
_WIDE.prec = 120


@dataclass
class RoundTrip:
    side: int  # 1 long, -1 short
    open_time_ms: int
    close_time_ms: int | None
    realized_pnl: Decimal
    fees: Decimal
    funding_paid: Decimal
    fills: int
    liquidation_cost: Decimal = ZERO

    @property
    def net_pnl(self):
        return self.realized_pnl - self.fees - self.funding_paid - self.liquidation_cost


def round_trips(result):
    """(closed trips, open trip or None) from a BacktestResult."""
    if not isinstance(result, research.BacktestResult):
        raise TypeError("result must be BacktestResult")
    closed, current = [], None
    events = sorted([(payment.time_ms, 0, payment) for payment in result.funding]
                    + [(trade.time_ms, 1, trade) for trade in result.trades], key=lambda item: (item[0], item[1]))
    position = ZERO
    liquidation_fill = result.trades[-1] if result.liquidation is not None else None
    with localcontext(_WIDE):
        for time_ms, kind, item in events:
            if kind == 0:
                if item.position != ZERO:
                    if current is None:
                        raise ValueError("funding_without_open_trip")
                    current.funding_paid += item.amount_paid
                continue
            old, new = position, item.position_after
            if old == ZERO:
                current = RoundTrip(1 if new > ZERO else -1, time_ms, None, ZERO, item.fee, ZERO, 1)
            elif new == ZERO or (old > ZERO) != (new > ZERO):
                closing_share = abs(old) / abs(item.quantity)
                current.realized_pnl += item.realized_pnl
                current.fees += item.fee * closing_share
                current.fills += 1
                current.close_time_ms = time_ms
                if item is liquidation_fill:
                    current.liquidation_cost = result.performance.liquidation_cost
                closed.append(current)
                current = None
                if new != ZERO:
                    current = RoundTrip(1 if new > ZERO else -1, time_ms, None, ZERO,
                                        item.fee - item.fee * closing_share, ZERO, 1)
            else:
                current.realized_pnl += item.realized_pnl
                current.fees += item.fee
                current.fills += 1
            position = new
    return closed, current


def _compact(value):
    """Drop trailing zeros the 120-digit sums leave behind; the value is unchanged."""
    if isinstance(value, dict):
        return {key: _compact(item) for key, item in value.items()}
    if not isinstance(value, Decimal) or not value.is_finite() or value.as_tuple().exponent >= 0:
        return value
    stripped = value.normalize(_WIDE)
    return stripped if stripped.as_tuple().exponent < 0 else value.quantize(Decimal(1), context=_WIDE)


def _ratio(numerator, denominator):
    """Ratios in the engine's 50-digit context; only sums need the wide one."""
    with localcontext(research._CONTEXT):
        return numerator / denominator if denominator else None


def trade_stats(result):
    """Win rate, payoff and expectancy over closed round trips; reconciles with net PnL."""
    closed, open_trip = round_trips(result)
    final = result.equity_curve[-1]
    with localcontext(_WIDE):
        pnls = [trip.net_pnl for trip in closed]
        wins = [pnl for pnl in pnls if pnl > ZERO]
        losses = [pnl for pnl in pnls if pnl < ZERO]
        open_pnl = open_trip.net_pnl + final.unrealized_pnl if open_trip else ZERO
        residual = sum(pnls, ZERO) + open_pnl - result.performance.net_pnl
        if abs(residual) > TOLERANCE:
            raise ValueError(f"round trips do not reconcile with net PnL: residual {residual}")
        streak = longest = 0
        for pnl in pnls:
            streak = streak + 1 if pnl < ZERO else 0
            longest = max(longest, streak)
        hours = [Decimal(trip.close_time_ms - trip.open_time_ms) / Decimal(HOUR_MS) for trip in closed]

        def side(sign):
            chosen = [trip.net_pnl for trip in closed if trip.side == sign]
            return {"trips": len(chosen), "wins": sum(pnl > ZERO for pnl in chosen),
                    "win_rate": _ratio(Decimal(sum(pnl > ZERO for pnl in chosen)), Decimal(len(chosen))),
                    "net_pnl": sum(chosen, ZERO)}

        average_win = _ratio(sum(wins, ZERO), Decimal(len(wins)))
        average_loss = _ratio(sum(losses, ZERO), Decimal(len(losses)))
        return _compact({
            "closed_trips": len(closed), "wins": len(wins), "losses": len(losses),
            "breakeven": len(pnls) - len(wins) - len(losses),
            "win_rate": _ratio(Decimal(len(wins)), Decimal(len(pnls))),
            "average_win": average_win, "average_loss": average_loss,
            "payoff_ratio": _ratio(average_win, -average_loss) if average_win is not None and average_loss else None,
            "profit_factor": _ratio(sum(wins, ZERO), -sum(losses, ZERO)) if losses else None,
            "expectancy": _ratio(sum(pnls, ZERO), Decimal(len(pnls))),
            "largest_win": max(pnls) if pnls else None, "largest_loss": min(pnls) if pnls else None,
            "max_consecutive_losses": longest,
            "average_hold_hours": _ratio(sum(hours, ZERO), Decimal(len(hours))),
            "long": side(1), "short": side(-1),
            "open_trip": None if open_trip is None else {
                "side": open_trip.side, "open_time_ms": open_trip.open_time_ms,
                "net_pnl_with_unrealized": open_pnl},
            "rounding_residual": residual,
            "notice": ("勝率以已平倉的往返交易計，扣手續費、滑價與資金費；期末未平倉的部位另列，不算勝負。"
                       "勝率高不代表賺錢，要同時看平均賺賠比與期望值。"),
        })
