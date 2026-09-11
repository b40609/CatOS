"""Generate offline synthetic reports: py -3 -B -m examples.report_demo."""

from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path

from catos.data_io import load_candles_csv
from catos.reporting import render_report
from catos.research import BacktestConfig, ContractSpec, FundingEvent, backtest
from examples.closed_bar_demo import SMATrend


def main():
    output = Path(__file__).resolve().parents[1] / "reports" / "visual-qa"
    output.mkdir(parents=True, exist_ok=True)
    step = 900_000
    prices = ("100", "101", "103", "102", "99", "98", "100", "102")
    csv_path = output / "synthetic.csv"
    csv_path.write_text("open_time_ms,open,high,low,close,closed\n" + "".join(
        f"{i * step},{p},{p},{p},{p},1\n" for i, p in enumerate(prices)
    ), encoding="utf-8")
    config = BacktestConfig(
        contract=ContractSpec("SYNTHETIC-USDT-SWAP", D("0.01"), D("0.01"), D("1"), D("1")),
        timeframe_ms=step, initial_balance=D("1000"), fee_rate=D("0.0005"),
        slippage_bps=D("2"),
        funding_events=(FundingEvent(3 * step + step // 2, D("0.0001"), D("102")),),
    )
    result = backtest(strategy=SMATrend, candles=load_candles_csv(csv_path, config=config),
                      config=config, warmup_bars=2)
    result = replace(result, assumptions=("合成資料示範，非歷史績效。",) + result.assumptions)
    (output / "synthetic-report.html").write_text(render_report(result), encoding="utf-8")
    # Explicitly fabricated display fixtures, separate from actual backtest output.
    for name, values in {
        "empty": (), "single": ("1E-18",), "flat": ("1E-18", "1E-18"),
        "tiny": ("1E-18", "2E-18", "1.5E-18"), "negative": ("100", "-50", "-200"),
    }.items():
        fixture = replace(result,
            equity_curve=tuple(replace(result.equity_curve[0], time_ms=i * step, equity=D(value))
                               for i, value in enumerate(values)),
            assumptions=("僅供版面邊界驗收：曲線為人工替換，與績效卡片不作會計比對。",))
        (output / f"fixture-{name}.html").write_text(render_report(fixture), encoding="utf-8")
    print(output / "synthetic-report.html")


if __name__ == "__main__":
    main()
