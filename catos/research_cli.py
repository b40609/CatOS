"""Command-line entry point for catOS research backtests.

Connects load_candles_csv, backtest, and render_report.
Uses only Python standard library.
"""

import argparse
from decimal import Decimal, InvalidOperation, localcontext
import json
import os
from pathlib import Path
import sys

from catos.data_io import load_candles_csv
from catos.reporting import render_report
from catos.research import (
    BacktestConfig,
    ContractSpec,
    FundingEvent,
    _CONTEXT,
    backtest,
)
from examples.closed_bar_demo import SMATrend

STRATEGY_MAP = {
    "sma-trend": SMATrend,
}

_ROOT_REQUIRED = {
    "contract",
    "timeframe_ms",
    "initial_balance",
    "fee_rate",
    "slippage_bps",
    "funding_events",
    "warmup_bars",
}

_CONTRACT_REQUIRED = {
    "inst_id",
    "base_per_contract",
    "tick_size",
    "lot_size",
    "min_size",
}

_EVENT_REQUIRED = {
    "time_ms",
    "rate",
    "mark_price",
}


def _reject_constant(val: str) -> None:
    raise ValueError(f"JSON contains forbidden constant: {val!r}")


def _pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for k, v in pairs:
        if k in result:
            raise ValueError(f"JSON contains duplicate key: {k!r}")
        result[k] = v
    return result


def parse_config_json(path: Path | str) -> tuple[BacktestConfig, int]:
    """Parse and validate JSON research configuration file.

    Returns
    -------
    tuple[BacktestConfig, int]
        Parsed BacktestConfig and warmup_bars; market validation runs in the pipeline.
    """
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"config file not found: {path}")

    raw_text = path_obj.read_text(encoding="utf-8-sig")
    data = json.loads(raw_text, object_pairs_hook=_pairs_hook, parse_constant=_reject_constant)

    if not isinstance(data, dict):
        raise ValueError("Root JSON configuration must be an object")

    missing_root = _ROOT_REQUIRED - data.keys()
    extra_root = data.keys() - _ROOT_REQUIRED
    if missing_root:
        raise ValueError(f"config missing required keys: {sorted(missing_root)}")
    if extra_root:
        raise ValueError(f"config contains unexpected keys: {sorted(extra_root)}")

    # Check timeframe_ms
    timeframe_ms = data["timeframe_ms"]
    if type(timeframe_ms) is not int:
        raise TypeError("field 'timeframe_ms' must be an integer, not bool, float, or string")

    # Check warmup_bars
    warmup_bars = data["warmup_bars"]
    if type(warmup_bars) is not int:
        raise TypeError("field 'warmup_bars' must be an integer, not bool, float, or string")
    if warmup_bars < 0:
        raise ValueError("field 'warmup_bars' must be a non-negative integer")

    with localcontext(_CONTEXT):
        # Check financial Decimal strings at root level
        for key in ("initial_balance", "fee_rate", "slippage_bps"):
            val = data[key]
            if type(val) is not str:
                raise TypeError(f"field {key!r} must be a string representing a Decimal, got {type(val).__name__}")
            try:
                Decimal(val)
            except InvalidOperation as e:
                raise ValueError(f"field {key!r} contains invalid decimal text: {val!r}") from e

        # Check contract object
        contract_data = data["contract"]
        if not isinstance(contract_data, dict):
            raise TypeError("field 'contract' must be an object")

        missing_contract = _CONTRACT_REQUIRED - contract_data.keys()
        extra_contract = contract_data.keys() - _CONTRACT_REQUIRED
        if missing_contract:
            raise ValueError(f"contract missing required keys: {sorted(missing_contract)}")
        if extra_contract:
            raise ValueError(f"contract contains unexpected keys: {sorted(extra_contract)}")

        inst_id = contract_data["inst_id"]
        if type(inst_id) is not str:
            raise TypeError("field 'contract.inst_id' must be a string")

        for key in ("base_per_contract", "tick_size", "lot_size", "min_size"):
            val = contract_data[key]
            if type(val) is not str:
                raise TypeError(f"field 'contract.{key}' must be a string representing a Decimal, got {type(val).__name__}")
            try:
                Decimal(val)
            except InvalidOperation as e:
                raise ValueError(f"field 'contract.{key}' contains invalid decimal text: {val!r}") from e

        # Check funding_events array
        events_data = data["funding_events"]
        if type(events_data) is not list:
            raise TypeError("field 'funding_events' must be an array")

        funding_events: list[FundingEvent] = []
        for i, ev in enumerate(events_data):
            if not isinstance(ev, dict):
                raise TypeError(f"funding_events[{i}] must be an object")
            missing_ev = _EVENT_REQUIRED - ev.keys()
            extra_ev = ev.keys() - _EVENT_REQUIRED
            if missing_ev:
                raise ValueError(f"funding_events[{i}] missing required keys: {sorted(missing_ev)}")
            if extra_ev:
                raise ValueError(f"funding_events[{i}] contains unexpected keys: {sorted(extra_ev)}")

            t_ms = ev["time_ms"]
            if type(t_ms) is not int:
                raise TypeError(f"funding_events[{i}].time_ms must be an integer, not bool, float, or string")

            for ev_key in ("rate", "mark_price"):
                val = ev[ev_key]
                if type(val) is not str:
                    raise TypeError(f"funding_events[{i}].{ev_key} must be a string representing a Decimal, got {type(val).__name__}")
                try:
                    Decimal(val)
                except InvalidOperation as e:
                    raise ValueError(f"funding_events[{i}].{ev_key} contains invalid decimal text: {val!r}") from e

            funding_events.append(FundingEvent(t_ms, Decimal(ev["rate"]), Decimal(ev["mark_price"])))

        contract_spec = ContractSpec(
            inst_id=inst_id,
            base_per_contract=Decimal(contract_data["base_per_contract"]),
            tick_size=Decimal(contract_data["tick_size"]),
            lot_size=Decimal(contract_data["lot_size"]),
            min_size=Decimal(contract_data["min_size"]),
        )
        config = BacktestConfig(
            contract=contract_spec,
            timeframe_ms=timeframe_ms,
            initial_balance=Decimal(data["initial_balance"]),
            fee_rate=Decimal(data["fee_rate"]),
            slippage_bps=Decimal(data["slippage_bps"]),
            funding_events=tuple(funding_events),
        )

    return config, warmup_bars


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="catOS research CLI: run closed-bar backtest and export HTML report."
    )
    parser.add_argument("--csv", required=True, help="Path to closed-bar CSV data file.")
    parser.add_argument("--config", required=True, help="Path to research JSON config file.")
    parser.add_argument(
        "--strategy",
        required=True,
        choices=list(STRATEGY_MAP.keys()),
        help="Strategy name (currently supported: 'sma-trend').",
    )
    parser.add_argument("--output", required=True, help="Path to output HTML report file.")
    return parser


def run_pipeline(csv_path: str, config_path: str, strategy_name: str, output_path: str) -> None:
    """Execute the full backtest pipeline and write output HTML file."""
    out_path = Path(output_path)
    if out_path.suffix.lower() != ".html":
        raise ValueError(f"output path must have .html extension, got {out_path.suffix!r}")

    csv_resolved = Path(csv_path).resolve()
    config_resolved = Path(config_path).resolve()
    out_resolved = out_path.resolve()

    if out_resolved == csv_resolved:
        raise ValueError("output path cannot be the same as input CSV path")
    if out_resolved == config_resolved:
        raise ValueError("output path cannot be the same as input config path")
    if out_resolved.exists():
        raise ValueError(f"output file already exists: {output_path}")

    # 1. Parse JSON configuration
    config, warmup_bars = parse_config_json(config_path)

    # 2. Load and validate candles CSV
    candles = load_candles_csv(csv_path, config=config)

    # 3. Strategy selection
    strategy_cls = STRATEGY_MAP[strategy_name]

    # 4. Run closed-bar backtest
    result = backtest(
        strategy=strategy_cls,
        candles=candles,
        config=config,
        warmup_bars=warmup_bars,
    )

    # 5. Render self-contained HTML report
    html_content = render_report(result)

    # 6. Exclusive creation write with cleanup on unexpected write failure
    out_resolved.parent.mkdir(parents=True, exist_ok=True)
    try:
        f = open(out_resolved, mode="x", encoding="utf-8")
    except FileExistsError as e:
        raise ValueError(f"output file already exists: {output_path}") from e

    try:
        created_stat = os.fstat(f.fileno())
        f.write(html_content)
        f.flush()
        f.close()
    except BaseException:
        try:
            f.close()
        except BaseException:
            pass
        try:
            if 'created_stat' in locals() and os.path.samestat(created_stat, out_resolved.stat()):
                out_resolved.unlink()
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        run_pipeline(args.csv, args.config, args.strategy, args.output)
    except (ValueError, TypeError, FileNotFoundError, OSError) as err:
        sys.stderr.write(f"錯誤: {err}\n")
        return 2

    sys.stdout.write(
        f"報告已成功輸出至: {args.output}\n"
        "聲明：本報告為純記憶體研究結果，合成或歷史資料來源由使用者自行負責；非 Demo／Live 交易執行器。\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
