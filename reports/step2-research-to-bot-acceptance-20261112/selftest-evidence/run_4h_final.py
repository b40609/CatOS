"""Self-test: one more 4H replay with the final code, same TEST approval file; repeat-compare with current-a.
Also regenerates consistency reports (with tool_sha256) for all runs under the root.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
root = Path(sys.argv[2]).resolve()
os.environ["CATOS_STRATEGY_APPROVALS"] = str(root / "test-approvals.jsonl")
sys.path.insert(0, str(repo))

from catos import local_sim_replay, replay_consistency, strategy_approvals  # noqa: E402
from catos.research_catalog import json_text  # noqa: E402

DATASET = "okx-btc-usdt-swap-4h-20211106-20261106"
profile = strategy_approvals.load_profile(repo / "catos" / "deployment_profiles" / "donchian-breakout-4h-192-48.json")
summary = asyncio.run(local_sim_replay.replay(profile=profile, dataset_id=DATASET, output_root=root / "final"))
evidence = json.loads((root / "evidence.json").read_text(encoding="utf-8"))
dirs = {label: Path(info["run_dir"]) for label, info in evidence["runs"].items()}
dirs["final"] = root / "final" / summary["run_id"]
for label, run_dir in dirs.items():
    report = replay_consistency.compare(run_dir)
    (run_dir / "consistency.json").write_text(json_text(report) + "\n", encoding="utf-8")
    (run_dir / "consistency.md").write_text(replay_consistency.markdown(report), encoding="utf-8")
    run_summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    evidence["runs"][label] = {"run_dir": str(run_dir), "status": run_summary["status"], "fills": run_summary["fills"],
                               "final_account": run_summary["final_account"],
                               "ledger_bytes": run_summary["ledger_bytes"], "build_id": run_summary["build_id"],
                               "passed": report["passed"], "checks": report["checks"], "counts": report["counts"],
                               "published_research": report.get("published_research"),
                               "tool_sha256": report["tool_sha256"],
                               "fill_digest": report["fill_digest"], "decision_digest": report["decision_digest"]}
    print(label, report["passed"], run_summary["status"]["state"], run_summary["status"]["elapsed_seconds"], flush=True)
evidence["repeat_current_a_vs_b"] = replay_consistency.compare_repeat(dirs["current-a"], dirs["current-b"])
evidence["repeat_current_a_vs_final"] = replay_consistency.compare_repeat(dirs["current-a"], dirs["final"])
evidence["current_vs_new_defaults_same_fills"] = (
    evidence["runs"]["current-a"]["fill_digest"] == evidence["runs"]["new-defaults"]["fill_digest"])
evidence["final_build_id"] = local_sim_replay.build_id()
(root / "evidence.json").write_text(json_text(evidence) + "\n", encoding="utf-8")
print("repeat a/b", evidence["repeat_current_a_vs_b"]["same"])
print("repeat a/final", evidence["repeat_current_a_vs_final"]["same"])
