"""Retained local W6 fixture: accept once, hide first reply, no Worker/ledger."""

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import socket

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

from catos.local_sim_control import LocalSimControlService, now
from catos.local_sim_control_api import PREFIX, mount_simulation
from catos.workspace_api import mount_workspace
from tests.simulation_ui_fixture import runner


def create_fixture(root, *, hide_reply="start"):
    if hide_reply not in {"start", "stop"}:
        raise ValueError("hide_reply must be start or stop")
    root = Path(root)
    app = FastAPI()
    observations = []
    hidden = False

    mount_workspace(app, evidence_root=root / "evidence")
    mount_simulation(app, root / "simulation",
                     service=LocalSimControlService(root / "simulation", runner=runner))

    @app.middleware("http")
    async def observe(request, call_next):
        nonlocal hidden
        if request.method != "POST" or not request.url.path.startswith(PREFIX):
            return await call_next(request)
        raw = (await request.body()).decode("utf-8")
        item = {"at": now(), "path": request.url.path, "body": raw,
                "content_type": request.headers.get("content-type"),
                "build": request.headers.get("x-catos-build"),
                "instance": request.headers.get("x-catos-instance")}
        response = await call_next(request)
        item["backend_status"] = response.status_code
        operation = "start" if request.url.path == PREFIX + "/start" else (
            "stop" if request.url.path.startswith(PREFIX + "/runs/") and request.url.path.endswith("/stop") else None)
        if operation == hide_reply and response.status_code == 202 and not hidden:
            hidden = True
            service = app.state.simulation
            binding = service._binding(json.loads(raw)["request_id"])
            item["accepted_run_ids"] = list(service.runs)
            item["accepted_run_id"] = binding[1]
            item["accepted_snapshot"] = service.snapshot(binding[1])
            item["accepted_stop_commands"] = deepcopy(service.runs[binding[1]]["stop_commands"])
            item["acceptance_evidence"] = "post_acceptance_controller_observation_not_http_response_body"
            item["hidden_operation"] = operation
            detail = "W6_FIXTURE_REPLY_UNCONFIRMED" if operation == "start" else "W8_FIXTURE_STOP_REPLY_UNCONFIRMED"
            response = JSONResponse({"detail": detail}, status_code=503)
        item["client_status"] = response.status_code
        observations.append(item)
        with (root / "commands.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(item) + "\n")
        return response

    @app.get("/__test/observations")
    def observed():
        return {"posts": observations}

    @app.get("/api/research/version")
    def research_version():
        return {"restart_required": False, "active_run_id": None}

    @app.get("/api/research/runs")
    def research_runs():
        return {"items": []}

    @app.get("/api/research/catalog")
    def catalog():
        return {"strategies": []}

    @app.post("/__test/shutdown")
    def shutdown():
        service = app.state.simulation
        if not service.runs or any(not run["cleanup_confirmed"] for run in service.runs.values()):
            raise HTTPException(409, "fixture_cleanup_not_confirmed")
        app.state.server.should_exit = True
        return {"shutdown": "requested"}

    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--hide-reply", choices=("start", "stop"), default="start")
    args = parser.parse_args()
    root = args.output_root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    app = create_fixture(root, hide_reply=args.hide_reply)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
        app.state.server = server
        (root / "listener.json").write_text(json.dumps({"port": port, "host": "127.0.0.1",
            "pid": os.getpid(), "output_root": str(root), "hide_reply": args.hide_reply}), encoding="utf-8")
        print(f"W6_FIXTURE_PORT={port}", flush=True)
        server.run(sockets=[listener])


if __name__ == "__main__":
    main()
