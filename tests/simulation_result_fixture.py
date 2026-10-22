"""Isolated real-Worker browser fixture for the bounded result work package."""

import argparse
import json
import os
from pathlib import Path
import socket
import shutil

from fastapi import FastAPI, HTTPException
import uvicorn

from catos import account_lock
from catos.local_sim_control import LocalSimControlService, now
from catos.local_sim_control_api import PREFIX, mount_simulation
from catos.workspace_api import mount_workspace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--history-from", type=Path)
    options = parser.parse_args()
    root = options.output_root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    if options.history_from:
        # Reopen a copy of this fixture's closed history, preserving the original evidence.
        history = options.history_from.resolve()
        exit_state = json.loads((history / "exit.json").read_text(encoding="utf-8"))
        if not exit_state["owner_closed"] or exit_state["active"] or any(
                not run["cleanup_confirmed"] for run in exit_state["runs"]):
            raise RuntimeError("history_cleanup_not_confirmed")
        shutil.copytree(history / "simulation", root / "simulation")
    account_lock.LOCK_DIRECTORY = root / "account-locks"
    app = FastAPI()
    mount_workspace(app, evidence_root=root / "unused-r4")
    service = LocalSimControlService(root / "simulation")
    mount_simulation(app, service.root, service=service)

    @app.middleware("http")
    async def commands(request, call_next):
        if request.method != "POST" or not request.url.path.startswith(PREFIX):
            return await call_next(request)
        raw = (await request.body()).decode("utf-8")
        response = await call_next(request)
        item = dict(at=now(), path=request.url.path, body=raw, status=response.status_code,
                    build=request.headers.get("x-catos-build"),
                    instance=request.headers.get("x-catos-instance"))
        with (root / "commands.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(item) + "\n")
        return response

    @app.get("/api/research/version")
    def version():
        return {"restart_required": False, "active_run_id": None}

    @app.get("/api/research/runs")
    def runs():
        return {"items": []}

    @app.get("/api/research/catalog")
    def catalog():
        return {"strategies": []}

    @app.post("/__test/shutdown")
    def shutdown():
        if service.active or not service.runs or any(
                not run["cleanup_confirmed"] for run in service.runs.values()):
            raise HTTPException(409, "fixture_cleanup_not_confirmed")
        app.state.server.should_exit = True
        return {"shutdown": "requested"}

    with socket.socket() as listener:
        # Port zero atomically reserves a free localhost port; no existing owner is touched.
        listener.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
        app.state.server = server
        ready = dict(port=listener.getsockname()[1], pid=os.getpid(),
                     root=str(root), build=service.loaded_build, instance=service.instance_id)
        (root / "ready.json").write_text(json.dumps(ready), encoding="utf-8")
        print(json.dumps(ready), flush=True)
        server.run(sockets=[listener])
    (root / "exit.json").write_text(json.dumps(dict(
        owner_closed=service.owner is None, active=service.active,
        runs=[service.snapshot(run_id) for run_id in service.runs])), encoding="utf-8")


if __name__ == "__main__":
    main()
