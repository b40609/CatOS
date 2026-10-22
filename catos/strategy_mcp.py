"""Local stdio MCP: immutable Python versions and read-only simulation results."""

import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request

from catos.research_mcp import ResearchHttpBridge, ResearchMcpError, MAX_REPLY_BYTES
from catos.python_strategy import artifact

PREFIX = "/api/workspace/simulation"


class StrategyHttpBridge(ResearchHttpBridge):
    def read(self, suffix):
        if suffix not in ("version", "strategy-contract", "strategies", "runs"):
            from catos.local_sim_control import valid_id
            if not suffix.startswith("runs/") or not valid_id(suffix[5:]):
                raise ResearchMcpError("invalid_result_id")
        return self._request(suffix)

    def _request(self, suffix, payload=None, version=None):
        headers = {"Accept": "application/json"}
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            if len(body) > 32768:
                raise ResearchMcpError("strategy_request_limit")
            headers.update({"Content-Type": "application/json", "X-CatOS-Build": version["build_id"],
                            "X-CatOS-Instance": version["instance_id"]})
        request = Request(self.base_url + PREFIX + "/" + suffix, headers=headers, data=body,
                          method="POST" if body is not None else "GET")
        try:
            with self._open(request, timeout=self.timeout_seconds) as response:
                raw = response.read(MAX_REPLY_BYTES + 1)
        except HTTPError as error:
            try:
                detail = self._error_detail(error)
            finally:
                error.close()
            raise ResearchMcpError(f"strategy_http_{error.code}: {detail}") from None
        except (URLError, OSError):
            raise ResearchMcpError("strategy_service_unavailable") from None
        if len(raw) > MAX_REPLY_BYTES:
            raise ResearchMcpError("strategy_reply_limit")
        value = json.loads(raw)
        if type(value) is not dict:
            raise ResearchMcpError("strategy_reply_contract")
        return value

    def create_version(self, request_id, manifest):
        checked = artifact(manifest)
        version = self.read("version")
        if version.get("restart_required") is not False or version.get("unavailable_reason"):
            raise ResearchMcpError("strategy_service_not_ready")
        return self._request("strategies", {"request_id": request_id, "manifest": checked}, version)


def create_server(bridge=None):
    from mcp.server.fastmcp import FastMCP
    bridge = bridge or StrategyHttpBridge()
    server = FastMCP("catOS Local Strategies")

    @server.tool()
    def strategy_contract() -> dict:
        """Read Python artifact schema, Worker hooks and trust boundary."""
        return bridge.read("strategy-contract")

    @server.tool()
    def list_strategy_versions() -> dict:
        """Read shared immutable strategy versions and parameter defaults."""
        return bridge.read("strategies")

    @server.tool()
    def create_strategy_version(request_id: str, manifest: dict) -> dict:
        """Create an immutable Python version, default local only; never allocate or start a Bot."""
        return bridge.create_version(request_id, manifest)

    @server.tool()
    def list_simulation_results() -> dict:
        """Read persisted local simulation history; never change execution."""
        return bridge.read("runs")

    @server.tool()
    def get_simulation_result(run_id: str) -> dict:
        """Read a local result, binding, event history and final account evidence."""
        return bridge.read("runs/" + run_id)

    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8770")
    args = parser.parse_args()
    create_server(StrategyHttpBridge(args.base_url)).run(transport="stdio")


if __name__ == "__main__":
    main()
