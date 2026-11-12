"""傾印新建 Journal 帳本的 schema，用來比對刪除 Virtual Lots 前後是否相同。

用法（在 repo 根目錄或任一份 catos 程式樹的根目錄執行）：
    python reports/remove-virtual-lots-acceptance-20261112/dump_journal_schema.py OUT.json

只在暫存目錄建立全新帳本，不開任何既有帳本。
"""

from contextlib import closing
from decimal import Decimal as D
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

sys.path.insert(0, str(Path.cwd()))

from catos import risk  # noqa: E402
from catos.journal import Journal  # noqa: E402

CONFIGS = {
    "plain": lambda path: Journal(path, "fake-account", D("100")),
    "risk": lambda path: Journal(path, "fake-account", D("100"), risk.Limits()),
    "risk_execution": lambda path: Journal(path, "fake-account", D("100"), risk.Limits(), True),
}


def dump(path):
    with closing(sqlite3.connect(path)) as db:
        rows = db.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()
        version = db.execute("PRAGMA user_version").fetchone()[0]
    return {"user_version": version, "sqlite_master": [list(row) for row in rows]}


def main(out):
    import catos
    result = {"catos_file": catos.__file__}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        for name, factory in CONFIGS.items():
            path = Path(tmp) / f"{name}.sqlite3"
            journal = factory(path)
            journal.close()
            result[name] = dump(path)
    Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(result["catos_file"], {k: (v["user_version"], len(v["sqlite_master"]))
                                 for k, v in result.items() if k != "catos_file"})


if __name__ == "__main__":
    main(sys.argv[1])
