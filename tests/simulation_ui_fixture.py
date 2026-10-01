"""Disposable browser fixture: temporary metadata, stub runner, no trading/DB."""
import asyncio
from pathlib import Path
import socket
import tempfile

from fastapi import FastAPI
import uvicorn

from catos.local_sim_control import LocalSimControlService
from catos.local_sim_control_api import mount_simulation
from catos.workspace_api import mount_workspace


async def runner(_directory, _run_id, stop, emit, update, _source_ok):
    update(control_state="running", warmup_bars=2)
    emit("signal", target="2", disposition="UI_FIXTURE", account={"equity": "1000.000000000000000001"})
    await stop.wait()
    await asyncio.sleep(6)  # Exercise still_finishing without Worker/ledger operations.
    return {"control_state": "stopped", "cleanup_confirmed": True, "worker_closed": True}


def main():
    with tempfile.TemporaryDirectory(prefix="catos-w3-ui-") as temporary:
        root = Path(temporary)
        app = FastAPI()
        posts = []

        @app.middleware("http")
        async def observe(request, call_next):
            if request.method == "POST":
                posts.append(request.url.path)
            return await call_next(request)

        @app.get("/__test/observations")
        def observations():
            return {"posts": posts}

        @app.get("/api/research/version")
        def version():
            return {"restart_required": False, "active_run_id": None}

        @app.get("/api/research/runs")
        def runs():
            return {"items": []}

        @app.get("/api/research/catalog")
        def catalog():
            return {"strategies": []}

        mount_workspace(app, evidence_root=root / "evidence")
        mount_simulation(app, root / "simulation",
                         service=LocalSimControlService(root / "simulation", runner=runner))
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            print(f"UI_FIXTURE_PORT={listener.getsockname()[1]}", flush=True)
            server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
            server.run(sockets=[listener])


if __name__ == "__main__":
    main()
