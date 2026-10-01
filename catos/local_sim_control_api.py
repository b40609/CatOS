"""Narrow localhost API; mutations bind to the loaded service instance."""

from contextlib import asynccontextmanager

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from catos.local_sim_control import ControlError, LocalSimControlService, strict_json, valid_id

PREFIX = "/api/workspace/simulation"


def mount_simulation(app, output_root, *, service=None):
    service = service or LocalSimControlService(output_root)
    app.state.simulation = service
    previous_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with previous_lifespan(application):
            service.open()
            try:
                yield
            finally:
                await service.close()

    app.router.lifespan_context = lifespan

    @app.exception_handler(ControlError)
    async def control_error(_request, error):
        return JSONResponse({"detail": str(error)}, status_code=error.status)

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(PREFIX):
            response.headers["X-CatOS-Build"] = service.loaded_build
            response.headers["X-CatOS-Instance"] = service.instance_id
            response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    async def command(request, keys):
        if request.url.hostname != "127.0.0.1":
            raise HTTPException(403, "simulation_requires_127_0_0_1")
        if request.headers.get("origin") not in (None, str(request.base_url).rstrip("/")):
            raise HTTPException(403, "simulation_origin_mismatch")
        if request.headers.get("content-type", "").split(";", 1)[0] != "application/json":
            raise HTTPException(415, "application_json_required")
        if request.headers.get("x-catos-instance") != service.instance_id:
            raise HTTPException(409, "service_instance_mismatch")
        if request.headers.get("x-catos-build") != service.loaded_build:
            raise HTTPException(409, "page_version_mismatch_reload_required")
        body = bytearray()
        async for block in request.stream():
            if len(body) + len(block) > 8192:
                raise HTTPException(413, "simulation_request_limit")
            body.extend(block)
        try:
            value = strict_json(body)
        except (ValueError, TypeError):
            raise HTTPException(422, "invalid_json") from None
        if type(value) is not dict or set(value) != set(keys) or not valid_id(value["request_id"]):
            raise HTTPException(422, "invalid_command_contract")
        if "template_id" in keys and type(value["template_id"]) is not str:
            raise HTTPException(422, "invalid_template_id")
        return value

    @app.get(PREFIX + "/version")
    async def version():
        return service.version()

    @app.get(PREFIX + "/runs")
    async def runs():
        return service.list_runs()

    @app.get(PREFIX + "/runs/{run_id}")
    async def run(run_id: str):
        return service.snapshot(run_id)

    @app.post(PREFIX + "/start", status_code=202)
    async def start(request: Request):
        value = await command(request, ("request_id", "template_id"))
        return await service.start(**value)

    @app.post(PREFIX + "/runs/{run_id}/stop", status_code=202)
    async def stop(run_id: str, request: Request):
        value = await command(request, ("request_id",))
        return await service.stop(run_id, **value)

    return app
