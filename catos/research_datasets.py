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
          "本根收盤決策、下一根開盤加滑價成交，沒有訂單簿、保證金與強平模型，不代表實盤可得績效。")
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


def _strict_json(path):
    def pairs(items):
        keys = [key for key, _ in items]
        if len(keys) != len(set(keys)):
            raise ValueError("manifest_duplicate_key")
        return dict(items)

    def reject(_value):
        raise ValueError("manifest_non_string_number")

    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs,
                      parse_float=reject, parse_constant=reject)


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
                "funding_coverage": self.funding_summary(), "notice": self.notice}

    def load(self, config):
        """Closed bars plus funding events; funding mark = the bar open at the funding time."""
        bars = load_candles_csv(self.candles_path, config=config)
        if len(bars) != self.bars:
            raise ValueError("dataset_bar_count_mismatch")
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
               *((rel_path(directory / name), files[name]) for name in FILES)),
        funding_path=directory / FUNDING,
        notice=notice,
        funding_from_ms=funding_times[0],
        funding_interval_ms=funding["interval_ms"],
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
