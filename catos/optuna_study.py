"""Optuna study script for optimizing moving average parameters on real market data.

Usage:
    py -3 -B -m catos.optuna_study --csv data/BTC-USDT-SWAP-1H.csv --trials 50
"""

import argparse
from collections import deque
from decimal import Decimal, localcontext
import math
from pathlib import Path
import sys

from catos.data_io import load_candles_csv
from catos.optimization import IntRange, optimize
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
    """Dual Moving Average Strategy for Optuna search."""

    def __init__(self, params):
        fast = params["fast"]
        slow = params["slow"]
        if fast >= slow:
            raise ValueError(f"fast ({fast}) must be < slow ({slow})")

        self.fast = fast
        self.slow = slow
        self.quantity = Decimal("2")
        self.closes_fast = deque(maxlen=fast)
        self.closes_slow = deque(maxlen=slow)

    def update_indicators(self, bar: Candle) -> None:
        self.closes_fast.append(bar.close)
        self.closes_slow.append(bar.close)

    @property
    def ready(self) -> bool:
        return len(self.closes_slow) == self.slow

    def on_bar(self, bar: Candle, account: AccountView) -> Decimal | None:
        sma_fast = sum(self.closes_fast, Decimal("0")) / Decimal(len(self.closes_fast))
        sma_slow = sum(self.closes_slow, Decimal("0")) / Decimal(len(self.closes_slow))
        if sma_fast > sma_slow:
            return self.quantity
        else:
            return Decimal("0")


def compute_annualized_sharpe(equity_curve: tuple[AccountView, ...], hours_per_year: float = 8760.0) -> float:
    """Calculate annualized Sharpe ratio from an hourly equity curve."""
    if len(equity_curve) < 2:
        return 0.0

    returns = []
    for i in range(1, len(equity_curve)):
        prev_eq = float(equity_curve[i - 1].equity)
        curr_eq = float(equity_curve[i].equity)
        if prev_eq > 0:
            returns.append((curr_eq - prev_eq) / prev_eq)
        else:
            returns.append(0.0)

    n = len(returns)
    if n == 0:
        return 0.0

    mean_r = sum(returns) / n
    variance = sum((r - mean_r) ** 2 for r in returns) / (n - 1 if n > 1 else 1)
    std_r = math.sqrt(variance)

    if std_r == 0:
        return 0.0

    return (mean_r / std_r) * math.sqrt(hours_per_year)


def run_study(
    csv_path: str = "data/BTC-USDT-SWAP-1H.csv",
    symbol: str = "BTC-USDT-SWAP",
    n_trials: int = 50,
    seed: int = 42,
    metric: str = "net_pnl",
) -> None:
    csv_p = Path(csv_path).resolve()
    if not csv_p.exists():
        raise FileNotFoundError(f"找不到 CSV 檔案: {csv_path}")

    # Maximum slow SMA to search is 80, so warmup_bars covers the maximum requirement
    max_slow = 80
    warmup_bars = max_slow

    with localcontext(_CONTEXT):
        contract = ContractSpec(
            inst_id=symbol,
            base_per_contract=Decimal("0.01"),
            tick_size=Decimal("0.1"),
            lot_size=Decimal("1"),
            min_size=Decimal("1"),
        )
        config = BacktestConfig(
            contract=contract,
            timeframe_ms=3600000,  # 1 hour
            initial_balance=Decimal("10000"),
            fee_rate=Decimal("0.0005"),
            slippage_bps=Decimal("1"),
            funding_events=(),
        )

        print(f"正在載入歷史數據: {csv_p} ...")
        candles = load_candles_csv(csv_p, config=config)
        print(f"數據載入完成，共 {len(candles)} 根 K 線 (預熱: {warmup_bars} 根，評估: {len(candles) - warmup_bars} 根)。")

        # Define search space
        search_space = {
            "fast": IntRange(3, 30, step=1),
            "slow": IntRange(10, max_slow, step=2),
        }

        print(f"\n開始執行 Optuna 搜尋 ({n_trials} 次 Trial，隨機種子: {seed})，目標指標: {metric} ...")

        # Score function
        if metric == "net_pnl":
            score_fn = lambda p: p.net_pnl
            score_name = "Net PnL (USDT)"
        else:
            # Calmar-like risk-adjusted net return
            score_fn = lambda p: p.net_pnl / (p.max_drawdown_pct + Decimal("1"))
            score_name = "Risk-Adjusted Net PnL"

        study_result = optimize(
            strategy_factory=lambda params: DualSMAStrategy(params),
            search_space=search_space,
            candles=candles,
            config=config,
            score=score_fn,
            score_name=score_name,
            n_trials=n_trials,
            seed=seed,
            warmup_bars=warmup_bars,
            direction="maximize",
        )

        # Collect and rank completed trials
        successful_trials = [t for t in study_result.trials if t.state == "COMPLETE" and t.score_decimal is not None]
        successful_trials.sort(key=lambda t: t.score_decimal, reverse=True)

        print(f"\n搜尋完成！總嘗試: {len(study_result.trials)} 次，成功完成: {len(successful_trials)} 次。")

        top_k = min(3, len(successful_trials))
        print(f"\n{'='*75}")
        print(f"★ 前 {top_k} 組最佳均線組合參數排行 (依 {score_name} 排序)")
        print(f"{'='*75}")

        for rank, trial in enumerate(successful_trials[:top_k], start=1):
            params = dict(trial.params)
            fast_val = params["fast"]
            slow_val = params["slow"]
            perf = trial.performance

            # Re-run single backtest to obtain equity curve for Sharpe ratio calculation
            detailed_result = backtest(
                strategy=lambda: DualSMAStrategy({"fast": fast_val, "slow": slow_val}),
                candles=candles,
                config=config,
                warmup_bars=warmup_bars,
            )
            sharpe = compute_annualized_sharpe(detailed_result.equity_curve)

            print(f"\n【第 {rank} 名】Trial #{trial.number}")
            print(f"  均線參數:   Fast SMA = {fast_val}, Slow SMA = {slow_val}")
            print(f"  淨損益:     {perf.net_pnl} USDT ({perf.return_pct}%)")
            print(f"  夏普比率:   {sharpe:.4f} (年化 1H)")
            print(f"  最大回撤:   {perf.max_drawdown_pct}%")
            print(f"  期末權益:   {perf.final_equity} USDT")
            print(f"  模擬成交:   {perf.trade_count} 筆 (手續費: {perf.fees} USDT)")
            print(f"  搜尋評分:   {trial.score_decimal}")

        print(f"\n{'='*75}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="catOS Optuna Parameter Study")
    parser.add_argument("--csv", default="data/BTC-USDT-SWAP-1H.csv", help="K 線 CSV 檔案路徑")
    parser.add_argument("--symbol", default="BTC-USDT-SWAP", help="交易合約代碼")
    parser.add_argument("--trials", type=int, default=50, help="Trial 搜尋次數 (預設: 50)")
    parser.add_argument("--seed", type=int, default=42, help="隨機種子 (預設: 42)")
    parser.add_argument("--metric", choices=["net_pnl", "risk_adjusted"], default="net_pnl", help="優化目標指標")

    args = parser.parse_args(argv)

    try:
        run_study(
            csv_path=args.csv,
            symbol=args.symbol,
            n_trials=args.trials,
            seed=args.seed,
            metric=args.metric,
        )
        return 0
    except Exception as err:
        sys.stderr.write(f"錯誤: {err}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
