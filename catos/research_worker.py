"""One trusted research computation; JSON stdin/stdout, no persistence/network."""

import json
import os
import sys

from catos.research_catalog import execute_request, json_text


def load_registered_optuna_dependency():
    """Expose only packaging, not the entire user site, to the -s worker."""
    try:
        import packaging  # noqa: F401
    except ModuleNotFoundError as error:
        if error.name != "packaging":
            raise
        import importlib.util
        from pathlib import Path

        package_file = Path(os.environ.get("CATOS_OPTUNA_PACKAGING", ""))
        if package_file.name != "__init__.py" or package_file.parent.name != "packaging" or not package_file.is_file():
            raise
        package_dir = package_file.parent
        spec = importlib.util.spec_from_file_location(
            "packaging", package_file, submodule_search_locations=[str(package_dir)]
        )
        if spec is None or spec.loader is None:
            raise ModuleNotFoundError("packaging")
        package = importlib.util.module_from_spec(spec)
        sys.modules["packaging"] = package
        try:
            spec.loader.exec_module(package)
        except Exception:
            sys.modules.pop("packaging", None)
            raise


def main():
    try:
        envelope = json.loads(sys.stdin.buffer.read(8193).decode("utf-8"))
        kind = envelope.get("kind", "backtest")
        if kind == "backtest":
            payload, report = execute_request(envelope["request"], envelope["provenance"])
        elif kind == "optimization":
            load_registered_optuna_dependency()
            from catos.research_optimization import execute_optimization
            payload, report = execute_optimization(envelope["request"], envelope["provenance"])
        else:
            raise ValueError("unknown_research_kind")
        reply = {"payload": payload, "report": report}
    except Exception as error:
        reply = {"error": f"{type(error).__name__}: {error}"}
    sys.stdout.buffer.write(json_text(reply).encode("utf-8"))


if __name__ == "__main__":
    main()
