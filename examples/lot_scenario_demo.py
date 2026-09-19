"""Fixed local S3 -> S5 -> S7 scenario example; never exchange evidence."""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path
import sys

from catos import lots
from catos.journal import Journal
from catos.lot_accounting import SyntheticFill
from catos.lot_scenario import SyntheticScenarioEvidence
from catos.lot_scenario_report import render_synthetic_scenario_report
from catos.research import ContractSpec


ACCOUNT_ID = "s8-example-account"
BOT_ID = "s8-example-bot"
SOURCE_ID = "s8-synthetic"
ORDER_ID = "s8-open-1"
TRADE_ID = "s8-trade-1"
NOW_MS = 1500


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m examples.lot_scenario_demo",
        allow_abbrev=False,
        description=(
            "Create one fixed local synthetic S3->S5->S7 example. "
            "The run retains its SQLite database and HTML reports, never overwrites an "
            "existing output directory, and failures may retain partial artifacts."
        ),
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=_nonempty_path,
        metavar="PATH",
        help="new output directory; its parent must already exist",
    )
    return parser


def _nonempty_path(value: str) -> str:
    if value == "":
        raise argparse.ArgumentTypeError("PATH must not be empty")
    return value


def _fixed_inputs():
    scope = lots.LotScope(ACCOUNT_ID, "local-sim")
    contract = ContractSpec(
        inst_id="SYNTHETIC-USDT-SWAP",
        base_per_contract=Decimal("0.01"),
        tick_size=Decimal("0.5"),
        lot_size=Decimal("0.5"),
        min_size=Decimal("1"),
    )
    context = lots.IntentContext(scope, BOT_ID, contract, 1, False)
    intent = lots.OpenLot(
        "long", Decimal("3"), lots.LotProtection("mark", None, None)
    )
    fill = SyntheticFill(
        scope=scope,
        source_id=SOURCE_ID,
        inst_id=contract.inst_id,
        order_id=ORDER_ID,
        trade_id=TRADE_ID,
        fill_seq=1,
        quantity=Decimal("1"),
        price=Decimal("100"),
        fee_paid=Decimal("0.01"),
        fee_currency="USDT",
    )
    return scope, contract, context, intent, fill


def _scenarios(capture, scope, contract):
    common = dict(
        source="synthetic_scenario",
        scope=scope,
        contract=contract,
        source_capture_id=capture.capture_id,
        physical_observed_at_ms=1100,
        physical_valid_until_ms=2100,
        physical_quantity=Decimal("1"),
    )
    complete = SyntheticScenarioEvidence(
        scenario_cut_id="s8-complete-cut",
        physical_complete=True,
        mark_quote_id="s8-mark-1",
        mark_observed_at_ms=1200,
        mark_valid_until_ms=2200,
        mark=Decimal("100.123456789012345678901234"),
        **common,
    )
    degraded = SyntheticScenarioEvidence(
        scenario_cut_id="s8-degraded-cut",
        physical_complete=False,
        mark_quote_id=None,
        mark_observed_at_ms=None,
        mark_valid_until_ms=None,
        mark=None,
        **common,
    )
    return complete, degraded


def _render_run(journal: Journal):
    scope, contract, context, intent, fill = _fixed_inputs()
    journal.lots.register_binding(scope=scope, bot_id=BOT_ID, contract=contract)
    journal.lot_fills.bind_order(
        source_id=SOURCE_ID, order_id=ORDER_ID, context=context, intent=intent
    )
    journal.lot_fills.apply_fill(fill)
    capture = journal.capture_lot_snapshot(
        scope=scope,
        inst_id=contract.inst_id,
        observed_at_ms=1000,
        valid_until_ms=2000,
    )
    complete, degraded = _scenarios(capture, scope, contract)
    complete_html = render_synthetic_scenario_report(
        capture=capture, scenario=complete, now_ms=NOW_MS
    )
    degraded_html = render_synthetic_scenario_report(
        capture=capture, scenario=degraded, now_ms=NOW_MS
    )
    return complete_html, degraded_html


def _write_exclusive(path: Path, content: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def _failure(stage: str, exc: BaseException, run_dir: Path | None) -> int:
    print(
        f"S8 example failed: stage={stage}; error={type(exc).__name__}",
        file=sys.stderr,
    )
    if run_dir is not None:
        print(
            f"artifacts={run_dir}; retained; retry with a new output directory",
            file=sys.stderr,
        )
    return 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    requested = Path(args.output_dir)
    run_dir: Path | None = None
    stage = "output_dir"
    try:
        requested.mkdir(parents=False, exist_ok=False)
        run_dir = requested.resolve()
        database = run_dir / "scenario.sqlite3"

        stage = "journal_init"
        journal = Journal(
            database,
            ACCOUNT_ID,
            Decimal("1000"),
            risk_limits=None,
            execution_enabled=False,
        )

        body_error: BaseException | None = None
        complete_html = degraded_html = None
        try:
            stage = "scenario"
            complete_html, degraded_html = _render_run(journal)
        except BaseException as exc:
            body_error = exc

        stage = "journal_close"
        try:
            journal.close()
        except BaseException as close_error:
            if body_error is not None:
                raise BaseExceptionGroup(
                    "S8 scenario and journal close both failed",
                    [body_error, close_error],
                )
            raise

        if body_error is not None:
            stage = "scenario"
            raise body_error

        stage = "write_complete"
        complete_path = run_dir / "complete.html"
        _write_exclusive(complete_path, complete_html)

        stage = "write_degraded"
        degraded_path = run_dir / "degraded.html"
        _write_exclusive(degraded_path, degraded_html)

        print(f"database={database}")
        print(f"complete={complete_path}")
        print(f"degraded={degraded_path}")
        return 0
    except Exception as exc:
        return _failure(stage, exc, run_dir)


if __name__ == "__main__":
    raise SystemExit(main())
