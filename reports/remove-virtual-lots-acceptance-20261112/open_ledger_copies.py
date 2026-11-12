"""用目前 cwd 的 catos 開啟帳本「複本」，印出開檔結果與 schema 摘要。

用法：
    python reports/remove-virtual-lots-acceptance-20261112/open_ledger_copies.py COPY_ROOT [OUT.json]

COPY_ROOT 底下每個子目錄放一份 state.sqlite3（含 -wal／-shm）的複本。
Journal 一開檔就會寫入，所以拒絕任何位於 outputs/ 底下的路徑。
"""

from contextlib import closing
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path.cwd()))

import catos  # noqa: E402
from catos import risk  # noqa: E402
from catos.journal import Journal  # noqa: E402

LOT_TABLES = ("lot_bindings", "lot_heads", "lot_revisions",
              "lot_fill_orders", "lot_fill_events", "lot_fill_terminals")


def summary(path):
    with closing(sqlite3.connect(path)) as db:
        return {
            "user_version": db.execute("PRAGMA user_version").fetchone()[0],
            "integrity_check": db.execute("PRAGMA integrity_check").fetchone()[0],
            "lot_rows": {t: db.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in LOT_TABLES},
            "tables": sorted(r[0] for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")),
        }


def open_copy(path):
    with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        meta = db.execute("SELECT * FROM metadata").fetchone()
        saved = db.execute("SELECT limits_json FROM risk_control WHERE id=1").fetchone()
        execution = db.execute("SELECT 1 FROM execution_mode").fetchone() is not None
    limits = None
    if saved is not None:
        limits = risk.Limits(**{k: Decimal(v) for k, v in json.loads(saved[0]).items()})
    journal = Journal(path, meta["account_id"], Decimal(meta["fixture_budget"]), limits, execution)
    try:
        bots = [row[0] for row in journal.connection.execute("SELECT bot_id FROM bots ORDER BY bot_id")]
        snapshots = {bot: journal.snapshot(bot)["revision"] for bot in bots}
        risk_mode = journal.risk_state().mode if limits is not None else None
    finally:
        journal.close()
    return {"opened": True, "risk": limits is not None, "execution": execution,
            "bots": snapshots, "risk_mode": risk_mode}


def main(root, out=None):
    root = Path(root).resolve()
    if "outputs" in {part.lower() for part in root.parts}:
        raise SystemExit("refusing a path under outputs/: copy the ledger first")
    result = {"catos_file": catos.__file__, "ledgers": {}}
    for path in sorted(root.glob("*/state.sqlite3")):
        before = summary(path)
        try:
            opened = open_copy(path)
        except Exception as exc:  # report every ledger, then fail below
            opened = {"opened": False, "error": f"{type(exc).__name__}: {exc}"}
        after = summary(path)
        result["ledgers"][path.parent.name] = {"before": before, "open": opened, "after": after}
        print(path.parent.name, before["user_version"], "->", after["user_version"],
              opened, "lot_rows", sum(after["lot_rows"].values()), after["integrity_check"])
    if out:
        Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if not result["ledgers"] or not all(v["open"]["opened"] for v in result["ledgers"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main(*sys.argv[1:])
