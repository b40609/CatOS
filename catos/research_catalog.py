"""Fixed trusted registry and strict Decimal-string research contract."""

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, localcontext
import builtins
import hashlib
import json
from pathlib import Path
import re
from types import ModuleType

from catos import research, research_costs, research_datasets, research_overfit, research_trades
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
DONCHIAN_ID = "donchian-breakout"
DONCHIAN_VERSION = "donchian-parameters-v1"
DONCHIAN_ENTRY = "catos.research_donchian:RegisteredDonchian"
DONCHIAN_SHA256 = "1596e3ace639379086f6fd5ff2ba73948697c2b34884366c3b32b15ba9ba6817"
DONCHIAN_FILES = ("catos/research_donchian.py",)
# Research only: the worker registry (strategy_registry) reads catos/research_artifacts
# alone, so a local-sim Bot can never resolve this strategy.
DONCHIAN_MANIFEST = (ROOT / "catos" / "research_only_artifacts"
                     / "donchian-breakout-donchian-parameters-v1.json")
DONCHIAN_PROVENANCE = {
    "origin": "catos-research-donchian",
    "approval_basis": "user-selected-inspected-local-artifact",
    "scope": "research-only",
}
# Channels up to ten 15m days (96 bars a day).
DONCHIAN_MAX_BARS = 960
# Package E (2026-11-06): three daily strategies preregistered before any real-data run.
DAILY_FILES = ("catos/research_daily.py",)
DAILY_SHA256 = "8f59036ce64615f3b2ebab0ecedf56e4808fa073f07f2153cc90ed970805dc85"
DAILY_PROVENANCE = {"origin": "catos-research-daily-preregistered", "approval_basis": "user-approved-preregistered-literature-rules", "scope": "research-only"}
DAILY_MANIFESTS = ROOT / "catos" / "research_only_artifacts"
# 366 complete days for the longest look-back plus the partial first day.
DAILY_WARMUP_DAYS = 367
DAILY_WARMUP_LIMIT = 60_000
DAY_MS = 86_400_000
# Package F (2026-11-07): intraday DCM rules from the user's calibration, preregistered.
INTRADAY_FILES = ("catos/research_intraday.py",)
INTRADAY_SHA256 = "f9616a00c9e91bd0d575d95415c9466cca6bc992fd4442f1be0cf233907d9b43"
INTRADAY_PROVENANCE = {"origin": "catos-research-intraday-preregistered", "approval_basis": "user-calibrated-preregistered-rules", "scope": "research-only"}
INTRADAY_WARMUP_DAYS = 3


@dataclass(frozen=True)
class ResearchStrategy:
    """One fixed, inspected research strategy: pinned identity, sources and request bounds."""
    strategy_id: str
    version: str
    entry: str
    sha256: str
    files: tuple
    manifest: Path
    artifact_provenance: dict
    name: str
    parameters: tuple  # (name, low, high) integers, in constructor order before quantity
    lookback: str  # the parameter warmup_bars must cover
    warmup_limit: int  # warmup_bars must stay below this
    # Daily strategies need whole days of warm-up whatever the bar size.
    min_warmup_days: int = 0
    # "fixed": quantity is the traded contracts; "vol_target": quantity caps the
    # contracts sized from equity, and the strategy receives the contract spec.
    sizing: str = "fixed"
    preset: dict | None = None  # frontend defaults for preregistered strategies


STRATEGIES = {spec.strategy_id: spec for spec in (
    ResearchStrategy(STRATEGY_ID, STRATEGY_VERSION, STRATEGY_ENTRY, APPROVED_STRATEGY_SHA256,
                     STRATEGY_FILES, STRATEGY_MANIFEST, ARTIFACT_PROVENANCE,
                     "SMA 趨勢（Long / Flat）", (("period", 2, 32),), "period", 64),
    ResearchStrategy(DONCHIAN_ID, DONCHIAN_VERSION, DONCHIAN_ENTRY, DONCHIAN_SHA256,
                     DONCHIAN_FILES, DONCHIAN_MANIFEST, DONCHIAN_PROVENANCE,
                     "Donchian 通道突破（Long / Short）",
                     (("entry_bars", 2, DONCHIAN_MAX_BARS), ("exit_bars", 1, DONCHIAN_MAX_BARS - 1)),
                     "entry_bars", DONCHIAN_MAX_BARS + 1),
    *(ResearchStrategy(artifact_id, version, f"catos.research_daily:{entry}", DAILY_SHA256, DAILY_FILES,
                       DAILY_MANIFESTS / f"{artifact_id}-{version}.json", DAILY_PROVENANCE, name,
                       ((param, 0, 1),), param, DAILY_WARMUP_LIMIT, DAILY_WARMUP_DAYS, sizing,
                       {"parameters": {param: default}, "quantity": quantity, "warmup_days": DAILY_WARMUP_DAYS})
      for artifact_id, version, entry, name, param, default, sizing, quantity in (
          ("donchian-ensemble", "donchian-ensemble-preregistered-v1", "DonchianEnsemble",
           "Donchian 多週期集成（Long / Flat，日線）", "vol_scaling", 1, "vol_target", "1000"),
          ("tsmom-multi", "tsmom-multi-preregistered-v1", "TimeSeriesMomentum",
           "時間序列動能 1／3／12 月（Long / Short，日線）", "vol_scaling", 1, "vol_target", "1000"),
          ("dcm-daily", "dcm-daily-preregistered-v1", "DCMDaily",
           "DCM 日線版（Long / Short）", "score_filter", 0, "fixed", "10"),
      )),
    *(ResearchStrategy(artifact_id, version, f"catos.research_intraday:{entry}", INTRADAY_SHA256,
                       INTRADAY_FILES, DAILY_MANIFESTS / f"{artifact_id}-{version}.json", INTRADAY_PROVENANCE,
                       name, ((param, low, high),), param, DAILY_WARMUP_LIMIT, INTRADAY_WARMUP_DAYS, "fixed",
                       {"parameters": {param: default}, "quantity": "10", "warmup_days": INTRADAY_WARMUP_DAYS})
      for artifact_id, version, entry, name, param, low, high, default in (
          ("dcm-fade", "dcm-fade-preregistered-v1", "DCMFade",
           "DCM 假突破反轉（Long / Short，短週期）", "exit_mode", 0, 1, 0),
          ("dcm-pullback", "dcm-pullback-preregistered-v1", "DCMPullback",
           "DCM 突破後回踩（Long，短週期）", "window_days", 1, 5, 3),
      )),
)}


def strategy_spec(strategy_id):
    spec = STRATEGIES.get(strategy_id) if type(strategy_id) is str else None
    if spec is None:
        raise ValueError("unknown_strategy")
    return spec
SHA256 = re.compile(r"[0-9a-f]{64}")
ENGINE_FILES = (
    "catos/research.py", "catos/data_io.py", "catos/reporting.py",
    "catos/research_catalog.py", "catos/research_worker.py",
    "catos/research_optimization.py", "catos/optimization.py",
    "catos/research_validation.py", "catos/research_regimes.py",
    "catos/research_validation_job.py", "catos/research_datasets.py",
    "catos/research_costs.py", "catos/research_overfit.py", "catos/research_trades.py",
)
DEFAULT_REQUEST = {
    "strategy_id": STRATEGY_ID, "dataset_id": DATASET_ID,
    "parameters": {"period": 2, "quantity": "2"},
    "initial_balance": "1000", "fee_rate": "0.0005",
    "slippage_bps": "2", "warmup_bars": 2,
}
# The Decimal core runs ~45k bars/s locally; the binding limit is output size:
# MAX_OUTPUT_BYTES caps the worker's stdout, which carries the payload AND the
# HTML report. Equity/drawdown curves above MAX_CURVE_POINTS are sampled in
# both, and the report lists at most REPORT_MAX_FILL_ROWS fills, so the report
# stays roughly fixed in size; the payload still lists every fill (~160 bytes
# each), so a 6-month 5m run tops out around 6,000-7,000 fills.
# 2026-11-07: raised from 20,000 so six months of 5m bars (~52,700) fit one run.
MAX_BARS = 60_000
MAX_CURVE_POINTS = 2_000
REPORT_MAX_FILL_ROWS = 400
MAX_RUNS = 200
TIMEOUT_SECONDS = 30
MAX_OUTPUT_BYTES = 2_000_000
# An optimization replays every bar once per trial plus one re-run of the best,
# so it is bounded by construction at (MAX_TRIALS + 1) x MAX_BARS = 1.26M bar
# evaluations; no separate preflight. Measured 2026-11-08 on the i7-14700 host:
# 20 trials on 6 months of 5m (52,704 bars) take 14.1-14.5 s through the worker,
# a single run 0.42-0.55 s in process, so the worst case is about 17 s of the
# 30 s TIMEOUT_SECONDS. A machine more than ~1.7x slower can time out on the
# longest datasets; lower n_trials there.
MAX_TRIALS = 20
MAX_VALIDATION_CANDIDATES = 20
MAX_VALIDATION_RUNS = 100
MAX_VALIDATION_WINDOWS = 8
# Walk-forward cost is the bars every training trial and OOS run replays
# (~19-54k per second measured locally on the fetched 15m dataset, depending on
# load), so a preflight bound keeps a submission well inside TIMEOUT_SECONDS.
MAX_VALIDATION_BAR_EVALUATIONS = 250_000
# The regime classifier sums its lookback window at every bar: (bars - L) x L
# steps, ~2.4M per second locally. Capping L bounds it to ~10M steps even at
# MAX_BARS (1.8 s for L = 512 on the fetched 8,640-bar dataset).
MAX_VALIDATION_LOOKBACK_BARS = 512
# Total OOS equity points kept in a validation payload, shared by its windows.
MAX_VALIDATION_CURVE_POINTS = 1_000
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


def _verified_strategy_source_snapshot(source_files, spec=STRATEGIES[STRATEGY_ID]):
    if type(source_files) is not list or source_files != list(spec.files):
        raise ValueError("artifact_source_files_mismatch")
    root = ROOT.resolve()
    snapshot = {}
    entries = []
    for name in source_files:
        if type(name) is not str or name not in spec.files:
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


def _verified_strategy_source_hash(source_files, spec=STRATEGIES[STRATEGY_ID]):
    return _verified_strategy_source_snapshot(source_files, spec)[1]


def validate_strategy_manifest(value, spec=STRATEGIES[STRATEGY_ID]):
    if type(value) is not dict or set(value) != ARTIFACT_FIELDS:
        raise ValueError("artifact_manifest_exact_fields_required")
    if value["schema"] != ARTIFACT_SCHEMA or type(value["schema"]) is not str:
        raise ValueError("artifact_manifest_schema_mismatch")
    if type(value["schema_version"]) is not int or value["schema_version"] != ARTIFACT_SCHEMA_VERSION:
        raise ValueError("artifact_manifest_schema_version_mismatch")
    if type(value["artifact_id"]) is not str or value["artifact_id"] != spec.strategy_id:
        raise ValueError("unknown_artifact")
    if type(value["version"]) is not str or value["version"] != spec.version:
        raise ValueError("artifact_version_mismatch")
    if type(value["sha256"]) is not str or SHA256.fullmatch(value["sha256"]) is None:
        raise ValueError("artifact_sha256_invalid")
    if value["sha256"] != spec.sha256:
        raise ValueError("artifact_identity_mismatch")
    if type(value["entry"]) is not str or value["entry"] != spec.entry:
        raise ValueError("artifact_entry_mismatch")
    if value["approval_state"] != "approved" or type(value["approval_state"]) is not str:
        raise ValueError("artifact_not_approved")
    if type(value["provenance"]) is not dict or value["provenance"] != spec.artifact_provenance:
        raise ValueError("artifact_provenance_mismatch")
    source_hash = _verified_strategy_source_hash(value["source_files"], spec)
    if value["sha256"] != source_hash:
        raise ValueError("artifact_hash_mismatch")
    return json.loads(json_text(value))


def load_strategy_manifest(spec=STRATEGIES[STRATEGY_ID]):
    manifest = spec.manifest
    if manifest.is_symlink():
        raise ValueError("artifact_manifest_symlink_rejected")
    try:
        resolved = manifest.resolve(strict=True)
        resolved.relative_to(ROOT.resolve())
        raw = manifest.read_text(encoding="utf-8")
    except (OSError, ValueError):
        raise ValueError("artifact_manifest_unavailable") from None
    if len(raw.encode("utf-8")) > 8192:
        raise ValueError("artifact_manifest_too_large")
    try:
        value = _strict_json(raw)
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError(str(error)) from None
    return validate_strategy_manifest(value, spec)


SYNTHETIC_CONTRACT = research.ContractSpec(
    "BTC-USDT-SWAP", Decimal("0.01"), Decimal("0.01"), Decimal("1"), Decimal("1"))


def _synthetic_dataset():
    return research_datasets.Dataset(
        dataset_id=DATASET_ID, name="合成 BTC 15m · 96 根已收盤 K 線", source="synthetic_closed_bars",
        candles_path=DATA_PATH, contract=SYNTHETIC_CONTRACT, timeframe_ms=900_000, bars=96,
        start_ms=None, end_ms=None,
        files=((DATA_PATH.relative_to(ROOT).as_posix(), file_hash(DATA_PATH)),),
        funding_path=None, notice="合成資料；不代表歷史市場績效。資金費事件明示為空。未套用保證金與強平模型。",
        margin_reason="synthetic_fixture",
    )


def datasets():
    """The built-in synthetic fixture first, then every valid fetched dataset."""
    return [_synthetic_dataset(), *research_datasets.list_datasets()[0]]


def resolve_dataset(dataset_id):
    if dataset_id == DATASET_ID:
        return _synthetic_dataset()
    if type(dataset_id) is not str or not research_datasets.DATASET_ID.fullmatch(dataset_id):
        raise ValueError("unknown_dataset")
    for dataset in research_datasets.list_datasets()[0]:
        if dataset.dataset_id == dataset_id:
            return dataset
    raise ValueError("unknown_dataset")


def provenance(dataset_id=DATASET_ID, strategy_id=STRATEGY_ID):
    spec = strategy_spec(strategy_id)
    artifact = load_strategy_manifest(spec)
    return {
        "strategy": {
            "id": artifact["artifact_id"], "version": artifact["version"],
            "sha256": artifact["sha256"], "source": "approved_fixed_artifact_manifest",
            "source_files": list(artifact["source_files"]), "entry": artifact["entry"],
            "approval_state": artifact["approval_state"],
            "artifact_manifest": {
                "schema": artifact["schema"], "schema_version": artifact["schema_version"],
                "sha256": file_hash(spec.manifest),
                "provenance": dict(artifact["provenance"]),
            },
        },
        "dataset": resolve_dataset(dataset_id).provenance(),
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
    spec = strategy_spec(value["strategy_id"])
    # Every execution path revalidates the fixed local artifact manifest and
    # current allowlisted source hash before accepting a registered strategy.
    load_strategy_manifest(spec)
    dataset = resolve_dataset(value["dataset_id"])
    params = value["parameters"]
    names = [name for name, _, _ in spec.parameters]
    if type(params) is not dict or set(params) != {*names, "quantity"}:
        raise ValueError(f"parameters: {', '.join(names)} and quantity required")
    for name, low, high in spec.parameters:
        if type(params[name]) is not int or not low <= params[name] <= high:
            raise ValueError(f"{name}: integer in [{low}, {high}] required")
    if spec.strategy_id == DONCHIAN_ID and params["exit_bars"] >= params["entry_bars"]:
        raise ValueError("exit_bars: must be below entry_bars")
    warmup = value["warmup_bars"]
    if type(warmup) is not int or not params[spec.lookback] <= warmup < spec.warmup_limit:
        raise ValueError(f"warmup_bars: integer >= {spec.lookback} and < {spec.warmup_limit} required")
    if spec.min_warmup_days and warmup * dataset.timeframe_ms < spec.min_warmup_days * DAY_MS:
        bars = -(-spec.min_warmup_days * DAY_MS // dataset.timeframe_ms)
        raise ValueError(f"warmup_bars: at least {bars} bars ({spec.min_warmup_days} days) required")
    # Donchian warm-up can exceed the 96-bar fixture; reject before a task is queued.
    if warmup >= dataset.bars:
        raise ValueError(f"warmup_bars: must leave evaluation bars in the {dataset.bars}-bar dataset")
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
    # Funding events are attached when the dataset's bars are loaded.
    cfg = research.BacktestConfig(dataset.contract, dataset.timeframe_ms, balance, fee, slip, ())
    # A JSON round-trip owns an immutable-by-convention request copy.
    snapshot = json.loads(json_text(value))
    return snapshot, cfg, {name: params[name] for name in names}, quantity


def require_search_names(spec, space):
    names = [name for name, _, _ in spec.parameters]
    if type(space) is not dict or set(space) != set(names):
        ranges = " and ".join(names) + (" ranges are" if len(names) > 1 else " range is")
        raise ValueError(f"search_space: only registered {ranges} supported")
    for name in names:
        if type(space[name]) is not dict or set(space[name]) != {"low", "high", "step"}:
            raise ValueError(f"{name}: low, high and step required")


def check_search_grid(spec, ranges, warmup):
    """Rules every grid point must meet; ``ranges`` maps a parameter to its (low, high)."""
    if spec.strategy_id == DONCHIAN_ID and ranges["exit_bars"][1] >= ranges["entry_bars"][0]:
        raise ValueError("exit_bars: highest searched value must be below lowest entry_bars")
    if warmup < ranges[spec.lookback][1]:
        raise ValueError(f"warmup_bars: must cover highest searched {spec.lookback}")


def validate_optimization_request(value):
    if type(value) is not dict or set(value) != set(DEFAULT_OPTIMIZATION):
        raise ValueError("optimization: exact registered fields required")
    backtest_request, config, _, quantity = validate_request(value["backtest"])
    spec = strategy_spec(backtest_request["strategy_id"])
    space = value["search_space"]
    require_search_names(spec, space)
    for name, low_bound, high_bound in spec.parameters:
        low, high, step = space[name]["low"], space[name]["high"], space[name]["step"]
        if any(type(number) is not int for number in (low, high, step)) or not (
            low_bound <= low <= high <= high_bound and 1 <= step <= high_bound - low_bound
            and (high - low) % step == 0
        ):
            raise ValueError(f"{name}: aligned integer range within [{low_bound}, {high_bound}] required")
    check_search_grid(spec, {name: (item["low"], item["high"]) for name, item in space.items()},
                      backtest_request["warmup_bars"])
    if type(value["n_trials"]) is not int or not 1 <= value["n_trials"] <= MAX_TRIALS:
        raise ValueError(f"n_trials: integer in [1, {MAX_TRIALS}] required")
    if type(value["seed"]) is not int or not 0 <= value["seed"] <= 2 ** 32 - 1:
        raise ValueError("seed: unsigned 32-bit integer required")
    snapshot = json.loads(json_text(value))
    snapshot["backtest"] = backtest_request
    return snapshot, config, quantity


def catalog():
    return {
        "strategies": [{**provenance(strategy_id=spec.strategy_id)["strategy"], "name": spec.name,
                        "parameters": {**{name: {"min": low, "max": high}
                                          for name, low, high in spec.parameters},
                                       "quantity": {"unit": "contracts"}},
                        "warmup": {"covers": spec.lookback, "below": spec.warmup_limit,
                                   "min_days": spec.min_warmup_days},
                        "sizing": spec.sizing, "preset": spec.preset}
                       for spec in STRATEGIES.values()],
        "datasets": [{**dataset.describe(), "contract": asdict(dataset.contract)}
                     for dataset in datasets()],
        "defaults": DEFAULT_REQUEST,
        "optimization": {"defaults": DEFAULT_OPTIMIZATION, "max_trials": MAX_TRIALS,
                         "score_name": "return_pct", "direction": "maximize",
                         "notice": "樣本內搜尋；未執行樣本外檢驗。"},
        "validation": {"example_request": DEFAULT_VALIDATION,
                       "max_candidates": MAX_VALIDATION_CANDIDATES,
                       "max_runs": MAX_VALIDATION_RUNS, "max_windows": MAX_VALIDATION_WINDOWS,
                       "max_bar_evaluations": MAX_VALIDATION_BAR_EVALUATIONS,
                       "max_lookback_bars": MAX_VALIDATION_LOOKBACK_BARS,
                       "max_curve_points": MAX_VALIDATION_CURVE_POINTS,
                       "score_name": "return_pct", "direction": "maximize",
                       "notice": "穩定區選參後做滾動 OOS 與分環境評估；各 OOS 視窗獨立，不是連續投資組合。分類門檻僅供示範，須明示。"},
        "limits": {"concurrent_tasks": 1, "max_bars": MAX_BARS,
                   "timeout_seconds": TIMEOUT_SECONDS, "max_runs": MAX_RUNS,
                   "max_output_bytes": MAX_OUTPUT_BYTES},
        "model": ("Market at next open plus explicit slippage; funding from the dataset "
                  "(synthetic: none); no order book, margin or liquidation model."),
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


def _module_strategy_from_verified_snapshot(snapshot, spec):
    """Build a single-file strategy from already-verified source bytes."""
    (name,) = spec.files
    if set(snapshot) != {name}:
        raise ValueError("artifact_source_snapshot_mismatch")
    module_name, attribute = spec.entry.split(":")
    module = ModuleType(module_name)
    module.__file__ = str(ROOT / name)
    exec(compile(snapshot[name], module.__file__, "exec"), module.__dict__)
    strategy = getattr(module, attribute, None)
    if not isinstance(strategy, type):
        raise ValueError("artifact_entry_unavailable")
    return strategy


def load_registered_strategy(expected_source):
    """Execute only a verified immutable snapshot of the approved strategy source."""
    spec = strategy_spec(expected_source["strategy"]["id"])
    dataset_id = expected_source["dataset"]["id"]
    if provenance(dataset_id, spec.strategy_id) != expected_source:
        raise ValueError("source_changed_restart_required")
    artifact = load_strategy_manifest(spec)
    snapshot, source_hash = _verified_strategy_source_snapshot(artifact["source_files"], spec)
    if source_hash != artifact["sha256"] or source_hash != spec.sha256:
        raise ValueError("artifact_hash_mismatch")
    strategy = (_strategy_from_verified_snapshot(snapshot) if spec.strategy_id == STRATEGY_ID
                else _module_strategy_from_verified_snapshot(snapshot, spec))
    if provenance(dataset_id, spec.strategy_id) != expected_source:
        raise ValueError("source_changed_during_strategy_load")
    return strategy


def registered_factory(expected_source, strategy_id, quantity, contract=None):
    """The verified strategy bound to a run's quantity; the request must name the same strategy.

    Volatility-targeted strategies size from equity, so they also get the contract spec.
    """
    if expected_source["strategy"]["id"] != strategy_id:
        raise ValueError("strategy_source_mismatch")
    spec = strategy_spec(strategy_id)
    if spec.sizing == "vol_target" and contract is None:
        raise ValueError("contract_required_for_vol_target")
    strategy = load_registered_strategy(expected_source)
    names = [name for name, _, _ in spec.parameters]
    if spec.sizing == "vol_target":
        return lambda params: strategy(*(params[name] for name in names), quantity, contract)
    return lambda params: strategy(*(params[name] for name in names), quantity)


def load_dataset_bars(dataset_id, config):
    """Hash-checked bars and funding for a registered dataset, within MAX_BARS."""
    bars, config = resolve_dataset(dataset_id).load(config)
    if len(bars) > MAX_BARS:
        raise ValueError("dataset_bar_limit")
    return bars, config


def buy_hold_quantity(strategy_id, quantity, result, bars):
    """Fixed-size strategies compare with the same contracts; equity-sized ones with 1x initial notional."""
    if strategy_id is None or strategy_spec(strategy_id).sizing != "vol_target":
        return quantity
    contract = result.config.contract
    first = next(bar for bar in bars if bar.open_time_ms >= result.evaluation_start_ms)
    with localcontext(research._CONTEXT):
        raw = result.config.initial_balance / (first.open * contract.base_per_contract)
        return (raw / contract.lot_size).to_integral_value(rounding="ROUND_DOWN") * contract.lot_size


def costs_for(result, bars, quantity, dataset, strategy_id=None):
    """Cost attribution and buy-and-hold baseline; a funding scenario only for partial funding."""
    scenario_from = None if dataset.funding_path is None or dataset.funding_complete else dataset.funding_from_ms
    interval = dataset.funding_interval_ms or research_costs.ASSUMED_FUNDING_INTERVAL_MS
    sized = strategy_id is not None and strategy_spec(strategy_id).sizing == "vol_target"
    return research_costs.cost_breakdown(result, bars, buy_hold_quantity(strategy_id, quantity, result, bars),
                                         scenario_from, interval_ms=interval, equity_sized=sized)


def costs_html(rows, title="成本拆解"):
    """A small read-only table for the HTML reports; rows are (label, value) pairs."""
    from html import escape
    body = "".join(f"<tr><th>{escape(label)}</th><td>{escape('—' if value is None else str(value))}</td></tr>"
                   for label, value in rows)
    return f"<h2>{escape(title)}</h2><table>{body}</table>"


def cost_rows(costs):
    """Report rows for one breakdown (dataclass or asdict form)."""
    value = costs if isinstance(costs, dict) else asdict(costs)
    rows = [(label, value[key]) for key, label in research_costs.REPORT_ROWS]
    hold = value["buy_hold"]
    rows.append((f"買進持有基準（同 {hold['quantity']} 張、成本前、未計資金費）", hold["pnl"]))
    rows.append(("標的漲跌 %", hold["underlying_return_pct"]))
    scenario = value["funding_scenario"]
    if scenario is not None:
        rows.append((f"假設資金費（{scenario['events']} 次，未涵蓋期間）", scenario["assumed_paid"]))
        rows.append(("淨損益（含假設資金費）", scenario["net_pnl_with_assumption"]))
        rows.append(("假設說明", scenario["notice"]))
    return rows


def drawdown_pcts(equity_curve, initial_balance):
    """Decimal drawdown percent from the running peak, starting at the initial balance."""
    with localcontext(research._CONTEXT):
        peak = initial_balance
        drawdowns = []
        for point in equity_curve:
            peak = max(peak, point.equity)
            drawdowns.append((peak - point.equity) / peak * Decimal("100"))
    return drawdowns


def sample_curve_indices(drawdowns, limit=MAX_CURVE_POINTS):
    """Indices kept for the payload chart: per bucket the deepest drawdown, plus the first and last points.

    Performance figures are computed on every bar before sampling; only the
    returned chart points are thinned so large datasets stay under the output cap.
    The first point (initial equity) is kept so the chart starts where the run
    starts (acceptance N6, 2026-11-08); at most `limit` indices are returned.
    """
    if limit < 3:
        raise ValueError("curve sampling limit must be at least 3 (first, last and one bucket)")
    total = len(drawdowns)
    if total <= limit:
        return list(range(total))
    size = -(-total // (limit - 2))
    keep = [max(range(start, min(start + size, total)), key=lambda i: (drawdowns[i], -i))
            for start in range(0, total, size)]
    if keep[0] != 0:
        keep.insert(0, 0)
    if keep[-1] != total - 1:
        keep.append(total - 1)
    return keep


def _wiped_out(result):
    """First time equity reached <= 0 (or the liquidation, with the margin model), or None."""
    index = research_overfit.first_non_positive(result.equity_curve)
    if index is None:
        return None
    notice = research_overfit.WIPED_OUT_NOTICE if result.liquidation is None else research_overfit.LIQUIDATION_NOTICE
    return {"time_ms": result.equity_curve[index].time_ms,
            "min_equity": min(point.equity for point in result.equity_curve),
            "liquidated": result.liquidation is not None, "notice": notice}


def slim_margin(value):
    """Replace each serialized MarginModel's tier table with its size; the sha256 still names it.

    The tiers come from a hash-checked snapshot listed in the provenance, so the
    payload keeps the label instead of ~8 KB of tiers in every result.
    """
    if isinstance(value, dict):
        margin = value.get("margin")
        if isinstance(margin, dict) and isinstance(margin.get("tiers"), (list, tuple)):
            value["margin"] = {**margin, "tiers": len(margin["tiers"])}
        for item in value.values():
            slim_margin(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            slim_margin(item)
    return value


def margin_rows(summary, result=None):
    """Report rows for the margin model of one run (summary = Dataset.margin_summary())."""
    if not summary["enabled"]:
        return [("保證金模型", f"未啟用：{summary['reason_text']}")]
    rows = [("保證金模型", "啟用：單合約全倉、OKX 部位檔位、K 線最不利價檢查"),
            ("檔位快照", summary["tiers_path"]), ("檔位 sha256", summary["tiers_sha256"])]
    if result is not None:
        liq = result.liquidation
        rows.append(("強平", "無" if liq is None else
                     f"{liq.time_ms}（UTC 毫秒）以 {liq.fill_price} 平 {liq.position} 張，"
                     f"強平手續費 {liq.fee_charged}、清算費 {liq.clearance_charged}、保險基金補足 {liq.deficit_covered}"))
        rows.append(("初始保證金不足拒單", result.margin_rejection_count))
    return rows


def execute_request(request, expected_source):
    snapshot, config, params, quantity = validate_request(request)
    # The worker, not MCP/web, executes the fixed strategy. Source bytes are
    # snapshotted and hash-verified before execution so validation and code
    # execution cannot observe different strategy file contents.
    build = registered_factory(expected_source, snapshot["strategy_id"], quantity, config.contract)
    dataset = resolve_dataset(snapshot["dataset_id"])
    bars, config = load_dataset_bars(dataset.dataset_id, config)
    result = research.backtest(
        strategy=lambda: build(params), candles=bars,
        config=config, warmup_bars=snapshot["warmup_bars"],
    )
    drawdown = [{"time_ms": point.time_ms, "drawdown_pct": value} for point, value
                in zip(result.equity_curve, drawdown_pcts(result.equity_curve, config.initial_balance))]
    result_payload = slim_margin(asdict(result))
    keep = sample_curve_indices([point["drawdown_pct"] for point in drawdown])
    costs = costs_for(result, bars, quantity, dataset, snapshot["strategy_id"])
    payload = {
        "request": snapshot, "provenance": expected_source,
        "result": result_payload, "drawdown_curve": drawdown,
        "costs": asdict(costs), "funding_coverage": dataset.funding_summary(),
        "margin_model": dataset.margin_summary(),
        "trade_stats": research_trades.trade_stats(result),
        "equity_wiped_out": _wiped_out(result),
        "data_notice": dataset.notice,
        "trade_count_unit": "simulated fills, not closed round trips",
    }
    if len(keep) < len(drawdown):
        result_payload["equity_curve"] = [result_payload["equity_curve"][i] for i in keep]
        payload["drawdown_curve"] = [drawdown[i] for i in keep]
        payload["curve_sampling"] = {"total_points": len(drawdown), "returned_points": len(keep),
                                     "method": "bucket_deepest_drawdown_keep_first_last"}
    report = render_report(result, curve_indices=keep, max_trade_rows=REPORT_MAX_FILL_ROWS)
    report = report.replace("</body>", costs_html(cost_rows(costs)) + "\n"
                            + costs_html(margin_rows(payload["margin_model"], result), "保證金與強平") + "\n</body>", 1)
    if provenance(dataset.dataset_id, snapshot["strategy_id"]) != expected_source:
        raise ValueError("source_changed_during_run")
    return json.loads(json_text(payload)), report
