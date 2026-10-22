"""Fixed trusted registry and strict Decimal-string research contract."""

from dataclasses import asdict
from decimal import Decimal, InvalidOperation, localcontext
import builtins
import hashlib
import json
from pathlib import Path
import re
from types import ModuleType

from catos import research
from catos.data_io import load_candles_csv
from catos.reporting import render_report

ROOT = Path(__file__).resolve().parent.parent
STRATEGY_ID = "sma-trend"
STRATEGY_VERSION = "sma-parameters-v1"
STRATEGY_ENTRY = "catos.research_strategy:RegisteredSMA"
APPROVED_STRATEGY_SHA256 = "3b411bb170572445bc8d4a28c5647387ed08cc3846b03c0c0b36949052f92cf2"
DATASET_ID = "synthetic-btc-15m-v1"
DATA_PATH = ROOT / "examples" / "research-web-synthetic.csv"
STRATEGY_FILES = (
    "examples/closed_bar_demo.py", "catos/research_strategy.py",
)
STRATEGY_MANIFEST = ROOT / "catos" / "research_artifacts" / "sma-trend-sma-parameters-v1.json"
ARTIFACT_SCHEMA = "catos.research.strategy-artifact"
ARTIFACT_SCHEMA_VERSION = 1
ARTIFACT_PROVENANCE = {
    "origin": "catos-r1-registered-sma",
    "approval_basis": "inspected-fixed-local-artifact",
    "scope": "synthetic-research-only",
}
ARTIFACT_FIELDS = {
    "schema", "schema_version", "artifact_id", "version", "sha256", "entry",
    "source_files", "approval_state", "provenance",
}
SHA256 = re.compile(r"[0-9a-f]{64}")
ENGINE_FILES = (
    "catos/research.py", "catos/data_io.py", "catos/reporting.py",
    "catos/research_catalog.py", "catos/research_worker.py",
    "catos/research_optimization.py", "catos/optimization.py",
    "catos/research_validation.py", "catos/research_regimes.py",
    "catos/research_validation_job.py",
)
DEFAULT_REQUEST = {
    "strategy_id": STRATEGY_ID, "dataset_id": DATASET_ID,
    "parameters": {"period": 2, "quantity": "2"},
    "initial_balance": "1000", "fee_rate": "0.0005",
    "slippage_bps": "2", "warmup_bars": 2,
}
MAX_BARS = 512
MAX_RUNS = 200
TIMEOUT_SECONDS = 30
MAX_OUTPUT_BYTES = 2_000_000
MAX_TRIALS = 20
MAX_VALIDATION_CANDIDATES = 20
MAX_VALIDATION_RUNS = 100
MAX_VALIDATION_WINDOWS = 8
DEFAULT_OPTIMIZATION = {
    "backtest": {**DEFAULT_REQUEST, "warmup_bars": 8},
    "search_space": {"period": {"low": 2, "high": 8, "step": 1}},
    "n_trials": 8, "seed": 42,
}
DEFAULT_VALIDATION = {
    "backtest": {**DEFAULT_REQUEST, "warmup_bars": 4},
    "search_space": {"period": {"low": 2, "high": 4, "step": 1}},
    "plan": {"train_bars": 24, "test_bars": 16, "windows": 3},
    "regime_rule": {"lookback_bars": 4, "trend_efficiency": "0.5",
                    "high_volatility_bps": "250"},
    "max_candidates": 3, "max_runs": 12,
}


def json_text(value):
    def encode(item):
        if isinstance(item, Decimal):
            return str(item)
        raise TypeError(f"Unsupported JSON value: {type(item).__name__}")
    return json.dumps(value, default=encode, ensure_ascii=False, allow_nan=False)


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def files_hash(names):
    entries = [(name, file_hash(ROOT / name)) for name in names]
    return hashlib.sha256(json_text(entries).encode("utf-8")).hexdigest()


def _strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("artifact_manifest_duplicate_field")
            result[key] = value
        return result

    def reject_constant(_value):
        raise ValueError("artifact_manifest_invalid_json_constant")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=reject_constant)


def _verified_strategy_source_snapshot(source_files):
    if type(source_files) is not list or source_files != list(STRATEGY_FILES):
        raise ValueError("artifact_source_files_mismatch")
    root = ROOT.resolve()
    snapshot = {}
    entries = []
    for name in source_files:
        if type(name) is not str or name not in STRATEGY_FILES:
            raise ValueError("artifact_source_files_mismatch")
        path = ROOT / name
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError):
            raise ValueError("artifact_source_path_invalid") from None
        cursor = path
        while cursor != ROOT:
            if cursor.is_symlink():
                raise ValueError("artifact_source_symlink_rejected")
            cursor = cursor.parent
        content = path.read_bytes()
        snapshot[name] = content
        entries.append((name, hashlib.sha256(content).hexdigest()))
    source_hash = hashlib.sha256(json_text(entries).encode("utf-8")).hexdigest()
    return snapshot, source_hash


def _verified_strategy_source_hash(source_files):
    return _verified_strategy_source_snapshot(source_files)[1]


def validate_strategy_manifest(value):
    if type(value) is not dict or set(value) != ARTIFACT_FIELDS:
        raise ValueError("artifact_manifest_exact_fields_required")
    if value["schema"] != ARTIFACT_SCHEMA or type(value["schema"]) is not str:
        raise ValueError("artifact_manifest_schema_mismatch")
    if type(value["schema_version"]) is not int or value["schema_version"] != ARTIFACT_SCHEMA_VERSION:
        raise ValueError("artifact_manifest_schema_version_mismatch")
    if type(value["artifact_id"]) is not str or value["artifact_id"] != STRATEGY_ID:
        raise ValueError("unknown_artifact")
    if type(value["version"]) is not str or value["version"] != STRATEGY_VERSION:
        raise ValueError("artifact_version_mismatch")
    if type(value["sha256"]) is not str or SHA256.fullmatch(value["sha256"]) is None:
        raise ValueError("artifact_sha256_invalid")
    if value["sha256"] != APPROVED_STRATEGY_SHA256:
        raise ValueError("artifact_identity_mismatch")
    if type(value["entry"]) is not str or value["entry"] != STRATEGY_ENTRY:
        raise ValueError("artifact_entry_mismatch")
    if value["approval_state"] != "approved" or type(value["approval_state"]) is not str:
        raise ValueError("artifact_not_approved")
    if type(value["provenance"]) is not dict or value["provenance"] != ARTIFACT_PROVENANCE:
        raise ValueError("artifact_provenance_mismatch")
    source_hash = _verified_strategy_source_hash(value["source_files"])
    if value["sha256"] != source_hash:
        raise ValueError("artifact_hash_mismatch")
    return json.loads(json_text(value))


def load_strategy_manifest():
    if STRATEGY_MANIFEST.is_symlink():
        raise ValueError("artifact_manifest_symlink_rejected")
    try:
        resolved = STRATEGY_MANIFEST.resolve(strict=True)
        resolved.relative_to(ROOT.resolve())
        raw = STRATEGY_MANIFEST.read_text(encoding="utf-8")
    except (OSError, ValueError):
        raise ValueError("artifact_manifest_unavailable") from None
    if len(raw.encode("utf-8")) > 8192:
        raise ValueError("artifact_manifest_too_large")
    try:
        value = _strict_json(raw)
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError(str(error)) from None
    return validate_strategy_manifest(value)


def provenance():
    artifact = load_strategy_manifest()
    return {
        "strategy": {
            "id": artifact["artifact_id"], "version": artifact["version"],
            "sha256": artifact["sha256"], "source": "approved_fixed_artifact_manifest",
            "source_files": list(artifact["source_files"]), "entry": artifact["entry"],
            "approval_state": artifact["approval_state"],
            "artifact_manifest": {
                "schema": artifact["schema"], "schema_version": artifact["schema_version"],
                "sha256": file_hash(STRATEGY_MANIFEST),
                "provenance": dict(artifact["provenance"]),
            },
        },
        "dataset": {"id": DATASET_ID, "source": "synthetic_closed_bars",
                    "sha256": file_hash(DATA_PATH)},
        "engine_sha256": files_hash(ENGINE_FILES),
    }


def decimal_string(value, name, *, positive=False):
    if type(value) is not str or not 1 <= len(value) <= 64 or value.strip() != value:
        raise ValueError(f"{name}: Decimal must be a bounded JSON string")
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError(f"{name}: invalid Decimal string") from None
    research._decimal(number, name, positive=positive)
    return number


def validate_request(value):
    if type(value) is not dict or set(value) != set(DEFAULT_REQUEST):
        raise ValueError("request: exact registered fields required")
    if value["strategy_id"] != STRATEGY_ID:
        raise ValueError("unknown_strategy")
    # Every execution path revalidates the fixed local artifact manifest and
    # current allowlisted source hash before accepting a registered strategy.
    load_strategy_manifest()
    if value["dataset_id"] != DATASET_ID:
        raise ValueError("unknown_dataset")
    params = value["parameters"]
    if type(params) is not dict or set(params) != {"period", "quantity"}:
        raise ValueError("parameters: period and quantity required")
    period = params["period"]
    warmup = value["warmup_bars"]
    if type(period) is not int or not 2 <= period <= 32:
        raise ValueError("period: integer in [2, 32] required")
    if type(warmup) is not int or not period <= warmup < 64:
        raise ValueError("warmup_bars: integer >= period and < 64 required")
    quantity = decimal_string(params["quantity"], "quantity", positive=True)
    if quantity > Decimal("1000") or quantity % Decimal("1"):
        raise ValueError("quantity: whole contracts in [1, 1000] required")
    balance = decimal_string(value["initial_balance"], "initial_balance", positive=True)
    if balance > Decimal("1000000000"):
        raise ValueError("initial_balance: maximum 1000000000 USDT")
    fee = decimal_string(value["fee_rate"], "fee_rate")
    slip = decimal_string(value["slippage_bps"], "slippage_bps")
    if not Decimal("0") <= fee <= Decimal("0.01"):
        raise ValueError("fee_rate: ratio in [0, 0.01] required")
    if not Decimal("0") <= slip <= Decimal("100"):
        raise ValueError("slippage_bps: in [0, 100] required")
    cfg = research.BacktestConfig(
        research.ContractSpec("BTC-USDT-SWAP", Decimal("0.01"),
                              Decimal("0.01"), Decimal("1"), Decimal("1")),
        900_000, balance, fee, slip, (),
    )
    # A JSON round-trip owns an immutable-by-convention request copy.
    snapshot = json.loads(json_text(value))
    return snapshot, cfg, period, quantity


def validate_optimization_request(value):
    if type(value) is not dict or set(value) != set(DEFAULT_OPTIMIZATION):
        raise ValueError("optimization: exact registered fields required")
    backtest_request, config, _, quantity = validate_request(value["backtest"])
    space = value["search_space"]
    if type(space) is not dict or set(space) != {"period"}:
        raise ValueError("search_space: only registered period range is supported")
    period = space["period"]
    if type(period) is not dict or set(period) != {"low", "high", "step"}:
        raise ValueError("period: low, high and step required")
    low, high, step = period["low"], period["high"], period["step"]
    if any(type(number) is not int for number in (low, high, step)) or not (
        2 <= low <= high <= 32 and 1 <= step <= 30 and (high - low) % step == 0
    ):
        raise ValueError("period: aligned integer range within [2, 32] required")
    if backtest_request["warmup_bars"] < high:
        raise ValueError("warmup_bars: must cover highest searched period")
    if type(value["n_trials"]) is not int or not 1 <= value["n_trials"] <= MAX_TRIALS:
        raise ValueError(f"n_trials: integer in [1, {MAX_TRIALS}] required")
    if type(value["seed"]) is not int or not 0 <= value["seed"] <= 2 ** 32 - 1:
        raise ValueError("seed: unsigned 32-bit integer required")
    snapshot = json.loads(json_text(value))
    snapshot["backtest"] = backtest_request
    return snapshot, config, quantity


def catalog():
    source = provenance()
    return {
        "strategies": [{**source["strategy"], "name": "SMA 趨勢（Long / Flat）",
                        "parameters": {"period": {"min": 2, "max": 32},
                                       "quantity": {"unit": "contracts"}}}],
        "datasets": [{**source["dataset"], "name": "合成 BTC 15m · 96 根已收盤 K 線",
                      "symbol": "BTC-USDT-SWAP", "timeframe": "15m", "bars": 96,
                      "contract": asdict(validate_request(DEFAULT_REQUEST)[1].contract)}],
        "defaults": DEFAULT_REQUEST,
        "optimization": {"defaults": DEFAULT_OPTIMIZATION, "max_trials": MAX_TRIALS,
                         "score_name": "return_pct", "direction": "maximize",
                         "notice": "僅合成資料、樣本內搜尋；未執行樣本外檢驗。"},
        "validation": {"example_request": DEFAULT_VALIDATION,
                       "max_candidates": MAX_VALIDATION_CANDIDATES,
                       "max_runs": MAX_VALIDATION_RUNS, "max_windows": MAX_VALIDATION_WINDOWS,
                       "score_name": "return_pct", "direction": "maximize",
                       "notice": "合成資料；穩定區選參後做滾動 OOS 與分環境評估。門檻僅供示範，須明示。"},
        "limits": {"concurrent_tasks": 1, "max_bars": MAX_BARS,
                   "timeout_seconds": TIMEOUT_SECONDS, "max_runs": MAX_RUNS,
                   "max_output_bytes": MAX_OUTPUT_BYTES},
        "model": "Synthetic only; market at next open; explicit zero funding events.",
    }


def _strategy_from_verified_snapshot(snapshot):
    """Build the fixed strategy from already-verified source bytes."""
    example_name = "examples/closed_bar_demo.py"
    strategy_name = "catos/research_strategy.py"
    if set(snapshot) != set(STRATEGY_FILES):
        raise ValueError("artifact_source_snapshot_mismatch")

    example_module = ModuleType("examples.closed_bar_demo")
    example_module.__file__ = str(ROOT / example_name)
    exec(compile(snapshot[example_name], example_module.__file__, "exec"), example_module.__dict__)

    original_import = builtins.__import__
    def snapshot_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "examples.closed_bar_demo":
            return example_module
        return original_import(name, globals, locals, fromlist, level)

    strategy_module = ModuleType("catos.research_strategy")
    strategy_module.__file__ = str(ROOT / strategy_name)
    safe_builtins = dict(vars(builtins))
    safe_builtins["__import__"] = snapshot_import
    strategy_module.__dict__["__builtins__"] = safe_builtins
    exec(compile(snapshot[strategy_name], strategy_module.__file__, "exec"), strategy_module.__dict__)
    RegisteredSMA = getattr(strategy_module, "RegisteredSMA", None)
    if not isinstance(RegisteredSMA, type):
        raise ValueError("artifact_entry_unavailable")
    return RegisteredSMA


def load_registered_strategy(expected_source):
    """Execute only a verified immutable snapshot of the approved strategy source."""
    if provenance() != expected_source:
        raise ValueError("source_changed_restart_required")
    artifact = load_strategy_manifest()
    snapshot, source_hash = _verified_strategy_source_snapshot(artifact["source_files"])
    if source_hash != artifact["sha256"] or source_hash != APPROVED_STRATEGY_SHA256:
        raise ValueError("artifact_hash_mismatch")
    RegisteredSMA = _strategy_from_verified_snapshot(snapshot)
    if provenance() != expected_source:
        raise ValueError("source_changed_during_strategy_load")
    return RegisteredSMA


def execute_request(request, expected_source):
    snapshot, config, period, quantity = validate_request(request)
    # The worker, not MCP/web, executes the fixed strategy. Source bytes are
    # snapshotted and hash-verified before execution so validation and code
    # execution cannot observe different strategy file contents.
    RegisteredSMA = load_registered_strategy(expected_source)
    bars = load_candles_csv(DATA_PATH, config=config)
    if len(bars) > MAX_BARS:
        raise ValueError("dataset_bar_limit")
    result = research.backtest(
        strategy=lambda: RegisteredSMA(period, quantity), candles=bars,
        config=config, warmup_bars=snapshot["warmup_bars"],
    )
    with localcontext(research._CONTEXT):
        peak = config.initial_balance
        drawdown = []
        for point in result.equity_curve:
            peak = max(peak, point.equity)
            drawdown.append({"time_ms": point.time_ms,
                             "drawdown_pct": (peak - point.equity) / peak * Decimal("100")})
    payload = {
        "request": snapshot, "provenance": expected_source,
        "result": asdict(result), "drawdown_curve": drawdown,
        "data_notice": "合成資料；不代表歷史市場績效。資金費事件明示為空。",
        "trade_count_unit": "simulated fills, not closed round trips",
    }
    report = render_report(result)
    if provenance() != expected_source:
        raise ValueError("source_changed_during_run")
    return json.loads(json_text(payload)), report
