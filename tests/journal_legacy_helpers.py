"""Test-only construction of pre-schema-7 ledgers; never a production downgrade."""

from catos.journal import RETAINED_LOT_FILL_TABLES, RETAINED_LOT_TABLES


def drop_empty_lot_schema(connection):
    """Drop the six empty retained tables so a fixture looks like schema 5 or older."""
    drop_empty_fill_schema(connection)
    _drop_empty(connection, RETAINED_LOT_TABLES)


def drop_empty_fill_schema(connection):
    """Drop the three empty retained fill tables so a fixture looks like schema 6."""
    _drop_empty(connection, RETAINED_LOT_FILL_TABLES)


def _drop_empty(connection, tables):
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 0:
        raise AssertionError("legacy fixture requires its own FK-disabled connection")
    existing = [table for table in tables if connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()]
    for table in existing:
        if connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]:
            raise AssertionError("refusing to discard a nonempty retained table")
    for table in reversed(existing):
        connection.execute(f"DROP TABLE {table}")
