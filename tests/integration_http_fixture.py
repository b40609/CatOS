"""Isolated loopback fixture for the real Vite proxy regression checks."""
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
    app = create_app(output_dir=root / "research", market_db=root / "missing.sqlite",
                     evidence_root=root / "evidence", simulation_root=root / "simulation")
    app.state.simulation.runner = held_runner
    uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[2]), log_level="warning")
