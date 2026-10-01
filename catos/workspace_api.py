"""F1 localhost shell; integrated app or temporary preview of the existing writer."""

import argparse
from datetime import datetime, timezone
import hashlib
import http.client
from pathlib import Path
import re
import socket

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from catos.workspace_snapshot import LocalSimReader, SnapshotError

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend" / "workspace"
ASSETS = {"workspace.css": "text/css", "workspace.js": "text/javascript",
          "home.css": "text/css", "home.js": "text/javascript",
          "desk.css": "text/css", "desk.js": "text/javascript", "simulation.js": "text/javascript",
          "home-layout.css": "text/css", "home-layout.js": "text/javascript"}
DESK_PAGES = {"research", "execution", "risk", "events", "yaozi", "settings"}
RESEARCH_PATH = re.compile(
    r"/api/research/(?:version|catalog|runs|runs/[0-9a-f]{32}(?:/result|/report)?)")
POST_PATHS = {"/api/research/backtests", "/api/research/optimizations"}


def workspace_build():
    digest = hashlib.sha256()
    for path in (Path(__file__), ROOT / "catos" / "workspace_snapshot.py",
                 *(FRONTEND / name for name in ("index.html", "home.html", "desk.html", *ASSETS))):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def mount_workspace(app, *, evidence_root=None, preview=False):
    reader = LocalSimReader(evidence_root or ROOT / "outputs" / "local-sim-r4")
    loaded_build = workspace_build()
    # Replace only the shell routes in the integrated app. Intelligence API and
    # its materialized dashboard retain their existing contracts.
    app.router.routes = [route for route in app.router.routes
                         if getattr(route, "path", "") not in ("/", "/quant")]

    @app.middleware("http")
    async def workspace_headers(request, call_next):
        if request.url.hostname != "127.0.0.1":
            return JSONResponse({"detail": "workspace_requires_127_0_0_1"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["X-Content-Type-Options"] = "nosniff"
        if (request.url.path in ("/", "/workspace", "/workspace/", "/workspace/home")
                or request.url.path in {"/workspace/" + page for page in DESK_PAGES}):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "connect-src 'self'; frame-src 'self'; img-src 'self' data:; "
                "object-src 'none'; base-uri 'none'; frame-ancestors 'self'")
        return response

    @app.get("/", response_class=HTMLResponse)
    @app.get("/quant", response_class=HTMLResponse)
    @app.get("/workspace", response_class=HTMLResponse)
    @app.get("/workspace/", response_class=HTMLResponse)
    def workspace_page():
        return FileResponse(FRONTEND / "home.html", media_type="text/html")

    @app.get("/workspace/legacy", response_class=HTMLResponse)
    def legacy_workspace_page():
        return FileResponse(FRONTEND / "index.html", media_type="text/html")

    @app.get("/workspace/home", response_class=HTMLResponse)
    def home_preview():
        return FileResponse(FRONTEND / "home.html", media_type="text/html")

    @app.get("/workspace/reference/{name}")
    def home_reference(name: str):
        references = {"gemini": "gemini-home.png", "previous": "current-home.png"}
        if name not in references:
            raise HTTPException(404, "reference_not_found")
        path = ROOT / "outputs" / "frontend-design-review-20260930" / references[name]
        if not path.is_file():
            raise HTTPException(404, "reference_not_available")
        return FileResponse(path, media_type="image/png")

    @app.get("/workspace/assets/{asset}")
    def workspace_asset(asset: str):
        if asset not in ASSETS:
            raise HTTPException(404, "workspace_asset_not_found")
        return FileResponse(FRONTEND / asset, media_type=ASSETS[asset])

    @app.get("/workspace/design", response_class=HTMLResponse)
    def design_page():
        path = ROOT / "outputs" / "frontend-design-f1-20260930" / "index.html"
        if not path.is_file():
            raise HTTPException(404, "design_sample_not_available")
        return FileResponse(path, media_type="text/html")

    @app.get("/workspace/{page}", response_class=HTMLResponse)
    def desk_page(page: str):
        if page not in DESK_PAGES:
            raise HTTPException(404, "workspace_page_not_found")
        return FileResponse(FRONTEND / "desk.html", media_type="text/html")

    @app.get("/api/workspace/version")
    def version():
        current = workspace_build()
        return {"contract": "catos.workspace.v1", "build_id": loaded_build,
                "current_build_id": current, "restart_required": loaded_build != current,
                "preview": preview, "research_owner": "existing_8770" if preview else "same_app",
                "runtime_controls": [], "observed_at": datetime.now(timezone.utc).isoformat()}

    @app.get("/api/workspace/local-sim/runs")
    def runs():
        try:
            return reader.list_runs()
        except (SnapshotError, OSError) as error:
            return {"state": "error", "items": [], "issues": [
                str(error) if isinstance(error, SnapshotError) else "evidence_unavailable"]}

    @app.get("/api/workspace/local-sim/runs/{run_id}")
    def snapshot(run_id: str, limit: int = Query(200, ge=1, le=200)):
        try:
            return reader.snapshot(run_id, limit=limit)
        except SnapshotError as error:
            raise HTTPException(422, str(error)) from None
        except FileNotFoundError:
            raise HTTPException(404, "run_not_found") from None
        except OSError:
            raise HTTPException(503, "evidence_unavailable") from None

    return app


def relay(method, path, body=b"", build=None):
    """Fixed loopback upstream; no credentials, redirects, user URLs or writer."""
    connection = http.client.HTTPConnection("127.0.0.1", 8770, timeout=5)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if build:
        headers["X-CatOS-Build"] = build
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise HTTPException(502, "research_response_limit")
        return Response(data, status_code=response.status,
                        media_type=response.getheader("Content-Type", "application/json"))
    except (OSError, http.client.HTTPException):
        raise HTTPException(503, "research_owner_unavailable") from None
    finally:
        connection.close()


def create_app(*, output_dir=None, market_db=None, evidence_root=None, preview=False,
               simulation_root=None):
    if not preview:
        from catos.research_api import create_app as create_research_app
        from catos.local_sim_control_api import mount_simulation
        app = mount_workspace(create_research_app(output_dir=output_dir, market_db=market_db),
                              evidence_root=evidence_root)
        return mount_simulation(app, simulation_root or ROOT / "outputs" / "local-sim-control")
    app = FastAPI(title="catOS F1 temporary localhost preview")

    @app.api_route("/api/research/{path:path}", methods=["GET", "POST"])
    async def research_proxy(path: str, request: Request):
        target = "/api/research/" + path
        if request.query_params:
            raise HTTPException(422, "preview_query_not_supported")
        if request.method == "GET":
            if RESEARCH_PATH.fullmatch(target) is None:
                raise HTTPException(404, "preview_route_not_found")
            from starlette.concurrency import run_in_threadpool
            return await run_in_threadpool(relay, "GET", target)
        if target not in POST_PATHS:
            raise HTTPException(405, "preview_mutation_not_supported")
        if request.headers.get("origin") not in (None, str(request.base_url).rstrip("/")):
            raise HTTPException(403, "research_origin_mismatch")
        if request.headers.get("content-type", "").split(";", 1)[0] != "application/json":
            raise HTTPException(415, "application_json_required")
        body = bytearray()
        async for block in request.stream():
            if len(body) + len(block) > 8192:
                raise HTTPException(413, "research_request_limit")
            body.extend(block)
        from starlette.concurrency import run_in_threadpool
        return await run_in_threadpool(relay, "POST", target, bytes(body),
                                       request.headers.get("x-catos-build"))

    return mount_workspace(app, evidence_root=evidence_root, preview=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="catOS F1 localhost workbench")
    parser.add_argument("--preview", action="store_true",
                        help="temporary port 8771 UI; research remains owned by existing 8770")
    args = parser.parse_args(argv)
    port = 8771 if args.preview else 8770
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        listener.bind(("127.0.0.1", port))
    except OSError:
        listener.close()
        print(f"Port {port} already in use; no owner stopped or alternate port selected.")
        return 2
    try:
        import uvicorn
        print(f"catOS F1 http://127.0.0.1:{port}/workspace/")
        uvicorn.Server(uvicorn.Config(create_app(preview=args.preview),
                                     host="127.0.0.1", port=port)).run(sockets=[listener])
    finally:
        listener.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
