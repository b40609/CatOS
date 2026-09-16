"""Command-line interface for catOS dual-moving-average strategy research.

Usage:
    Supply --csv, --symbol, --base-per-contract, --tick-size, --lot-size,
    --min-size and --report explicitly. Specs are research inputs, not verified
    exchange metadata. See README.md for the synthetic example.
"""

import argparse
import csv
import os
from collections import deque
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
import sys

from catos.data_io import load_candles_csv
from catos.reporting import render_report
from catos.research import (
    AccountView,
    BacktestConfig,
    Candle,
    ContractSpec,
    Strategy,
    _CONTEXT,
    backtest,
)


class DualSMAStrategy(Strategy):
    """Dual Simple Moving Average Strategy (Fast SMA vs Slow SMA)."""

    def __init__(self, fast: int, slow: int, quantity: Decimal = Decimal("2")):
        if fast >= slow:
            raise ValueError(f"fast period ({fast}) must be strictly less than slow period ({slow})")
        self.fast = fast
        self.slow = slow
        self.quantity = quantity
        self.closes_fast = deque(maxlen=fast)
        self.closes_slow = deque(maxlen=slow)

    def update_indicators(self, bar: Candle) -> None:
        self.closes_fast.append(bar.close)
        self.closes_slow.append(bar.close)

    @property
    def ready(self) -> bool:
        return len(self.closes_slow) == self.slow

    def on_bar(self, bar: Candle, account: AccountView) -> Decimal | None:
        # Calculate fast and slow SMA in Decimal
        sma_fast = sum(self.closes_fast, Decimal("0")) / Decimal(len(self.closes_fast))
        sma_slow = sum(self.closes_slow, Decimal("0")) / Decimal(len(self.closes_slow))

        if sma_fast > sma_slow:
            # Bullish trend: maintain long position
            return self.quantity
        else:
            # Bearish trend: flatten
            return Decimal("0")


def detect_timeframe_ms(csv_path: Path | str) -> int:
    """Read first two candle rows to detect timeframe in milliseconds."""
    with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        _header = next(reader)
        row1 = next(reader)
        row2 = next(reader)
        t1 = int(row1[0])
        t2 = int(row2[0])
        delta = t2 - t1
        if delta <= 0:
            raise ValueError("CSV timestamps must be strictly increasing")
        return delta


def run_cli(
    csv_path: str,
    symbol: str,
    fast: int,
    slow: int,
    report_path: str,
    quantity: str = "2",
    initial_balance: str = "10000",
    fee_rate: str = "0.0005",
    slippage_bps: str = "1",
    *,
    contract: ContractSpec | None = None,
) -> Path:
    """Execute research with explicit caller-supplied, symbol-matched specs."""
    csv_p = Path(csv_path).resolve()
    if not csv_p.exists():
        raise FileNotFoundError(f"CSV 檔案不存在: {csv_path}")

    report_p = Path(report_path).resolve()
    if report_p == csv_p:
        raise ValueError("output path cannot be the same as input CSV path")
    if report_p.suffix.lower() != ".html":
        raise ValueError("output path must end with .html")
    if report_p.exists():
        raise ValueError(f"output file already exists: {report_p}")

    if not isinstance(contract, ContractSpec) or contract.inst_id != symbol:
        raise ValueError("explicit ContractSpec matching symbol is required")
    timeframe_ms = detect_timeframe_ms(csv_p)

    with localcontext(_CONTEXT):
        config = BacktestConfig(
            contract=contract,
            timeframe_ms=timeframe_ms,
            initial_balance=Decimal(initial_balance),
            fee_rate=Decimal(fee_rate),
            slippage_bps=Decimal(slippage_bps),
            funding_events=(),
        )

        # Load and validate candles
        candles = load_candles_csv(csv_p, config=config)

        target_qty = Decimal(quantity)

        # Run backtest with DualSMAStrategy
        result = backtest(
            strategy=lambda: DualSMAStrategy(fast=fast, slow=slow, quantity=target_qty),
            candles=candles,
            config=config,
            warmup_bars=slow,
        )

        # Render before creating the output; never truncate an existing file.
        html_report = render_report(result)
        report_p.parent.mkdir(parents=True, exist_ok=True)
        try:
            stream = open(report_p, mode="x", encoding="utf-8")
        except FileExistsError as exc:
            raise ValueError(f"output file already exists: {report_p}") from exc
        created_stat = None
        try:
            created_stat = os.fstat(stream.fileno())
            stream.write(html_report)
            stream.flush()
            stream.close()
        except BaseException:
            try:
                stream.close()
            except BaseException:
                pass
            # Only remove our partial output, not a replacement at this path.
            try:
                if created_stat is not None and os.path.samestat(created_stat, report_p.stat()):
                    report_p.unlink()
            except OSError:
                pass
            raise

        # Print backtest summary
        p = result.performance
        print(f"\n=== catOS 回測完成 ({symbol}) ===")
        print(f"K 線總數: {len(candles)} 根 (預熱: {result.warmup_bars} 根, 評估: {len(candles) - result.warmup_bars} 根)")
        print(f"策略設定: Fast SMA={fast}, Slow SMA={slow}, 目標張數={quantity}")
        print(f"初始權益: {p.initial_equity} USDT")
        print(f"期末權益: {p.final_equity} USDT")
        print(f"淨損益:   {p.net_pnl} USDT ({p.return_pct}%)")
        print(f"最大回撤: {p.max_drawdown_pct}%")
        print(f"成交筆數: {p.trade_count} 筆")
        print(f"手續費:   {p.fees} USDT")
        print(f"報告已輸出至: {report_p}\n")

    return report_p


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="catOS Dual SMA Strategy Backtest CLI"
    )
    parser.add_argument("--csv", required=True, help="Path to candle CSV file")
    parser.add_argument("--symbol", required=True, help="Contract symbol matching caller-supplied specs")
    parser.add_argument("--base-per-contract", required=True, help="Explicit base-asset units per contract")
    parser.add_argument("--tick-size", required=True, help="Explicit price tick")
    parser.add_argument("--lot-size", required=True, help="Explicit contract quantity step")
    parser.add_argument("--min-size", required=True, help="Explicit minimum contract quantity")
    parser.add_argument("--fast", type=int, default=10, help="Fast SMA period")
    parser.add_argument("--slow", type=int, default=30, help="Slow SMA period")
    parser.add_argument("--quantity", default="2", help="Target contract size")
    parser.add_argument("--report", required=True, help="Output HTML report path")

    args = parser.parse_args(argv)

    try:
        run_cli(
            csv_path=args.csv,
            symbol=args.symbol,
            fast=args.fast,
            slow=args.slow,
            report_path=args.report,
            quantity=args.quantity,
            contract=ContractSpec(args.symbol, Decimal(args.base_per_contract),
                                  Decimal(args.tick_size), Decimal(args.lot_size), Decimal(args.min_size)),
        )
        return 0
    except Exception as e:
        sys.stderr.write(f"錯誤: {e}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
