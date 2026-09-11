"""Single-contract closed-bar research with an explicit Decimal execution model.

No Jesse dependency, network, persistence, account risk engine, or live adapter.
Prices and sizes must already be Decimal; timestamps and counts are integers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import (
    Context, Decimal, FloatOperation, ROUND_CEILING, ROUND_FLOOR,
    ROUND_HALF_EVEN, localcontext,
)
from typing import Callable, Iterable


ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")
BPS = Decimal("10000")
_CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN, Emin=-99, Emax=99)
_CONTEXT.traps[FloatOperation] = True


def _decimal(value: Decimal, name: str, *, positive: bool = False) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be Decimal (construct from a string)")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    if (len(value.as_tuple().digits) > 28 or value.as_tuple().exponent < -18
            or value.adjusted() > 18):
        raise ValueError(f"{name} exceeds the supported input precision/range")
    if positive and value <= ZERO:
        raise ValueError(f"{name} must be positive")


def _integer(value: int, name: str, *, minimum: int = 0) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer, not bool or float")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")


def _multiple(value: Decimal, step: Decimal, name: str) -> None:
    if value % step != ZERO:
        raise ValueError(f"{name} must be a multiple of {step}")


@dataclass(frozen=True)
class ContractSpec:
    """Caller-supplied specification for one linear USDT-settled SWAP.

    base_per_contract is normalized base-asset units per contract, not ctMult.
    This research fixture is not a substitute for live metadata verification.
    """

    inst_id: str
    base_per_contract: Decimal
    tick_size: Decimal
    lot_size: Decimal
    min_size: Decimal


@dataclass(frozen=True)
class Candle:
    open_time_ms: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    closed: bool = True


@dataclass(frozen=True)
class FundingEvent:
    time_ms: int
    rate: Decimal
    mark_price: Decimal


@dataclass(frozen=True)
class BacktestConfig:
    contract: ContractSpec
    timeframe_ms: int
    initial_balance: Decimal
    fee_rate: Decimal
    slippage_bps: Decimal
    # An explicit empty tuple means the caller assumes no funding events.
    funding_events: tuple[FundingEvent, ...]


@dataclass(frozen=True)
class AccountView:
    time_ms: int
    position: Decimal
    average_entry: Decimal
    balance: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    equity: Decimal
    fees: Decimal
    funding_paid: Decimal


class Strategy(ABC):
    """A fresh instance is created by the supplied factory for each run.

    update_indicators is called during warm-up and evaluation; it returns None.
    on_bar runs only after an evaluation bar closes. Return a signed target
    contract quantity, zero to flatten, or None to leave the position unchanged.
    Only the current closed bar and immutable account view are exposed.
    """

    @abstractmethod
    def update_indicators(self, bar: Candle) -> None:
        pass

    @property
    def ready(self) -> bool:
        return True

    @abstractmethod
    def on_bar(self, bar: Candle, account: AccountView) -> Decimal | None:
        pass


@dataclass(frozen=True)
class Intent:
    decision_time_ms: int
    target_position: Decimal


@dataclass(frozen=True)
class Trade:
    """One simulated fill (not a completed round trip); quantity is signed."""

    time_ms: int
    decision_time_ms: int
    quantity: Decimal
    price: Decimal
    fee: Decimal
    realized_pnl: Decimal
    position_after: Decimal


@dataclass(frozen=True)
class FundingPayment:
    time_ms: int
    position: Decimal
    rate: Decimal
    mark_price: Decimal
    amount_paid: Decimal  # Positive is a debit; negative is a credit.


@dataclass(frozen=True)
class Performance:
    initial_equity: Decimal
    final_equity: Decimal
    net_pnl: Decimal
    return_pct: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    fees: Decimal
    funding_paid: Decimal
    max_drawdown_pct: Decimal
    trade_count: int


@dataclass(frozen=True)
class BacktestResult:
    config: BacktestConfig
    warmup_bars: int
    evaluation_start_ms: int
    evaluation_end_ms: int
    trades: tuple[Trade, ...]
    funding: tuple[FundingPayment, ...]
    equity_curve: tuple[AccountView, ...]
    performance: Performance
    pending_intent: Intent | None
    assumptions: tuple[str, ...]


_ASSUMPTIONS = (
    "Research only: no margin, liquidation, Guardian, or live order state machine.",
    "Closed bars at the requested timeframe; no finer data or intrabar path replay.",
    "Full market fill at next open with adverse bps slippage and tick rounding.",
    "Slippage is the total execution penalty; no additional bid/ask spread model.",
    "Funding uses supplied timestamps/rates/marks; none are inferred from candles.",
    "At equal timestamps funding settles on the old position before the open fill.",
    "Close-marked equity/drawdown; candle close is not an exchange mark price.",
    "Warm-up excluded; no terminal liquidation; the final intent can remain unfilled.",
    "Decimal precision 50, ROUND_HALF_EVEN; execution ticks round against the trade.",
)


def _validate(config: BacktestConfig, bars: tuple[Candle, ...], warmup: int) -> None:
    if not isinstance(config, BacktestConfig):
        raise TypeError("config must be BacktestConfig")
    _integer(warmup, "warmup_bars")
    if len(bars) <= warmup:
        raise ValueError("candles must include warm-up and at least one evaluation bar")
    _integer(config.timeframe_ms, "timeframe_ms", minimum=60_000)
    if config.timeframe_ms % 60_000:
        raise ValueError("timeframe_ms must be a whole number of minutes")
    spec = config.contract
    if not isinstance(spec, ContractSpec):
        raise TypeError("contract must be ContractSpec")
    if not isinstance(spec.inst_id, str) or not spec.inst_id.endswith("-USDT-SWAP"):
        raise ValueError("contract label must identify a USDT SWAP")
    for name in ("base_per_contract", "tick_size", "lot_size", "min_size"):
        _decimal(getattr(spec, name), name, positive=True)
    _multiple(spec.min_size, spec.lot_size, "min_size")
    _decimal(config.initial_balance, "initial_balance", positive=True)
    _decimal(config.fee_rate, "fee_rate")
    _decimal(config.slippage_bps, "slippage_bps")
    if not ZERO <= config.fee_rate < ONE:
        raise ValueError("fee_rate must be in [0, 1)")
    if not ZERO <= config.slippage_bps < BPS:
        raise ValueError("slippage_bps must be in [0, 10000)")
    for index, bar in enumerate(bars):
        if not isinstance(bar, Candle):
            raise TypeError("candles must contain Candle objects")
        _integer(bar.open_time_ms, "open_time_ms")
        if bar.closed is not True:
            raise ValueError("only closed candles are accepted")
        if index and bar.open_time_ms != bars[index - 1].open_time_ms + config.timeframe_ms:
            raise ValueError("candles must be ordered and contiguous; gaps are not filled")
        for name in ("open", "high", "low", "close"):
            value = getattr(bar, name)
            _decimal(value, name, positive=True)
            _multiple(value, spec.tick_size, name)
        if not bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high:
            raise ValueError("invalid OHLC bounds")
    if not isinstance(config.funding_events, tuple):
        raise TypeError("funding_events must be an explicit tuple (empty means none)")
    previous = -1
    for event in config.funding_events:
        if not isinstance(event, FundingEvent):
            raise TypeError("funding_events must contain FundingEvent objects")
        _integer(event.time_ms, "funding time_ms")
        _decimal(event.rate, "funding rate")
        _decimal(event.mark_price, "funding mark_price", positive=True)
        if not -ONE < event.rate < ONE:
            raise ValueError("funding rate must be in (-1, 1)")
        if event.time_ms <= previous:
            raise ValueError("funding events must have unique, increasing timestamps")
        if not bars[0].open_time_ms <= event.time_ms <= bars[-1].open_time_ms + config.timeframe_ms:
            raise ValueError("funding event outside candle coverage")
        previous = event.time_ms


class _Ledger:
    """Net futures accounting; no exchange or strategy access."""

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.position = ZERO
        self.average_entry = ZERO
        self.balance = config.initial_balance
        self.realized_pnl = ZERO
        self.fees = ZERO
        self.funding_paid = ZERO

    def view(self, time_ms: int, price: Decimal) -> AccountView:
        unrealized = self.position * self.config.contract.base_per_contract * (price - self.average_entry)
        return AccountView(time_ms, self.position, self.average_entry, self.balance,
                           self.realized_pnl, unrealized, self.balance + unrealized,
                           self.fees, self.funding_paid)

    def fill(self, intent: Intent, bar: Candle) -> Trade:
        spec = self.config.contract
        delta = intent.target_position - self.position
        direction = ONE if delta > ZERO else -ONE
        raw_price = bar.open * (ONE + direction * self.config.slippage_bps / BPS)
        rounding = ROUND_CEILING if delta > ZERO else ROUND_FLOOR
        price = (raw_price / spec.tick_size).to_integral_value(rounding=rounding) * spec.tick_size
        if price <= ZERO:
            raise ValueError("slippage and tick size produced a nonpositive fill price")
        fee = abs(delta) * spec.base_per_contract * price * self.config.fee_rate
        old = self.position
        target = intent.target_position
        realized = ZERO
        if old == ZERO:
            self.average_entry = price
        elif old * delta > ZERO:
            self.average_entry = (abs(old) * self.average_entry + abs(delta) * price) / abs(target)
        else:
            closed = min(abs(old), abs(delta))
            old_direction = ONE if old > ZERO else -ONE
            realized = closed * spec.base_per_contract * (price - self.average_entry) * old_direction
            if target == ZERO:
                self.average_entry = ZERO
            elif old * target < ZERO:
                self.average_entry = price
        self.position = target
        self.realized_pnl += realized
        self.fees += fee
        self.balance += realized - fee
        return Trade(bar.open_time_ms, intent.decision_time_ms, delta, price, fee, realized, target)

    def fund(self, event: FundingEvent) -> FundingPayment:
        paid = self.position * self.config.contract.base_per_contract * event.mark_price * event.rate
        self.balance -= paid
        self.funding_paid += paid
        return FundingPayment(event.time_ms, self.position, event.rate, event.mark_price, paid)


def _call(function: Callable, *args):
    # Strategy arithmetic cannot accidentally change the ledger's Decimal context.
    with localcontext(_CONTEXT):
        return function(*args)


def _ready(strategy: Strategy) -> bool:
    ready = _call(lambda: strategy.ready)
    if type(ready) is not bool:
        raise TypeError("strategy.ready must be bool")
    return ready


def backtest(
    *, strategy: Callable[[], Strategy], candles: Iterable[Candle],
    config: BacktestConfig, warmup_bars: int = 0,
) -> BacktestResult:
    """Run a fresh strategy over in-memory closed bars; never reads or writes files.

    Inputs are validated before the strategy runs. Supply a factory/class, not a
    reused strategy instance. A target is effective only at the next bar open.
    The first evaluation bar may initialize a zero-warm-up strategy's indicators.
    With positive warm-up, readiness is required at the end of that warm-up.
    """
    with localcontext(_CONTEXT):
        bars = tuple(candles)
        _validate(config, bars, warmup_bars)
        if not callable(strategy):
            raise TypeError("strategy must be a factory returning a fresh Strategy")
        instance = _call(strategy)
        if not isinstance(instance, Strategy):
            raise TypeError("strategy factory must return a Strategy")
        for bar in bars[:warmup_bars]:
            if _call(instance.update_indicators, bar) is not None:
                raise ValueError("update_indicators must return None, never an intent")
        if warmup_bars and not _ready(instance):
            raise ValueError("strategy indicators are not ready after warm-up")

        start = bars[warmup_bars].open_time_ms
        ledger = _Ledger(config)
        curve = [ledger.view(start, bars[warmup_bars].open)]
        trades: list[Trade] = []
        payments: list[FundingPayment] = []
        pending: Intent | None = None
        events = iter(event for event in config.funding_events if event.time_ms >= start)
        next_event = next(events, None)

        def settle_through(time_ms: int) -> None:
            nonlocal next_event
            while next_event is not None and next_event.time_ms <= time_ms:
                payments.append(ledger.fund(next_event))
                next_event = next(events, None)

        for bar in bars[warmup_bars:]:
            settle_through(bar.open_time_ms)
            if pending is not None:
                trades.append(ledger.fill(pending, bar))
                pending = None
            close_time = bar.open_time_ms + config.timeframe_ms
            settle_through(close_time)
            view = ledger.view(close_time, bar.close)
            curve.append(view)
            if _call(instance.update_indicators, bar) is not None:
                raise ValueError("update_indicators must return None, never an intent")
            if not _ready(instance):
                raise ValueError("strategy indicators are not ready for evaluation")
            target = _call(instance.on_bar, bar, view)
            if target is None:
                continue
            _decimal(target, "target_position")
            spec = config.contract
            _multiple(target, spec.lot_size, "target_position")
            if target != ZERO and abs(target) < spec.min_size:
                raise ValueError("target_position is below min_size")
            delta = target - ledger.position
            if delta != ZERO:
                if abs(delta) < spec.min_size:
                    raise ValueError("order quantity is below min_size")
                pending = Intent(close_time, target)

        final = curve[-1]
        peak = config.initial_balance
        drawdown = ZERO
        for point in curve:
            peak = max(peak, point.equity)
            drawdown = max(drawdown, (peak - point.equity) / peak * HUNDRED)
        net = final.equity - config.initial_balance
        performance = Performance(
            config.initial_balance, final.equity, net,
            net / config.initial_balance * HUNDRED,
            final.realized_pnl, final.unrealized_pnl, final.fees,
            final.funding_paid, drawdown, len(trades),
        )
        return BacktestResult(config, warmup_bars, start, final.time_ms,
                              tuple(trades), tuple(payments), tuple(curve),
                              performance, pending, _ASSUMPTIONS)
