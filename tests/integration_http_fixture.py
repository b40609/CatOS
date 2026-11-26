"""Isolated loopback fixture for the real Vite proxy regression checks."""
import os
from pathlib import Path
import sys

import uvicorn

from catos import account_lock
from catos.workspace_api import create_app


async def held_runner(directory, run_id, stop, emit, update, source_ok):
    update(control_state="running")
    await stop.wait()
    return dict(control_state="stopped", cleanup_confirmed=True, worker_closed=True)


if __name__ == "__main__":
    root = Path(sys.argv[1]).resolve()
    # Every mutable or production path points inside the temporary fixture root (CAT-BX-06 / CAT-AX-05).
    os.environ["CATOS_KILL_SWITCH"] = str(root / "kill-switch.jsonl")
    os.environ["CATOS_STRATEGY_APPROVALS"] = str(root / "approvals.jsonl")
    os.environ["CATOS_STRATEGY_HOME"] = str(root / "strategy-home")
    os.environ["CATOS_LOCK_DIRECTORY"] = str(root / "locks")
    account_lock.LOCK_DIRECTORY = root / "locks"
    app = create_app(
        output_dir=root / "research",
        evidence_root=root / "evidence",
        simulation_root=root / "simulation",
        replay_root=root / "replay",
        demo_bot_root=root / "demo-bot",
    )
    # "real" keeps the bounded synthetic runner (8 bars, 1 s each) for end-to-end checks;
    # the default held runner never touches a Supervisor or SQLite.
    if len(sys.argv) < 4 or sys.argv[3] != "real":
        app.state.simulation.runner = held_runner
    uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[2]), log_level="warning")
