"""Manifest-driven strategy registry: approval, source hash binding and fail-closed resolution."""

from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from catos import ipc, strategy_registry as registry
from catos.research_catalog import ROOT, STRATEGY_FILES, json_text
from test_ipc import STEP, bar, config

D = Decimal
MANIFEST = json.loads((ROOT / "catos" / "research_artifacts" / "sma-trend-sma-parameters-v1.json")
                      .read_text(encoding="utf-8"))


def fixture_root(temp, *, approval="approved", sha256=None, tamper=False, manifest_name="sma.json"):
    """Copy the real approved sources into an isolated root and write one manifest for them."""
    root = Path(temp)
    entries = []
    for name in STRATEGY_FILES:
        content = (ROOT / name).read_bytes()
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        entries.append((name, hashlib.sha256(content).hexdigest()))
    joint = hashlib.sha256(json_text(entries).encode("utf-8")).hexdigest()
    directory = root / "catos" / "research_artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {**MANIFEST, "sha256": sha256 or joint, "approval_state": approval}
    (directory / manifest_name).write_text(json.dumps(manifest), encoding="utf-8")
    if tamper:
        with (root / "catos" / "research_strategy.py").open("ab") as stream:
            stream.write(b"\n# tampered after approval\n")
    return root, directory, joint


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())

    def test_unregistered_identity_is_rejected(self):
        root, directory, _ = fixture_root(self.temp)
        for strategy_id, version in (("arbitrary-module", None), ("sma-trend", "other"),
                                     ("sma-trend", "sma-parameters-v2")):
            with self.subTest(strategy_id=strategy_id, version=version):
                with self.assertRaisesRegex(registry.RegistryError, "unknown_strategy"):
                    registry.resolve(strategy_id, version, directory=directory, root=root)
        for invalid in ("../x", "", "a" * 65, 7, None):
            with self.subTest(invalid=invalid), self.assertRaises(registry.RegistryError):
                registry.resolve(invalid, directory=directory, root=root)
        with self.assertRaisesRegex(registry.RegistryError, "directory_unavailable"):
            registry.resolve("sma-trend", directory=root / "absent", root=root)

    def test_unapproved_manifest_is_rejected(self):
        root, directory, _ = fixture_root(self.temp, approval="draft")
        with self.assertRaisesRegex(registry.RegistryError, "artifact_not_approved"):
            registry.resolve("sma-trend", "sma-parameters-v1", directory=directory, root=root)
        self.assertEqual(registry.manifests(directory, root)[("sma-trend", "sma-parameters-v1")].approved, False)

    def test_source_hash_mismatch_fails_closed(self):
        root, directory, joint = fixture_root(self.temp, tamper=True)
        entry = registry.resolve("sma-trend", "sma-parameters-v1", directory=directory, root=root)
        self.assertEqual(entry.sha256, joint)
        checkpoint = ipc.Checkpoint(config(), 2, STEP, (D("100"), D("101")))
        for action in (entry.load, entry.instantiate, lambda: entry.restore(checkpoint)):
            with self.subTest(action=action), self.assertRaisesRegex(registry.RegistryError, "artifact_hash_mismatch"):
                action()
        root, directory, _ = fixture_root(self.temp, sha256="0" * 64)
        with self.assertRaisesRegex(registry.RegistryError, "artifact_hash_mismatch"):
            registry.resolve("sma-trend", directory=directory, root=root).load()

    def test_malformed_manifests_fail_closed(self):
        root, directory, _ = fixture_root(self.temp)
        cases = {
            "duplicate_field": '{"schema": 1, "schema": 2}',
            "exact_fields": json.dumps({**MANIFEST, "extra": 1}),
            "entry": json.dumps({**MANIFEST, "entry": "../evil:Strategy"}),
            "source": json.dumps({**MANIFEST, "source_files": ["../outside.py"]}),
            "constant": '{"schema": NaN}',
        }
        for name, raw in cases.items():
            with self.subTest(name=name):
                (directory / "sma.json").write_text(raw, encoding="utf-8")
                with self.assertRaises(registry.RegistryError):
                    registry.resolve("sma-trend", directory=directory, root=root)

    def test_registered_sma_resolves_and_restores_checkpoint(self):
        entry = registry.resolve("sma-trend", "sma-parameters-v1")
        self.assertEqual(registry.resolve("sma-trend"), entry)
        self.assertEqual((entry.strategy_id, entry.version, entry.entry, entry.sha256),
                         (MANIFEST["artifact_id"], MANIFEST["version"], MANIFEST["entry"], MANIFEST["sha256"]))
        strategy_class = entry.load()
        self.assertEqual(strategy_class.__name__, "RegisteredSMA")
        checkpoint = ipc.Checkpoint(config(), 2, STEP, (D("100"), D("101")))
        strategy = entry.restore(checkpoint)
        self.assertEqual(entry.snapshot(strategy), (D("100"), D("101")))
        self.assertTrue(strategy.ready)
        self.assertEqual(strategy.on_bar(bar(2, "103"), None), D("2"))
        self.assertEqual(strategy.on_bar(bar(2, "99"), None), D("0"))

    def test_ipc_identity_is_validated_through_registry(self):
        root, directory, _ = fixture_root(self.temp, approval="draft")
        wire = config().to_wire()
        self.assertEqual(ipc.WorkerConfig.from_wire(wire).strategy_id, "sma-trend")
        with patch.object(registry, "MANIFEST_DIR", directory), patch.object(registry, "ROOT", root):
            with self.assertRaisesRegex(ipc.ProtocolError, "not_approved"):
                ipc.WorkerConfig.from_wire(wire)
        for strategy_id in ("arbitrary-module", "", None, 1):
            with self.subTest(strategy_id=strategy_id), self.assertRaises(ipc.ProtocolError):
                ipc.WorkerConfig.from_wire({**wire, "strategy_id": strategy_id})


if __name__ == "__main__":
    unittest.main()
