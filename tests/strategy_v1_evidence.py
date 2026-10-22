"""Evidence for explicitly named fresh fixtures; never inspect product roots."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
from catos.local_sim_control import BUILD_FILES, build_id
from catos.local_sim_control_runner import DATA_PATH
from catos.workspace_api import ASSETS, workspace_build

ROOT = Path(__file__).resolve().parent.parent

def hashes():
    names = set(BUILD_FILES) | {"catos/workspace_snapshot.py"}
    names |= {"frontend/workspace/" + n for n in ("index.html", "home.html", "desk.html", *ASSETS)}
    names |= {"tests/" + n for n in ("test_python_strategy_v1.py", "test_python_strategy_api.py", "strategy_v1_mcp_probe.py", "strategy_v1_evidence.py", "simulation_result_fixture.py")}
    names.add(str(DATA_PATH.relative_to(ROOT)).replace("\\", "/"))
    return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(names)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--fixture", type=Path)
    options = parser.parse_args()
    value = {"python": platform.python_version(), "runtime_build": build_id(), "workspace_build": workspace_build(), "sha256": hashes()}
    if options.baseline:
        previous = json.loads(options.baseline.read_text(encoding="utf-8"))
        assert previous == value, "source/input drift"
        value["baseline_unchanged"] = True
    if options.fixture:
        root = options.fixture.resolve()
        assert root.is_relative_to(ROOT/"outputs"/"v1-local-core-20261002-dev"), "not this work package fixture"
        ready = json.loads((root/"ready.json").read_text())
        closed = json.loads((root/"exit.json").read_text())
        assert ready["build"] == value["runtime_build"]
        assert closed["owner_closed"] and closed["active"] is None
        evidence = []
        for run in closed["runs"]:
            assert run["cleanup_confirmed"] and run["control_state"] in ("completed", "stopped")
            outcome = {key: run[key] for key in ("worker_closed", "worker_returncode", "input_hash", "effective_input_hash", "worker_pid")}
            assert outcome["worker_closed"] and outcome["worker_returncode"] == 0
            db = root/"simulation"/run["run_id"]/"state.sqlite3"
            with sqlite3.connect(db.as_uri()+"?mode=ro", uri=True) as connection:
                assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                evidence.append({"run_id": run["run_id"], "state": run["control_state"], "database_sha256": hashlib.sha256(db.read_bytes()).hexdigest(), "tables": sorted(tables), "outcome": outcome})
        value["fixture"] = {"ready": ready, "exit": closed, "databases": evidence}
    options.output.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(options.output), "sources": len(value["sha256"]), "runs": len(value.get("fixture", {}).get("databases", []))}))

if __name__ == "__main__":
    main()
