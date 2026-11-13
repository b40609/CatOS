"""Isolated loopback fixture for the real Vite proxy regression checks."""
import os
from pathlib import Path
import sys

import uvicorn

from catos.workspace_api import create_app


async def held_runner(directory, run_id, stop, emit, update, source_ok):
    update(control_state="running")
    await stop.wait()
    return dict(control_state="stopped", cleanup_confirmed=True, worker_closed=True)


if __name__ == "__main__":
    root = Path(sys.argv[1]).resolve()
    # Work package B: the Kill-Switch record file lives in the isolated root, never outputs/.
    os.environ["CATOS_KILL_SWITCH"] = str(root / "kill-switch.jsonl")
    app = create_app(output_dir=root / "research",
                     evidence_root=root / "evidence", simulation_root=root / "simulation")
    # "real" keeps the bounded synthetic runner (8 bars, 1 s each) for end-to-end checks;
    # the default held runner never touches a Supervisor or SQLite.
    if len(sys.argv) < 4 or sys.argv[3] != "real":
        app.state.simulation.runner = held_runner
    uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[2]), log_level="warning")
