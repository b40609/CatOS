"""Same-origin research adapter, mounted beside the existing shell/Yaozi surfaces."""

import argparse
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import os
import socket
import sqlite3
import uuid

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from catos.market_api import MarketIntelReader, create_app as create_market_app
from catos.market_intel import MarketIntelError
from catos.research_catalog import ROOT, catalog, files_hash, json_text
from catos.research_service import ResearchError, ResearchService

FRONTEND = ROOT / "frontend" / "research"
RUNTIME_FILES = (
    "catos/research_api.py", "catos/research_catalog.py", "catos/research_service.py",
    "catos/research_worker.py", "catos/research_strategy.py", "catos/research.py",
    "catos/research_optimization.py", "catos/optimization.py",
    "catos/data_io.py", "catos/reporting.py", "catos/market_api.py", "catos/app_shell.py",
    "catos/research_artifacts/sma-trend-sma-parameters-v1.json",
    "examples/closed_bar_demo.py", "examples/research-web-synthetic.csv",
)


def build_files():
    return tuple(RUNTIME_FILES) + tuple(sorted(
        path.relative_to(ROOT).as_posix() for path in FRONTEND.rglob("*") if path.is_file()
    ))


class UnavailableMarketReader:
    """Keep existing intelligence routes explicit without creating a database."""

    def __init__(self, reason):
        self.reason = reason

    def __getattr__(self, name):
        def unavailable(*args, **kwargs):
            raise HTTPException(503, {"status": "unavailable", "reason": self.reason})
        return unavailable


def create_app(*, output_dir=None, market_db=None):
    service = ResearchService(output_dir or ROOT / "outputs" / "research-web")
    database = market_db or ROOT / "data" / "market_intel.sqlite"
    market_status = "ready"
    try:
        market_reader = MarketIntelReader(database)
    except (MarketIntelError, sqlite3.Error) as error:
        market_status = str(error)
        market_reader = UnavailableMarketReader(market_status)
    app = create_market_app(database, market_reader=market_reader)
    app.state.research = service
    names = build_files()
    loaded_build = files_hash(names)
    instance = {"instance_id": uuid.uuid4().hex, "pid": os.getpid(),
                "started_at": datetime.now(timezone.utc).isoformat(),
                "workspace": str(ROOT), "build_id": loaded_build, "market_status": market_status}
    assets = {path.relative_to(FRONTEND).as_posix(): path for path in FRONTEND.rglob("*")
              if path.is_file() and path.suffix in (".js", ".css")}

    def version():
        try:
            current = files_hash(build_files())
        except OSError:
            current = "source_unavailable"
        return {**instance, "current_build_id": current,
                "restart_required": current != loaded_build,
                "active_run_id": service.active_run, "mode": "local_research_synthetic",
                "cache_policy": "no-store"}

    @asynccontextmanager
    async def lifespan(_app):
        service.start()
        try:
            yield
        finally:
            service.close()

    app.router.lifespan_context = lifespan

    @app.middleware("http")
    async def research_headers(request, call_next):
        is_research = request.url.path.startswith(("/research", "/api/research"))
        if is_research and request.url.hostname != "127.0.0.1":
            return JSONResponse({"detail": "research_requires_127_0_0_1"}, status_code=403)
        response = await call_next(request)
        if is_research:
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["X-CatOS-Build"] = loaded_build
            response.headers["X-CatOS-Instance"] = instance["instance_id"]
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(ResearchError)
    async def research_error(_request, error):
        return JSONResponse({"detail": str(error)}, status_code=error.status)

    @app.get("/api/research/version")
    def research_version():
        return version()

    @app.get("/api/research/catalog")
    def research_catalog():
        return JSONResponse(json.loads(json_text(catalog())))

    @app.get("/api/research/runs")
    def research_runs():
        return {"items": service.list_runs()}

    async def parse_submission(request: Request):
        if request.headers.get("origin") not in (None, str(request.base_url).rstrip("/")):
            raise HTTPException(403, "research_origin_mismatch")
        if request.headers.get("content-type", "").split(";", 1)[0] != "application/json":
            raise HTTPException(415, "application_json_required")
        if version()["restart_required"]:
            raise HTTPException(409, "source_changed_restart_required")
        if request.headers.get("x-catos-build") != loaded_build:
            raise HTTPException(409, "page_version_mismatch_reload_required")
        body = bytearray()
        async for block in request.stream():
            if len(body) + len(block) > 8192:
                raise HTTPException(413, "research_request_limit")
            body.extend(block)
        try:
            def pairs(items):
                result = {}
                for key, value in items:
                    if key in result:
                        raise ValueError("duplicate_json_field")
                    result[key] = value
                return result
            def reject_constant(_value):
                raise ValueError("invalid_json_constant")
            return json.loads(body, object_pairs_hook=pairs, parse_constant=reject_constant)
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error)) from None

    @app.post("/api/research/backtests", status_code=202)
    async def research_submit(request: Request):
        value = await parse_submission(request)
        try:
            return service.submit(value, loaded_build)
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error)) from None

    @app.post("/api/research/optimizations", status_code=202)
    async def optimization_submit(request: Request):
        value = await parse_submission(request)
        try:
            return service.submit_optimization(value, loaded_build)
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error)) from None

    @app.get("/api/research/runs/{run_id}")
    def research_task(run_id: str):
        return service.task(run_id)

    @app.get("/api/research/runs/{run_id}/result")
    def research_result(run_id: str):
        return service.result(run_id)

    @app.get("/api/research/runs/{run_id}/report", response_class=HTMLResponse)
    def research_report(run_id: str):
        return HTMLResponse(service.report(run_id))

    @app.get("/research/assets/{asset:path}")
    def research_asset(asset: str):
        if asset not in assets:
            raise HTTPException(404, "research_asset_not_found")
        return FileResponse(assets[asset])

    @app.get("/research", response_class=HTMLResponse)
    @app.get("/research/", response_class=HTMLResponse)
    def research_page():
        page = (FRONTEND / "index.html").read_text(encoding="utf-8")
        bootstrap = json_text({"build_id": loaded_build, "instance_id": instance["instance_id"]})
        return HTMLResponse(page.replace("__CATOS_BOOTSTRAP__", bootstrap)
                            .replace("__CATOS_BUILD__", loaded_build))

    return app


def main(argv=None):
    parser = argparse.ArgumentParser(description="catOS R1 localhost research; fixed default port, no fallback")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("port must be in [1024, 65535]")
    # Bind once and pass that owned socket to uvicorn: no probe/bind race, no
    # silent port fallback, no guessing or killing an existing port owner.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        listener.bind(("127.0.0.1", args.port))
    except OSError:
        listener.close()
        print(f"Port {args.port} already in use. No process stopped and no alternate port selected.")
        return 2
    try:
        import uvicorn
        app = create_app()
        print(f"catOS R1 http://127.0.0.1:{args.port}/research/ | workspace={ROOT}")
        print("After source updates, finish active research then Ctrl+C and restart this command.")
        uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port)).run(sockets=[listener])
    finally:
        listener.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
