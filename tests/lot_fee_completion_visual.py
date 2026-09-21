"""Opt-in S9 visual fixtures for Sol; no execution on import."""

from contextlib import closing
from decimal import Decimal as D
from pathlib import Path

from catos.journal import Journal
from catos.lot_scenario_report import render_synthetic_scenario_report_v2
from lot_fill_helpers import opening, terminal
from lot_journal_helpers import scope, contract
from test_lot_fee_completion import completion, fill_v2
from test_lot_scenario import evidence


def build(directory):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    with closing(Journal(root / "scenario.sqlite3", "fake-account", D(100), lot_schema_version=8)) as journal:
        journal.lots.register_binding(scope=scope(), bot_id="lot-bot", contract=contract())
        opening(journal)
        journal.lot_fills.apply_fill_v2(fill_v2(quantity=D(3)))
        terminal(journal)
        for name in ("incomplete", "complete"):
            if name == "complete":
                journal.lot_fills.complete_fee(completion(fee=D("0.123456789012345678")))
            capture = journal.capture_lot_snapshot_v2(scope=scope(), inst_id=contract().inst_id,
                                                       observed_at_ms=90, valid_until_ms=110)
            html = render_synthetic_scenario_report_v2(capture=capture,
                scenario=evidence(capture, physical_quantity=D(3)), now_ms=100)
            with (root / (name + ".html")).open("x", encoding="utf-8") as target:
                target.write(html)
    return root
