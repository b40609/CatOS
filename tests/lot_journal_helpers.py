"""Synthetic S2 fixtures, including removal of EMPTY S2 tables for legacy tests."""

from decimal import Decimal as D

from catos import lots
from catos.lot_journal import TABLES
from catos.research import ContractSpec


def scope():
    return lots.LotScope("fake-account", "local-sim")


def contract(**changes):
    values = dict(inst_id="SYNTHETIC-USDT-SWAP", base_per_contract=D("0.01"),
                  tick_size=D("0.5"), lot_size=D("0.5"), min_size=D("1"))
    values.update(changes)
    return ContractSpec(**values)


def snapshot(bot="lot-bot", seq=1, spec=None, **changes):
    context = lots.IntentContext(scope(), bot, spec or contract(), seq, False)
    key = lots.make_intent_key(context)
    values = dict(scope=context.scope, bot_id=bot, inst_id=context.contract.inst_id,
                  lot_id=lots.make_lot_id(key), open_intent_key=key, side="long",
                  opened_qty=D("2"), remaining_qty=D("2"), average_entry=D("100.25"),
                  realized_pnl=D("0"), fees_paid=D("-0.1"), funding_paid=None,
                  protection=lots.LotProtection("mark", None, None), revision=1)
    values.update(changes)
    return lots.Lot(**values)


def create(journal, value=None, *, write_id="create-1", seq=1, opening=False, closing=False):
    value = value or snapshot(seq=seq)
    return journal.lots.create(scope=scope(), bot_id=value.bot_id, write_id=write_id,
                               open_event_seq=seq, after=value,
                               opening_unresolved=opening, closing_unresolved=closing)


def update(journal, value, *, write_id="update-1", expected=1, opening=False, closing=False):
    return journal.lots.replace(scope=scope(), bot_id=value.bot_id, write_id=write_id,
                                expected_revision=expected, after=value,
                                opening_unresolved=opening, closing_unresolved=closing)


def drop_empty_lot_schema(connection):
    """Test-only legacy fixture construction, never a production downgrade."""
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 0:
        raise AssertionError("legacy fixture requires its own FK-disabled connection")
    drop_empty_fill_schema(connection)
    for table in TABLES:
        if connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]:
            raise AssertionError("refusing to discard nonempty S2 fixture")
    for table in reversed(TABLES):
        connection.execute(f"DROP TABLE {table}")


def drop_empty_fill_schema(connection):
    from catos.lot_fills import TABLES as fill_tables
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 0:
        raise AssertionError("legacy fixture requires FK-disabled connection")
    existing = [table for table in fill_tables if connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone()]
    for table in existing:
        if connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]:
            raise AssertionError("refusing nonempty S3 fixture")
    for table in reversed(existing):
        connection.execute(f"DROP TABLE {table}")
