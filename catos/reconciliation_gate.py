"""Pure offline reconciliation gate and durable local ownership snapshot model.

No HTTP, credential access, database writes, order routing, or trade authorization.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import hashlib
import json

from catos import research, risk
from catos.okx_collection import SNAPSHOT_SEMANTICS_CONTRACT, WINDOW_COVERAGE_CONTRACT


D = Decimal
VERSION = "reconciliation-gate.v1"

BLOCKERS = frozenset((
    "scope_mismatch",
    "local_revision_changed",
    "collection_incomplete",
    "evidence_integrity_failed",
    "record_invalid",
    "mode_mismatch",
    "ownership_snapshot_missing",
    "local_bot_isolated",
    "position_identity_unavailable",
    "foreign_position",
    "foreign_order",
    "foreign_algo",
    "local_position_unverified",
    "local_unknown",
    "fill_reconciliation_failed",
    "freshness_policy_unset",
    "snapshot_freshness_unverified",
    "window_coverage_unverified",
    "fill_window_coverage_unverified",
    "bill_window_coverage_unverified",
    "day_baseline_unverified",
    "external_flow_unavailable",
    "external_flow_mismatch",
    "unknown_external_flow",
    "unsupported_account_activity",
    "algo_identity_unavailable",
    "p6_protection_unverified",
    "p6_triggered_not_reconciled",
))


def _token(value, name):
    if not isinstance(value, str) or not value or value.strip() != value or len(value) > 256:
        raise ValueError(f"invalid {name}")
    return value


def _integer(value, name, *, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"invalid {name}")
    return value


def _money(value, name, *, positive=False):
    if type(value) is str:
        try:
            value = D(value)
        except Exception:
            raise ValueError(f"invalid {name}") from None
    if type(value) is not D or not value.is_finite() or (positive and value <= 0):
        raise ValueError(f"invalid {name}")
    return value


def _digest(value):
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _report_digest(report):
    if type(report) is not dict or type(report.get("content_digest")) is not str:
        return None
    body = dict(report)
    claimed = body.pop("content_digest")
    actual = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    return claimed if actual == claimed else None


@dataclass(frozen=True)
class OwnershipSnapshot:
    bot_id: str
    bot_revision: int
    inst_id: str
    local_position: Decimal | None
    owned_exchange_order_ids: tuple[str, ...]
    owned_exchange_algo_ids: tuple[str, ...]
    owned_remote_position_ids: tuple[tuple[str, str], ...]
    unresolved_local_ids: tuple[str, ...]
    ordinary_open_count: int
    conditional_open_count: int
    unknown_count: int
    terminal_incomplete_count: int
    fills_reconciled_local: bool
    isolated: bool
    protection_state: tuple[tuple[str, object], ...]
    snapshot_digest: str

    def _payload(self):
        return {
            "bot_id": self.bot_id,
            "bot_revision": self.bot_revision,
            "inst_id": self.inst_id,
            "local_position": None if self.local_position is None else str(self.local_position),
            "owned_exchange_order_ids": list(self.owned_exchange_order_ids),
            "owned_exchange_algo_ids": list(self.owned_exchange_algo_ids),
            "owned_remote_position_ids": [list(item) for item in self.owned_remote_position_ids],
            "unresolved_local_ids": list(self.unresolved_local_ids),
            "ordinary_open_count": self.ordinary_open_count,
            "conditional_open_count": self.conditional_open_count,
            "unknown_count": self.unknown_count,
            "terminal_incomplete_count": self.terminal_incomplete_count,
            "fills_reconciled_local": self.fills_reconciled_local,
            "isolated": self.isolated,
            "protection_state": dict(self.protection_state),
        }

    def valid(self):
        try:
            _token(self.bot_id, "bot_id")
            _integer(self.bot_revision, "bot_revision")
            _token(self.inst_id, "inst_id")
            if self.local_position is not None:
                _money(self.local_position, "local_position")
            for values, name in ((self.owned_exchange_order_ids, "order ids"),
                                 (self.owned_exchange_algo_ids, "algo ids"),
                                 (self.unresolved_local_ids, "unresolved ids")):
                if type(values) is not tuple or len(set(values)) != len(values):
                    return False
                for value in values:
                    _token(value, name)
            if type(self.owned_remote_position_ids) is not tuple:
                return False
            for item in self.owned_remote_position_ids:
                if type(item) is not tuple or len(item) != 2:
                    return False
                _token(item[0], "position instrument")
                _token(item[1], "position id")
            for name in ("ordinary_open_count", "conditional_open_count", "unknown_count",
                         "terminal_incomplete_count"):
                _integer(getattr(self, name), name)
            if type(self.fills_reconciled_local) is not bool or type(self.isolated) is not bool:
                return False
            if type(self.protection_state) is not tuple:
                return False
            return _digest(self._payload()) == self.snapshot_digest
        except (ValueError, TypeError):
            return False

    def report_attribution(self):
        positions = {}
        if self.local_position is not None:
            positions = {key: self.local_position for key in self.owned_remote_position_ids}
        return {
            "owned_order_ids": frozenset(self.owned_exchange_order_ids),
            "owned_algo_ids": frozenset(self.owned_exchange_algo_ids),
            "owned_positions": positions,
            "unresolved_local_ids": frozenset(self.unresolved_local_ids),
        }


@dataclass(frozen=True)
class PositionBootstrapLineage:
    bot_id: str
    bot_revision: int
    inst_id: str
    local_position: Decimal
    fills: tuple[tuple[str, str, str, str], ...]
    lineage_digest: str

    def _payload(self):
        return {
            "bot_id": self.bot_id,
            "bot_revision": self.bot_revision,
            "inst_id": self.inst_id,
            "local_position": str(self.local_position),
            "fills": [list(item) for item in self.fills],
        }

    def valid(self):
        try:
            _token(self.bot_id, "bot_id")
            _integer(self.bot_revision, "bot_revision")
            _token(self.inst_id, "inst_id")
            _money(self.local_position, "local_position")
            if type(self.fills) is not tuple:
                return False
            with localcontext(research._CONTEXT):
                total = D("0")
                for item in self.fills:
                    if type(item) is not tuple or len(item) != 4:
                        return False
                    exchange_id, trade_id, signed_quantity, price = item
                    _token(exchange_id, "exchange order id")
                    _token(trade_id, "trade id")
                    quantity = _money(signed_quantity, "signed fill quantity")
                    if quantity == 0 or _money(price, "fill price", positive=True) <= 0:
                        return False
                    total += quantity
            return bool(self.fills) and total == self.local_position and _digest(self._payload()) == self.lineage_digest
        except (ValueError, TypeError):
            return False


@dataclass(frozen=True)
class PositionIdentityEvidence:
    version: str
    bot_id: str
    bot_revision: int
    inst_id: str
    local_position: Decimal
    remote_pos_id: str
    ownership_snapshot_digest: str
    lineage_digest: str
    report_content_digest: str
    evidence_id: str

    def _payload(self):
        return {
            "version": self.version,
            "bot_id": self.bot_id,
            "bot_revision": self.bot_revision,
            "inst_id": self.inst_id,
            "local_position": str(self.local_position),
            "remote_pos_id": self.remote_pos_id,
            "ownership_snapshot_digest": self.ownership_snapshot_digest,
            "lineage_digest": self.lineage_digest,
            "report_content_digest": self.report_content_digest,
        }

    def valid(self):
        try:
            if self.version != "position-bootstrap.v1":
                return False
            _token(self.bot_id, "bot_id")
            _integer(self.bot_revision, "bot_revision")
            _token(self.inst_id, "inst_id")
            if _money(self.local_position, "local_position") == 0:
                return False
            _token(self.remote_pos_id, "remote position id")
            for value, name in ((self.ownership_snapshot_digest, "ownership digest"),
                                (self.lineage_digest, "lineage digest"),
                                (self.report_content_digest, "report digest"),
                                (self.evidence_id, "bootstrap evidence id")):
                if type(value) is not str or len(value) != 64:
                    raise ValueError(f"invalid {name}")
                int(value, 16)
            return _digest(self._payload()) == self.evidence_id
        except (ValueError, TypeError):
            return False


def position_bootstrap_lineage(*, bot_id, bot_revision, inst_id, local_position, fills):
    """Create immutable local fill lineage used only for first remote posId binding."""
    local_position = _money(local_position, "local_position")
    normalized = []
    for exchange_id, trade_id, signed_quantity, price in fills:
        normalized.append((_token(exchange_id, "exchange order id"),
                           _token(trade_id, "trade id"),
                           str(_money(signed_quantity, "signed fill quantity")),
                           str(_money(price, "fill price", positive=True))))
    normalized = tuple(sorted(normalized))
    draft = PositionBootstrapLineage(
        _token(bot_id, "bot_id"), _integer(bot_revision, "bot_revision"),
        _token(inst_id, "inst_id"), local_position, normalized, "")
    result = PositionBootstrapLineage(
        draft.bot_id, draft.bot_revision, draft.inst_id, draft.local_position,
        draft.fills, _digest(draft._payload()))
    if not result.valid():
        raise ValueError("local fill lineage does not exactly explain current position")
    return result


_BOOTSTRAP_ALLOWED_DISCREPANCIES = frozenset((
    "foreign_position", "freshness_unverified", "window_coverage_unverified",
    "day_baseline_unverified",
))


def _bootstrap_raw_facts(result):
    from catos import account_report, okx_readonly as ia
    from catos.okx_collection import CollectionResult
    if not isinstance(result, CollectionResult):
        raise ValueError("invalid bootstrap collection")
    manifests = {item.alias: item for item in result.manifest.endpoint_manifests}
    facts = []
    for page in result.pages:
        if page.endpoint_alias not in ("positions", "fills", "fills_history"):
            continue
        manifest = manifests.get(page.endpoint_alias)
        if manifest is None or manifest.complete is not True:
            raise ValueError("bootstrap source incomplete")
        evidence = next((item for item in manifest.pages if item.page_number == page.page_number), None)
        if (evidence is None or evidence.request_cursor != page.request_cursor
                or hashlib.sha256(page.payload_json.encode("utf-8")).hexdigest() != evidence.digest):
            raise ValueError("bootstrap page evidence mismatch")
        for row in ia.rows(json.loads(page.payload_json)):
            facts.append(account_report.decode_row(page.endpoint_alias, row))
    return facts


def build_position_identity_evidence(report, result, snapshot, lineage):
    """Return first-posId evidence only when local and remote fill lineage is exact.

    The remote posId is never treated as ownership evidence by itself.  The only
    accepted bootstrap is a unique nonzero remote position whose quantity is
    exactly explained by all durable local exchange fills and whose raw remote
    fill identities match those durable fills one-for-one.
    """
    if (_report_digest(report) is None or report.get("collection_complete") is not True
            or not isinstance(snapshot, OwnershipSnapshot) or not snapshot.valid()
            or not isinstance(lineage, PositionBootstrapLineage) or not lineage.valid()):
        return None
    if (snapshot.local_position in (None, D("0")) or snapshot.owned_remote_position_ids
            or snapshot.unresolved_local_ids or snapshot.unknown_count or snapshot.terminal_incomplete_count
            or snapshot.isolated or lineage.bot_id != snapshot.bot_id
            or lineage.bot_revision != snapshot.bot_revision or lineage.inst_id != snapshot.inst_id
            or lineage.local_position != snapshot.local_position
            or report.get("instrument") != snapshot.inst_id or report.get("environment") != "demo"):
        return None
    discrepancies = report.get("discrepancies")
    if type(discrepancies) is not list or any(type(item) is not str for item in discrepancies):
        return None
    issues = set(discrepancies)
    if "foreign_position" not in issues or issues - _BOOTSTRAP_ALLOWED_DISCREPANCIES:
        return None
    try:
        facts = _bootstrap_raw_facts(result)
    except (ValueError, TypeError, AttributeError, json.JSONDecodeError):
        return None
    positions = {}
    remote_fills = {}
    for fact in facts:
        kind = fact.get("kind")
        if kind == "positions" and fact["pos"] != 0:
            key = (fact["instId"], fact["posId"])
            if key in positions and positions[key] != fact["pos"]:
                return None
            positions[key] = fact["pos"]
        elif kind == "fill":
            key = (fact["instId"], fact["tradeId"])
            value = (fact["ordId"], fact["fillSz"], fact["fillPx"])
            if key in remote_fills and remote_fills[key] != value:
                return None
            remote_fills[key] = value
    candidates = [(pos_id, quantity) for (inst_id, pos_id), quantity in positions.items()
                  if inst_id == snapshot.inst_id]
    if (len(positions) != 1 or len(candidates) != 1
            or candidates[0][1] != snapshot.local_position):
        return None
    local_fills = {
        (snapshot.inst_id, trade_id): (exchange_id, abs(D(signed_quantity)), D(price))
        for exchange_id, trade_id, signed_quantity, price in lineage.fills
    }
    if remote_fills != local_fills:
        return None
    remote_pos_id = candidates[0][0]
    fields = dict(
        version="position-bootstrap.v1",
        bot_id=snapshot.bot_id,
        bot_revision=snapshot.bot_revision,
        inst_id=snapshot.inst_id,
        local_position=snapshot.local_position,
        remote_pos_id=remote_pos_id,
        ownership_snapshot_digest=snapshot.snapshot_digest,
        lineage_digest=lineage.lineage_digest,
        report_content_digest=report["content_digest"],
    )
    draft = PositionIdentityEvidence(**fields, evidence_id="")
    evidence = PositionIdentityEvidence(**fields, evidence_id=_digest(draft._payload()))
    return evidence if evidence.valid() else None


def ownership_snapshot_from_rows(*, bot_id, bot_revision, inst_id, local_position,
                                 owner_reconciled_revision, fills_reconciled,
                                 isolated, execution_rows, protection,
                                 remote_position_id=None):
    """Materialize a snapshot from one Journal read transaction."""
    _token(bot_id, "bot_id")
    _integer(bot_revision, "bot_revision")
    _token(inst_id, "inst_id")
    if local_position is not None:
        local_position = _money(local_position, "local_position")
    if remote_position_id is not None:
        remote_position_id = _token(remote_position_id, "remote position id")
    if type(fills_reconciled) is not bool or type(isolated) is not bool:
        raise ValueError("invalid local ownership flags")
    if type(execution_rows) is not tuple or type(protection) is not dict:
        raise ValueError("invalid local ownership input")

    owned_orders = set()
    unresolved = set()
    ordinary_open = unknown = terminal_incomplete = 0
    terminal = frozenset(("FILLED", "CANCELED", "REJECTED", "ABORTED"))
    for row in execution_rows:
        if type(row) is not dict:
            raise ValueError("invalid execution row")
        key = _token(row.get("order_key"), "order_key")
        state = _token(row.get("state"), "order state")
        exchange_id = row.get("exchange_id")
        if exchange_id is not None:
            owned_orders.add(_token(exchange_id, "exchange order id"))
        settled = row.get("settled")
        if settled not in (0, 1):
            raise ValueError("invalid settled flag")
        if settled:
            continue
        if state in ("LIVE", "PARTIAL"):
            ordinary_open += 1
        if state in ("UNKNOWN", "SUBMITTING"):
            unknown += 1
        if state in terminal:
            terminal_incomplete += 1
        if exchange_id is None or state in ("UNKNOWN", "SUBMITTING"):
            unresolved.add(key)

    ratio = _money(protection.get("config", {}).get("ratio"), "protection ratio")
    active_state = protection.get("active")
    active = active_state is not None
    pending = protection.get("pending") is not None
    uncertain = protection.get("uncertain")
    triggered = protection.get("triggered")
    failed = protection.get("failed")
    if any(type(value) is not bool for value in (uncertain, triggered, failed)):
        raise ValueError("invalid protection flags")
    owned_algos = set()
    if active:
        if type(active_state) is not dict:
            raise ValueError("invalid active protection")
        algo_id = active_state.get("algo_id")
        if algo_id is not None:
            owned_algos.add(_token(algo_id, "remote algo id"))
    if triggered and not owned_algos:
        report = protection.get("report")
        if type(report) is dict and report.get("algo_id") is not None:
            owned_algos.add(_token(report["algo_id"], "remote algo id"))
    protection_summary = tuple(sorted({
        "ratio": str(ratio),
        "active": active,
        "pending": pending,
        "uncertain": uncertain,
        "triggered": triggered,
        "failed": failed,
        "obligation": active or pending or uncertain or triggered,
    }.items()))

    fields = dict(
        bot_id=bot_id,
        bot_revision=bot_revision,
        inst_id=inst_id,
        local_position=local_position,
        owned_exchange_order_ids=tuple(sorted(owned_orders)),
        owned_exchange_algo_ids=tuple(sorted(owned_algos)),
        owned_remote_position_ids=(
            ((inst_id, remote_position_id),)
            if local_position not in (None, D("0")) and remote_position_id is not None else ()),
        unresolved_local_ids=tuple(sorted(unresolved)),
        ordinary_open_count=ordinary_open,
        conditional_open_count=int(active),
        unknown_count=unknown,
        terminal_incomplete_count=terminal_incomplete,
        fills_reconciled_local=bool(fills_reconciled and owner_reconciled_revision == bot_revision),
        isolated=isolated,
        protection_state=protection_summary,
    )
    draft = OwnershipSnapshot(**fields, snapshot_digest="")
    return OwnershipSnapshot(**fields, snapshot_digest=_digest(draft._payload()))


@dataclass(frozen=True)
class FreshnessPolicy:
    policy_id: str
    max_report_age_ms: int
    max_batch_span_ms: int
    max_clock_skew_ms: int
    max_clock_sample_age_ms: int
    checked_at_ms: int

    def __post_init__(self):
        _token(self.policy_id, "freshness policy")
        for name in ("max_report_age_ms", "max_batch_span_ms", "max_clock_skew_ms",
                     "max_clock_sample_age_ms"):
            _integer(getattr(self, name), name, minimum=1)
        _integer(self.checked_at_ms, "checked_at_ms")


@dataclass(frozen=True)
class FreshnessEvidence:
    server_time_ms: int
    local_time_ms: int

    def __post_init__(self):
        _integer(self.server_time_ms, "server_time_ms")
        _integer(self.local_time_ms, "local_time_ms")


@dataclass(frozen=True)
class DayLedgerEvidence:
    trading_day_start_ms: int
    baseline_equity_usdt: Decimal
    baseline_evidence_id: str
    external_flow_usdt: Decimal
    flow_classification_id: str
    unknown_flow_count: int
    day_flow_cutoff_ms: int | None = None
    period_basis: risk.DayBasis | None = None

    def __post_init__(self):
        _integer(self.trading_day_start_ms, "trading_day_start_ms")
        if self.period_basis is not None and not isinstance(self.period_basis, risk.DayBasis):
            raise ValueError("invalid risk period basis")
        _money(self.baseline_equity_usdt, "baseline equity", positive=True)
        _token(self.baseline_evidence_id, "baseline evidence")
        _money(self.external_flow_usdt, "external flow")
        _token(self.flow_classification_id, "flow classification")
        _integer(self.unknown_flow_count, "unknown flow count")
        if self.day_flow_cutoff_ms is not None:
            _integer(self.day_flow_cutoff_ms, "day_flow_cutoff_ms")
            if self.day_flow_cutoff_ms < self.trading_day_start_ms:
                raise ValueError("day_flow_cutoff_ms cannot precede trading_day_start_ms")


@dataclass(frozen=True)
class GateResult:
    version: str
    bot_id: str
    bot_revision: int
    report_content_digest: str
    ownership_snapshot_digest: str
    reconciled: bool
    trade_authorized: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    evidence_id: str


_PLACEHOLDERS = frozenset(("freshness_unverified", "window_coverage_unverified",
                           "day_baseline_unverified"))


def _report_blockers(discrepancies):
    blockers = set()
    for issue in discrepancies:
        if issue in _PLACEHOLDERS:
            continue
        if issue == "incomplete_collection" or issue == "missing_governance_source":
            blockers.add("collection_incomplete")
        elif issue.startswith("invalid_record:") or issue.startswith("missing_or_ambiguous:"):
            blockers.add("record_invalid")
        elif issue in ("page_evidence_gap", "page_evidence_mismatch", "page_chain_invalid",
                       "manifest_completion_mismatch", "malformed_page") or issue.startswith("conflicting_observation:"):
            blockers.add("evidence_integrity_failed")
        elif issue == "mode_mismatch":
            blockers.add("mode_mismatch")
        elif issue in ("scope_mismatch", "not_subaccount", "unsupported_instrument",
                       "unsupported_contract", "instrument_scope_mismatch"):
            blockers.add("scope_mismatch")
        elif issue in ("foreign_position", "foreign_order", "foreign_algo", "local_position_unverified",
                       "local_unknown", "external_flow_unavailable", "unknown_external_flow",
                       "unsupported_account_activity",
                       "p6_protection_unverified", "p6_triggered_not_reconciled"):
            blockers.add(issue)
        elif issue == "position_mismatch":
            blockers.add("local_position_unverified")
        elif issue in ("fill_totals_unavailable", "fill_window_gap", "orphan_fill", "fill_conflict",
                       "invalid_terminal"):
            blockers.add("fill_reconciliation_failed")
        elif issue == "outside_window:fill":
            blockers.update(("window_coverage_unverified", "fill_window_coverage_unverified"))
        elif issue == "outside_window:bill":
            blockers.update(("window_coverage_unverified", "bill_window_coverage_unverified"))
        else:
            blockers.add("evidence_integrity_failed")
    return blockers


_SNAPSHOT_STATE_SOURCES = frozenset(("balance", "positions", "orders_pending", "algo_pending"))
_SNAPSHOT_FILL_SOURCES = frozenset(("fills", "fills_history"))
_SNAPSHOT_BILL_SOURCES = frozenset(("bills", "bills_archive"))
_EVENT_RECORD_SOURCES = _SNAPSHOT_FILL_SOURCES | _SNAPSHOT_BILL_SOURCES


def _bounded_sequential_snapshot_verified(report):
    """Verify one bounded, sequential observation batch from report metadata.

    This does not claim an exchange-atomic snapshot. Record update timestamps and
    transport timestamps are explicitly excluded as snapshot fences.
    """
    if type(report) is not dict:
        return False
    semantics = report.get("snapshot_semantics")
    if semantics != {
            "contract_id": SNAPSHOT_SEMANTICS_CONTRACT,
            "mode": "bounded_sequential_observation",
            "atomic_snapshot": False,
            "record_update_time_is_snapshot_fence": False,
            "transport_time_is_snapshot_fence": False,
    }:
        return False
    started, completed = report.get("started_ms"), report.get("completed_ms")
    if (type(started) is not int or type(completed) is not int
            or started < 0 or completed < started):
        return False
    sources = report.get("sources")
    if type(sources) is not list or not sources:
        return False
    aliases = [source.get("alias") for source in sources if type(source) is dict]
    if len(aliases) != len(sources) or any(type(alias) is not str or not alias for alias in aliases):
        return False
    alias_set = set(aliases)
    if (len(alias_set) != len(aliases)
            or not _SNAPSHOT_STATE_SOURCES <= alias_set
            or not (_SNAPSHOT_FILL_SOURCES & alias_set)
            or not (_SNAPSHOT_BILL_SOURCES & alias_set)):
        return False

    previous_completed = started
    for source in sources:
        source_started = source.get("started_ms")
        source_completed = source.get("completed_ms")
        if (type(source_started) is not int or type(source_completed) is not int
                or source_started < previous_completed or source_completed < source_started
                or source_completed > completed
                or source.get("complete") is not True
                or source.get("issue") != ""
                or type(source.get("requests")) is not int or source["requests"] <= 0
                or source.get("source_time_semantics") != "transport_supplied_not_verified_snapshot"):
            return False
        expected_record_semantics = (
            "event_ms" if source["alias"] in _EVENT_RECORD_SOURCES
            else "last_update_or_reference_ms_not_snapshot")
        if source.get("record_time_semantics") != expected_record_semantics:
            return False
        pages = source.get("pages")
        if type(pages) is not list or not pages:
            return False
        for number, page in enumerate(pages, 1):
            if (type(page) is not dict or page.get("page_number") != number
                    or type(page.get("received_ms")) is not int
                    or not source_started <= page["received_ms"] <= source_completed
                    or type(page.get("source_ms")) is not int):
                return False
        previous_completed = source_completed
    return True


def _freshness_blockers(report, policy, evidence):
    if policy is None:
        return {"freshness_policy_unset", "snapshot_freshness_unverified"}
    if not isinstance(policy, FreshnessPolicy) or not isinstance(evidence, FreshnessEvidence):
        return {"snapshot_freshness_unverified"}
    started, completed = report.get("started_ms"), report.get("completed_ms")
    if type(started) is not int or type(completed) is not int or started < 0 or completed < started:
        return {"snapshot_freshness_unverified"}
    bad = (policy.checked_at_ms < completed
           or policy.checked_at_ms - completed > policy.max_report_age_ms
           or completed - started > policy.max_batch_span_ms
           or abs(evidence.server_time_ms - evidence.local_time_ms) > policy.max_clock_skew_ms
           or evidence.local_time_ms > policy.checked_at_ms
           or policy.checked_at_ms - evidence.local_time_ms > policy.max_clock_sample_age_ms
           or not _bounded_sequential_snapshot_verified(report))
    return {"snapshot_freshness_unverified"} if bad else set()


def _window_group_covered(report, aliases, fact_kind):
    if type(report) is not dict:
        return False
    begin, end = report.get("window_start_ms"), report.get("window_end_ms")
    if type(begin) is not int or type(end) is not int or begin < 0 or begin >= end:
        return False
    sources = report.get("sources")
    if type(sources) is not list:
        return False
    selected = [source for source in sources
                if type(source) is dict and source.get("alias") in aliases]
    if not selected:
        return False
    expected = {
        "contract_id": WINDOW_COVERAGE_CONTRACT,
        "begin_ms": begin,
        "end_ms": end,
        "event_time_field": "ts",
        "cursor_semantics": "after_bill_id",
        "filter_semantics": "exact_inclusive_begin_end",
    }
    for source in selected:
        if (source.get("complete") is not True or source.get("issue") != ""
                or type(source.get("requests")) is not int or source["requests"] <= 0
                or source.get("window_request_evidence") != expected):
            return False
        pages = source.get("pages")
        if type(pages) is not list or not pages:
            return False
        previous_next = None
        seen = set()
        for number, page in enumerate(pages, 1):
            if type(page) is not dict or page.get("page_number") != number:
                return False
            request_cursor = page.get("request_cursor")
            next_cursor = page.get("next_cursor")
            if (request_cursor is not None and (type(request_cursor) is not str or not request_cursor)):
                return False
            if next_cursor is not None and (type(next_cursor) is not str or not next_cursor):
                return False
            if request_cursor != previous_next or (number > 1 and previous_next is None):
                return False
            if next_cursor is not None:
                if next_cursor in seen:
                    return False
                seen.add(next_cursor)
            previous_next = next_cursor
        if previous_next is not None:
            return False

    facts = report.get("facts")
    if type(facts) is not list:
        return False
    for fact in facts:
        if type(fact) is not dict or fact.get("kind") != fact_kind:
            continue
        stamp = fact.get("ts")
        if type(stamp) is not int or not begin <= stamp <= end:
            return False
    return True


def _window_blockers(report):
    blockers = set()
    if not _window_group_covered(report, _SNAPSHOT_FILL_SOURCES, "fill"):
        blockers.add("fill_window_coverage_unverified")
    if not _window_group_covered(report, _SNAPSHOT_BILL_SOURCES, "bill"):
        blockers.add("bill_window_coverage_unverified")
    if blockers:
        blockers.add("window_coverage_unverified")
    return blockers


DAY_MS = 86_400_000
TAIPEI_OFFSET_MS = 28_800_000


def _day_blockers(report, evidence, freshness_policy=None):
    if not isinstance(evidence, DayLedgerEvidence):
        return {"day_baseline_unverified"}
    if evidence.period_basis is not None:
        return _period_blockers(report, evidence, freshness_policy)
    blockers = set()
    if (evidence.trading_day_start_ms + TAIPEI_OFFSET_MS) % DAY_MS != 0:
        blockers.add("day_baseline_unverified")

    target_ms = None
    if freshness_policy is not None and hasattr(freshness_policy, "checked_at_ms"):
        target_ms = freshness_policy.checked_at_ms
    elif type(report) is dict and type(report.get("completed_ms")) is int and report["completed_ms"] > 0:
        target_ms = report["completed_ms"]
    elif type(report) is dict and type(report.get("window_end_ms")) is int:
        target_ms = report["window_end_ms"]
    elif type(report) is dict and type(report.get("started_ms")) is int and report["started_ms"] > 0:
        target_ms = report["started_ms"]

    if target_ms is None:
        blockers.add("day_baseline_unverified")
    else:
        target_day = (target_ms + TAIPEI_OFFSET_MS) // DAY_MS
        expected_day_start_ms = target_day * DAY_MS - TAIPEI_OFFSET_MS

        if type(report) is dict:
            started_ms = report.get("started_ms")
            completed_ms = report.get("completed_ms")
            win_start = report.get("window_start_ms")
            win_end = report.get("window_end_ms")
            rep_start = report.get("day_flow_start_ms")
            rep_cutoff = report.get("day_flow_cutoff_ms")

            if type(started_ms) is int and type(completed_ms) is int and 0 < started_ms <= completed_ms:
                if (started_ms + TAIPEI_OFFSET_MS) // DAY_MS != (completed_ms + TAIPEI_OFFSET_MS) // DAY_MS:
                    blockers.add("day_baseline_unverified")

            # Day C_t coverage verification (R2):
            if rep_start is not None and rep_start != expected_day_start_ms:
                blockers.add("day_baseline_unverified")

            if evidence.day_flow_cutoff_ms is not None:
                if rep_cutoff != evidence.day_flow_cutoff_ms:
                    blockers.add("day_baseline_unverified")
                if rep_cutoff is None or rep_cutoff < expected_day_start_ms:
                    blockers.add("day_baseline_unverified")
                if type(win_end) is int and rep_cutoff > win_end:
                    blockers.add("day_baseline_unverified")

        if evidence.trading_day_start_ms != expected_day_start_ms:
            blockers.add("day_baseline_unverified")

        facts = report.get("facts") if type(report) is dict else None
        if type(facts) is list:
            for fact in facts:
                if (type(fact) is dict and fact.get("kind") == "bill"
                        and fact.get("ts") == expected_day_start_ms):
                    timing = fact.get("timing_verified")
                    timing_evidence_id = fact.get("timing_evidence_id")
                    if ((timing is not None or timing_evidence_id is not None)
                            and (timing not in ("prior_to_baseline", "after_baseline")
                                 or timing_evidence_id != evidence.baseline_evidence_id)):
                        blockers.add("day_baseline_unverified")

    if evidence.unknown_flow_count:
        blockers.add("unknown_external_flow")
    # Catalog coverage is informational. Actual unknown/forbidden bills remain
    # blockers through report discrepancies and the day-ledger unknown count.
    if report.get("flow_classification_id") != evidence.flow_classification_id:
        blockers.add("external_flow_mismatch")

    # Strict Day C_t: forbidden to fallback to 24h observed_external_flow_usdt
    observed = report.get("day_external_flow_usdt")
    if observed is None:
        blockers.add("external_flow_unavailable")
    else:
        try:
            if _money(observed, "day external flow") != evidence.external_flow_usdt:
                blockers.add("external_flow_mismatch")
        except ValueError:
            blockers.add("external_flow_unavailable")
    return blockers


def _period_blockers(report, evidence, policy):
    basis = evidence.period_basis
    target = getattr(policy, "checked_at_ms", report.get("completed_ms"))
    blockers = set()
    if (type(target) is not int or basis.source != risk.RISK_PERIOD_SOURCE
            or not risk.is_verified_baseline(basis, account_alias=report.get("account_alias"),
                environment=report.get("environment"), target_day=risk.taipei_day(target))):
        return {"day_baseline_unverified"}
    start = basis.evidence.observed_at_ms
    cutoff = evidence.day_flow_cutoff_ms
    begin, end = report.get("window_start_ms"), report.get("window_end_ms")
    if (evidence.trading_day_start_ms != basis.evidence.trading_day_start_ms
            or evidence.baseline_equity_usdt != basis.equity
            or evidence.baseline_evidence_id != basis.evidence_id
            or report.get("risk_period_start_ms") != start
            or report.get("risk_period_basis_id") != basis.evidence_id
            or report.get("day_flow_start_ms") != start
            or type(begin) is not int or begin > start
            or type(cutoff) is not int or not start <= cutoff <= target
            or type(end) is not int or cutoff != end
            or report.get("day_flow_cutoff_ms") != cutoff
            or report.get("started_ms", -1) < basis.evidence.trading_day_start_ms):
        blockers.add("day_baseline_unverified")
    if evidence.unknown_flow_count or report.get("day_unknown_flow_count"):
        blockers.add("unknown_external_flow")
    if report.get("flow_classification_id") != evidence.flow_classification_id:
        blockers.add("external_flow_mismatch")
    try:
        if _money(report.get("day_external_flow_usdt"), "period flow") != evidence.external_flow_usdt:
            blockers.add("external_flow_mismatch")
    except ValueError:
        blockers.add("external_flow_unavailable")
    for fact in report.get("facts", []):
        if fact.get("kind") == "bill" and fact.get("ts") == start:
            if (fact.get("timing_verified") not in ("prior_to_baseline", "after_baseline")
                    or fact.get("timing_evidence_id") != basis.evidence_id):
                blockers.add("external_flow_unavailable")
    return blockers


def evaluate(report, snapshot, *, revision_before, revision_after,
             freshness_policy=None, freshness_evidence=None,
             day_ledger=None):
    """Return a deterministic fail-closed reconciliation verdict."""
    blockers = set()
    digest = _report_digest(report)
    if digest is None:
        blockers.add("evidence_integrity_failed")
        digest = report.get("content_digest", "") if type(report) is dict else ""
    if not isinstance(snapshot, OwnershipSnapshot) or not snapshot.valid():
        blockers.add("ownership_snapshot_missing")
        bot_id, bot_revision, snapshot_digest = "invalid", 0, ""
    else:
        bot_id, bot_revision, snapshot_digest = snapshot.bot_id, snapshot.bot_revision, snapshot.snapshot_digest
        if snapshot.isolated:
            blockers.add("local_bot_isolated")
        if snapshot.local_position is None:
            blockers.add("ownership_snapshot_missing")
        elif snapshot.local_position != 0 and not snapshot.owned_remote_position_ids:
            blockers.add("position_identity_unavailable")
        if snapshot.unresolved_local_ids or snapshot.unknown_count:
            blockers.add("local_unknown")
        if snapshot.terminal_incomplete_count:
            blockers.add("fill_reconciliation_failed")
        protection = dict(snapshot.protection_state)
        if protection.get("obligation") and not snapshot.owned_exchange_algo_ids:
            blockers.update(("algo_identity_unavailable", "p6_protection_unverified"))
        if protection.get("triggered"):
            blockers.add("p6_triggered_not_reconciled")

    if type(revision_before) is not int or type(revision_after) is not int or (
            revision_before != bot_revision or revision_after != bot_revision):
        blockers.add("local_revision_changed")

    if type(report) is not dict:
        blockers.add("evidence_integrity_failed")
    else:
        local_period = (isinstance(day_ledger, DayLedgerEvidence)
                        and isinstance(day_ledger.period_basis, risk.DayBasis)
                        and report.get("environment") == "local-sim")
        if report.get("instrument") != getattr(snapshot, "inst_id", None) or (report.get("environment") != "demo" and not local_period):
            blockers.add("scope_mismatch")
        if report.get("collection_complete") is not True:
            blockers.add("collection_incomplete")
        if report.get("reconciled") is not False or report.get("trade_authorized") is not False:
            blockers.add("evidence_integrity_failed")
        discrepancies = report.get("discrepancies")
        if type(discrepancies) is not list or any(type(item) is not str for item in discrepancies):
            blockers.add("evidence_integrity_failed")
        else:
            blockers.update(_report_blockers(discrepancies))
        facts = report.get("facts")
        if type(facts) is list and isinstance(snapshot, OwnershipSnapshot):
            live_orders = sum(f.get("kind") == "order" and f.get("state") in ("live", "partially_filled")
                              for f in facts if type(f) is dict)
            if live_orders != snapshot.ordinary_open_count:
                blockers.add("local_unknown")

    blockers.update(_freshness_blockers(report if type(report) is dict else {}, freshness_policy, freshness_evidence))
    blockers.update(_window_blockers(report if type(report) is dict else {}))
    blockers.update(_day_blockers(report if type(report) is dict else {}, day_ledger, freshness_policy=freshness_policy))
    if not blockers <= BLOCKERS:
        raise AssertionError("unregistered reconciliation blocker")

    ordered = tuple(sorted(blockers))
    evidence_id = _digest({"version": VERSION, "bot_id": bot_id, "bot_revision": bot_revision,
                           "report": digest, "snapshot": snapshot_digest, "blockers": ordered})[:32]
    return GateResult(VERSION, bot_id, bot_revision, digest, snapshot_digest, not ordered,
                      False, ordered, (), evidence_id)
