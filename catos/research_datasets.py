"""Fetched OKX research datasets, used only through a hash-checked manifest.

Each dataset lives in ``data/okx/<instId>/<bar>/<dataset_id>/`` with fixed file
names. ``write_dataset`` is the only producer: it refuses gaps, irregular
funding, funding that stops before the end, and overwrites. Funding may start
after the first bar (OKX keeps only about three months of funding history); the
manifest then records ``complete: false`` and every run states that funding before
the first event is not counted. Resolving a dataset re-hashes every file the
manifest names; a hash mismatch, a gap, a funding mismatch, an unknown field or
an unsupported instrument rejects it (fail-closed), the same rule the strategy
registry applies to strategy sources. Nothing here touches the network:
``tools/fetch_okx_candles.py`` fetches, then calls ``write_dataset``.

Position tiers (2026-11-12, docs/research-margin-model.md) are a separate
snapshot per instrument in ``data/okx/<instId>/position-tiers/``, written only by
``write_position_tiers``. Every dataset of that instrument uses the newest one
for the backtest margin model and lists it, with its sha256, among its files; an
invalid snapshot rejects the dataset, and no snapshot leaves the model off with
that reason stated in every run.
"""

import csv
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
from pathlib import Path
import re

from catos import research
from catos.data_io import REQUIRED_COLUMNS, load_candles_csv

ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = ROOT / "data" / "okx"
SCHEMA = "catos.research.dataset"
SCHEMA_VERSION = 1
SOURCE = "okx_public_history"
MANIFEST = "manifest.json"
CANDLES = "candles.csv"
FUNDING = "funding.csv"
INSTRUMENT = "instrument.json"
FILES = (CANDLES, FUNDING, INSTRUMENT)
FUNDING_COLUMNS = ("funding_time_ms", "realized_rate", "funding_rate")
RATE_FIELD = "realizedRate"
MARK_PRICE_SOURCE = "candle_open_at_funding_time"
ENDPOINTS = (
    "/api/v5/market/history-candles",
    "/api/v5/public/funding-rate-history",
    "/api/v5/public/instruments",
)
# Position tiers for the backtest margin model (2026-11-11 authorization: BTC-USDT-SWAP only).
# Kept out of ENDPOINTS: candle dataset manifests list exactly those three endpoints.
TIERS_ENDPOINT = "/api/v5/public/position-tiers"
TIERS_INST_IDS = ("BTC-USDT-SWAP",)
BAR_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "1H": 3_600_000, "4H": 14_400_000}
MANIFEST_FIELDS = {
    "schema", "schema_version", "dataset_id", "source", "inst_id", "bar", "timeframe_ms",
    "start_ms", "end_ms", "bars", "fetched_at_ms", "endpoints", "requests", "files",
    "contract", "funding", "gaps",
}
CONTRACT_FIELDS = {"inst_id", "base_per_contract", "tick_size", "lot_size", "min_size"}
FUNDING_FIELDS = {"rate_field", "mark_price_source", "events", "interval_ms", "complete"}
DATASET_ID = re.compile(r"okx-[a-z0-9]+(?:-[a-z0-9]+)*-\d{8}-\d{8}")
SHA256 = re.compile(r"[0-9a-f]{64}")
INST_ID = re.compile(r"[A-Z0-9]+-USDT-SWAP")
NOTICE = ("OKX 公開歷史 K 線（已收盤）與實際資金費率；資金費以結算當下 K 線開盤價近似 mark price。"
          "本根收盤決策、下一根開盤加滑價成交，沒有訂單簿，不代表實盤可得績效。")
MARGIN_ON_NOTICE = ("保證金與強平：單合約全倉、OKX 部位檔位（{fetched} UTC 快照），以 K 線最不利價（多單最低價、"
                    "空單最高價）檢查，成交價代替標記價格，會高估強平。")
MARGIN_OFF_NOTICE = "本機沒有這個合約的部位檔位快照，未啟用保證金與強平模型，有槓桿時結果偏樂觀。"
TIERS_SCHEMA = "catos.research.position_tiers"
TIERS_SOURCE = "okx_public_position_tiers"
TIERS_DIR = "position-tiers"
TIERS_FIELDS = {"schema", "schema_version", "source", "endpoint", "params", "inst_id", "td_mode",
                "fetched_at_ms", "requests", "records"}
MARGIN_REASONS = {
    "no_position_tiers": "本機沒有這個合約的部位檔位快照",
    "synthetic_fixture": "內建合成資料集的合約規格是測試用的，不套用真實檔位",
}
PARTIAL_FUNDING_NOTICE = "資金費只涵蓋 {first} UTC 之後；之前的期間未計資金費（OKX 只保留約 3 個月的資金費歷史）。"


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel_path(path):
    """Repo-relative POSIX path for provenance; absolute only for data outside the repo (tests)."""
    path = Path(path)
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def utc_day(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y%m%d")


def dataset_id_for(inst_id, bar, start_ms, end_ms):
    """Stable id: instrument, bar and the UTC days of [start, end)."""
    return f"okx-{inst_id.lower()}-{bar.lower()}-{utc_day(start_ms)}-{utc_day(end_ms)}"


def _positive_decimal(value, name):
    if type(value) is not str:
        raise ValueError(f"{name}: Decimal string required")
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError(f"{name}: invalid Decimal string") from None
    if not number.is_finite() or number <= 0:
        raise ValueError(f"{name}: positive Decimal required")
    return number


def contract_from_instrument(record, inst_id):
    """Linear USDT-settled SWAP only; base_per_contract = ctVal x ctMult in the base asset."""
    if type(record) is not dict or record.get("instId") != inst_id:
        raise ValueError("instrument_mismatch")
    base = inst_id.split("-")[0]
    if (record.get("instType"), record.get("ctType"), record.get("settleCcy"), record.get("ctValCcy")) != (
        "SWAP", "linear", "USDT", base,
    ):
        raise ValueError("instrument_not_linear_usdt_swap")
    per_contract = _positive_decimal(record.get("ctVal"), "ctVal") * _positive_decimal(record.get("ctMult"), "ctMult")
    return {
        "inst_id": inst_id,
        "base_per_contract": str(per_contract),
        "tick_size": str(_positive_decimal(record.get("tickSz"), "tickSz")),
        "lot_size": str(_positive_decimal(record.get("lotSz"), "lotSz")),
        "min_size": str(_positive_decimal(record.get("minSz"), "minSz")),
    }


def tiers_params(inst_id):
    """Request parameters of the tier snapshot: cross margin, the instrument family <BASE>-USDT."""
    return {"instType": "SWAP", "tdMode": "cross", "instFamily": inst_id.rsplit("-", 1)[0]}


def _record_decimal(record, key):
    value = record.get(key)
    if type(value) is not str:
        raise ValueError(f"position_tiers_{key}_invalid")
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError(f"position_tiers_{key}_invalid") from None
    if not number.is_finite() or number < 0:
        raise ValueError(f"position_tiers_{key}_invalid")
    return number


def parse_tiers(records, inst_id):
    """research.MarginTier rows from raw OKX records; fail on anything unexpected.

    Tiers must be numbered 1..n in order, start at 0 contracts and be contiguous
    (each minSz above the previous maxSz), with 0 < mmr < imr <= 1.
    """
    family = tiers_params(inst_id)["instFamily"]
    if type(records) is not list or not records:
        raise ValueError("position_tiers_empty")
    tiers, previous = [], None
    for number, record in enumerate(records, start=1):
        if type(record) is not dict or record.get("instFamily") != family or record.get("tier") != str(number):
            raise ValueError("position_tiers_record_mismatch")
        low, high = _record_decimal(record, "minSz"), _record_decimal(record, "maxSz")
        mmr, imr = _record_decimal(record, "mmr"), _record_decimal(record, "imr")
        if (low != 0 if previous is None else low <= previous) or high <= low:
            raise ValueError("position_tiers_not_contiguous")
        if not 0 < mmr < imr <= 1:
            raise ValueError("position_tiers_rates_invalid")
        tiers.append(research.MarginTier(number, high, mmr, imr))
        previous = high
    return tuple(tiers)


def _tiers_name(inst_id, fetched_at_ms):
    stamp = datetime.fromtimestamp(fetched_at_ms / 1000, tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"okx-{inst_id.lower()}-position-tiers-cross-{stamp}.json"


def write_position_tiers(root=None, *, inst_id, records, fetched_at_ms, requests):
    """Write one tier snapshot (the raw OKX records) atomically and return its path."""
    if inst_id not in TIERS_INST_IDS:
        raise ValueError(f"position_tiers_not_authorized: {inst_id}")
    parse_tiers(records, inst_id)
    root = Path(root) if root is not None else DATA_ROOT
    parent = root / inst_id / TIERS_DIR
    target = parent / _tiers_name(inst_id, fetched_at_ms)
    if target.exists():
        raise FileExistsError(f"position_tiers_exist: {target}")
    content = _json_bytes({
        "schema": TIERS_SCHEMA, "schema_version": SCHEMA_VERSION, "source": TIERS_SOURCE,
        "endpoint": TIERS_ENDPOINT, "params": tiers_params(inst_id), "inst_id": inst_id, "td_mode": "cross",
        "fetched_at_ms": fetched_at_ms, "requests": requests, "records": records,
    })
    parent.mkdir(parents=True, exist_ok=True)
    staging = parent / f".{target.name}.staging-{os.getpid()}"
    staging.write_bytes(content)
    os.replace(staging, target)
    return target


@dataclass(frozen=True)
class PositionTiers:
    inst_id: str
    path: Path
    sha256: str
    fetched_at_ms: int
    tiers: tuple

    def model(self):
        return research.MarginModel(self.tiers, self.sha256)


def load_position_tiers(path, root=None):
    """Verify one tier snapshot; raise ValueError on any doubt."""
    root = Path(root) if root is not None else DATA_ROOT
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("position_tiers_path_invalid")
    data = path.read_bytes()
    value = _strict_json(path, data)
    if type(value) is not dict or set(value) != TIERS_FIELDS:
        raise ValueError("position_tiers_fields_mismatch")
    inst_id, fetched = value["inst_id"], value["fetched_at_ms"]
    if ((value["schema"], value["schema_version"], value["source"], value["endpoint"], value["td_mode"])
            != (TIERS_SCHEMA, SCHEMA_VERSION, TIERS_SOURCE, TIERS_ENDPOINT, "cross")):
        raise ValueError("position_tiers_schema_mismatch")
    if inst_id not in TIERS_INST_IDS or value["params"] != tiers_params(inst_id):
        raise ValueError("position_tiers_instrument_invalid")
    if type(fetched) is not int or type(value["requests"]) is not int:
        raise ValueError("position_tiers_integer_required")
    if (path.parent.name, path.parent.parent.name) != (TIERS_DIR, inst_id) or path.name != _tiers_name(inst_id, fetched):
        raise ValueError("position_tiers_name_mismatch")
    tiers = parse_tiers(value["records"], inst_id)
    return PositionTiers(inst_id, path, hashlib.sha256(data).hexdigest(), fetched, tiers)


def latest_position_tiers(inst_id, root=None):
    """The newest valid snapshot for inst_id, or None; any invalid snapshot is an error (fail-closed)."""
    root = Path(root) if root is not None else DATA_ROOT
    directory = root / inst_id / TIERS_DIR
    if not directory.is_dir():
        return None
    snapshots = [load_position_tiers(path, root) for path in sorted(directory.glob("*.json"))]
    return max(snapshots, key=lambda item: item.fetched_at_ms, default=None)


def find_gaps(times, start_ms, end_ms, timeframe_ms):
    """Expected bar open times in [start, end) that are missing from times."""
    present = set(times)
    return [ms for ms in range(start_ms, end_ms, timeframe_ms) if ms not in present]


def funding_coverage(times, start_ms, end_ms, timeframe_ms):
    """(interval_ms, complete) for ascending funding times; irregular spacing is an error.

    complete means the events cover [start, end); a run of events that reaches the
    end but starts late is allowed (complete False) and is disclosed per run.
    Events that stop before the end are an error: the missing tail is not a
    history limit, so it is never silently treated as zero.
    """
    if not times:
        raise ValueError("funding_empty")
    if any(ms % timeframe_ms or not start_ms <= ms < end_ms for ms in times):
        raise ValueError("funding_time_outside_bars")
    gaps = {later - earlier for earlier, later in zip(times, times[1:])}
    if len(gaps) != 1 or min(gaps) <= 0:
        raise ValueError("funding_interval_irregular")
    interval = gaps.pop()
    if end_ms - times[-1] > interval:
        raise ValueError(f"funding_stops_before_end: last {times[-1]}")
    return interval, times[0] - start_ms < interval


def _strict_json(path, data=None):
    """Strict JSON from path, or from data (bytes already read) so a hash covers the parsed bytes."""
    def pairs(items):
        keys = [key for key, _ in items]
        if len(keys) != len(set(keys)):
            raise ValueError("manifest_duplicate_key")
        return dict(items)

    def reject(_value):
        raise ValueError("manifest_non_string_number")

    text = Path(path).read_text(encoding="utf-8") if data is None else data.decode("utf-8")
    return json.loads(text, object_pairs_hook=pairs, parse_float=reject, parse_constant=reject)


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _csv_bytes(header, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def write_dataset(root=None, *, inst_id, bar, start_ms, end_ms, candles, funding, instrument,
                  fetched_at_ms, requests):
    """Write one dataset atomically and return its directory.

    candles: ascending (open_time_ms, open, high, low, close) strings covering [start, end)
    funding: ascending (funding_time_ms, realized_rate, funding_rate) strings in [start, end)
    instrument: the raw OKX instrument record
    Gaps, irregular funding, funding that stops before the end, and an existing
    dataset directory are errors; funding that starts after ``start_ms`` is
    recorded as ``complete: false``.
    """
    root = Path(root) if root is not None else DATA_ROOT
    timeframe = BAR_MS[bar]
    times = [row[0] for row in candles]
    if times != sorted(set(times)):
        raise ValueError("candles_not_ascending_unique")
    gaps = find_gaps(times, start_ms, end_ms, timeframe)
    if gaps or len(times) != (end_ms - start_ms) // timeframe:
        raise ValueError(f"dataset_has_gaps: {len(gaps)} missing, first {gaps[:3]}")
    funding_times = [row[0] for row in funding]
    interval, complete = funding_coverage(funding_times, start_ms, end_ms, timeframe)
    contract = contract_from_instrument(instrument, inst_id)
    dataset_id = dataset_id_for(inst_id, bar, start_ms, end_ms)
    parent = root / inst_id / bar
    target = parent / dataset_id
    if target.exists():
        raise FileExistsError(f"dataset_exists: {target}")
    contents = {
        CANDLES: _csv_bytes(REQUIRED_COLUMNS, [(*row, "1") for row in candles]),
        FUNDING: _csv_bytes(FUNDING_COLUMNS, funding),
        INSTRUMENT: _json_bytes(instrument),
    }
    manifest = {
        "schema": SCHEMA, "schema_version": SCHEMA_VERSION, "dataset_id": dataset_id,
        "source": SOURCE, "inst_id": inst_id, "bar": bar, "timeframe_ms": timeframe,
        "start_ms": start_ms, "end_ms": end_ms, "bars": len(candles),
        "fetched_at_ms": fetched_at_ms, "endpoints": list(ENDPOINTS), "requests": requests,
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()},
        "contract": contract,
        "funding": {"rate_field": RATE_FIELD, "mark_price_source": MARK_PRICE_SOURCE,
                    "events": len(funding), "interval_ms": interval, "complete": complete},
        "gaps": [],
    }
    parent.mkdir(parents=True, exist_ok=True)
    staging = parent / f".{dataset_id}.staging-{os.getpid()}"
    staging.mkdir()
    for name, data in {**contents, MANIFEST: _json_bytes(manifest)}.items():
        (staging / name).write_bytes(data)
    os.replace(staging, target)
    return target


@dataclass(frozen=True)
class Dataset:
    dataset_id: str
    name: str
    source: str
    candles_path: Path
    contract: research.ContractSpec
    timeframe_ms: int
    bars: int
    start_ms: int | None
    end_ms: int | None
    # (path, sha256) for every file a run depends on; see rel_path.
    files: tuple[tuple[str, str], ...]
    funding_path: Path | None
    notice: str
    # First funding event and spacing; None for a dataset without funding.
    funding_from_ms: int | None = None
    funding_interval_ms: int | None = None
    # Position tiers for the margin model; None leaves it off for margin_reason.
    position_tiers: PositionTiers | None = None
    margin_reason: str = "no_position_tiers"

    def margin_summary(self):
        """Whether runs on this dataset use the margin model, and which tier snapshot."""
        tiers = self.position_tiers
        if tiers is None:
            return {"enabled": False, "reason": self.margin_reason,
                    "reason_text": MARGIN_REASONS.get(self.margin_reason, self.margin_reason),
                    "tiers_path": None, "tiers_sha256": None, "tiers": None, "tiers_fetched_at_ms": None,
                    "leverage": None}
        return {"enabled": True, "reason": None, "reason_text": None, "tiers_path": rel_path(tiers.path),
                "tiers_sha256": tiers.sha256, "tiers": len(tiers.tiers), "tiers_fetched_at_ms": tiers.fetched_at_ms,
                "leverage": "tier_max"}

    @property
    def funding_complete(self):
        return (self.funding_path is not None
                and self.funding_from_ms - self.start_ms < self.funding_interval_ms)

    def funding_summary(self):
        """How funding is counted in a run, for payloads and reports."""
        if self.funding_path is None:
            return {"source": "none", "complete": False, "from_ms": None, "interval_ms": None}
        return {"source": "dataset", "complete": self.funding_complete,
                "from_ms": self.funding_from_ms, "interval_ms": self.funding_interval_ms}

    def provenance(self):
        entry = {"id": self.dataset_id, "source": self.source,
                 "sha256": dict(self.files)[rel_path(self.candles_path)]}
        if self.source == SOURCE:
            entry["files"] = dict(self.files)
        return entry

    def describe(self):
        return {**self.provenance(), "name": self.name, "symbol": self.contract.inst_id,
                "timeframe": next(bar for bar, ms in BAR_MS.items() if ms == self.timeframe_ms),
                "bars": self.bars, "start_ms": self.start_ms, "end_ms": self.end_ms,
                "funding": self.funding_path is not None,
                "funding_coverage": self.funding_summary(), "margin_model": self.margin_summary(),
                "notice": self.notice}

    def load(self, config):
        """Closed bars plus funding events (mark = the bar open at the funding time) and the margin model."""
        bars = load_candles_csv(self.candles_path, config=config)
        if len(bars) != self.bars:
            raise ValueError("dataset_bar_count_mismatch")
        if self.position_tiers is not None:
            if sha256_file(self.position_tiers.path) != self.position_tiers.sha256:
                raise ValueError("position_tiers_changed")
            config = replace(config, margin=self.position_tiers.model())
        if self.funding_path is None:
            return bars, config
        opens = {bar.open_time_ms: bar.open for bar in bars}
        events = []
        with open(self.funding_path, encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            if tuple(next(reader, ())) != FUNDING_COLUMNS:
                raise ValueError("funding_header_mismatch")
            for row in reader:
                if len(row) != len(FUNDING_COLUMNS) or not row[0].isdigit():
                    raise ValueError("funding_row_invalid")
                time_ms = int(row[0])
                if time_ms not in opens:
                    raise ValueError("funding_time_without_candle")
                try:
                    rate = Decimal(row[1])
                except InvalidOperation:
                    raise ValueError("funding_rate_invalid") from None
                events.append(research.FundingEvent(time_ms, rate, opens[time_ms]))
        return bars, replace(config, funding_events=tuple(events))


def _funding_times(path):
    """Funding times from a hash-checked funding.csv; rates are rechecked on load."""
    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, strict=True)
        if tuple(next(reader, ())) != FUNDING_COLUMNS:
            raise ValueError("funding_header_mismatch")
        times = []
        for row in reader:
            if len(row) != len(FUNDING_COLUMNS) or not row[0].isdigit():
                raise ValueError("funding_row_invalid")
            times.append(int(row[0]))
    return times


def load_manifest(path, root=None):
    """Verify one manifest and the files it names; raise ValueError on any doubt."""
    root = Path(root) if root is not None else DATA_ROOT
    path = Path(path)
    directory = path.parent
    if path.is_symlink() or directory.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("dataset_path_outside_root")
    value = _strict_json(path)
    if type(value) is not dict or set(value) != MANIFEST_FIELDS:
        raise ValueError("manifest_fields_mismatch")
    if (value["schema"], value["schema_version"], value["source"]) != (SCHEMA, SCHEMA_VERSION, SOURCE):
        raise ValueError("manifest_schema_mismatch")
    dataset_id, inst_id, bar = value["dataset_id"], value["inst_id"], value["bar"]
    if type(dataset_id) is not str or not DATASET_ID.fullmatch(dataset_id):
        raise ValueError("dataset_id_invalid")
    if type(inst_id) is not str or not INST_ID.fullmatch(inst_id) or bar not in BAR_MS:
        raise ValueError("dataset_instrument_or_bar_invalid")
    if (directory.name, directory.parent.name, directory.parent.parent.name) != (dataset_id, bar, inst_id):
        raise ValueError("dataset_directory_mismatch")
    timeframe, start, end, bars = value["timeframe_ms"], value["start_ms"], value["end_ms"], value["bars"]
    if any(type(item) is not int for item in (timeframe, start, end, bars, value["fetched_at_ms"], value["requests"])):
        raise ValueError("manifest_integer_required")
    if timeframe != BAR_MS[bar] or start % timeframe or end <= start or (end - start) // timeframe != bars:
        raise ValueError("dataset_range_invalid")
    if dataset_id != dataset_id_for(inst_id, bar, start, end):
        raise ValueError("dataset_id_mismatch")
    if value["endpoints"] != list(ENDPOINTS):
        raise ValueError("dataset_endpoints_mismatch")
    if value["gaps"] != []:
        raise ValueError("dataset_has_gaps")
    funding = value["funding"]
    if type(funding) is not dict or set(funding) != FUNDING_FIELDS:
        raise ValueError("funding_fields_mismatch")
    if ((funding["rate_field"], funding["mark_price_source"]) != (RATE_FIELD, MARK_PRICE_SOURCE)
            or type(funding["complete"]) is not bool or type(funding["events"]) is not int
            or type(funding["interval_ms"]) is not int):
        raise ValueError("funding_unsupported")
    files = value["files"]
    if type(files) is not dict or set(files) != set(FILES):
        raise ValueError("dataset_files_mismatch")
    for name in FILES:
        target = directory / name
        if target.is_symlink() or not target.is_file():
            raise ValueError("dataset_file_missing")
        if type(files[name]) is not str or not SHA256.fullmatch(files[name]) or sha256_file(target) != files[name]:
            raise ValueError("dataset_hash_mismatch")
    # Recompute coverage from the hashed file: the manifest flag is a claim, not a source.
    funding_times = _funding_times(directory / FUNDING)
    if (len(funding_times) != funding["events"] or funding_times != sorted(set(funding_times))
            or funding_coverage(funding_times, start, end, timeframe) != (
                funding["interval_ms"], funding["complete"])):
        raise ValueError("funding_manifest_mismatch")
    contract = value["contract"]
    if type(contract) is not dict or set(contract) != CONTRACT_FIELDS:
        raise ValueError("contract_fields_mismatch")
    if contract != contract_from_instrument(_strict_json(directory / INSTRUMENT), inst_id):
        raise ValueError("contract_instrument_mismatch")
    spec = research.ContractSpec(inst_id, *(Decimal(contract[key]) for key in (
        "base_per_contract", "tick_size", "lot_size", "min_size")))
    first, last, funding_first = (datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                                  for ms in (start, end - timeframe, funding_times[0]))
    funding_label = "含資金費" if funding["complete"] else f"資金費自 {funding_first} 起"
    notice = NOTICE if funding["complete"] else NOTICE + PARTIAL_FUNDING_NOTICE.format(
        first=datetime.fromtimestamp(funding_times[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"))
    tiers = latest_position_tiers(inst_id, root)
    notice += MARGIN_OFF_NOTICE if tiers is None else MARGIN_ON_NOTICE.format(
        fetched=datetime.fromtimestamp(tiers.fetched_at_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"))
    tier_files = () if tiers is None else ((rel_path(tiers.path), tiers.sha256),)
    return Dataset(
        dataset_id=dataset_id,
        name=f"OKX {inst_id} {bar} · {first} ~ {last} · {bars:,} 根已收盤 K 線（{funding_label}）",
        source=SOURCE,
        candles_path=directory / CANDLES,
        contract=spec,
        timeframe_ms=timeframe,
        bars=bars,
        start_ms=start,
        end_ms=end,
        files=((rel_path(path), sha256_file(path)),
               *((rel_path(directory / name), files[name]) for name in FILES), *tier_files),
        funding_path=directory / FUNDING,
        notice=notice,
        funding_from_ms=funding_times[0],
        funding_interval_ms=funding["interval_ms"],
        position_tiers=tiers,
    )


def list_datasets(root=None):
    """Valid datasets under root (sorted by id) and the manifests that were rejected."""
    root = Path(root) if root is not None else DATA_ROOT
    valid, rejected = [], []
    if not root.is_dir():
        return valid, rejected
    for manifest in sorted(root.glob(f"*/*/*/{MANIFEST}")):
        try:
            valid.append(load_manifest(manifest, root))
        except (ValueError, OSError, UnicodeDecodeError) as error:
            rejected.append((manifest.relative_to(root).as_posix(), str(error)))
    return sorted(valid, key=lambda item: item.dataset_id), rejected
