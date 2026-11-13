"""CatOS localhost app: research and local-sim APIs plus the built React UI on one port."""

import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import socket

from fastapi import HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from catos.workspace_snapshot import LocalSimReader, SnapshotError

ROOT = Path(__file__).resolve().parent.parent
UI_DIST = ROOT / "frontend" / "cat-os-vite" / "dist"
# Explicit types: Windows registry MIME lookups can label .js as text/plain, which
# browsers refuse to run as a module script. Unlisted suffixes are not served.
UI_TYPES = {
    ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript",
    ".css": "text/css", ".json": "application/json", ".map": "application/json",
    ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".webp": "image/webp", ".ico": "image/x-icon",
    ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf",
    ".txt": "text/plain", ".webmanifest": "application/manifest+json",
}
UI_CSP = (
    "default-src 'self'; script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: blob:; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'")
UI_NOT_BUILT = """<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><title>CatOS</title></head>
<body style="font-family:system-ui,sans-serif;max-width:42rem;margin:4rem auto;line-height:1.7">
<h1>CatOS 介面尚未建置</h1>
<p>後端 API 已在執行，但找不到 <code>frontend/cat-os-vite/dist/index.html</code>。</p>
<p>在專案根目錄執行 <code>start.bat</code>，或手動建置後重新整理此頁：</p>
<pre>cd frontend\\cat-os-vite
npm ci
npm run build</pre>
</body></html>
"""


def workspace_build():
    digest = hashlib.sha256()
    for path in (Path(__file__), ROOT / "catos" / "workspace_snapshot.py"):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def ui_file(dist, relative):
    """Resolve one built UI file; anything outside dist or of an unlisted type is 404."""
    root = dist.resolve()
    try:
        path = (root / relative).resolve()
    except (OSError, ValueError):
        raise HTTPException(404, "ui_file_not_found") from None
    if root not in path.parents or path.suffix.lower() not in UI_TYPES or not path.is_file():
        raise HTTPException(404, "ui_file_not_found")
    return FileResponse(path, media_type=UI_TYPES[path.suffix.lower()])


def mount_workspace(app, *, evidence_root=None, ui_dist=None):
    reader = LocalSimReader(evidence_root or ROOT / "outputs" / "local-sim-r4")
    dist = Path(ui_dist) if ui_dist is not None else UI_DIST
    loaded_build = workspace_build()

    @app.middleware("http")
    async def workspace_headers(request, call_next):
        if request.url.hostname != "127.0.0.1":
            return JSONResponse({"detail": "workspace_requires_127_0_0_1"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path == "/":
            response.headers["Content-Security-Policy"] = UI_CSP
        return response

    @app.get("/", response_class=HTMLResponse)
    def ui_index():
        if not (dist / "index.html").is_file():
            return HTMLResponse(UI_NOT_BUILT, status_code=503)
        return ui_file(dist, "index.html")

    @app.get("/assets/{asset:path}")
    def ui_asset(asset: str):
        return ui_file(dist, "assets/" + asset)

    @app.get("/api/workspace/version")
    def version():
        current = workspace_build()
        return {"contract": "catos.workspace.v1", "build_id": loaded_build,
                "current_build_id": current, "restart_required": loaded_build != current,
                "ui": "ready" if (dist / "index.html").is_file() else "not_built",
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

    # Files Vite copies from public/ to the dist root (logo, favicon). Single path
    # segment only, so it never shadows /api/... or /assets/... routes.
    @app.get("/{name}")
    def ui_root_file(name: str):
        if name.startswith(".") or "\\" in name:
            raise HTTPException(404, "ui_file_not_found")
        return ui_file(dist, name)

    return app


def create_app(*, output_dir=None, evidence_root=None, simulation_root=None, ui_dist=None, replay_root=None):
    from catos.research_api import create_app as create_research_app
    from catos.local_sim_control_api import mount_simulation
    from catos.replay_api import mount_replay
    app = mount_workspace(create_research_app(output_dir=output_dir),
                          evidence_root=evidence_root, ui_dist=ui_dist)
    # Read-only approvals and Bot replay progress (step 2); writes stay CLI-only.
    mount_replay(app, root=replay_root)
    return mount_simulation(app, simulation_root or ROOT / "outputs" / "local-sim-control")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="CatOS localhost app (UI, research and local-sim) on 127.0.0.1:8770")
    parser.parse_args(argv)
    port = 8770
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
        print(f"CatOS http://127.0.0.1:{port}/")
        if not (UI_DIST / "index.html").is_file():
            print("UI is not built yet: run start.bat, or `npm ci && npm run build` "
                  "in frontend/cat-os-vite.")
        uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port)).run(
            sockets=[listener])
    finally:
        listener.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
