"""Actual SDK stdio calls, with a local-only bridge and raw result evidence."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from catos.worker_host import worker_environment
from test_python_strategy_v1 import manifest, command

async def probe(options):
    records = []
    params = StdioServerParameters(command=sys.executable,
        args=["-m", "catos.strategy_mcp", "--base-url", options.base_url], env=worker_environment())
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(tool.name for tool in tools.tools)
            assert names == sorted(["strategy_contract", "list_strategy_versions", "create_strategy_version", "list_simulation_results", "get_simulation_result"]), names
            records.append({"tools": names})
            async def call(name, arguments=None):
                result = await session.call_tool(name, arguments or {})
                raw = result.model_dump(mode="json", exclude_none=True)
                records.append({"tool": name, "arguments": arguments or {}, "result": raw})
                assert not result.isError, raw
                value = result.structuredContent
                if value is None:
                    value = json.loads(next(block.text for block in result.content if block.type == "text"))
                assert type(value) is dict, raw
                return value
            await call("strategy_contract")
            if options.create:
                value = manifest("mcp-v1")
                request = command()
                created = await call("create_strategy_version", {"request_id": request, "manifest": value})
                assert await call("create_strategy_version", {"request_id": request, "manifest": value}) == created
                await call("create_strategy_version", {"request_id": command(), "manifest": manifest("mcp-hold-v1", True)})
                file_value = manifest("file-v1")
                (options.output.parent / "file-strategy.json").write_text(json.dumps(file_value), encoding="utf-8")
            await call("list_strategy_versions")
            history = await call("list_simulation_results")
            for run in history["items"]:
                result = await call("get_simulation_result", {"run_id": run["run_id"]})
                assert result == run, (result, run)
    options.output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"tool_calls": len(records)-1, "history": len(history["items"]), "output": str(options.output)}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--create", action="store_true")
    asyncio.run(probe(parser.parse_args()))
