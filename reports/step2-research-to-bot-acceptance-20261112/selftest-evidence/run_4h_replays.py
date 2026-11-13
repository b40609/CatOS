"""Self-test on the 4H five-year dataset: isolated data root and a TEST approval record.

Not the user's approval: the approvals file lives inside the isolated self-test root.
Writes each run's consistency.json/.md and evidence.json at the root.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
root = Path(sys.argv[2]).resolve()
root.mkdir(parents=True, exist_ok=False)
os.environ["CATOS_STRATEGY_APPROVALS"] = str(root / "test-approvals.jsonl")
sys.path.insert(0, str(repo))

from catos import local_sim_replay, replay_consistency, strategy_approvals  # noqa: E402
from catos.research_catalog import json_text  # noqa: E402

DATASET = "okx-btc-usdt-swap-4h-20211106-20261106"
profile = strategy_approvals.load_profile(repo / "catos" / "deployment_profiles" / "donchian-breakout-4h-192-48.json")
artifact, _ = strategy_approvals.deployment_identity(profile)
record = strategy_approvals.approve(strategy_id=profile["strategy_id"], version=profile["version"],
                                    sha256=artifact["sha256"], profile=profile,
                                    confirm=lambda text, word: True,
                                    research_basis="selftest-test-record-not-user-approval")
print("test approval", record["record_id"], flush=True)
evidence = {"approval_id": record["record_id"], "approvals_path": os.environ["CATOS_STRATEGY_APPROVALS"],
            "dataset": DATASET, "runs": {}}
dirs = {}
for label, limits in (("current-a", "current"), ("current-b", "current"), ("new-defaults", "new-defaults")):
    summary = asyncio.run(local_sim_replay.replay(profile=profile, dataset_id=DATASET,
                                                  output_root=root / label, limits=limits))
    run_dir = root / label / summary["run_id"]
    dirs[label] = run_dir
    report = replay_consistency.compare(run_dir)
    (run_dir / "consistency.json").write_text(json_text(report) + "\n", encoding="utf-8")
    (run_dir / "consistency.md").write_text(replay_consistency.markdown(report), encoding="utf-8")
    evidence["runs"][label] = {"run_dir": str(run_dir), "status": summary["status"], "fills": summary["fills"],
                               "final_account": summary["final_account"], "ledger_bytes": summary["ledger_bytes"],
                               "passed": report["passed"], "checks": report["checks"], "counts": report["counts"],
                               "published_research": report.get("published_research"),
                               "fill_digest": report["fill_digest"], "decision_digest": report["decision_digest"]}
    print(label, json.dumps(evidence["runs"][label]["status"], ensure_ascii=False), report["passed"], flush=True)
evidence["repeat_current_a_vs_b"] = replay_consistency.compare_repeat(dirs["current-a"], dirs["current-b"])
evidence["current_vs_new_defaults_same_fills"] = (
    evidence["runs"]["current-a"]["fill_digest"] == evidence["runs"]["new-defaults"]["fill_digest"])
(root / "evidence.json").write_text(json_text(evidence) + "\n", encoding="utf-8")
print("repeat", evidence["repeat_current_a_vs_b"]["passed"], "new_defaults_same", evidence["current_vs_new_defaults_same_fills"])
