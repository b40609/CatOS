"""Narrow localhost API; mutations bind to the loaded service instance."""

from contextlib import asynccontextmanager

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from catos.local_sim_control import (TEMPLATE, ControlError, LocalSimControlService, strict_json,
                                     valid_id)
from catos.simulation_catalog import MAX_EVENT_LIMIT

PREFIX = "/api/workspace/simulation"
FORBIDDEN_MODES = {"demo", "live"}


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
        if request.url.path.startswith(PREFIX):
            # Every simulation route is loopback-only and local-sim-only. demo/live
            # anywhere in the path or query is refused (403), not treated as unknown.
            if request.url.hostname != "127.0.0.1":
                return guarded(403, "simulation_requires_127_0_0_1", service)
            segments = request.url.path[len(PREFIX):].lower().split("/")
            query = request.query_params
            if (FORBIDDEN_MODES & set(segments)
                    or any(key.lower() in FORBIDDEN_MODES or value.lower() in FORBIDDEN_MODES
                           for key, value in query.multi_items())):
                return guarded(403, "mode_not_available", service)
        response = await call_next(request)
        if request.url.path.startswith(PREFIX):
            stamp(response, service)
        return response

    async def command(request, keys, optional=(), *, bound=True):
        if request.url.hostname != "127.0.0.1":
            raise HTTPException(403, "simulation_requires_127_0_0_1")
        if request.headers.get("origin") not in (None, str(request.base_url).rstrip("/")):
            raise HTTPException(403, "simulation_origin_mismatch")
        if request.headers.get("content-type", "").split(";", 1)[0] != "application/json":
            raise HTTPException(415, "application_json_required")
        # Kill engage (bound=False) is the safe direction: it must work from a stale
        # page or while the source changed on disk, so it skips instance/build binding.
        if bound and request.headers.get("x-catos-instance") != service.instance_id:
            raise HTTPException(409, "service_instance_mismatch")
        if bound and request.headers.get("x-catos-build") != service.loaded_build:
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
        if (type(value) is not dict or not set(keys) <= set(value) <= set(keys) | set(optional)
                or not valid_id(value["request_id"])):
            raise HTTPException(422, "invalid_command_contract")
        if "template_id" in keys and type(value["template_id"]) is not str:
            raise HTTPException(422, "invalid_template_id")
        return value

    def integer_query(request, name, default, code):
        raw = request.query_params.get(name)
        if raw is None:
            return default
        if type(raw) is not str or not raw.isascii() or not raw.isdigit() or len(raw) > 18:
            raise ControlError(code, 422)
        return int(raw)

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

    # v1 workspace projections: read-only, idempotent, control-plane memory only.

    @app.get(PREFIX + "/state")
    async def state(request: Request):
        since = integer_query(request, "since_version", None, "invalid_since_version")
        return service.state(since)

    @app.get(PREFIX + "/strategies")
    async def strategies():
        return service.strategies()

    @app.get(PREFIX + "/bots")
    async def bots():
        return service.bots()

    @app.get(PREFIX + "/bots/{bot_id}")
    async def bot(bot_id: str):
        return service.bot(bot_id)

    @app.get(PREFIX + "/risk")
    async def risk_snapshot():
        return service.risk()

    @app.get(PREFIX + "/positions")
    async def positions():
        return service.positions()

    @app.get(PREFIX + "/events")
    async def events(request: Request):
        since = integer_query(request, "since", 0, "invalid_since")
        limit = integer_query(request, "limit", 40, "invalid_limit")
        if limit > MAX_EVENT_LIMIT:
            raise ControlError("invalid_limit", 422)
        return service.events(since, limit)

    # Kill-Switch (work package B). Engage: anyone. Clear: the user, with a reason
    # and the typed confirmation word; agents must not call it (AGENTS.md 紅線).

    @app.get(PREFIX + "/kill-switch")
    async def kill_status():
        return service.kill_switch()

    @app.post(PREFIX + "/kill-switch/engage")
    async def kill_engage(request: Request):
        value = await command(request, ("request_id", "reason"), bound=False)
        return await service.engage_kill(value["request_id"], value["reason"])

    @app.post(PREFIX + "/kill-switch/clear")
    async def kill_clear(request: Request):
        value = await command(request, ("request_id", "reason", "confirm"))
        return await service.clear_kill(value["request_id"], value["reason"], value["confirm"])

    @app.post(PREFIX + "/bots/start", status_code=202)
    async def start_bot(request: Request):
        value = await command(request, ("request_id", "bot_id"), optional=("mode",))
        if value.get("mode", "local") != "local":
            raise HTTPException(403, "mode_not_available")
        service.bot(value["bot_id"])  # 422 invalid_bot_id / 404 bot_not_found before binding
        run = await service.start(value["request_id"], TEMPLATE)
        return {"run": run, "bot": service.bot(value["bot_id"]), "version": service.state_version}

    return app


def stamp(response, service):
    response.headers["X-CatOS-Build"] = service.loaded_build
    response.headers["X-CatOS-Instance"] = service.instance_id
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


def guarded(status, code, service):
    return stamp(JSONResponse({"detail": code}, status_code=status), service)
