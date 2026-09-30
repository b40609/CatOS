"""R3 stdio MCP bridge to the single localhost ResearchService writer."""

import json
import re
from typing import Any, TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener


SERVICE_BASE = "http://127.0.0.1:8770"
REQUEST_TIMEOUT_SECONDS = 5
MAX_REQUEST_BYTES = 8192
MAX_REPLY_BYTES = 2_100_000
RUN_ID = re.compile(r"[0-9a-f]{32}")
SHA256 = re.compile(r"[0-9a-f]{64}")
_LOCAL_OPENER = build_opener(ProxyHandler({})).open


class ResearchMcpError(RuntimeError):
    pass


class StrategyBinding(TypedDict):
    id: str
    version: str
    sha256: str


class ResearchHttpBridge:
    """Fixed-loopback adapter; all mutations stay in the running web service."""

    def __init__(self, base_url=SERVICE_BASE, *, opener=None,
                 timeout_seconds=REQUEST_TIMEOUT_SECONDS):
        parts = urlsplit(base_url)
        if (parts.scheme != "http" or parts.hostname != "127.0.0.1"
                or parts.username is not None or parts.password is not None
                or parts.path not in ("", "/") or parts.query or parts.fragment):
            raise ValueError("research_mcp_requires_127_0_0_1_http")
        try:
            port = parts.port
        except ValueError:
            raise ValueError("research_mcp_invalid_port") from None
        if port is None or not 1024 <= port <= 65535:
            raise ValueError("research_mcp_invalid_port")
        self.base_url = f"http://127.0.0.1:{port}"
        self._open = opener or _LOCAL_OPENER
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _error_detail(error):
        try:
            body = error.read(8193)
        except OSError:
            return "http_error"
        if len(body) > 8192:
            return "http_error_body_too_large"
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return "http_error"
        if isinstance(value, dict) and isinstance(value.get("detail"), (str, int, float, bool)):
            return str(value["detail"])
        return "http_error"

    def _json(self, path, *, method="GET", payload=None, build_id=None):
        if not path.startswith("/api/research/") or ".." in path:
            raise ResearchMcpError("research_mcp_invalid_api_path")
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            try:
                body = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                                  separators=(",", ":")).encode("utf-8")
            except (TypeError, ValueError) as error:
                raise ResearchMcpError(f"invalid_json_request: {error}") from None
            if len(body) > MAX_REQUEST_BYTES:
                raise ResearchMcpError("research_request_limit")
            headers["Content-Type"] = "application/json"
            if not isinstance(build_id, str) or not build_id:
                raise ResearchMcpError("research_build_id_missing")
            headers["X-CatOS-Build"] = build_id
        request = Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with self._open(request, timeout=self.timeout_seconds) as response:
                raw = response.read(MAX_REPLY_BYTES + 1)
        except HTTPError as error:
            try:
                detail = self._error_detail(error)
            finally:
                error.close()
            raise ResearchMcpError(f"research_http_{error.code}: {detail}") from None
        except (URLError, OSError):
            raise ResearchMcpError("research_service_unavailable") from None
        if len(raw) > MAX_REPLY_BYTES:
            raise ResearchMcpError("research_reply_limit")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ResearchMcpError("research_invalid_json_reply") from None
        if not isinstance(value, dict):
            raise ResearchMcpError("research_invalid_json_reply")
        return value

    def version(self):
        return self._json("/api/research/version")

    def catalog(self):
        return self._json("/api/research/catalog")

    def list_runs(self):
        return self._json("/api/research/runs")

    @staticmethod
    def _strategy_binding(value):
        if type(value) is not dict or set(value) != {"id", "version", "sha256"}:
            raise ResearchMcpError("strategy_binding_exact_fields_required")
        if (type(value["id"]) is not str or not value["id"]
                or type(value["version"]) is not str or not value["version"]
                or type(value["sha256"]) is not str or SHA256.fullmatch(value["sha256"]) is None):
            raise ResearchMcpError("invalid_strategy_binding")
        return dict(value)

    def _require_registered_strategy(self, value):
        expected = self._strategy_binding(value)
        strategies = self.catalog().get("strategies")
        if type(strategies) is not list:
            raise ResearchMcpError("research_invalid_catalog")
        for strategy in strategies:
            if isinstance(strategy, dict) and strategy.get("id") == expected["id"]:
                current = {key: strategy.get(key) for key in ("id", "version", "sha256")}
                if current != expected:
                    raise ResearchMcpError("strategy_binding_mismatch")
                return expected
        raise ResearchMcpError("strategy_binding_mismatch")

    def _mutation(self, path, strategy_binding, request):
        version = self.version()
        if version.get("restart_required") is not False:
            raise ResearchMcpError("source_changed_restart_required")
        build_id = version.get("build_id")
        if not isinstance(build_id, str) or not build_id:
            raise ResearchMcpError("research_build_id_missing")
        self._require_registered_strategy(strategy_binding)
        return self._json(path, method="POST", payload=request, build_id=build_id)

    def submit_backtest(self, strategy_binding: StrategyBinding, request: dict[str, Any]):
        return self._mutation("/api/research/backtests", strategy_binding, request)

    def submit_optimization(self, strategy_binding: StrategyBinding, request: dict[str, Any]):
        return self._mutation("/api/research/optimizations", strategy_binding, request)

    @staticmethod
    def _run_id(run_id):
        if type(run_id) is not str or RUN_ID.fullmatch(run_id) is None:
            raise ResearchMcpError("invalid_run_id")
        return run_id

    def get_run(self, run_id: str):
        return self._json(f"/api/research/runs/{self._run_id(run_id)}")

    def get_result(self, run_id: str):
        return self._json(f"/api/research/runs/{self._run_id(run_id)}/result")

    def get_report(self, run_id: str):
        run_id = self._run_id(run_id)
        request = Request(
            self.base_url + f"/api/research/runs/{run_id}/report",
            headers={"Accept": "text/html"}, method="GET",
        )
        try:
            with self._open(request, timeout=self.timeout_seconds) as response:
                raw = response.read(MAX_REPLY_BYTES + 1)
        except HTTPError as error:
            try:
                detail = self._error_detail(error)
            finally:
                error.close()
            raise ResearchMcpError(f"research_http_{error.code}: {detail}") from None
        except (URLError, OSError):
            raise ResearchMcpError("research_service_unavailable") from None
        if len(raw) > MAX_REPLY_BYTES:
            raise ResearchMcpError("research_reply_limit")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            raise ResearchMcpError("research_invalid_text_reply") from None


def create_mcp_server(bridge=None):
    from mcp.server import FastMCP
    from mcp.server.fastmcp.exceptions import ToolError

    client = bridge or ResearchHttpBridge()
    server = FastMCP(
        "catOS Research R3",
        instructions=(
            "Local synthetic research only. Use the registered strategy/dataset catalog; "
            "no arbitrary Python, path, URL, trading, credentials, or database access."
        ),
        log_level="ERROR",
    )

    def call(method, *args):
        try:
            return method(*args)
        except ResearchMcpError as error:
            raise ToolError(str(error)) from None

    @server.tool(name="research_catalog",
                 description="Read the trusted strategy/dataset registry with version and SHA256 provenance.")
    def research_catalog() -> dict[str, Any]:
        return call(client.catalog)

    @server.tool(name="research_list_runs",
                 description="List persisted research tasks written by the shared localhost ResearchService.")
    def research_list_runs() -> dict[str, Any]:
        return call(client.list_runs)

    @server.tool(name="research_submit_backtest",
                 description="Create one synthetic backtest after binding the exact registered strategy version and SHA256.")
    def research_submit_backtest(strategy: StrategyBinding,
                                 request: dict[str, Any]) -> dict[str, Any]:
        return call(client.submit_backtest, strategy, request)

    @server.tool(name="research_submit_optimization",
                 description="Create one bounded Optuna job after binding the exact registered strategy version and SHA256.")
    def research_submit_optimization(strategy: StrategyBinding,
                                     request: dict[str, Any]) -> dict[str, Any]:
        return call(client.submit_optimization, strategy, request)

    @server.tool(name="research_get_run",
                 description="Read status for a 32-hex research run id.")
    def research_get_run(run_id: str) -> dict[str, Any]:
        return call(client.get_run, run_id)

    @server.tool(name="research_get_result",
                 description="Read a completed research result. Decimal performance values remain JSON strings.")
    def research_get_result(run_id: str) -> dict[str, Any]:
        return call(client.get_result, run_id)

    @server.tool(name="research_get_report",
                 description="Read the persisted HTML report for a completed research run.")
    def research_get_report(run_id: str) -> str:
        return call(client.get_report, run_id)

    return server


def main():
    create_mcp_server().run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
