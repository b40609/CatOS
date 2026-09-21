"""Fixed schema8 DDL. Installed only in a newly created Journal database."""

from catos import lot_journal, lot_fills

LOT_SCHEMA = (lot_journal.SCHEMA[0], lot_journal.SCHEMA[1], """CREATE TABLE lot_revisions (
    lot_id TEXT NOT NULL,
    bot_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK(revision BETWEEN 1 AND 9223372036854775807),
    expected_revision INTEGER NOT NULL CHECK(expected_revision BETWEEN 0 AND 9223372036854775806),
    write_id TEXT NOT NULL CHECK(length(write_id) BETWEEN 1 AND 64),
    commit_seq INTEGER NOT NULL CHECK(commit_seq BETWEEN 1 AND 9223372036854775807),
    operation TEXT NOT NULL CHECK(operation IN ('CREATE','REPLACE')),
    opened_qty TEXT NOT NULL CHECK(typeof(opened_qty)='text'),
    remaining_qty TEXT NOT NULL CHECK(typeof(remaining_qty)='text'),
    average_entry TEXT NOT NULL CHECK(typeof(average_entry)='text'),
    realized_pnl TEXT NOT NULL CHECK(typeof(realized_pnl)='text'),
    fee_coverage TEXT NOT NULL CHECK(fee_coverage IN ('MANAGED','UNVERIFIED')),
    known_fee_subtotal TEXT CHECK(known_fee_subtotal IS NULL OR typeof(known_fee_subtotal)='text'),
    fee_unknown_fill_count INTEGER CHECK(fee_unknown_fill_count IS NULL OR fee_unknown_fill_count BETWEEN 0 AND 9223372036854775807),
    funding_paid TEXT CHECK(funding_paid IS NULL OR typeof(funding_paid)='text'),
    trigger_price_type TEXT NOT NULL CHECK(trigger_price_type='mark'),
    take_profit TEXT CHECK(take_profit IS NULL OR typeof(take_profit)='text'),
    stop_loss TEXT CHECK(stop_loss IS NULL OR typeof(stop_loss)='text'),
    opening_unresolved INTEGER NOT NULL CHECK(opening_unresolved IN (0,1)),
    closing_unresolved INTEGER NOT NULL CHECK(closing_unresolved IN (0,1)),
    request_json TEXT NOT NULL CHECK(length(CAST(request_json AS BLOB)) BETWEEN 1 AND 65536),
    request_hash TEXT NOT NULL CHECK(length(request_hash)=64 AND request_hash NOT GLOB '*[^0-9a-f]*'),
    PRIMARY KEY(lot_id,revision), UNIQUE(bot_id,write_id), UNIQUE(bot_id,commit_seq),
    FOREIGN KEY(lot_id,bot_id) REFERENCES lot_heads(lot_id,bot_id),
    CHECK(revision=expected_revision+1),
    CHECK((operation='CREATE' AND expected_revision=0) OR (operation='REPLACE' AND expected_revision>=1)),
    CHECK((fee_coverage='MANAGED' AND known_fee_subtotal IS NOT NULL AND fee_unknown_fill_count IS NOT NULL)
       OR (fee_coverage='UNVERIFIED' AND known_fee_subtotal IS NULL AND fee_unknown_fill_count IS NULL))
) STRICT""")

FILL_TABLES = (*lot_fills.TABLES, "lot_fee_completions")
FILL_SCHEMA = (lot_fills.SCHEMA[0], f"""CREATE TABLE lot_fill_events (
    order_key TEXT NOT NULL REFERENCES lot_fill_orders(order_key),
    trade_id TEXT NOT NULL, fill_seq INTEGER NOT NULL CHECK(fill_seq>0),
    quantity TEXT NOT NULL, price TEXT NOT NULL,
    fee_state TEXT NOT NULL CHECK(fee_state IN ('KNOWN','UNKNOWN')),
    fee_paid TEXT,
    fee_currency TEXT NOT NULL CHECK(fee_currency='USDT'),
    {lot_fills._COMMON}, PRIMARY KEY(order_key,trade_id), UNIQUE(order_key,fill_seq),
    CHECK((fee_state='KNOWN' AND fee_paid IS NOT NULL AND typeof(fee_paid)='text')
       OR (fee_state='UNKNOWN' AND fee_paid IS NULL))
) STRICT""", lot_fills.SCHEMA[2], """CREATE TABLE lot_fee_completions (
    order_key TEXT NOT NULL, trade_id TEXT NOT NULL,
    fee_paid TEXT NOT NULL, fee_currency TEXT NOT NULL CHECK(fee_currency='USDT'),
    seq INTEGER NOT NULL UNIQUE CHECK(seq>0),
    request_json TEXT NOT NULL CHECK(length(CAST(request_json AS BLOB)) BETWEEN 1 AND 65536),
    request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
    lot_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0),
    commit_seq INTEGER NOT NULL CHECK(commit_seq>0),
    PRIMARY KEY(order_key,trade_id),
    FOREIGN KEY(order_key,trade_id) REFERENCES lot_fill_events(order_key,trade_id),
    FOREIGN KEY(lot_id,revision) REFERENCES lot_revisions(lot_id,revision),
    UNIQUE(lot_id,revision)
) STRICT""")


def install_lot_schema(db):
    for sql in LOT_SCHEMA:
        db.execute(sql)


def install_fill_schema(db):
    for sql in FILL_SCHEMA:
        db.execute(sql)


class LotJournalV2(lot_journal.LotJournal):
    schema_version = 8
    schema = LOT_SCHEMA


class LotFillJournalV2(lot_fills.LotFillJournal):
    v2 = True
    tables = FILL_TABLES
    schema = FILL_SCHEMA
    kinds = ("bind", "fill", "terminal", "fee_completion")

    @staticmethod
    def _write_id(seq, fingerprint):
        return "s9_" + lot_journal._hash(lot_journal._json(dict(seq=seq, fingerprint=fingerprint)))[:61]
