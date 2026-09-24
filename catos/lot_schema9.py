"""Fixed schema9 and private correction proof gates on the existing writer."""

from contextlib import contextmanager

from catos import lot_journal, lot_fills, lot_schema8


LOT_SCHEMA = lot_schema8.LOT_SCHEMA
FILL_TABLES = (*lot_schema8.FILL_TABLES, "lot_fee_corrections")
FILL_SCHEMA = (*lot_schema8.FILL_SCHEMA, """CREATE TABLE lot_fee_corrections (
    order_key TEXT NOT NULL,
    trade_id TEXT NOT NULL,
    correction_id TEXT NOT NULL CHECK(length(correction_id) BETWEEN 1 AND 64),
    predecessor_event_seq INTEGER NOT NULL
        CHECK(predecessor_event_seq BETWEEN 1 AND 9223372036854775807),
    fee_paid TEXT NOT NULL CHECK(typeof(fee_paid)='text'),
    fee_currency TEXT NOT NULL CHECK(fee_currency='USDT'),
    seq INTEGER NOT NULL UNIQUE CHECK(seq BETWEEN 1 AND 9223372036854775807),
    request_json TEXT NOT NULL
        CHECK(length(CAST(request_json AS BLOB)) BETWEEN 1 AND 65536),
    request_hash TEXT NOT NULL
        CHECK(length(request_hash)=64 AND request_hash NOT GLOB '*[^0-9a-f]*'),
    lot_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK(revision BETWEEN 1 AND 9223372036854775807),
    commit_seq INTEGER NOT NULL CHECK(commit_seq BETWEEN 1 AND 9223372036854775807),
    PRIMARY KEY(order_key,trade_id,correction_id),
    FOREIGN KEY(order_key,trade_id) REFERENCES lot_fill_events(order_key,trade_id),
    FOREIGN KEY(lot_id,revision) REFERENCES lot_revisions(lot_id,revision),
    UNIQUE(lot_id,revision),
    UNIQUE(predecessor_event_seq),
    CHECK(predecessor_event_seq<seq)
) STRICT""")


def install_lot_schema(db):
    for sql in LOT_SCHEMA:
        db.execute(sql)


def install_fill_schema(db):
    for sql in FILL_SCHEMA:
        db.execute(sql)


class LotJournalV3(lot_journal.LotJournal):
    schema_version = 9
    schema = LOT_SCHEMA

    def __init__(self, journal):
        super().__init__(journal)
        self._structural_scan = False
        self._correction_candidate = None

    @contextmanager
    def _access(self):
        with super()._access():
            # Every public S2/S3 access, including absent lookups and bindings,
            # must prove the whole ledger before returning any state.
            self._recover_in_transaction()
            yield

    def _transition(self, before, after, opening, closing):
        try:
            super()._transition(before, after, opening, closing)
        except lot_journal.LotStorageError as exc:
            if exc.code != "no_change":
                raise
            managed = (before.lot.fee_quality.coverage == "MANAGED"
                       and after.fee_quality.coverage == "MANAGED")
            if managed and (self._structural_scan
                            or self._correction_candidate == (after, opening, closing)):
                return
            raise

    def _structural_recover(self):
        self._structural_scan = True
        try:
            return super()._recover_in_transaction()
        finally:
            self._structural_scan = False

    def _recover_in_transaction(self):
        report = self._structural_recover()
        # S3 calls only _structural_recover, never this full proof entry point.
        self.j.lot_fills._recover_in_transaction()
        return report


class LotFillJournalV3(lot_fills.LotFillJournal):
    v2 = True
    v3 = True
    tables = FILL_TABLES
    schema = FILL_SCHEMA
    kinds = ("bind", "fill", "terminal", "fee_completion", "fee_correction")

    @staticmethod
    def _write_id(seq, fingerprint):
        return "s10_" + lot_journal._hash(lot_journal._json(dict(seq=seq, fingerprint=fingerprint)))[:60]

    def _save_result(self, payload, seq, fingerprint, result):
        # Called only after deterministic evaluation of all prior events plus
        # this candidate. The capability is scoped to this exact Lot and flags.
        _, after, opening, closing, _ = result
        if payload["kind"] != "fee_correction":
            return super()._save_result(payload, seq, fingerprint, result)
        self.j.lots._correction_candidate = (after, opening, closing)
        try:
            return super()._save_result(payload, seq, fingerprint, result)
        finally:
            self.j.lots._correction_candidate = None
