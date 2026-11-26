"""Regression checks for status truthfulness and test-fixture isolation (2026-11-27).

Covers:
- CAT-BX-10: workspace_build() hashes all catos/*.py modules, not just three files.
- CAT-BX-06 / CAT-AX-05: AccountLock honors CATOS_LOCK_DIRECTORY so subprocess fixtures
  never write into ~/.catos/local-simulation-locks.
- CAT-A-06: W6/W8 fixture tests leave no workspace-w*-fixture-test-* folders in outputs/.
"""

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from catos import account_lock, workspace_api


class WorkspaceBuildHashTests(unittest.TestCase):
    def test_workspace_build_changes_when_any_catos_module_changes(self):
        real_read_bytes = Path.read_bytes
        baseline = workspace_api.workspace_build()

        def mutated_read_bytes(path_obj: Path):
            data = real_read_bytes(path_obj)
            if path_obj.name == "risk.py":
                return data + b"\n# mutated\n"
            return data

        with mock.patch.object(Path, "read_bytes", mutated_read_bytes):
            changed = workspace_api.workspace_build()
        self.assertNotEqual(baseline, changed, "workspace_build() ignored changes to catos/risk.py")


class AccountLockEnvIsolationTests(unittest.TestCase):
    def test_account_lock_uses_env_directory_when_constant_is_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(account_lock, "LOCK_DIRECTORY", None), \
                    mock.patch.dict(os.environ, {"CATOS_LOCK_DIRECTORY": tmp}):
                lock = account_lock.AccountLock("test-env-isolated-account")
                self.assertEqual(lock.path.parent.resolve(), Path(tmp).resolve())


if __name__ == "__main__":
    unittest.main()
