"""Read-only acceptance of a finished R4 run; never starts or stops processes."""

import argparse
from contextlib import closing
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3

from catos import ipc, risk
from catos.local_sim_r4 import PROFILES, RUNTIME_FILES, project_account
from catos.research_catalog import ROOT, DEFAULT_REQUEST, files_hash, provenance, validate_request


class VerificationError(ValueError):
    pass


def require(condition, name):
    if not condition:
        raise VerificationError(name)


def process_alive(pid):
    require(type(pid) is int and pid > 0, "invalid_process_id")
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)  # Query-only handle.
        if not handle:
            require(ctypes.get_last_error() == 87, "process_liveness_unavailable")
            return False
        try:
            code = wintypes.DWORD()
            require(kernel.GetExitCodeProcess(handle, ctypes.byref(code)), "process_liveness_unavailable")
            return code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)  # POSIX-only existence probe; never used on Windows.
        return True
    except ProcessLookupError:
        return False


def read_json(path):
    require(path.is_file() and not path.is_symlink(), "missing_or_symlink_evidence")
    require(path.stat().st_size <= 65536, "evidence_size_limit")
    return json.loads(path.read_text(encoding="utf-8"))


def verify_directory(directory, *, alive=process_alive):
    directory = Path(directory)
    require(not directory.is_symlink(), "symlink_run_rejected")
    manifest = read_json(directory / "manifest.json")
    status = read_json(directory / "status.json")
    require(manifest["run_id"] == status["run_id"] == directory.name, "run_identity_mismatch")
    require(manifest["profile"] == status["profile"] and status["profile"] in PROFILES, "profile_mismatch")
    profile = status["profile"]
    if status["state"] != "complete":
        return dict(verdict="PENDING" if status["state"] in ("starting", "running") else "FAIL",
                    run_id=status["run_id"], state=status["state"], bars=status["bars"],
                    fills=status["fills"], anomalies=status["anomalies"], error=status.get("error"))
    count, interval = PROFILES[profile]
    require(manifest["bars"] == count and manifest["interval_seconds"] == interval, "schedule_mismatch")
    require(status["planned_seconds"] == count * interval, "planned_duration_mismatch")
    elapsed = status["elapsed_seconds"]
    require(type(elapsed) in (float, int) and math.isfinite(elapsed) and elapsed >= count * interval, "wall_duration_incomplete")
    start, end = (datetime.fromisoformat(status[key]) for key in ("started_at", "finished_at"))
    require(start.utcoffset() is not None and end.utcoffset() is not None, "wall_timezone_missing")
    require(abs((end - start).total_seconds() - elapsed) < 2, "wall_monotonic_duration_mismatch")
    require(status["bars"] == count and status["warmup_bars"] == 2 and status["anomalies"] == 0, "counts_or_anomalies")
    require(status.get("worker_closed") is True, "worker_cleanup_unproven")
    require(not alive(status["worker_pid"]) and not alive(status["pid"]), "run_process_still_alive")
    require(manifest["runtime_files"] == list(RUNTIME_FILES), "runtime_manifest_mismatch")
    require(manifest["runtime_sha256"] == files_hash(RUNTIME_FILES), "runtime_digest_changed")
    require(manifest["provenance"] == provenance(), "strategy_or_engine_provenance_changed")
    request, config, _, _ = validate_request(DEFAULT_REQUEST)
    require(manifest["request"] == request and manifest["funding"] == "explicit_zero", "request_or_funding_mismatch")
    require(manifest["worker_config"] == ipc.WorkerConfig(config.contract, config.timeframe_ms, 2,
            "sma-parameters-v1").to_wire(), "registered_worker_config_mismatch")
    events_path = directory / "events.jsonl"
    require(not events_path.is_symlink() and events_path.stat().st_size <= 2_000_000, "events_size_or_symlink")
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    warmups = [row for row in events if row["kind"] == "warmup"]
    signals = [row for row in events if row["kind"] == "signal"]
    fills = [row for row in events if row["kind"] == "fill"]
    final = [row for row in events if row["kind"] == "final_account"]
    require(not any(row["kind"] in ("anomaly", "stop") for row in events), "anomaly_event_present")
    require([row["seq"] for row in warmups] == [1, 2] and all(row["target"] is None for row in warmups), "warmup_intent_or_sequence")
    require([row["seq"] for row in signals] == list(range(3, count + 3)), "signal_sequence_gap")
    require(len(final) == 1 and len(fills) == status["fills"], "final_or_fill_count_mismatch")
    for index, signal in enumerate(signals, 1):
        offset = (datetime.fromisoformat(signal["wall_time"]) - start).total_seconds()
        require(0 <= offset - index * interval <= 120, "signal_wall_cadence_mismatch")
        require(signal["synthetic_time_ms"] == manifest["synthetic_anchor_ms"] + (index + 2) * config.timeframe_ms, "synthetic_cadence_mismatch")
    database = directory / "state.sqlite3"
    require(database.is_file() and not database.is_symlink(), "missing_or_symlink_database")
    require(Path(manifest["database"]).resolve() == database.resolve(), "database_path_mismatch")
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")  # Pin all read-only checks to one WAL snapshot.
        require(db.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "journal_integrity_failed")
        metadata = db.execute("SELECT * FROM metadata").fetchone()
        require(metadata["account_id"] == "r4-" + status["run_id"] and metadata["environment"] == "local-sim", "account_scope_mismatch")
        bot = db.execute("SELECT * FROM bots").fetchall()
        require(len(bot) == 1 and bot[0]["consumed_seq"] == count + 2 and not bot[0]["isolated"], "bot_state_mismatch")
        require(json.loads(bot[0]["config_json"]) == manifest["worker_config"], "checkpoint_artifact_config_mismatch")
        inputs = db.execute("SELECT * FROM inputs ORDER BY seq").fetchall()
        require([row["seq"] for row in inputs] == list(range(1, count + 3)) and all(row["state"] == "COMMITTED" for row in inputs), "journal_input_gap")
        for row, event in zip(inputs, warmups + signals):
            for body, stored_hash in (("input_json", "input_hash"), ("result_json", "result_hash")):
                require(hashlib.sha256(row[body].encode("utf-8")).hexdigest() == row[stored_hash], "journal_content_digest_mismatch")
            receipt = json.loads(row["receipt_json"])
            require(receipt["target"] == event["target"] and receipt["disposition"] == event["disposition"], "signal_receipt_mismatch")
            if row["seq"] <= 2:
                require(receipt["intent_key"] is None, "persisted_warmup_intent")
            else:
                require(receipt["intent_key"] == event["intent_key"], "intent_identity_mismatch")
        require(json.loads(bot[0]["checkpoint_json"]) == json.loads(inputs[-1]["receipt_json"])["checkpoint"], "final_checkpoint_mismatch")
        for table in ("reservations", "outbox", "risk_orders"):
            require(db.execute("SELECT count(*) FROM " + table).fetchone()[0] == 0, "unreleased_" + table)
        orders = db.execute("SELECT * FROM execution_orders ORDER BY rowid").fetchall()
        require(len(orders) == len(fills) and all(row["state"] == "FILLED" and row["settled"] == 1 for row in orders), "unresolved_orders")
        stored_fills = db.execute("""SELECT f.*,o.quantity AS order_quantity,i.seq FROM execution_fills f
            JOIN execution_orders o ON o.order_key=f.order_key
            JOIN intents i ON i.intent_key=o.intent_key ORDER BY f.rowid""").fetchall()
        require(len(stored_fills) == len(fills), "journal_fill_count_mismatch")
        for row, event, order in zip(stored_fills, fills, orders):
            require(row["seq"] == event["seq"] and order["intent_key"] == signals[row["seq"] - 3]["intent_key"], "fill_sequence_mismatch")
            require(json.loads(order["payload_json"]) == event["request"], "fill_request_mismatch")
            payload = event["request"]
            require(payload["tag"] == "41cb53c54d6dABDE" and payload["tdMode"] == "cross" and payload["posSide"] == "net", "order_invariant_failed")
            require(event["synthetic_time_ms"] == signals[row["seq"] - 3]["synthetic_time_ms"], "next_open_boundary_mismatch")
            require(row["trade_id"] == event["fill"]["trade_id"], "trade_identity_mismatch")
            for key in ("quantity", "price", "fee"):
                require(type(event["fill"][key]) is str and row[key] == event["fill"][key], "decimal_fill_mismatch")
                ipc.decimal_text(row[key], key, derived=True)
            require(Decimal(row["quantity"]) == Decimal(order["quantity"]).copy_abs() == Decimal(order["filled"]), "incomplete_fill")
        for table, columns in (("execution_fills", ("quantity", "price", "fee")), ("execution_orders", ("quantity", "filled", "reservation"))):
            for column in columns:
                require(db.execute(f"SELECT count(*) FROM {table} WHERE typeof({column})!='text'").fetchone()[0] == 0, "sqlite_financial_type_mismatch")
        for signal, row in zip(signals, inputs[2:]):
            incoming = json.loads(row["input_json"])["payload"]
            prior = [dict(fill) for fill in stored_fills if fill["seq"] < row["seq"]]
            view = project_account(prior, config, signal["synthetic_time_ms"], Decimal(incoming["bar"]["close"]))
            require(ipc.account_to_wire(view) == signal["account"] == incoming["account"], "account_projection_mismatch")
        last_input = json.loads(inputs[-1]["input_json"])["payload"]
        view = project_account([dict(row) for row in stored_fills], config, signals[-1]["synthetic_time_ms"], Decimal(last_input["bar"]["close"]))
        require(ipc.account_to_wire(view) == final[0]["account"], "final_account_mismatch")
        owner = db.execute("SELECT * FROM ownership").fetchone()
        require(Decimal(owner["position"]) == view.position and owner["fills_reconciled"] == 1 and owner["reconciled_revision"] == bot[0]["revision"], "position_or_reconciliation_mismatch")
        state = risk.State.from_wire(json.loads(db.execute("SELECT state_json FROM risk_control").fetchone()[0]))
        require(not state.reasons and risk.is_verified_baseline(state.basis, account_alias=metadata["account_id"], environment="local-sim", target_day=risk.taipei_day(view.time_ms)), "risk_or_baseline_mismatch")
    return dict(verdict="PASS" if profile == "eight-hour" else "SMOKE_PASS", run_id=status["run_id"],
                profile=profile, elapsed_seconds=elapsed, bars=count, fills=len(fills), anomalies=0,
                final_equity=str(view.equity), fees=str(view.fees), database_mode="read-only", runtime_digest_unchanged=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    args = parser.parse_args()
    if re.fullmatch(r"[0-9a-f]{32}", args.run_id) is None:
        parser.error("run_id must be 32 lowercase hex characters")
    try:
        result = verify_directory(ROOT / "outputs" / "local-sim-r4" / args.run_id)
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as error:
        result = dict(verdict="FAIL", run_id=args.run_id, error=str(error))
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["verdict"] in ("PASS", "SMOKE_PASS") else 2 if result["verdict"] == "PENDING" else 1


if __name__ == "__main__":
    raise SystemExit(main())
