"""Manifest-driven registry of approved strategy artifacts.

The worker never hard-codes a strategy module. Every approved artifact is a
manifest under ``catos/research_artifacts`` naming its ``entry`` and the
``source_files`` whose joint sha256 must still match before the entry is
executed. Any mismatch, missing manifest or non-approved state fails closed:
nothing falls back to a default strategy.

Executed modules are built from the verified bytes in memory and are never
inserted into ``sys.modules``, so the parent process can import this module
without loading strategy code.
"""

import builtins
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from types import ModuleType

from catos.research_catalog import DEFAULT_REQUEST, ROOT, json_text

MANIFEST_DIR = ROOT / "catos" / "research_artifacts"
SCHEMA = "catos.research.strategy-artifact"
SCHEMA_VERSION = 1
MANIFEST_FIELDS = frozenset({
    "schema", "schema_version", "artifact_id", "version", "sha256", "entry",
    "source_files", "approval_state", "provenance",
})
MAX_MANIFEST_BYTES = 8192
MAX_SOURCE_FILES = 8
_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SOURCE = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*\.py\Z")
_ENTRY = re.compile(r"((?:[A-Za-z_][A-Za-z0-9_]*\.)*[A-Za-z_][A-Za-z0-9_]*):([A-Za-z_][A-Za-z0-9_]*)\Z")


class RegistryError(ValueError):
    pass


def _strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise RegistryError("artifact_manifest_duplicate_field")
            result[key] = value
        return result

    def reject_constant(_value):
        raise RegistryError("artifact_manifest_invalid_json_constant")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=reject_constant)
    except json.JSONDecodeError:
        raise RegistryError("artifact_manifest_invalid_json") from None


def _module_name(source_file):
    return source_file[:-3].replace("/", ".")


@dataclass(frozen=True)
class RegisteredStrategy:
    """One approved manifest; ``load`` verifies the sources before executing them."""
    strategy_id: str
    version: str
    entry: str
    sha256: str
    source_files: tuple
    approval_state: str
    manifest_path: Path
    root: Path

    @property
    def approved(self):
        return self.approval_state == "approved"

    def verified_sources(self):
        """Read every source file once, reject links/escapes, and check the joint hash."""
        root = self.root.resolve()
        snapshot = {}
        entries = []
        for name in self.source_files:
            path = self.root / name
            try:
                path.resolve(strict=True).relative_to(root)
            except (OSError, ValueError):
                raise RegistryError("artifact_source_path_invalid") from None
            cursor = path
            while cursor != self.root:
                if cursor.is_symlink():
                    raise RegistryError("artifact_source_symlink_rejected")
                cursor = cursor.parent
            content = path.read_bytes()
            snapshot[name] = content
            entries.append((name, hashlib.sha256(content).hexdigest()))
        source_hash = hashlib.sha256(json_text(entries).encode("utf-8")).hexdigest()
        if source_hash != self.sha256:
            raise RegistryError("artifact_hash_mismatch")
        return snapshot

    def load(self):
        """Return the entry class built only from hash-verified source bytes."""
        if not self.approved:
            raise RegistryError("artifact_not_approved")
        snapshot = self.verified_sources()
        files = {_module_name(name): name for name in snapshot}
        module_name, attribute = _ENTRY.fullmatch(self.entry).groups()
        if module_name not in files:
            raise RegistryError("artifact_entry_mismatch")
        modules = {}
        original_import = builtins.__import__

        def build(name):
            if name in modules:
                return modules[name]
            module = ModuleType(name)
            module.__file__ = str(self.root / files[name])
            safe_builtins = dict(vars(builtins))
            safe_builtins["__import__"] = hooked_import
            module.__dict__["__builtins__"] = safe_builtins
            modules[name] = module
            exec(compile(snapshot[files[name]], module.__file__, "exec"), module.__dict__)
            return module

        def hooked_import(name, globals=None, locals=None, fromlist=(), level=0):
            if level == 0 and name in files:
                return build(name)
            return original_import(name, globals, locals, fromlist, level)

        value = getattr(build(module_name), attribute, None)
        if not isinstance(value, type):
            raise RegistryError("artifact_entry_unavailable")
        return value

    def instantiate(self):
        """Bind the catalog's registered default parameters (v1: period 2, quantity 2)."""
        parameters = DEFAULT_REQUEST["parameters"]
        return self.load()(parameters["period"], Decimal(parameters["quantity"]))

    def restore(self, checkpoint):
        strategy = self.instantiate()
        strategy.closes.extend(checkpoint.closes)
        return strategy

    @staticmethod
    def snapshot(strategy):
        return tuple(strategy.closes)


def read_manifest(path, root=None):
    root = ROOT if root is None else root
    if path.is_symlink():
        raise RegistryError("artifact_manifest_symlink_rejected")
    try:
        path.resolve(strict=True).relative_to(root.resolve())
        raw = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        raise RegistryError("artifact_manifest_unavailable") from None
    if len(raw.encode("utf-8")) > MAX_MANIFEST_BYTES:
        raise RegistryError("artifact_manifest_too_large")
    value = _strict_json(raw)
    if type(value) is not dict or set(value) != MANIFEST_FIELDS:
        raise RegistryError("artifact_manifest_exact_fields_required")
    if value["schema"] != SCHEMA or type(value["schema"]) is not str:
        raise RegistryError("artifact_manifest_schema_mismatch")
    if type(value["schema_version"]) is not int or value["schema_version"] != SCHEMA_VERSION:
        raise RegistryError("artifact_manifest_schema_version_mismatch")
    for name in ("artifact_id", "version", "approval_state"):
        if type(value[name]) is not str or _TOKEN.fullmatch(value[name]) is None:
            raise RegistryError(f"artifact_manifest_invalid_{name}")
    if type(value["sha256"]) is not str or _SHA256.fullmatch(value["sha256"]) is None:
        raise RegistryError("artifact_sha256_invalid")
    if type(value["entry"]) is not str or _ENTRY.fullmatch(value["entry"]) is None:
        raise RegistryError("artifact_entry_invalid")
    sources = value["source_files"]
    if (type(sources) is not list or not 1 <= len(sources) <= MAX_SOURCE_FILES
            or any(type(name) is not str or _SOURCE.fullmatch(name) is None for name in sources)
            or len(set(sources)) != len(sources)):
        raise RegistryError("artifact_source_files_invalid")
    if type(value["provenance"]) is not dict:
        raise RegistryError("artifact_provenance_invalid")
    return RegisteredStrategy(value["artifact_id"], value["version"], value["entry"], value["sha256"],
                              tuple(sources), value["approval_state"], path, root)


def manifests(directory=None, root=None):
    """Every manifest in the directory, keyed by (strategy_id, version); invalid files fail closed."""
    directory = MANIFEST_DIR if directory is None else directory
    if not directory.is_dir():
        raise RegistryError("artifact_manifest_directory_unavailable")
    result = {}
    for path in sorted(directory.glob("*.json")):
        entry = read_manifest(path, root)
        key = (entry.strategy_id, entry.version)
        if key in result:
            raise RegistryError("artifact_duplicate_manifest")
        result[key] = entry
    return result


def resolve(strategy_id, version=None, *, directory=None, root=None):
    """Approved manifest for the identity; ``version=None`` means the single approved version."""
    if type(strategy_id) is not str or _TOKEN.fullmatch(strategy_id) is None:
        raise RegistryError("invalid_strategy_id")
    if version is not None and (type(version) is not str or _TOKEN.fullmatch(version) is None):
        raise RegistryError("invalid_strategy_version")
    candidates = [entry for (sid, _), entry in manifests(directory, root).items() if sid == strategy_id]
    if version is not None:
        candidates = [entry for entry in candidates if entry.version == version]
    if not candidates:
        raise RegistryError("unknown_strategy")
    approved = [entry for entry in candidates if entry.approved]
    if not approved:
        raise RegistryError("artifact_not_approved")
    if len(approved) != 1:
        raise RegistryError("ambiguous_strategy_version")
    return approved[0]

