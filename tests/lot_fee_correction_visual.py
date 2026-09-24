"""Opt-in S10 visual fixtures; creates only a new explicitly named directory."""

from contextlib import closing
from decimal import Decimal as D
from pathlib import Path

from catos.journal import Journal
from catos.lot_scenario_report import render_synthetic_scenario_report_v3
from lot_fill_helpers import opening, terminal
from lot_journal_helpers import scope, contract
from test_lot_fee_completion import completion, fill_v2
from test_lot_fee_correction import correction
from test_lot_scenario import evidence


def build(directory):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    with closing(Journal(root / "scenario.sqlite3", "fake-account", D(100), lot_schema_version=9)) as journal:
        journal.lots.register_binding(scope=scope(), bot_id="lot-bot", contract=contract())
        opening(journal)
        journal.lot_fills.apply_fill_v2(fill_v2(fee=D(".02")))
        journal.lot_fills.apply_fill_v2(fill_v2(seq=2, quantity=D(2)))
        terminal(journal, seq=2)
        for name in ("before", "corrected-incomplete", "corrected-complete"):
            if name == "corrected-incomplete":
                journal.lot_fills.correct_fee(correction(fee=D("-.123456789012345678")))
            elif name == "corrected-complete":
                journal.lot_fills.complete_fee(completion(trade="trade-2", fee=D(".012345678901234567")))
            captured = journal.capture_lot_snapshot_v3(scope=scope(), inst_id=contract().inst_id,
                                                      observed_at_ms=90, valid_until_ms=110)
            html = render_synthetic_scenario_report_v3(capture=captured,
                scenario=evidence(captured, physical_quantity=D(3)), now_ms=100)
            with (root / (name + ".html")).open("x", encoding="utf-8") as target:
                target.write(html)
    return root
