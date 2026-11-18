"""Same scenario as test_2e/test_2b/test_2c, against the parent commit's catos/ (extract first: git archive 6d600094^ catos | tar -x -C reports/flatten-resend-20261118/scratch/old)."""
import sys, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "tests"))
sys.path.insert(0, str(HERE / "old"))  # parent-commit catos first
import catos.okx_demo_exchange as ex
print("adapter in use:", ex.__file__, "has expTime support:", hasattr(ex, "SUBMIT_DEADLINE_MS"))
import test_acceptance_scratch as S
suite = unittest.TestSuite([S.BotLevelTests(n) for n in (
    "test_2e_backward_clock_step_within_the_offset_cache_fails_the_kill_flatten",
    "test_2b_misjudged_flatten_order_stops_on_position_mismatch")])
r = unittest.TextTestRunner(verbosity=2).run(suite)
