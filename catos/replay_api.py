"""Read-only view of strategy approvals and Bot replays for the workspace UI (step 2).

GET /api/workspace/replay lists the local approval records (active or revoked,
and whether the strategy source still matches) and the newest replay runs with
their progress and consistency result. It never writes: approving, revoking and
starting a replay stay CLI-only (strategy_approvals, local_sim_replay).
"""

import json
from pathlib import Path

from catos import research_catalog, strategy_approvals
from catos.local_sim_replay import DEFAULT_OUTPUT

PATH = "/api/workspace/replay"
MAX_RUNS = 30
MAX_FILE_BYTES = 2_000_000


def _json(path):
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("file_too_large")
    return json.loads(raw.decode("utf-8"))


def _approvals():
    try:
        records = strategy_approvals.read_records()
    except (strategy_approvals.ApprovalError, OSError, ValueError) as error:
        return "unavailable", [], [f"approvals_{error}"]
    revoked = {r["approval_id"]: r["created_at"] for r in records if r["action"] == "revoke"}
    items = []
    for record in records:
        if record["action"] != "approve":
            continue
        profile = record["profile"]
        try:
            artifact, manifest_sha = strategy_approvals.deployment_identity(profile)
            source = ("current" if (artifact["sha256"], manifest_sha) == (record["source_sha256"],
                                                                           record["manifest_sha256"]) else "changed")
        except (strategy_approvals.ApprovalError, ValueError, OSError):
            source = "changed"
        items.append({
            "approval_id": record["record_id"], "state": "revoked" if record["record_id"] in revoked else "active",
            "revoked_at": revoked.get(record["record_id"]), "created_at": record["created_at"],
            "strategy_id": record["strategy_id"], "version": record["version"], "entry": record["entry"],
            "source_sha256": record["source_sha256"], "manifest_sha256": record["manifest_sha256"],
            "source": source, "research_basis": record["research_basis"],
            "parameters": profile["parameters"], "quantity": profile["quantity"], "inst_id": profile["inst_id"],
            "timeframe_ms": profile["timeframe_ms"], "warmup_bars": profile["warmup_bars"],
            "initial_balance": profile["initial_balance"], "fee_rate": profile["fee_rate"],
            "slippage_bps": profile["slippage_bps"]})
    return "available", list(reversed(items)), []


def _run(directory):
    manifest = _json(directory / "manifest.json")
    status = _json(directory / "status.json") if (directory / "status.json").is_file() else {}
    summary = _json(directory / "summary.json") if (directory / "summary.json").is_file() else None
    consistency = _json(directory / "consistency.json") if (directory / "consistency.json").is_file() else None
    profile = manifest["profile"]
    final = None if summary is None else summary.get("final_account")
    return {
        "run_id": manifest["run_id"], "created_at": manifest["created_at"], "approval_id": manifest["approval_id"],
        "approvals_path": manifest["approvals_path"],
        "formal_approval": Path(manifest["approvals_path"]).resolve() == strategy_approvals.DEFAULT_PATH.resolve(),
        "strategy_id": profile["strategy_id"], "version": profile["version"], "parameters": profile["parameters"],
        "inst_id": profile["inst_id"], "timeframe_ms": profile["timeframe_ms"],
        "dataset_id": None if manifest.get("dataset") is None else manifest["dataset"].get("id"),
        "bars": manifest["bars"], "risk_limits": manifest["risk_limits"], "pace_seconds": manifest["pace_seconds"],
        "state": status.get("state", "unknown"), "bars_done": status.get("bars", 0),
        "fills": status.get("fills"), "stop_reason": status.get("stop_reason"),
        "last_time_ms": status.get("last_time_ms"), "elapsed_seconds": status.get("elapsed_seconds"),
        "final_equity": None if final is None else final.get("equity"),
        "final_position": None if final is None else final.get("position"),
        "consistency": None if consistency is None else {
            "passed": consistency.get("passed"), "checks": consistency.get("checks"),
            "research_fills": (consistency.get("counts") or {}).get("research_fills"),
            "reversal_decisions": (consistency.get("counts") or {}).get("reversal_decisions")},
    }


def replay_overview(root=None):
    root = Path(DEFAULT_OUTPUT if root is None else root)
    approvals_state, approvals, issues = _approvals()
    runs = []
    if root.is_dir():
        directories = sorted((p for p in root.iterdir() if p.is_dir() and (p / "manifest.json").is_file()),
                             key=lambda p: (p / "manifest.json").stat().st_mtime, reverse=True)
        for directory in directories[:MAX_RUNS]:
            try:
                runs.append(_run(directory))
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                issues.append(f"run_unreadable:{directory.name[:64]}")
    return {"contract": "catos.replay.v1", "approvals_state": approvals_state,
            "approvals_path": str(strategy_approvals.approvals_path()),
            "eligible": [{"strategy_id": sid, "version": version,
                          "source_sha256": research_catalog.strategy_spec(sid).sha256}
                         for sid, version in strategy_approvals.BOT_STRATEGIES],
            "approvals": approvals, "runs": runs, "issues": issues,
            "notice": "核准與重播只能用 CLI（python -m catos.cli strategy …／replay …）；這裡唯讀。"}


def mount_replay(app, *, root=None):
    @app.get(PATH)
    def replay():
        return replay_overview(root)

    return app
