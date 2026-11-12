"""Single-contract closed-bar research with an explicit Decimal execution model.

No Jesse dependency, network, persistence, account risk engine, or live adapter.
Prices and sizes must already be Decimal; timestamps and counts are integers.

An optional MarginModel (config.margin) adds single-contract cross margin in net
mode from OKX position tiers: initial-margin checks on fills that grow the
position, and a liquidation check at each bar's adverse extreme. Formulas and
their OKX sources are in docs/research-margin-model.md.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import (
    Context, Decimal, FloatOperation, ROUND_CEILING, ROUND_FLOOR,
    ROUND_HALF_EVEN, localcontext,
)
import re
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
class MarginTier:
    """One OKX position tier: |position| in contracts up to max_contracts (inclusive)."""

    tier: int
    max_contracts: Decimal
    maintenance_rate: Decimal  # OKX mmr
    initial_rate: Decimal  # OKX imr


@dataclass(frozen=True)
class MarginModel:
    """Single-contract cross margin, net mode; tiers ascend and cover (0, last max].

    tiers_sha256 labels the tier snapshot the run used. leverage None means the
    tier's own imr (the exchange maximum); otherwise max(1 / leverage, imr).
    The liquidation fee uses the run's fee_rate (all research fills are taker).
    """

    tiers: tuple[MarginTier, ...]
    tiers_sha256: str
    leverage: Decimal | None = None

    def tier_for(self, contracts: Decimal) -> MarginTier | None:
        for tier in self.tiers:
            if contracts <= tier.max_contracts:
                return tier
        return None

    def initial_rate(self, tier: MarginTier) -> Decimal:
        if self.leverage is None:
            return tier.initial_rate
        return max(tier.initial_rate, ONE / self.leverage)


@dataclass(frozen=True)
class BacktestConfig:
    contract: ContractSpec
    timeframe_ms: int
    initial_balance: Decimal
    fee_rate: Decimal
    slippage_bps: Decimal
    # An explicit empty tuple means the caller assumes no funding events.
    funding_events: tuple[FundingEvent, ...]
    # None keeps the original model: no margin checks and no liquidation.
    margin: MarginModel | None = None


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
    # Clearance fee charged at liquidation minus any deficit the security fund
    # covered; net_pnl = realized - fees - funding - liquidation_cost + unrealized.
    liquidation_cost: Decimal = ZERO


@dataclass(frozen=True)
class Liquidation:
    """The forced close; trades[-1] is its fill (fee = the liquidation fee charged)."""

    time_ms: int  # the fill's time: the bar open, or the bar close for "after_funding"
    bar_open_time_ms: int
    # "open" (the open gapped through it, checked before any fill), "adverse_extreme"
    # (bar low/high) or "after_funding" (the close, after close-time funding)
    trigger: str
    trigger_price: Decimal
    liquidation_price: Decimal  # tick-rounded against the trader
    fill_price: Decimal
    gapped: bool  # the reference price was already through the liquidation price
    position: Decimal
    average_entry: Decimal
    tier: int
    maintenance_rate: Decimal
    balance_before: Decimal
    realized_pnl: Decimal
    clearance_fee: Decimal  # notional x mmr at the fill price (the maintenance margin)
    liquidation_fee: Decimal  # notional x fee_rate at the fill price
    fee_charged: Decimal
    clearance_charged: Decimal
    deficit_covered: Decimal
    balance_after: Decimal


@dataclass(frozen=True)
class MarginRejection:
    decision_time_ms: int
    time_ms: int
    position: Decimal
    target_position: Decimal
    fill_price: Decimal
    reason: str  # "insufficient_initial_margin" or "above_max_tier"
    equity_after: Decimal | None
    required_initial_margin: Decimal | None


MAX_REJECTIONS_KEPT = 20


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
    liquidation: Liquidation | None = None
    margin_rejection_count: int = 0
    # The first MAX_REJECTIONS_KEPT rejected fills; the count covers all of them.
    margin_rejections: tuple[MarginRejection, ...] = ()


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
_MARGIN_ASSUMPTIONS = (
    "Single-contract cross margin, net mode, OKX position tiers; no Guardian or live order state machine.",
    "Liquidation when equity <= maintenance margin + fee_rate liquidation fee at the bar's adverse extreme "
    "(low for longs, high for shorts); trade prices stand in for the mark price.",
    "A position the open gapped through is liquidated at the open before any fill; the pending intent is void.",
    "Liquidation fills at the tick-rounded liquidation price (the open if it gapped through), charges the "
    "liquidation fee and a tier-MMR clearance fee, floors equity at 0 and stops trading; "
    "tier 3+ is not reduced in steps.",
    "Fills that grow the position are rejected when post-fill equity, valued at the open (mark stand-in, so "
    "slippage counts as order loss), is below the tier initial margin there.",
)
_SHA256 = re.compile(r"[0-9a-f]{64}")


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
    if config.margin is not None:
        _validate_margin(config)
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


def _validate_margin(config: BacktestConfig) -> None:
    margin = config.margin
    if not isinstance(margin, MarginModel):
        raise TypeError("margin must be MarginModel or None")
    if not isinstance(margin.tiers_sha256, str) or not _SHA256.fullmatch(margin.tiers_sha256):
        raise ValueError("margin tiers_sha256 must be a sha256 hex digest")
    if not isinstance(margin.tiers, tuple) or not margin.tiers:
        raise ValueError("margin tiers must be a non-empty tuple")
    previous = ZERO
    for number, tier in enumerate(margin.tiers, start=1):
        if not isinstance(tier, MarginTier):
            raise TypeError("margin tiers must contain MarginTier objects")
        if type(tier.tier) is not int or tier.tier != number:
            raise ValueError("margin tiers must be numbered 1, 2, ... in order")
        for name in ("max_contracts", "maintenance_rate", "initial_rate"):
            _decimal(getattr(tier, name), name, positive=True)
        if tier.max_contracts <= previous:
            raise ValueError("margin tier limits must increase")
        if not tier.maintenance_rate < tier.initial_rate <= ONE:
            raise ValueError("margin rates must satisfy 0 < mmr < imr <= 1")
        if tier.maintenance_rate + config.fee_rate >= ONE:
            raise ValueError("maintenance rate plus fee_rate must be below 1")
        previous = tier.max_contracts
    if margin.leverage is not None:
        _decimal(margin.leverage, "leverage")
        if margin.leverage < ONE:
            raise ValueError("leverage must be >= 1")


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
        self.liquidation_cost = ZERO

    def view(self, time_ms: int, price: Decimal) -> AccountView:
        unrealized = self.position * self.config.contract.base_per_contract * (price - self.average_entry)
        return AccountView(time_ms, self.position, self.average_entry, self.balance,
                           self.realized_pnl, unrealized, self.balance + unrealized,
                           self.fees, self.funding_paid)

    def execution(self, target: Decimal, bar: Candle) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
        """(delta, price, fee, realized, average_entry after) of a next-open fill, without applying it."""
        spec = self.config.contract
        delta = target - self.position
        direction = ONE if delta > ZERO else -ONE
        raw_price = bar.open * (ONE + direction * self.config.slippage_bps / BPS)
        rounding = ROUND_CEILING if delta > ZERO else ROUND_FLOOR
        price = (raw_price / spec.tick_size).to_integral_value(rounding=rounding) * spec.tick_size
        if price <= ZERO:
            raise ValueError("slippage and tick size produced a nonpositive fill price")
        fee = abs(delta) * spec.base_per_contract * price * self.config.fee_rate
        old = self.position
        realized = ZERO
        average = self.average_entry
        if old == ZERO:
            average = price
        elif old * delta > ZERO:
            average = (abs(old) * self.average_entry + abs(delta) * price) / abs(target)
        else:
            closed = min(abs(old), abs(delta))
            old_direction = ONE if old > ZERO else -ONE
            realized = closed * spec.base_per_contract * (price - self.average_entry) * old_direction
            if target == ZERO:
                average = ZERO
            elif old * target < ZERO:
                average = price
        return delta, price, fee, realized, average

    def fill(self, intent: Intent, bar: Candle, execution=None) -> Trade:
        delta, price, fee, realized, average = execution or self.execution(intent.target_position, bar)
        target = intent.target_position
        self.average_entry = average
        self.position = target
        self.realized_pnl += realized
        self.fees += fee
        self.balance += realized - fee
        return Trade(bar.open_time_ms, intent.decision_time_ms, delta, price, fee, realized, target)

    def margin_rejection(self, intent: Intent, bar: Candle, execution) -> MarginRejection | None:
        """Initial-margin check for a fill that grows |position|; reductions always pass.

        The bar open stands in for the mark price: post-fill equity is valued
        there, so the slippage between the open and the fill price counts as the
        order loss OKX charges against an opening order.
        """
        margin = self.config.margin
        target = intent.target_position
        if margin is None or abs(target) <= abs(self.position):
            return None
        _, price, fee, realized, average = execution
        per_contract = self.config.contract.base_per_contract
        tier = margin.tier_for(abs(target))
        if tier is None:
            return MarginRejection(intent.decision_time_ms, bar.open_time_ms, self.position, target, price,
                                   "above_max_tier", None, None)
        mark = bar.open
        equity = self.balance + realized - fee + target * per_contract * (mark - average)
        required = abs(target) * per_contract * mark * margin.initial_rate(tier)
        if equity >= required:
            return None
        return MarginRejection(intent.decision_time_ms, bar.open_time_ms, self.position, target, price,
                               "insufficient_initial_margin", equity, required)

    def liquidation_price(self, price: Decimal, reference: Decimal):
        """(tier, liquidation price, fill price, gapped) if equity at price <= MM + liquidation fee, else None.

        reference is where the position stood before the move to price: the bar
        open for the adverse-extreme check (a gap through fills there), or the
        close itself for the after-funding check.
        """
        margin = self.config.margin
        position = self.position
        if margin is None or position == ZERO:
            return None
        spec = self.config.contract
        per_contract = spec.base_per_contract
        tier = margin.tier_for(abs(position))
        if tier is None:  # unreachable: fills above the last tier are rejected
            raise ValueError("position above the last margin tier")
        rate = tier.maintenance_rate + self.config.fee_rate
        equity = self.balance + position * per_contract * (price - self.average_entry)
        if equity > abs(position) * per_contract * price * rate:
            return None
        size = abs(position) * per_contract
        if position > ZERO:
            raw = (size * self.average_entry - self.balance) / (size * (ONE - rate))
            # Round the fill against the trader: down for a long, up for a short. The
            # trigger itself is exact, so the rounded price stays within [low, open].
            liquidation = (raw / spec.tick_size).to_integral_value(rounding=ROUND_FLOOR) * spec.tick_size
            gapped = reference <= liquidation
        else:
            raw = (self.balance + size * self.average_entry) / (size * (ONE + rate))
            liquidation = (raw / spec.tick_size).to_integral_value(rounding=ROUND_CEILING) * spec.tick_size
            gapped = reference >= liquidation
        return tier, liquidation, (reference if gapped else liquidation), gapped

    def liquidate(self, *, time_ms: int, bar: Candle, trigger: str, trigger_price: Decimal,
                  found) -> tuple[Trade, Liquidation]:
        tier, liquidation_price, price, gapped = found
        per_contract = self.config.contract.base_per_contract
        position, entry, before = self.position, self.average_entry, self.balance
        realized = position * per_contract * (price - entry)
        notional = abs(position) * per_contract * price
        fee = notional * self.config.fee_rate
        clearance = notional * tier.maintenance_rate
        equity = before + realized
        if equity <= ZERO:
            fee_charged = clearance_charged = ZERO
            deficit = -equity
        else:
            fee_charged = min(fee, equity)
            clearance_charged = min(clearance, equity - fee_charged)
            deficit = ZERO
        self.realized_pnl += realized
        self.fees += fee_charged
        self.liquidation_cost += clearance_charged - deficit
        self.balance = equity - fee_charged - clearance_charged + deficit
        self.position = ZERO
        self.average_entry = ZERO
        trade = Trade(time_ms, time_ms, -position, price, fee_charged, realized, ZERO)
        record = Liquidation(time_ms, bar.open_time_ms, trigger, trigger_price, liquidation_price, price, gapped,
                             position, entry, tier.tier, tier.maintenance_rate, before, realized, clearance, fee,
                             fee_charged, clearance_charged, deficit, self.balance)
        return trade, record

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
        liquidation: Liquidation | None = None
        rejections: list[MarginRejection] = []
        rejection_count = 0
        events = iter(event for event in config.funding_events if event.time_ms >= start)
        next_event = next(events, None)

        def settle_through(time_ms: int) -> None:
            nonlocal next_event
            while next_event is not None and next_event.time_ms <= time_ms:
                payments.append(ledger.fund(next_event))
                next_event = next(events, None)

        for bar in bars[warmup_bars:]:
            settle_through(bar.open_time_ms)
            if liquidation is None and ledger.position != ZERO:
                # A gap through the liquidation price between the last close and this
                # open liquidates the held position at the open, before the pending
                # intent could fill; the intent is then void.
                found = ledger.liquidation_price(bar.open, bar.open)
                if found is not None:
                    trade, liquidation = ledger.liquidate(time_ms=bar.open_time_ms, bar=bar, trigger="open",
                                                          trigger_price=bar.open, found=found)
                    trades.append(trade)
                    pending = None
            if pending is not None:
                execution = ledger.execution(pending.target_position, bar)
                rejection = ledger.margin_rejection(pending, bar, execution)
                if rejection is None:
                    trades.append(ledger.fill(pending, bar, execution))
                else:
                    rejection_count += 1
                    if len(rejections) < MAX_REJECTIONS_KEPT:
                        rejections.append(rejection)
                pending = None
            close_time = bar.open_time_ms + config.timeframe_ms
            if liquidation is None and ledger.position != ZERO:
                adverse = bar.low if ledger.position > ZERO else bar.high
                found = ledger.liquidation_price(adverse, bar.open)
                if found is not None:
                    trade, liquidation = ledger.liquidate(time_ms=bar.open_time_ms, bar=bar,
                                                          trigger="adverse_extreme", trigger_price=adverse,
                                                          found=found)
                    trades.append(trade)
            settle_through(close_time)
            if liquidation is None and ledger.position != ZERO:
                # Close-time funding can push equity to the threshold at the close itself.
                found = ledger.liquidation_price(bar.close, bar.close)
                if found is not None:
                    trade, liquidation = ledger.liquidate(time_ms=close_time, bar=bar, trigger="after_funding",
                                                          trigger_price=bar.close, found=found)
                    trades.append(trade)
            view = ledger.view(close_time, bar.close)
            curve.append(view)
            if liquidation is not None:
                continue  # stopped: no strategy calls and no intents after a liquidation
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
            final.funding_paid, drawdown, len(trades), ledger.liquidation_cost,
        )
        assumptions = _ASSUMPTIONS if config.margin is None else _MARGIN_ASSUMPTIONS + _ASSUMPTIONS[1:]
        return BacktestResult(config, warmup_bars, start, final.time_ms,
                              tuple(trades), tuple(payments), tuple(curve),
                              performance, pending, assumptions, liquidation,
                              rejection_count, tuple(rejections))
