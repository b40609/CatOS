"""Strategies kept as files in ``strategies/<strategy_id>/`` (2026-11-17).

docs/agent-strategy-submission-proposal.md, approved by the user as "完全同意你的所有建議":
an Agent (or the user) writes ``strategy.json`` and ``strategy.py`` into a folder and
research runs them with no CatOS code change and no approval. Every read recomputes
the sha256 of the source and of the manifest; results are bound to them, so an edited
file is a new version. A Bot still needs the user's CLI approval, and approving a
folder strategy first runs the restart-consistency check below.

This module only reads and parses files. Strategy code is executed by ``build_class``,
which the research worker and the Bot Worker call in their own child processes (and
the approval CLI through the same research worker). It is trusted local code, not a
sandbox (AGENTS.md P1); the import allow-list keeps a strategy to one hashed file and
the Decimal contract, it does not stop a determined program.
"""

import ast
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import traceback
from types import ModuleType

from catos import research

ROOT = Path(__file__).resolve().parent.parent
HOME_ENV = "CATOS_STRATEGY_HOME"  # isolated tests and self-tests: <home>/strategies
FOLDER = "strategies"
SCHEMA = "catos.user-strategy"
SCHEMA_VERSION = 1
MANIFEST_NAME = "strategy.json"
SOURCE_NAME = "strategy.py"
MANIFEST_FIELDS = frozenset({
    "schema", "schema_version", "strategy_id", "version", "name", "description",
    "entry", "parameters", "lookback", "constraints",
})
PARAMETER_FIELDS = frozenset({"name", "min", "max", "default"})
MAX_MANIFEST_BYTES = 8192
MAX_SOURCE_BYTES = 64_000
MAX_PARAMETERS = 8  # ipc.Deployment carries at most eight parameters
MAX_PARAMETER_VALUE = 1_000_000
MAX_CONSTRAINTS = 8
WARMUP_LIMIT = 60_000  # research_catalog.MAX_BARS
STRATEGY_ID = re.compile(r"[a-z][a-z0-9-]{1,47}\Z")
VERSION = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
PARAMETER = re.compile(r"[a-z_][a-z0-9_]{0,31}\Z")
CLASS_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
# One hashed file: anything else a strategy imported would escape its sha256. No float
# module (math, statistics): prices and targets stay Decimal (AGENTS.md INVARIANTS).
ALLOWED_IMPORTS = frozenset({
    "__future__", "collections", "collections.abc", "dataclasses", "decimal", "enum", "functools",
    "itertools", "typing", "catos.research",
})
# print/input would write to or read from the worker's stdin/stdout, which carry its replies.
FORBIDDEN_NAMES = ("float", "__import__", "eval", "exec", "compile", "open", "print", "input")
CONSTRAINT_OPERATORS = {"<": "must be below", "<=": "must not exceed"}
ORIGIN = "user-strategy-folder"
PROVENANCE = {"origin": ORIGIN, "scope": "research; a Bot only through the user's CLI approval"}


class StrategyFolderError(ValueError):
    pass


@dataclass(frozen=True)
class FolderStrategy:
    """One valid folder, read now; the same attributes research_catalog.ResearchStrategy has."""
    strategy_id: str
    version: str
    entry: str
    sha256: str  # joint hash of the source files, same formula as the built-in artifacts
    files: tuple
    manifest: Path
    artifact_provenance: dict
    name: str
    parameters: tuple  # (name, low, high)
    lookback: str
    warmup_limit: int = WARMUP_LIMIT
    min_warmup_days: int = 0
    sizing: str = "fixed"
    preset: dict | None = None
    constraints: tuple = ()
    origin: str = "folder"
    base: Path = ROOT
    description: str = ""
    entry_class: str = ""
    manifest_sha256: str = ""
    defaults: dict = field(default_factory=dict)


def home():
    override = os.environ.get(HOME_ENV)
    return Path(override) if override else ROOT


def folder_root():
    return home() / FOLDER


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def source_hash(entries):
    """sha256 over [(name, file sha256)], the formula research_catalog.files_hash uses."""
    return _sha256(json.dumps([list(item) for item in entries], ensure_ascii=False).encode("utf-8"))


def _strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise StrategyFolderError(f"strategy.json: duplicate field {key}")
            result[key] = value
        return result

    def reject(value):
        raise StrategyFolderError(f"strategy.json: {value} is not allowed (integers and strings only)")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=reject, parse_float=reject)
    except json.JSONDecodeError as error:
        raise StrategyFolderError(f"strategy.json: invalid JSON ({error.msg}, line {error.lineno})") from None


def _read(path, limit, what):
    """Bytes of a regular file inside the strategy folder; links and escapes are refused."""
    root = folder_root()
    cursor = path
    while cursor != root and cursor != cursor.parent:
        if cursor.is_symlink():
            raise StrategyFolderError(f"{what}: symbolic links are not allowed")
        cursor = cursor.parent
    try:
        path.resolve(strict=True).relative_to(root.resolve())
        if not path.is_file():
            raise OSError
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
    except (OSError, ValueError):
        raise StrategyFolderError(f"{what}: missing or unreadable") from None
    if len(data) > limit:
        raise StrategyFolderError(f"{what}: larger than {limit} bytes")
    return data


def _int(value, what):
    if type(value) is not int or not 0 <= value <= MAX_PARAMETER_VALUE:
        raise StrategyFolderError(f"{what}: integer in [0, {MAX_PARAMETER_VALUE}] required")
    return value


def _manifest(value, strategy_id):
    if type(value) is not dict or set(value) != MANIFEST_FIELDS:
        missing = sorted(MANIFEST_FIELDS - set(value)) if type(value) is dict else []
        extra = sorted(set(value) - MANIFEST_FIELDS) if type(value) is dict else []
        raise StrategyFolderError(f"strategy.json: exact fields required (missing {missing}, unknown {extra})")
    if value["schema"] != SCHEMA or value["schema_version"] != SCHEMA_VERSION or type(value["schema_version"]) is not int:
        raise StrategyFolderError(f'strategy.json: schema must be "{SCHEMA}" with schema_version {SCHEMA_VERSION}')
    if value["strategy_id"] != strategy_id:
        raise StrategyFolderError(f"strategy.json: strategy_id must equal the folder name {strategy_id}")
    if type(value["version"]) is not str or not VERSION.fullmatch(value["version"]):
        raise StrategyFolderError("strategy.json: version must be 1-64 letters, digits, _ or -")
    for name, limit in (("name", 80), ("description", 2000)):
        if type(value[name]) is not str or not 0 < len(value[name]) <= limit or value[name].strip() != value[name]:
            raise StrategyFolderError(f"strategy.json: {name} must be 1-{limit} characters, no outer spaces")
    if type(value["entry"]) is not str or not CLASS_NAME.fullmatch(value["entry"]):
        raise StrategyFolderError("strategy.json: entry must be the strategy class name in strategy.py")
    items = value["parameters"]
    if type(items) is not list or not 1 <= len(items) <= MAX_PARAMETERS:
        raise StrategyFolderError(f"strategy.json: parameters must list 1-{MAX_PARAMETERS} integer parameters")
    parameters, defaults = [], {}
    for item in items:
        if type(item) is not dict or set(item) != PARAMETER_FIELDS:
            raise StrategyFolderError('strategy.json: each parameter needs exactly "name", "min", "max", "default"')
        name = item["name"]
        if type(name) is not str or not PARAMETER.fullmatch(name) or name == "quantity":
            raise StrategyFolderError(f"strategy.json: parameter name {name!r} must be snake_case and not quantity")
        if name in defaults:
            raise StrategyFolderError(f"strategy.json: duplicate parameter {name}")
        low, high, default = (_int(item[key], f"strategy.json: {name}.{key}") for key in ("min", "max", "default"))
        if not low <= default <= high or low == high:
            raise StrategyFolderError(f"strategy.json: {name} needs min < max and min <= default <= max")
        parameters.append((name, low, high))
        defaults[name] = default
    if value["lookback"] not in defaults:
        raise StrategyFolderError("strategy.json: lookback must name the parameter holding the strategy's longest window")
    if any(low < 1 for name, low, _ in parameters if name == value["lookback"]):
        raise StrategyFolderError("strategy.json: the lookback parameter's min must be at least 1")
    constraints = value["constraints"]
    if type(constraints) is not list or len(constraints) > MAX_CONSTRAINTS:
        raise StrategyFolderError(f'strategy.json: constraints must be a list (at most {MAX_CONSTRAINTS}) such as ["fast", "<", "slow"]')
    checked = []
    for item in constraints:
        if (type(item) is not list or len(item) != 3 or item[1] not in CONSTRAINT_OPERATORS
                or item[0] not in defaults or item[2] not in defaults or item[0] == item[2]):
            raise StrategyFolderError(f'strategy.json: constraint {item!r} must be ["a", "<" or "<=", "b"] over two parameters')
        checked.append(tuple(item))
    for problem in constraint_problems(tuple(checked), defaults):
        raise StrategyFolderError(f"strategy.json: defaults break a constraint ({problem})")
    return tuple(parameters), defaults, tuple(checked)


def constraint_problems(constraints, parameters):
    """Messages for every constraint the parameter values break, in research_catalog's wording."""
    problems = []
    for a, op, b in constraints:
        if not (parameters[a] < parameters[b] if op == "<" else parameters[a] <= parameters[b]):
            problems.append(f"{a}: {CONSTRAINT_OPERATORS[op]} {b}")
    return problems


def _source_problems(tree, entry):
    """Reasons the source is outside the contract; the AST is only inspected, never run."""
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in ALLOWED_IMPORTS:
                    problems.append(f"line {node.lineno}: import {alias.name} is not allowed")
        elif isinstance(node, ast.ImportFrom):
            research_only = node.module == "catos" and all(alias.name == "research" for alias in node.names)
            if node.level or not (node.module in ALLOWED_IMPORTS or research_only):
                problems.append(f"line {node.lineno}: from {'.' * node.level}{node.module or ''} import is not allowed")
        elif isinstance(node, ast.Constant) and type(node.value) in (float, complex):
            problems.append(f"line {node.lineno}: float literal {node.value!r}; use Decimal(\"{node.value}\")")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            problems.append(f"line {node.lineno}: {node.id} is not allowed in a strategy")
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == entry]
    if len(classes) != 1:
        problems.append(f"strategy.py must define exactly one top-level class {entry} (the manifest's entry)")
    return problems


def load(strategy_id):
    """The folder strategy as it is on disk now; StrategyFolderError explains what is wrong."""
    if type(strategy_id) is not str or not STRATEGY_ID.fullmatch(strategy_id):
        raise StrategyFolderError("folder name must be 2-48 lowercase letters, digits or -, starting with a letter")
    directory = folder_root() / strategy_id
    manifest_path = directory / MANIFEST_NAME
    source_path = directory / SOURCE_NAME
    raw_manifest = _read(manifest_path, MAX_MANIFEST_BYTES, "strategy.json")
    try:
        text = raw_manifest.decode("utf-8")
    except UnicodeDecodeError:
        raise StrategyFolderError("strategy.json: must be UTF-8") from None
    value = _strict_json(text)
    parameters, defaults, constraints = _manifest(value, strategy_id)
    source = _read(source_path, MAX_SOURCE_BYTES, "strategy.py")
    try:
        tree = ast.parse(source.decode("utf-8"), filename=f"{FOLDER}/{strategy_id}/{SOURCE_NAME}")
    except UnicodeDecodeError:
        raise StrategyFolderError("strategy.py: must be UTF-8") from None
    except SyntaxError as error:
        raise StrategyFolderError(f"strategy.py: syntax error on line {error.lineno}: {error.msg}") from None
    problems = _source_problems(tree, value["entry"])
    if problems:
        raise StrategyFolderError("strategy.py: " + "; ".join(problems[:5]))
    relative = f"{FOLDER}/{strategy_id}/{SOURCE_NAME}"
    return FolderStrategy(
        strategy_id=strategy_id, version=value["version"], entry=f"{relative}:{value['entry']}",
        sha256=source_hash([(relative, _sha256(source))]), files=(relative,), manifest=manifest_path,
        artifact_provenance=dict(PROVENANCE), name=value["name"], parameters=parameters,
        lookback=value["lookback"], preset={"parameters": dict(defaults), "quantity": "1", "warmup_days": 0},
        constraints=constraints, base=home(), description=value["description"],
        entry_class=value["entry"], manifest_sha256=_sha256(raw_manifest), defaults=defaults)


def discover(reserved=()):
    """({strategy_id: FolderStrategy}, [errors]); one broken folder never hides the others."""
    root = folder_root()
    specs, errors = {}, []
    if not root.is_dir():
        return specs, errors
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if not path.is_dir() or path.name.startswith((".", "_")) or path.name == "__pycache__":
            continue
        if path.name in reserved:
            errors.append({"strategy_id": path.name, "error": "name is taken by a built-in strategy; rename the folder"})
            continue
        try:
            specs[path.name] = load(path.name)
        except StrategyFolderError as error:
            errors.append({"strategy_id": path.name, "error": str(error)})
    return specs, errors


def artifact(spec):
    """The artifact-manifest view research_catalog.provenance expects; re-read and re-checked now."""
    current = load(spec.strategy_id)
    if (current.sha256, current.manifest_sha256, current.version) != (spec.sha256, spec.manifest_sha256, spec.version):
        raise StrategyFolderError("strategy_source_changed")
    return {"schema": SCHEMA, "schema_version": SCHEMA_VERSION, "artifact_id": spec.strategy_id,
            "version": spec.version, "sha256": spec.sha256, "entry": spec.entry,
            "source_files": list(spec.files), "approval_state": "research",
            "provenance": dict(spec.artifact_provenance)}


def build_class(spec, snapshot):
    """The entry class executed from already hash-verified bytes.

    The module is in sys.modules only while its body runs (``@dataclass`` with postponed
    annotations looks it up there) and is removed again; nothing imports it later.
    """
    (name,) = spec.files
    if set(snapshot) != {name}:
        raise StrategyFolderError("artifact_source_snapshot_mismatch")
    module = ModuleType("catos_strategy_" + spec.strategy_id.replace("-", "_"))
    module.__file__ = str(spec.base / name)
    if module.__name__ in sys.modules:
        raise StrategyFolderError("strategy_module_name_in_use")
    sys.modules[module.__name__] = module
    try:
        exec(compile(snapshot[name], module.__file__, "exec"), module.__dict__)
    finally:
        sys.modules.pop(module.__name__, None)
    value = getattr(module, spec.entry_class, None)
    if not isinstance(value, type) or not issubclass(value, research.Strategy):
        raise StrategyFolderError(f"{spec.entry_class} must be a class derived from catos.research.Strategy")
    return value


# ---- the check: runs inside the research worker (a child process) ----

CHECK_TIMEFRAME_MS = 900_000
CHECK_START_MS = 1_704_067_200_000  # 2024-01-01T00:00Z
# Wall-clock seconds the restart test may spend inside the research worker (whose whole
# run has research_catalog.TIMEOUT_SECONDS = 30). Every evaluation bar is a restart point;
# trade decisions and the bars around them go first, then the rest spread out, so a slow
# strategy that runs out of time reports how far it got instead of a bare timeout.
CHECK_RESTART_SECONDS = 15


def synthetic_bars(count, seed=20261117):
    """Deterministic trending random walk: alternating 120-bar up and down regimes plus noise."""
    state = seed
    price = Decimal("60000.0")
    tick = Decimal("0.1")
    bars = []
    for index in range(count):
        state = (state * 6364136223846793005 + 1442695040888963407) % 2 ** 64
        unit = Decimal(state >> 11) / Decimal(2 ** 53)
        drift = Decimal("0.002") if (index // 120) % 2 == 0 else Decimal("-0.002")
        close = (price * (1 + drift + (unit - Decimal("0.5")) * Decimal("0.02"))).quantize(tick)
        high = (max(price, close) * (1 + unit * Decimal("0.003"))).quantize(tick, ROUND_CEILING)
        low = (min(price, close) * (1 - (1 - unit) * Decimal("0.003"))).quantize(tick, ROUND_FLOOR)
        bars.append(research.Candle(CHECK_START_MS + index * CHECK_TIMEFRAME_MS, price, high, low, close))
        price = close
    return tuple(bars)


def where(error, spec):
    """'strategy.py line N: code' for the innermost frame inside the strategy file, if any."""
    target = str(spec.base / spec.files[0])
    frames = [frame for frame in traceback.extract_tb(error.__traceback__) if frame.filename == target]
    if not frames:
        return ""
    frame = frames[-1]
    return f" (strategy.py line {frame.lineno}: {(frame.line or '').strip()})"


def check(spec, strategy_class, parameters, quantity):
    """Load, run and restart-test one parameter set on synthetic bars; a JSON-ready report.

    Two Bot rules (ipc.parse_result, ipc.parse_history):
    - readiness: ``ready`` is False until exactly ``lookback`` bars were fed, then True;
    - restart consistency: a restarted Worker is rebuilt from the last ``lookback`` closed
      bars only. At every evaluation bar (within CHECK_RESTART_SECONDS), a fresh instance fed
      only those bars must return the same target as the instance that saw everything.
    Otherwise the strategy can still be researched but cannot go on a Bot. Passing is
    necessary, not sufficient: a restarted instance that later drifts is not simulated.
    """
    from catos import research_catalog

    lookback = parameters[spec.lookback]
    count = min(max(3 * lookback + 300, 600), 6000)
    bars = synthetic_bars(count)
    config = research.BacktestConfig(research_catalog.SYNTHETIC_CONTRACT, CHECK_TIMEFRAME_MS, Decimal("10000"),
                                     Decimal("0.0005"), Decimal("2"), ())
    report = {"parameters": dict(parameters), "quantity": str(quantity), "bars": count, "warmup_bars": lookback,
              "data": "合成 15m K 線（固定種子的趨勢隨機漫步），只用來檢查程式，不代表績效。",
              "stages": [], "trades": None, "decisions_checked": 0, "restart_points": 0, "exhaustive": False,
              "ok": False, "bot_eligible": False, "bot_reason": None}
    stages = report["stages"]

    def stage(name, function):
        try:
            value = function()
        except Exception as error:  # the strategy's own error, reported back to its author
            detail = f"{type(error).__name__}: {error}{where(error, spec)}"
            if "not ready" in str(error):
                detail += (f"。預熱是 lookback（{spec.lookback} = {lookback}）根，ready 必須剛好在第 {lookback} 根變 True；"
                           f"要比較 N 根之前的收盤就需要 N+1 根，讓 {spec.lookback} 代表持有的根數（N+1）")
            stages.append({"name": name, "ok": False, "detail": detail})
            raise
        stages.append({"name": name, "ok": True, "detail": None})
        return value

    def factory():
        return strategy_class(quantity=quantity, **parameters)

    try:
        stage("construct", factory)
        first = stage("backtest", lambda: research.backtest(strategy=factory, candles=bars, config=config,
                                                            warmup_bars=lookback))
        second = research.backtest(strategy=factory, candles=bars, config=config, warmup_bars=lookback)
        if (second.trades, second.equity_curve) != (first.trades, first.equity_curve):
            stages.append({"name": "deterministic", "ok": False,
                           "detail": "兩次執行結果不同：策略用了隨機數、時間或外部狀態"})
            return report
        stages.append({"name": "deterministic", "ok": True, "detail": None})
    except Exception:
        return report
    report["trades"] = len(first.trades)
    report["ok"] = True

    evaluation = bars[lookback:]
    views = first.equity_curve[1:]
    reference = factory()
    for count, bar in enumerate(bars[:lookback], start=1):
        research._call(reference.update_indicators, bar)
        ready = research._ready(reference)
        if report["bot_reason"] is None and ready != (count >= lookback):
            report["bot_reason"] = (f"餵到第 {count} 根時 ready 是 {ready}：Bot 要求 ready 在剛好餵滿 lookback"
                                    f"（{spec.lookback} = {lookback}）根時才變成 True，之前都是 False。"
                                    "基底類別預設的 ready 永遠是 True，要自己寫")
    targets = []
    decisions = []
    for index, (bar, view) in enumerate(zip(evaluation, views)):
        research._call(reference.update_indicators, bar)
        target = research._call(reference.on_bar, bar, view)
        targets.append(target)
        if target is not None and target != view.position:
            decisions.append(index)
    total = len(evaluation)
    report["restart_points"] = total
    near = [index for decision in decisions for index in range(decision - 3, decision + 4) if 0 <= index < total]
    stride = max(1, int(total ** 0.5))
    spread = [index for offset in range(stride) for index in range(offset, total, stride)]
    indices = list(dict.fromkeys([*decisions, *near, *spread]))  # every bar exactly once, priority order
    if report["bot_reason"] is not None:
        indices = []
    deadline = time.monotonic() + CHECK_RESTART_SECONDS
    checked = 0
    for index in indices:
        if time.monotonic() > deadline:
            report["bot_reason"] = (f"時間到（{CHECK_RESTART_SECONDS} 秒）只比對了 {checked}／{total} 個重啟時點："
                                    "update 太慢（例如每根都重算整個視窗），改成增量計算或縮短 lookback。"
                                    "研究可以繼續用，但核准要求每個時點都比對過")
            break
        checked += 1
        restarted = factory()
        start = lookback + index
        for bar in bars[start - lookback:start]:
            research._call(restarted.update_indicators, bar)
        research._call(restarted.update_indicators, bars[start])
        if not research._ready(restarted):
            report["bot_reason"] = (f"只餵最近 {lookback} 根（{spec.lookback}）重建後，第 {start} 根時 ready 是 False："
                                    f"策略需要的歷史比 lookback 長，lookback 要指向最長的視窗")
            break
        target = research._call(restarted.on_bar, bars[start], views[index])
        if target != targets[index]:
            report["bot_reason"] = (f"第 {start} 根：看過全部歷史的實例回 {targets[index]}，只看最近 {lookback} 根重建的實例回 "
                                    f"{target}。策略狀態不只由最近 {spec.lookback} 根 K 線決定（例如記住進場價、"
                                    "移動停損或計數器），可以研究，但不能上 Bot")
            break
    else:
        report["bot_eligible"] = report["bot_reason"] is None
    report["decisions_checked"] = checked
    report["exhaustive"] = bool(indices) and checked == total
    stages.append({"name": "restart_consistency", "ok": report["bot_eligible"], "detail": report["bot_reason"]})
    if report["trades"] == 0:
        report["notice"] = "合成資料上沒有任何成交：重啟一致性只檢查到不下單的情況，參數可能太保守。"
    return report
