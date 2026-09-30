"""Read-only localhost API for materialized market-intelligence state.

The API never recalculates persisted model scores or lifecycle transitions. It
reads only the already-materialized market_intel.sqlite state. Read-only product
surfaces may deterministically aggregate those facts while preserving missing
and conflict semantics. P1/P2 surfaces that do not yet have materialized backing
tables are exposed as explicit unavailable responses instead of synthetic data.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation, localcontext
import json
from pathlib import Path
import sqlite3
import sys

from catos import research
from catos.market_intel import MarketIntelError, SCHEMA_VERSION


SUPPORTED_VIEWS = frozenset(("flow", "momentum", "opportunity", "risk", "history"))
SIGNAL_EVENT_FAMILIES = frozenset((
    "signal", "pattern", "flow", "onchain", "lifecycle", "status", "candidate",
))
KLINE_TIMEFRAMES = {
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}
MONEY_FLOW_WINDOWS = {
    "5m": 300_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "24h": 86_400_000,
}


def inspect_database(path):
    """Read only the market DB header needed for startup compatibility checks."""
    resolved = Path(path).resolve()
    result = {
        "path": str(resolved),
        "expected_schema": SCHEMA_VERSION,
        "actual_schema": None,
        "format": None,
        "read_only": True,
    }
    if not resolved.is_file():
        return {**result, "status": "market_intel_not_found"}
    uri = f"file:{resolved.as_posix()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=0.25)
        try:
            connection.execute("PRAGMA query_only=ON")
            result["actual_schema"] = connection.execute("PRAGMA user_version").fetchone()[0]
            try:
                metadata = connection.execute(
                    "SELECT format FROM metadata WHERE id=1").fetchone()
            except sqlite3.Error:
                metadata = None
            result["format"] = None if metadata is None else metadata[0]
        finally:
            connection.close()
    except sqlite3.Error:
        return {**result, "status": "database_unreadable"}
    if result["actual_schema"] != SCHEMA_VERSION:
        return {**result, "status": "unsupported_schema"}
    if result["format"] != "catos-market-intel-v1":
        return {**result, "status": "metadata_mismatch"}
    return {**result, "status": "ready"}


def _symbol(value: str) -> str:
    if type(value) is not str or not value.endswith("-USDT-SWAP"):
        raise ValueError("invalid_symbol")
    return value


def _limit(value: int) -> int:
    if type(value) is not int or not 1 <= value <= 1000:
        raise ValueError("invalid_limit")
    return value


def _timeframe(value: str) -> str:
    if type(value) is not str or value not in KLINE_TIMEFRAMES:
        raise ValueError("invalid_timeframe")
    return value


def _signal_family(value: str) -> str:
    if type(value) is not str or value not in SIGNAL_EVENT_FAMILIES:
        raise ValueError("invalid_signal_family")
    return value


def _signal_view(value: str) -> str:
    if type(value) is not str or value not in SUPPORTED_VIEWS:
        raise ValueError("invalid_signal_view")
    return value


def _signal_window(since_ms, until_ms):
    for value in (since_ms, until_ms):
        if value is not None and (type(value) is not int or not 0 <= value <= 2**63 - 1):
            raise ValueError("invalid_signal_window")
    if since_ms is not None and until_ms is not None and since_ms > until_ms:
        raise ValueError("invalid_signal_window")
    return since_ms, until_ms


def _option_family(value: str) -> str:
    from catos.market_options import PublicOptionError, option_family
    try:
        return option_family(value)
    except PublicOptionError as error:
        raise ValueError(str(error)) from None


def _decode_json(value, code):
    if value is None:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        raise MarketIntelError(code) from None


def _stored_decimal(value):
    if value is None:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise MarketIntelError("stored_snapshot_invalid") from None


def _since_return_text(current_price_text, first_push_price_text):
    """Return first-push-to-current percentage using Decimal-only materialized inputs."""
    current = _stored_decimal(current_price_text)
    first = _stored_decimal(first_push_price_text)
    if current is None or first is None:
        return None
    if current <= 0 or first <= 0:
        raise MarketIntelError("stored_snapshot_invalid")
    with localcontext(research._CONTEXT):
        return str((current - first) * Decimal("100") / first)


def _cost_reference_window(rows, required_bars):
    if len(rows) < required_bars:
        return {
            "status": "missing",
            "missing_reason": "insufficient_contiguous_4h_candles",
            "required_bars": required_bars,
            "available_bars": len(rows),
            "cost_text": None,
            "distance_from_latest_close_pct_text": None,
        }
    selected = rows[-required_bars:]
    volume_units = {row["volume_unit"] for row in selected if row["volume_unit"] is not None}
    if len(volume_units) != 1 or any(row["volume_text"] is None for row in selected):
        return {
            "status": "missing",
            "missing_reason": "volume_basis_incomplete_or_inconsistent",
            "required_bars": required_bars,
            "available_bars": len(rows),
            "cost_text": None,
            "distance_from_latest_close_pct_text": None,
        }
    total_volume = Decimal("0")
    weighted_close = Decimal("0")
    with localcontext(research._CONTEXT):
        for row in selected:
            close = _stored_decimal(row["close_text"])
            volume = _stored_decimal(row["volume_text"])
            if close is None or volume is None or close <= 0 or volume < 0:
                raise MarketIntelError("stored_snapshot_invalid")
            total_volume += volume
            weighted_close += close * volume
        if total_volume <= 0:
            return {
                "status": "missing",
                "missing_reason": "nonpositive_total_volume",
                "required_bars": required_bars,
                "available_bars": len(rows),
                "cost_text": None,
                "distance_from_latest_close_pct_text": None,
            }
        cost = weighted_close / total_volume
        latest_close = _stored_decimal(selected[-1]["close_text"])
        distance = (latest_close - cost) * Decimal("100") / cost
    return {
        "status": "materialized",
        "missing_reason": None,
        "required_bars": required_bars,
        "available_bars": len(rows),
        "bars_used": required_bars,
        "volume_unit": next(iter(volume_units)),
        "window_start_ms": selected[0]["open_time_ms"],
        "window_end_ms": selected[-1]["open_time_ms"] + KLINE_TIMEFRAMES["4h"],
        "cost_text": str(cost),
        "latest_close_text": selected[-1]["close_text"],
        "distance_from_latest_close_pct_text": str(distance),
    }


class MarketIntelReader:
    """Open a fresh SQLite read-only connection for each query."""

    def __init__(self, path):
        self.path = Path(path).resolve()
        if not self.path.is_file():
            raise MarketIntelError("market_intel_not_found")
        with self._connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            metadata = connection.execute("SELECT format FROM metadata WHERE id=1").fetchone()
            if version != SCHEMA_VERSION:
                raise MarketIntelError("unsupported_schema")
            if metadata is None or metadata[0] != "catos-market-intel-v1":
                raise MarketIntelError("metadata_mismatch")

    @contextmanager
    def _connect(self):
        uri = f"file:{self.path.as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=0.25)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            yield connection
        finally:
            connection.close()

    def _rows(self, sql, params=()):
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def _row(self, sql, params=()):
        with self._connect() as connection:
            row = connection.execute(sql, params).fetchone()
            return None if row is None else dict(row)

    @staticmethod
    def _decode(row, *fields):
        if row is None:
            return None
        decoded = dict(row)
        for field in fields:
            if field in decoded:
                decoded[field] = _decode_json(decoded[field], "stored_snapshot_invalid")
        return decoded

    def exists(self, symbol):
        _symbol(symbol)
        return self._row("SELECT symbol FROM instrument WHERE symbol=?", (symbol,)) is not None

    def radar(self, limit=200):
        limit = _limit(limit)
        rows = self._rows(
            """SELECT i.symbol,i.active,m.observed_at_ms,m.price_text,m.volume_24h_text,
                      m.change_1h_text,m.change_24h_text,m.market_cap_text,m.source_health_json
               FROM instrument AS i
               LEFT JOIN market_snapshot AS m
                 ON m.symbol=i.symbol
                AND m.observed_at_ms=(SELECT MAX(m2.observed_at_ms) FROM market_snapshot AS m2
                                      WHERE m2.symbol=i.symbol)
               WHERE i.active=1
               ORDER BY m.observed_at_ms DESC,i.symbol ASC LIMIT ?""",
            (limit,),
        )
        return {
            "status": "materialized_unranked",
            "ranking": None,
            "items": [self._decode(row, "source_health_json") for row in rows],
        }

    def picks(self, view, limit=100):
        if view not in SUPPORTED_VIEWS:
            raise ValueError("invalid_view")
        limit = _limit(limit)
        if view == "momentum":
            return self.momentum(limit)
        if view == "history":
            from catos.market_proof import history_flat_rule_versions
            rows = self._rows(
                """SELECT * FROM cycle WHERE ended_at_ms IS NOT NULL
                   ORDER BY ended_at_ms DESC,cycle_id ASC LIMIT ?""",
                (limit,),
            )
            rules = history_flat_rule_versions()
            return {
                "view": view,
                "status": "materialized",
                "items": rows,
                "flat_rule_versions": [
                    {
                        "version": rule.version,
                        "threshold_pct": str(rule.threshold_pct),
                        "effective_from": (
                            None if rule.effective_from is None else rule.effective_from.isoformat()),
                        "effective_until": (
                            None if rule.effective_until is None else rule.effective_until.isoformat()),
                    }
                    for rule in rules
                ],
                "flat_item_classification": None,
                "flat_item_classification_status": "source_date_timezone_not_published",
                "result_semantics": {
                    "mfe": "captured_excursion",
                    "hold_until_exit": "separate_realized_history_result",
                },
            }
        rows = self._rows(
            """SELECT v.* FROM view_state AS v
               WHERE v.view_name=?
                 AND v.observed_at_ms=(SELECT MAX(v2.observed_at_ms) FROM view_state AS v2
                                       WHERE v2.symbol=v.symbol AND v2.view_name=v.view_name)
               ORDER BY v.observed_at_ms DESC,v.symbol ASC LIMIT ?""",
            (view, limit),
        )
        return {
            "view": view,
            "status": "materialized",
            "items": [self._decode(row, "evidence_json") for row in rows],
        }

    def momentum(self, limit=100):
        """Compose the published Momentum inputs without inventing a score or Funnel state."""
        limit = _limit(limit)
        scans = self._rows(
            """SELECT s.symbol,MAX(s.observed_at_ms) AS observed_at_ms
               FROM signal_state AS s
               JOIN instrument AS i ON i.symbol=s.symbol AND i.active=1
               GROUP BY s.symbol
               ORDER BY observed_at_ms DESC,s.symbol ASC LIMIT ?""",
            (limit,),
        )
        all_states = self._rows(
            """SELECT s.* FROM signal_state AS s
               JOIN instrument AS i ON i.symbol=s.symbol AND i.active=1
               WHERE s.observed_at_ms=(SELECT MAX(s2.observed_at_ms) FROM signal_state AS s2
                                       WHERE s2.symbol=s.symbol)
               ORDER BY s.symbol ASC,s.signal_version ASC,s.signal_type ASC"""
        )
        all_smf = self._rows(
            """SELECT s.* FROM smf_snapshot AS s
               JOIN instrument AS i ON i.symbol=s.symbol AND i.active=1
               WHERE s.observed_at_ms=(SELECT MAX(s2.observed_at_ms) FROM smf_snapshot AS s2
                                       WHERE s2.symbol=s.symbol)
               ORDER BY s.symbol ASC,s.model_version ASC"""
        )
        all_cross_axis = self._rows(
            """SELECT e.* FROM cross_axis_evaluation AS e
               JOIN instrument AS i ON i.symbol=e.symbol AND i.active=1
               WHERE e.observed_at_ms=(SELECT MAX(e2.observed_at_ms) FROM cross_axis_evaluation AS e2
                                       WHERE e2.symbol=e.symbol)
               ORDER BY e.symbol ASC,e.cross_axis_version ASC,e.axis_type ASC"""
        )
        all_status_labels = self._rows(
            """SELECT s.* FROM status_label_snapshot AS s
               JOIN instrument AS i ON i.symbol=s.symbol AND i.active=1
               WHERE s.observed_at_ms=(SELECT MAX(s2.observed_at_ms) FROM status_label_snapshot AS s2
                                       WHERE s2.symbol=s.symbol)
               ORDER BY s.symbol ASC,s.label_version ASC,s.label_type ASC"""
        )
        states_by_symbol = {}
        for row in all_states:
            states_by_symbol.setdefault(row["symbol"], []).append(row)
        smf_by_symbol = {}
        for row in all_smf:
            smf_by_symbol[row["symbol"]] = row
        cross_axis_by_symbol = {}
        for row in all_cross_axis:
            cross_axis_by_symbol.setdefault(row["symbol"], []).append(row)
        status_labels_by_symbol = {}
        for row in all_status_labels:
            status_labels_by_symbol.setdefault(row["symbol"], []).append(row)
        items = []
        for scan in scans:
            symbol = scan["symbol"]
            observed_at_ms = scan["observed_at_ms"]
            states = [row for row in states_by_symbol.get(symbol, ())
                      if row["observed_at_ms"] == observed_at_ms]
            decoded_states = [self._decode(
                row, "evidence_json", "threshold_json", "source_snapshot_ids_json") for row in states]
            smf = smf_by_symbol.get(symbol)
            versions = sorted({row["signal_version"] for row in states})
            items.append({
                "symbol": symbol,
                "observed_at_ms": observed_at_ms,
                "score": None,
                "score_contract": "no_independent_momentum_score",
                "smf": self._decode(smf, "component_json"),
                "l2_states": decoded_states,
                "l2_state_count": len(decoded_states),
                "l2_versions": versions,
                "cross_axis": [self._decode(
                    row, "evidence_json", "threshold_json", "source_snapshot_ids_json")
                    for row in cross_axis_by_symbol.get(symbol, ())],
                "status_labels": [self._decode(
                    row, "evidence_json", "threshold_json", "source_snapshot_ids_json")
                    for row in status_labels_by_symbol.get(symbol, ())],
                "funnel": {
                    "status": "not_materialized",
                    "reason": "yaozi_funnel_contract_unpublished",
                },
            })
        return {
            "view": "momentum",
            "status": "materialized_partial",
            "ranking": None,
            "reason": "smf_and_l2_materialized_funnel_unknown",
            "items": items,
        }

    def cross_axis(self, limit=200, symbol=None):
        limit = _limit(limit)
        if symbol is not None:
            _symbol(symbol)
        clause = "" if symbol is None else "AND e.symbol=?"
        params = () if symbol is None else (symbol,)
        rows = self._rows(
            f"""SELECT e.* FROM cross_axis_evaluation AS e
                WHERE e.observed_at_ms=(SELECT MAX(e2.observed_at_ms) FROM cross_axis_evaluation AS e2
                                        WHERE e2.symbol=e.symbol)
                  {clause}
                ORDER BY e.observed_at_ms DESC,e.symbol ASC,e.axis_type ASC LIMIT ?""",
            (*params, limit),
        )
        return {
            "status": "materialized_unranked" if rows else "materialized_empty",
            "ranking": None,
            "yaozi_formula_status": "published_cross_axis_rules_only",
            "items": [self._decode(
                row, "evidence_json", "threshold_json", "source_snapshot_ids_json") for row in rows],
        }

    def status_labels(self, limit=200, symbol=None):
        limit = _limit(limit)
        if symbol is not None:
            _symbol(symbol)
        clause = "" if symbol is None else "AND s.symbol=?"
        params = () if symbol is None else (symbol,)
        rows = self._rows(
            f"""SELECT s.* FROM status_label_snapshot AS s
                WHERE s.observed_at_ms=(SELECT MAX(s2.observed_at_ms) FROM status_label_snapshot AS s2
                                        WHERE s2.symbol=s.symbol)
                  {clause}
                ORDER BY s.observed_at_ms DESC,s.symbol ASC,s.label_type ASC LIMIT ?""",
            (*params, limit),
        )
        return {
            "status": "materialized" if rows else "materialized_empty",
            "derivation": "caller_explicit_source_state_only",
            "yaozi_private_gate_status": "unknown_unpublished",
            "items": [self._decode(
                row, "evidence_json", "threshold_json", "source_snapshot_ids_json") for row in rows],
        }

    def today(self, limit=50):
        """catOS P0 latest-materialized aggregate; not a reverse-engineered Yaozi Today formula."""
        limit = _limit(limit)
        return {
            "surface": "today",
            "status": "materialized_catos_latest",
            "contract_version": "catos-p0-today-v2",
            "yaozi_contract": "unverified",
            "time_semantics": "latest_materialized_no_wall_clock",
            "since_contract": "active_cycle_first_push_to_latest_materialized_price",
            "radar": self.radar(limit),
            "views": {
                "flow": self.picks("flow", limit),
                "momentum": self.picks("momentum", limit),
                "opportunity": self.picks("opportunity", limit),
                "risk": self.picks("risk", limit),
            },
            "holdings": self.holdings(limit),
            "signals": self.signals(limit),
            "proof": self.proof(limit),
        }

    def decision_surface(self, limit=20):
        """Aggregate materialized facts into the deterministic v0.2 decision surface."""
        from catos.market_decision import build_decision_surface

        limit = _limit(limit)
        market_rows = self._rows(
            """SELECT m.* FROM market_snapshot AS m
               JOIN instrument AS i ON i.symbol=m.symbol AND i.active=1
               WHERE m.observed_at_ms=(
                   SELECT MAX(m2.observed_at_ms) FROM market_snapshot AS m2
                   WHERE m2.symbol=m.symbol)
               ORDER BY m.symbol ASC"""
        )
        derivative_rows = self._rows(
            """SELECT d.* FROM derivative_snapshot AS d
               JOIN instrument AS i ON i.symbol=d.symbol AND i.active=1
               WHERE d.observed_at_ms=(
                   SELECT MAX(d2.observed_at_ms) FROM derivative_snapshot AS d2
                   WHERE d2.symbol=d.symbol)
               ORDER BY d.symbol ASC"""
        )
        flow_rows = self._rows(
            """SELECT f.* FROM flow_snapshot AS f
               JOIN instrument AS i ON i.symbol=f.symbol AND i.active=1
               WHERE f.observed_at_ms=(
                   SELECT MAX(f2.observed_at_ms) FROM flow_snapshot AS f2
                   WHERE f2.symbol=f.symbol)
               ORDER BY f.symbol ASC"""
        )
        capital_flow_rows = [
            self._decode(row, "evidence_json", "source_snapshot_ids_json")
            for row in self._rows(
                """SELECT e.* FROM capital_flow_event AS e
                   JOIN instrument AS i ON i.symbol=e.symbol AND i.active=1
                   WHERE e.event_type IN ('inflow','outflow')
                     AND e.observed_at_ms=(
                         SELECT MAX(e2.observed_at_ms) FROM capital_flow_event AS e2
                         WHERE e2.symbol=e.symbol
                           AND e2.event_type IN ('inflow','outflow'))
                   ORDER BY e.symbol ASC,e.event_id ASC"""
            )
        ]
        view_rows = [
            self._decode(row, "evidence_json")
            for row in self._rows(
                """SELECT v.* FROM view_state AS v
                   JOIN instrument AS i ON i.symbol=v.symbol AND i.active=1
                   WHERE v.view_name IN ('opportunity','risk')
                     AND v.observed_at_ms=(
                         SELECT MAX(v2.observed_at_ms) FROM view_state AS v2
                         WHERE v2.symbol=v.symbol AND v2.view_name=v.view_name)
                   ORDER BY v.symbol ASC,v.view_name ASC"""
            )
        ]
        return build_decision_surface(
            market_rows=market_rows,
            derivative_rows=derivative_rows,
            flow_rows=flow_rows,
            capital_flow_rows=capital_flow_rows,
            view_rows=view_rows,
            source_coverage=self.source_coverage(1000),
            limit=limit,
        )

    def symbol_decision(self, symbol):
        """Return the v0.3 decision projection for one known instrument."""
        from catos.market_decision import build_symbol_decision

        _symbol(symbol)
        if not self.exists(symbol):
            return None
        return build_symbol_decision(self.decision_surface(1000), symbol)

    def decision_compare(self, limit=20):
        """Return the v0.4 watchlist-ranked side-by-side decision comparison."""
        from catos.market_decision import build_decision_compare

        limit = _limit(limit)
        return build_decision_compare(self.decision_surface(limit), limit)

    def holdings(self, limit=100):
        """Expose only genuinely active lifecycle cycles as tracked holdings."""
        limit = _limit(limit)
        rows = self._rows(
            """SELECT c.*,m.price_text,m.change_24h_text
               FROM cycle AS c
               LEFT JOIN market_snapshot AS m
                 ON m.symbol=c.symbol
                AND m.observed_at_ms=(SELECT MAX(m2.observed_at_ms) FROM market_snapshot AS m2
                                      WHERE m2.symbol=c.symbol)
               WHERE c.ended_at_ms IS NULL
               ORDER BY c.latest_push_at_ms DESC,c.symbol ASC LIMIT ?""",
            (limit,),
        )
        for row in rows:
            row["since_return_text"] = _since_return_text(
                row.get("price_text"), row.get("first_push_price_text"))
            row["since_contract"] = "first_push_to_latest_materialized_price"
        return {"status": "materialized_active_cycles", "items": rows}

    def kline_workbench(self, symbol, limit=200, timeframe=None):
        """Read raw closed candles for the five documented YAOZI chart timeframes."""
        _symbol(symbol)
        limit = _limit(limit)
        if timeframe is not None:
            timeframe = _timeframe(timeframe)
        if not self.exists(symbol):
            return None

        requested = (timeframe,) if timeframe is not None else tuple(KLINE_TIMEFRAMES)
        series = []
        for interval in requested:
            rows = self._rows(
                """SELECT venue,symbol,interval,open_time_ms,timeframe_ms,
                          open_text,high_text,low_text,close_text,volume_text,volume_unit,closed
                   FROM (
                       SELECT venue,symbol,interval,open_time_ms,timeframe_ms,
                              open_text,high_text,low_text,close_text,volume_text,volume_unit,closed
                       FROM market_candle
                       WHERE symbol=? AND interval=? AND closed=1
                       ORDER BY open_time_ms DESC,venue ASC
                       LIMIT ?
                   )
                   ORDER BY open_time_ms ASC,venue ASC""",
                (symbol, interval, limit),
            )
            expected_ms = KLINE_TIMEFRAMES[interval]
            issues = []
            for row in rows:
                row["closed"] = row["closed"] == 1
                if row["timeframe_ms"] != expected_ms:
                    issues.append("stored_timeframe_ms_mismatch")
            series.append({
                "timeframe": interval,
                "timeframe_ms": expected_ms,
                "status": (
                    "materialized_inconsistent" if issues else
                    "materialized" if rows else
                    "missing"
                ),
                "missing_reason": None if rows else "no_closed_candles_materialized",
                "available_venues": sorted({row["venue"] for row in rows}),
                "issues": sorted(set(issues)),
                "items": rows,
            })

        materialized = sum(bool(item["items"]) for item in series)
        status = (
            "materialized" if materialized == len(series) else
            "materialized_empty" if materialized == 0 else
            "materialized_partial"
        )
        cost_reference = self._cost_reference(symbol)
        return {
            "symbol": symbol,
            "status": status,
            "closed_only": True,
            "timeframes": series,
            "derived_indicators": None,
            "cost_reference": cost_reference,
            "yaozi_overlay_status": "unknown_unpublished",
            "ranking": None,
        }

    def _cost_reference(self, symbol):
        """Build a transparent CatOS cost proxy from persisted closed 4h candles only."""
        rows = self._rows(
            """SELECT venue,open_time_ms,timeframe_ms,close_text,volume_text,volume_unit
               FROM market_candle
               WHERE symbol=? AND interval='4h' AND closed=1
               ORDER BY venue ASC,open_time_ms ASC""",
            (symbol,),
        )
        by_venue = {}
        expected_ms = KLINE_TIMEFRAMES["4h"]
        for row in rows:
            if row["timeframe_ms"] != expected_ms:
                continue
            by_venue.setdefault(row["venue"], []).append(row)

        candidates = []
        for venue, venue_rows in by_venue.items():
            tail = []
            for row in reversed(venue_rows):
                if not tail or tail[-1]["open_time_ms"] - row["open_time_ms"] == expected_ms:
                    tail.append(row)
                else:
                    break
            tail.reverse()
            priority = 0 if venue.lower() == "okx" else 1 if venue.lower() == "binance" else 2
            candidates.append((len(tail), -priority, venue, tail))

        if not candidates:
            return {
                "contract": "catos-closed-candle-cost-reference-v1",
                "status": "missing",
                "method": "volume_weighted_close_over_trailing_contiguous_4h_candles",
                "venue": None,
                "yaozi_equivalence_status": "not_claimed_private_formula_unpublished",
                "holder_share_status": "not_materialized_no_verified_holder_source",
                "windows": {
                    "7d": _cost_reference_window([], 42),
                    "30d": _cost_reference_window([], 180),
                },
            }
        _, _, venue, tail = max(candidates, key=lambda item: (item[0], item[1], item[2]))
        windows = {
            "7d": _cost_reference_window(tail, 42),
            "30d": _cost_reference_window(tail, 180),
        }
        materialized_count = sum(item["status"] == "materialized" for item in windows.values())
        return {
            "contract": "catos-closed-candle-cost-reference-v1",
            "status": (
                "materialized" if materialized_count == len(windows) else
                "missing" if materialized_count == 0 else
                "materialized_partial"
            ),
            "method": "volume_weighted_close_over_trailing_contiguous_4h_candles",
            "venue": venue,
            "contiguous_4h_bars": len(tail),
            "yaozi_equivalence_status": "not_claimed_private_formula_unpublished",
            "holder_share_status": "not_materialized_no_verified_holder_source",
            "windows": windows,
        }

    def single_coin(self, symbol):
        _symbol(symbol)
        instrument = self._row("SELECT * FROM instrument WHERE symbol=?", (symbol,))
        if instrument is None:
            return None
        market = self._row(
            "SELECT * FROM market_snapshot WHERE symbol=? ORDER BY observed_at_ms DESC LIMIT 1", (symbol,))
        derivative = self._row(
            "SELECT * FROM derivative_snapshot WHERE symbol=? ORDER BY observed_at_ms DESC LIMIT 1", (symbol,))
        feature = self._row(
            "SELECT * FROM feature_snapshot WHERE symbol=? ORDER BY observed_at_ms DESC LIMIT 1", (symbol,))
        flow = self._row(
            "SELECT * FROM flow_snapshot WHERE symbol=? ORDER BY observed_at_ms DESC LIMIT 1", (symbol,))
        smf = self._row(
            "SELECT * FROM smf_snapshot WHERE symbol=? ORDER BY observed_at_ms DESC LIMIT 1", (symbol,))
        views = self._rows(
            """SELECT v.* FROM view_state AS v
               WHERE v.symbol=?
                 AND v.observed_at_ms=(SELECT MAX(v2.observed_at_ms) FROM view_state AS v2
                                       WHERE v2.symbol=v.symbol AND v2.view_name=v.view_name)
               ORDER BY v.view_name ASC""",
            (symbol,),
        )
        signals = self._rows(
            "SELECT * FROM signal_hit WHERE symbol=? ORDER BY observed_at_ms DESC,signal_type ASC LIMIT 50",
            (symbol,),
        )
        signal_states = self._rows(
            """SELECT s.* FROM signal_state AS s
               WHERE s.symbol=?
                 AND s.observed_at_ms=(SELECT MAX(s2.observed_at_ms) FROM signal_state AS s2
                                       WHERE s2.symbol=s.symbol)
               ORDER BY s.signal_version ASC,s.signal_type ASC""",
            (symbol,),
        )
        patterns = self._rows(
            """SELECT p.* FROM pattern_hit AS p
               WHERE p.symbol=?
                 AND p.observed_at_ms=(SELECT MAX(p2.observed_at_ms) FROM pattern_hit AS p2
                                       WHERE p2.symbol=p.symbol AND p2.pattern_type=p.pattern_type)
               ORDER BY p.pattern_type ASC""",
            (symbol,),
        )
        cross_axis = self._rows(
            """SELECT e.* FROM cross_axis_evaluation AS e
               WHERE e.symbol=?
                 AND e.observed_at_ms=(SELECT MAX(e2.observed_at_ms) FROM cross_axis_evaluation AS e2
                                       WHERE e2.symbol=e.symbol)
               ORDER BY e.cross_axis_version ASC,e.axis_type ASC""",
            (symbol,),
        )
        status_labels = self._rows(
            """SELECT s.* FROM status_label_snapshot AS s
               WHERE s.symbol=?
                 AND s.observed_at_ms=(SELECT MAX(s2.observed_at_ms) FROM status_label_snapshot AS s2
                                       WHERE s2.symbol=s.symbol)
               ORDER BY s.label_version ASC,s.label_type ASC""",
            (symbol,),
        )
        active_cycle = self._row(
            "SELECT * FROM cycle WHERE symbol=? AND ended_at_ms IS NULL ORDER BY started_at_ms DESC LIMIT 1",
            (symbol,),
        )
        if active_cycle is not None:
            active_cycle["current_price_text"] = None if market is None else market.get("price_text")
            active_cycle["since_return_text"] = _since_return_text(
                active_cycle["current_price_text"], active_cycle.get("first_push_price_text"))
            active_cycle["since_contract"] = "first_push_to_latest_materialized_price"
        latest_push = self._row(
            "SELECT * FROM push_snapshot WHERE symbol=? ORDER BY pushed_at_ms DESC LIMIT 1", (symbol,))
        return {
            "symbol": symbol,
            "instrument": self._decode(instrument, "venues_json", "sector_json"),
            "market": self._decode(market, "source_health_json"),
            "derivative": self._decode(derivative, "concentration_json", "provenance_json"),
            "feature": self._decode(feature, "payload_json"),
            "flow": self._decode(flow, "provenance_json"),
            "smf": self._decode(smf, "component_json"),
            "views": [self._decode(row, "evidence_json") for row in views],
            "signals": [self._decode(row, "evidence_json", "threshold_json", "source_snapshot_ids_json")
                        for row in signals],
            "signal_states": [self._decode(
                row, "evidence_json", "threshold_json", "source_snapshot_ids_json")
                for row in signal_states],
            "patterns": [self._decode(row, "evidence_json") for row in patterns],
            "cross_axis": [self._decode(
                row, "evidence_json", "threshold_json", "source_snapshot_ids_json")
                for row in cross_axis],
            "status_labels": [self._decode(
                row, "evidence_json", "threshold_json", "source_snapshot_ids_json")
                for row in status_labels],
            "active_cycle": active_cycle,
            "latest_push": self._decode(latest_push, "frozen_payload_json"),
        }

    def timeline(self, symbol, limit=200):
        _symbol(symbol)
        limit = _limit(limit)
        events = []
        for row in self._rows(
                "SELECT * FROM cycle_event WHERE symbol=? ORDER BY observed_at_ms DESC LIMIT ?",
                (symbol, limit)):
            item = self._decode(row, "payload_json")
            item["kind"] = "cycle_event"
            events.append(item)
        for row in self._rows(
                "SELECT * FROM signal_hit WHERE symbol=? ORDER BY observed_at_ms DESC LIMIT ?",
                (symbol, limit)):
            item = self._decode(row, "evidence_json", "threshold_json", "source_snapshot_ids_json")
            item["kind"] = "signal_hit"
            events.append(item)
        for row in self._rows(
                "SELECT * FROM pattern_hit WHERE symbol=? ORDER BY observed_at_ms DESC LIMIT ?",
                (symbol, limit)):
            item = self._decode(row, "evidence_json")
            item["kind"] = "pattern_evaluation"
            events.append(item)
        for row in self._rows(
                "SELECT * FROM push_snapshot WHERE symbol=? ORDER BY pushed_at_ms DESC LIMIT ?",
                (symbol, limit)):
            item = self._decode(row, "frozen_payload_json")
            item["kind"] = "push_snapshot"
            item["observed_at_ms"] = item["pushed_at_ms"]
            events.append(item)
        events.sort(key=lambda item: (item["observed_at_ms"], item["kind"]), reverse=True)
        return {"symbol": symbol, "items": events[:limit]}

    def journey(self, symbol, limit=50):
        _symbol(symbol)
        limit = _limit(limit)
        cycles = self._rows(
            "SELECT * FROM cycle WHERE symbol=? ORDER BY started_at_ms DESC LIMIT ?", (symbol, limit))
        result = []
        for cycle in cycles:
            events = self._rows(
                "SELECT * FROM cycle_event WHERE cycle_id=? ORDER BY observed_at_ms ASC,event_id ASC",
                (cycle["cycle_id"],),
            )
            pushes = self._rows(
                "SELECT * FROM push_snapshot WHERE cycle_id=? ORDER BY pushed_at_ms ASC,push_id ASC",
                (cycle["cycle_id"],),
            )
            result.append({
                "cycle": cycle,
                "events": [self._decode(row, "payload_json") for row in events],
                "pushes": [self._decode(row, "frozen_payload_json") for row in pushes],
            })
        return {"symbol": symbol, "cycles": result}

    def signals(self, limit=100, symbol=None, family=None, view=None, since_ms=None, until_ms=None):
        limit = _limit(limit)
        if symbol is not None:
            _symbol(symbol)
        if family is not None:
            _signal_family(family)
        if view is not None:
            _signal_view(view)
        since_ms, until_ms = _signal_window(since_ms, until_ms)

        def rows(table, id_column, *, explicit_view=False):
            clauses = []
            params = []
            if symbol is not None:
                clauses.append("symbol=?")
                params.append(symbol)
            if since_ms is not None:
                clauses.append("observed_at_ms>=?")
                params.append(since_ms)
            if until_ms is not None:
                clauses.append("observed_at_ms<=?")
                params.append(until_ms)
            if view is not None:
                if not explicit_view:
                    return []
                clauses.append("view_name=?")
                params.append(view)
            where = "" if not clauses else " WHERE " + " AND ".join(clauses)
            params.append(limit)
            return self._rows(
                f"SELECT * FROM {table}{where} "
                f"ORDER BY observed_at_ms DESC,{id_column} ASC LIMIT ?",
                tuple(params),
            )

        families = SIGNAL_EVENT_FAMILIES if family is None else frozenset((family,))
        signal_rows = rows("signal_hit", "hit_id") if "signal" in families else []
        pattern_rows = rows("pattern_hit", "hit_id") if "pattern" in families else []
        flow_rows = rows("capital_flow_event", "event_id") if "flow" in families else []
        lifecycle_rows = rows(
            "cycle_event", "event_id", explicit_view=True) if "lifecycle" in families else []
        candidate_rows = rows(
            "public_event_candidate", "candidate_id") if "candidate" in families else []

        # These tables have composite identities rather than a single id column.
        def composite_rows(table, tie_order):
            clauses = []
            params = []
            if symbol is not None:
                clauses.append("symbol=?")
                params.append(symbol)
            if since_ms is not None:
                clauses.append("observed_at_ms>=?")
                params.append(since_ms)
            if until_ms is not None:
                clauses.append("observed_at_ms<=?")
                params.append(until_ms)
            if view is not None:
                return []
            where = "" if not clauses else " WHERE " + " AND ".join(clauses)
            params.append(limit)
            return self._rows(
                f"SELECT * FROM {table}{where} "
                f"ORDER BY observed_at_ms DESC,{tie_order} LIMIT ?",
                tuple(params),
            )

        onchain_rows = composite_rows(
            "onchain_activity", "symbol ASC,chain ASC") if "onchain" in families else []
        status_rows = composite_rows(
            "status_label_snapshot", "symbol ASC,label_type ASC,label_version ASC") \
            if "status" in families else []

        items = []

        def append(decoded, event_family, kind, source_id, event_type, route, explicit_view=None):
            decoded["family"] = event_family
            decoded["kind"] = kind
            decoded["source_id"] = source_id
            decoded["event_type"] = event_type
            decoded["view"] = explicit_view
            decoded["alert_route"] = route
            decoded["taxonomy_contract"] = "catos_source_semantic_only"
            decoded["yaozi_taxonomy_mapping_status"] = "unknown_unpublished"
            items.append(decoded)

        for row in signal_rows:
            item = self._decode(row, "evidence_json", "threshold_json", "source_snapshot_ids_json")
            append(item, "signal", "signal_hit", item["hit_id"], item["signal_type"], "signals")
        for row in pattern_rows:
            item = self._decode(row, "evidence_json")
            append(item, "pattern", "pattern_evaluation", item["hit_id"], item["pattern_type"], "signals")
        for row in flow_rows:
            item = self._decode(row, "evidence_json", "source_snapshot_ids_json")
            append(item, "flow", "capital_flow_event", item["event_id"], item["event_type"], "flow")
        for row in onchain_rows:
            item = dict(row)
            source_id = f'{item["symbol"]}:{item["chain"]}:{item["observed_at_ms"]}'
            append(item, "onchain", "onchain_activity", source_id, item["state"], "onchain")
        for row in lifecycle_rows:
            item = self._decode(row, "payload_json")
            route = "risk" if item["view_name"] == "risk" else "lifecycle"
            append(
                item, "lifecycle", "cycle_event", item["event_id"], item["event_type"], route,
                item["view_name"],
            )
        for row in status_rows:
            item = self._decode(row, "evidence_json", "threshold_json", "source_snapshot_ids_json")
            route = "risk" if item["label_type"] == "DUMP_WARNING" else "status"
            source_id = ":".join((
                item["symbol"], str(item["observed_at_ms"]), item["label_type"], item["label_version"],
            ))
            append(item, "status", "status_label_snapshot", source_id, item["label_type"], route)
        for row in candidate_rows:
            item = self._decode(
                row, "possible_yaozi_event_types_json", "evidence_json", "source_snapshot_ids_json")
            append(
                item, "candidate", "public_event_candidate", item["candidate_id"],
                item["candidate_type"], "public_evidence",
            )

        items.sort(key=lambda item: (-item["observed_at_ms"], item["family"], item["source_id"]))
        return {
            "status": "materialized" if items else "materialized_empty",
            "taxonomy_contract": "catos_source_semantic_only",
            "yaozi_taxonomy_mapping_status": "unknown_unpublished",
            "view_filter_contract": "explicit_cycle_event_view_name_only",
            "time_window_contract": "inclusive_observed_at_ms",
            "filters": {
                "family": family,
                "view": view,
                "since_ms": since_ms,
                "until_ms": until_ms,
                "symbol": symbol,
            },
            "families": sorted(SIGNAL_EVENT_FAMILIES),
            "items": items[:limit],
            "signals": [self._decode(row, "evidence_json", "threshold_json", "source_snapshot_ids_json")
                        for row in signal_rows],
            "patterns": [self._decode(row, "evidence_json") for row in pattern_rows],
            "dex_windows": ([self.signal_dex_window(symbol)] if symbol is not None
                            else self.signal_dex_windows(limit)),
        }

    def alerts(self, limit=100, symbol=None, family=None, view=None, since_ms=None, until_ms=None):
        stream = self.signals(limit, symbol, family, view, since_ms, until_ms)
        routes = {}
        for item in stream["items"]:
            routes.setdefault(item["alert_route"], []).append(item)
        return {
            "status": stream["status"],
            "contract": "read_only_projection_of_materialized_signal_events",
            "mutation_supported": False,
            "unread_state": None,
            "unread_state_status": "not_materialized",
            "taxonomy_contract": stream["taxonomy_contract"],
            "yaozi_taxonomy_mapping_status": stream["yaozi_taxonomy_mapping_status"],
            "filters": stream["filters"],
            "routes": routes,
            "items": stream["items"],
        }

    def signal_dex_window(self, symbol, end_ms=None):
        """Summarize persisted public DEX runs with explicit pool and identity coverage.

        This is a Signal/Onchain observation read model, not a Dealer FLOW axis.
        Exact quote values are parsed as Decimal in Python; SQLite never performs
        numeric coercion on the persisted TEXT values.
        """
        _symbol(symbol)
        if end_ms is None:
            latest = self._row(
                "SELECT MAX(observed_at_ms) AS observed_at_ms FROM dex_collector_run WHERE symbol=?",
                (symbol,),
            )
            end_ms = None if latest is None else latest["observed_at_ms"]
        elif type(end_ms) is not int or end_ms < 0:
            raise ValueError("invalid_end_ms")
        if end_ms is None:
            return {
                "symbol": symbol,
                "status": "materialized_empty",
                "observed_at_ms": None,
                "window_start_ms": None,
                "window_end_ms": None,
                "window_ms": 3_600_000,
                "swap_count": 0,
                "buy_count": 0,
                "sell_count": 0,
                "known_distinct_buyers": 0,
                "buy_gross_text": None,
                "sell_gross_text": None,
                "net_flow_text": None,
                "quote_currency": None,
                "coverage_status": "unavailable",
                "coverage_scope": None,
                "coverage": None,
                "net_flow_status": "missing_no_collector_run",
                "issues": ["no_dex_collector_run"],
                "source_run_id": None,
                "source_run_ids": [],
                "dealer_flow_eligible": False,
            }
        anchor = self._row(
            "SELECT MAX(observed_at_ms) AS observed_at_ms FROM dex_collector_run WHERE symbol=? AND observed_at_ms<=?",
            (symbol, end_ms),
        )
        run_observed_at_ms = None if anchor is None else anchor["observed_at_ms"]
        runs = [] if run_observed_at_ms is None else self._rows(
            """SELECT observed_at_ms,chain,source,issues_json,coverage_json FROM dex_collector_run
               WHERE symbol=? AND observed_at_ms=? ORDER BY chain ASC,source ASC""",
            (symbol, run_observed_at_ms),
        )
        start_ms = max(0, end_ms - 3_600_000)
        rows = self._rows(
            """SELECT side,quote_notional_text,quote_currency,wallet,source_ms,chain,source
               FROM dex_swap_observation
               WHERE symbol=? AND observed_at_ms<=? AND source_ms>? AND source_ms<=?
               ORDER BY source_ms ASC,source_id ASC""",
            (symbol, end_ms, start_ms, end_ms),
        )
        if runs:
            allowed = {(run["chain"], run["source"]) for run in runs}
            rows = [row for row in rows if (row["chain"], row["source"]) in allowed]
        issues = []
        coverage = None
        source_run_id = None
        source_run_ids = []
        run_coverages = []
        for run in runs:
            run_issues = _decode_json(run["issues_json"], "stored_snapshot_invalid") or []
            issues.extend(str(item[1] if isinstance(item, list) and len(item) > 1 else item)
                          for item in run_issues)
            run_coverage = None
            if run["coverage_json"] is not None:
                run_coverage = _decode_json(run["coverage_json"], "stored_snapshot_invalid")
            run_coverages.append(run_coverage)
            source_run_ids.append(
                f"dex-run:{symbol}:{run['observed_at_ms']}:{run['chain']}:{run['source']}")

        coverage_status = "unverified_window_coverage"
        coverage_scope = None
        identity_complete = True
        if len(runs) == 1:
            coverage = run_coverages[0]
            source_run_id = source_run_ids[0]
            if run_observed_at_ms == end_ms and isinstance(coverage, dict):
                coverage_status = str(coverage.get("status") or coverage_status)
                coverage_scope = coverage.get("scope")
        elif len(runs) > 1:
            coverage_scope = "multi_pool"
            chains = {run["chain"] for run in runs}
            base_tokens = [
                item.get("base_token_address") if isinstance(item, dict) else None
                for item in run_coverages
            ]
            identity_complete = (
                len(chains) == 1
                and all(type(value) is str and value for value in base_tokens)
                and len(set(base_tokens)) == 1
            )
            if len(chains) != 1:
                issues.append("cross_chain_asset_identity_unverified")
            elif not all(type(value) is str and value for value in base_tokens):
                issues.append("missing_base_token_identity")
            elif len(set(base_tokens)) != 1:
                issues.append("base_token_identity_mismatch")
            all_verified = all(
                isinstance(item, dict)
                and item.get("status") == "verified_pool_window"
                and item.get("scope") == "single_pool"
                for item in run_coverages
            )
            if not identity_complete:
                coverage_status = "unverified_asset_identity"
            elif run_observed_at_ms == end_ms and all_verified:
                coverage_status = "verified_multi_pool_window"
            elif any(isinstance(item, dict) and item.get("status") == "provider_limit_truncated"
                     for item in run_coverages):
                coverage_status = "provider_limit_truncated"
            coverage = {
                "status": coverage_status,
                "scope": coverage_scope,
                "chain": next(iter(chains)) if len(chains) == 1 else None,
                "base_token_address": base_tokens[0] if identity_complete else None,
                "run_count": len(runs),
                "sources": [run["source"] for run in runs],
                "runs": run_coverages,
            }
        elif len({row["chain"] for row in rows}) > 1:
            identity_complete = False
            issues.append("cross_chain_asset_identity_unverified")

        currencies = set()
        buy_gross = Decimal("0")
        sell_gross = Decimal("0")
        quote_complete = bool(rows)
        currency_complete = bool(rows)
        buyers = set()
        buy_count = 0
        sell_count = 0
        for row in rows:
            if row["side"] == "BUY":
                buy_count += 1
                if row["wallet"] is not None:
                    buyers.add(row["wallet"])
            else:
                sell_count += 1
            amount = _stored_decimal(row["quote_notional_text"])
            if amount is None:
                quote_complete = False
            currency = row["quote_currency"]
            if currency is None:
                currency_complete = False
            else:
                currencies.add(currency)
            if amount is not None:
                if row["side"] == "BUY":
                    buy_gross += amount
                else:
                    sell_gross += amount
        if rows and not quote_complete:
            issues.append("missing_quote_notional")
        if rows and not currency_complete:
            issues.append("missing_quote_currency")
        if len(currencies) > 1:
            issues.append("mixed_quote_currency")
        exact = (bool(rows) and identity_complete and quote_complete
                 and currency_complete and len(currencies) == 1)
        net_flow = buy_gross - sell_gross if exact else None
        currency = next(iter(currencies)) if exact else None
        if exact:
            net_status = "observed_sum"
        elif not rows:
            net_status = "missing_no_swaps"
        elif not identity_complete:
            net_status = "missing_asset_identity"
        else:
            net_status = "missing_incompatible_quote_data"
        return {
            "symbol": symbol,
            "status": "materialized_observation" if runs else "materialized_without_run",
            "observed_at_ms": end_ms,
            "window_start_ms": start_ms,
            "window_end_ms": end_ms,
            "window_ms": 3_600_000,
            "swap_count": len(rows),
            "buy_count": buy_count,
            "sell_count": sell_count,
            "known_distinct_buyers": len(buyers),
            "buy_gross_text": str(buy_gross) if exact else None,
            "sell_gross_text": str(sell_gross) if exact else None,
            "net_flow_text": str(net_flow) if net_flow is not None else None,
            "quote_currency": currency,
            "coverage_status": coverage_status,
            "coverage_scope": coverage_scope,
            "coverage": coverage,
            "net_flow_status": net_status,
            "issues": sorted(set(issues)),
            "source_run_id": source_run_id,
            "source_run_ids": source_run_ids,
            "dealer_flow_eligible": False,
        }

    def signal_dex_windows(self, limit=100):
        limit = _limit(limit)
        rows = self._rows(
            """SELECT symbol,MAX(observed_at_ms) AS observed_at_ms
               FROM dex_collector_run GROUP BY symbol
               ORDER BY observed_at_ms DESC,symbol ASC LIMIT ?""",
            (limit,),
        )
        return [self.signal_dex_window(row["symbol"], row["observed_at_ms"]) for row in rows]

    def _money_flow_cex_window(self, symbol, start_ms, end_ms):
        rows = self._rows(
            """SELECT observed_at_ms,cvd_quote_text,trade_window_start_ms,
                      trade_window_end_ms,provenance_json
               FROM flow_snapshot
               WHERE symbol=? AND trade_window_complete=1
                 AND cvd_quote_text IS NOT NULL
                 AND trade_window_start_ms>=? AND trade_window_end_ms<=?
               ORDER BY trade_window_start_ms ASC,trade_window_end_ms ASC,observed_at_ms ASC""",
            (symbol, start_ms, end_ms),
        )
        intervals = {}
        sources = {}
        for row in rows:
            key = (row["trade_window_start_ms"], row["trade_window_end_ms"])
            value = _stored_decimal(row["cvd_quote_text"])
            provenance = self._decode(row, "provenance_json")["provenance_json"]
            source = None
            if isinstance(provenance, dict):
                source = provenance.get("trade_venue") or provenance.get("source") or provenance.get("trades")
            if key in intervals and intervals[key] != value:
                return {
                    "status": "missing_conflicting_windows", "net_flow_text": None,
                    "quote_currency": "USDT", "segments": 0, "sources": [],
                }
            intervals[key] = value
            sources[key] = source

        exact = (start_ms, end_ms)
        if exact in intervals:
            source = sources.get(exact)
            return {
                "status": "complete", "net_flow_text": str(intervals[exact]),
                "quote_currency": "USDT", "segments": 1,
                "sources": [] if source is None else [str(source)],
            }

        cursor = start_ms
        total = Decimal("0")
        used_sources = set()
        segments = 0
        while cursor < end_ms:
            matches = [key for key in intervals if key[0] == cursor and key[1] <= end_ms]
            if len(matches) != 1:
                return {
                    "status": "missing_incomplete_or_ambiguous_coverage", "net_flow_text": None,
                    "quote_currency": "USDT", "segments": segments,
                    "sources": sorted(used_sources),
                }
            key = matches[0]
            total += intervals[key]
            source = sources.get(key)
            if source is not None:
                used_sources.add(str(source))
            cursor = key[1]
            segments += 1
        if cursor != end_ms or len(used_sources) > 1:
            return {
                "status": (
                    "missing_source_mismatch" if len(used_sources) > 1
                    else "missing_incomplete_or_ambiguous_coverage"),
                "net_flow_text": None, "quote_currency": "USDT",
                "segments": segments, "sources": sorted(used_sources),
            }
        return {
            "status": "complete", "net_flow_text": str(total),
            "quote_currency": "USDT", "segments": segments,
            "sources": sorted(used_sources),
        }

    def _money_flow_dex_window(self, symbol, start_ms, end_ms):
        anchor = self._row(
            "SELECT MAX(observed_at_ms) AS observed_at_ms FROM dex_collector_run "
            "WHERE symbol=? AND observed_at_ms<=?",
            (symbol, end_ms),
        )
        observed_at_ms = None if anchor is None else anchor["observed_at_ms"]
        if observed_at_ms is None:
            return {
                "status": "missing_no_collector_run", "net_flow_text": None,
                "quote_currency": None, "coverage_complete": False,
                "large_swaps": [], "issues": ["no_dex_collector_run"],
            }
        runs = self._rows(
            """SELECT chain,source,coverage_json,issues_json FROM dex_collector_run
               WHERE symbol=? AND observed_at_ms=? ORDER BY chain ASC,source ASC""",
            (symbol, observed_at_ms),
        )
        issues = []
        coverages = []
        for run in runs:
            coverage = _decode_json(run["coverage_json"], "stored_snapshot_invalid")
            coverages.append(coverage)
            run_issues = _decode_json(run["issues_json"], "stored_snapshot_invalid") or []
            issues.extend(str(item[1] if isinstance(item, list) and len(item) > 1 else item)
                          for item in run_issues)
        chains = {run["chain"] for run in runs}
        base_tokens = [item.get("base_token_address") if isinstance(item, dict) else None
                       for item in coverages]
        identity_complete = (
            bool(runs) and len(chains) == 1
            and all(type(value) is str and value for value in base_tokens)
            and len(set(base_tokens)) == 1
        )
        coverage_complete = identity_complete and all(
            isinstance(item, dict)
            and item.get("status") == "verified_pool_window"
            and item.get("scope") == "single_pool"
            and type(item.get("window_start_ms")) is int
            and type(item.get("window_end_ms")) is int
            and item["window_start_ms"] <= start_ms
            and item["window_end_ms"] >= end_ms
            for item in coverages
        )
        allowed = {(run["chain"], run["source"]) for run in runs}
        rows = self._rows(
            """SELECT source_id,side,quote_notional_text,quote_currency,tx_hash,source_ms,chain,source
               FROM dex_swap_observation
               WHERE symbol=? AND observed_at_ms<=? AND source_ms>? AND source_ms<=?
               ORDER BY source_ms ASC,source_id ASC""",
            (symbol, observed_at_ms, start_ms, end_ms),
        )
        rows = [row for row in rows if (row["chain"], row["source"]) in allowed]
        currencies = set()
        net = Decimal("0")
        exact = bool(rows) or coverage_complete
        large_swaps = []
        for row in rows:
            amount = _stored_decimal(row["quote_notional_text"])
            currency = row["quote_currency"]
            if amount is None or currency is None:
                exact = False
                issues.append("missing_quote_data")
                continue
            currencies.add(currency)
            net += amount if row["side"] == "BUY" else -amount
            if currency in ("USD", "USDT", "USDC") and amount >= Decimal("1000"):
                large_swaps.append({
                    "source_id": row["source_id"], "side": row["side"],
                    "notional_text": str(amount), "quote_currency": currency,
                    "tx_hash": row["tx_hash"], "source_ms": row["source_ms"],
                    "source": row["source"],
                })
        if len(currencies) > 1:
            exact = False
            issues.append("mixed_quote_currency")
        currency = next(iter(currencies)) if exact and len(currencies) == 1 else None
        if coverage_complete and not rows:
            currency = None
        return {
            "status": "complete" if coverage_complete and exact else "observed_partial",
            "net_flow_text": str(net) if coverage_complete and exact else None,
            "quote_currency": currency,
            "coverage_complete": bool(coverage_complete),
            "coverage_scope": "latest_configured_pools",
            "large_swaps": large_swaps,
            "issues": sorted(set(issues)),
        }

    def _money_flow_window(self, symbol, end_ms, window_ms):
        start_ms = max(0, end_ms - window_ms)
        dex = self._money_flow_dex_window(symbol, start_ms, end_ms)
        cex = self._money_flow_cex_window(symbol, start_ms, end_ms)
        if dex["status"] == "complete" and dex["net_flow_text"] is not None:
            selected_source = "DEX"
            selected = dex
        elif cex["status"] == "complete" and cex["net_flow_text"] is not None:
            selected_source = "CEX_TAKER"
            selected = cex
        else:
            selected_source = None
            selected = {"net_flow_text": None, "quote_currency": None}
        return {
            "window_start_ms": start_ms,
            "window_end_ms": end_ms,
            "window_ms": window_ms,
            "source": selected_source,
            "net_flow_text": selected["net_flow_text"],
            "quote_currency": selected["quote_currency"],
            "dex": dex,
            "cex": cex,
        }

    def money_flow(self, symbol, end_ms=None):
        """Guide-published MoneyFlow read model with coverage-safe DEX -> CEX fallback."""
        _symbol(symbol)
        if end_ms is None:
            anchors = self._row(
                """SELECT MAX(value) AS observed_at_ms FROM (
                     SELECT MAX(observed_at_ms) AS value FROM flow_snapshot WHERE symbol=?
                     UNION ALL
                     SELECT MAX(observed_at_ms) AS value FROM dex_collector_run WHERE symbol=?)""",
                (symbol, symbol),
            )
            end_ms = None if anchors is None else anchors["observed_at_ms"]
        elif type(end_ms) is not int or end_ms < 0:
            raise ValueError("invalid_end_ms")
        if end_ms is None:
            return {
                "symbol": symbol, "status": "materialized_empty", "observed_at_ms": None,
                "windows": {}, "peak_90d": None,
                "peak_90d_status": "not_materialized_no_flow_data",
                "contract": "yaozi-guide-money-flow-public-v1",
                "observation_only": True, "smf_eligible": False,
            }

        windows = {}
        for label, window_ms in MONEY_FLOW_WINDOWS.items():
            current = self._money_flow_window(symbol, end_ms, window_ms)
            previous = self._money_flow_window(symbol, max(0, end_ms - window_ms), window_ms)
            delta = None
            delta_status = "missing_previous_or_source_mismatch"
            if (current["net_flow_text"] is not None and previous["net_flow_text"] is not None
                    and current["source"] == previous["source"]
                    and current["quote_currency"] == previous["quote_currency"]):
                with localcontext(research._CONTEXT):
                    delta = (_stored_decimal(current["net_flow_text"])
                             - _stored_decimal(previous["net_flow_text"]))
                delta_status = "available"
            market = self._row(
                """SELECT market_cap_text FROM market_snapshot
                   WHERE symbol=? AND observed_at_ms<=? AND market_cap_text IS NOT NULL
                   ORDER BY observed_at_ms DESC LIMIT 1""",
                (symbol, end_ms),
            )
            ratio = None
            if current["net_flow_text"] is not None and market is not None:
                market_cap = _stored_decimal(market["market_cap_text"])
                if market_cap is not None and market_cap > 0:
                    with localcontext(research._CONTEXT):
                        ratio = _stored_decimal(current["net_flow_text"]) / market_cap
            current["delta_vs_previous_text"] = None if delta is None else str(delta)
            current["delta_status"] = delta_status
            current["flow_market_cap_ratio_text"] = None if ratio is None else str(ratio)
            windows[label] = current
        return {
            "symbol": symbol,
            "status": "materialized_partial" if any(
                item["net_flow_text"] is not None for item in windows.values()) else "materialized_missing",
            "observed_at_ms": end_ms,
            "contract": "yaozi-guide-money-flow-public-v1",
            "fallback_contract": "verified_dex_first_else_complete_cex_taker",
            "large_swap_display_threshold_usd_text": "1000",
            "large_swap_threshold_scope": "display_only_not_whale_gate",
            "windows": windows,
            "peak_90d": None,
            "peak_90d_status": "calendar_day_timezone_contract_unpublished",
            "observation_only": True,
            "smf_eligible": False,
        }

    def proof(self, limit=100, symbol=None):
        limit = _limit(limit)
        params = []
        where = ""
        if symbol is not None:
            _symbol(symbol)
            where = "WHERE p.symbol=?"
            params.append(symbol)
        params.append(limit)
        rows = self._rows(
            f"""SELECT p.*,f.horizon,f.measured_at_ms,f.return_text,f.mfe_text,f.mae_text,
                       f.market_baseline_text,f.vol_matched_baseline_text
                FROM push_snapshot AS p
                LEFT JOIN forward_return AS f ON f.push_id=p.push_id
                {where}
                ORDER BY p.pushed_at_ms DESC,p.push_id ASC LIMIT ?""",
            tuple(params),
        )
        return {"items": [self._decode(row, "frozen_payload_json") for row in rows]}

    def raw_flow(self, symbol, limit=200):
        _symbol(symbol)
        limit = _limit(limit)
        hyperliquid = self._rows(
            """SELECT * FROM hyperliquid_observation WHERE symbol=?
               ORDER BY source_ms DESC,source_id ASC LIMIT ?""", (symbol, limit))
        dex = self._rows(
            """SELECT * FROM dex_swap_observation WHERE symbol=?
               ORDER BY source_ms DESC,source_id ASC LIMIT ?""", (symbol, limit))
        return {
            "symbol": symbol,
            "hyperliquid": [self._decode(row, "provenance_json") for row in hyperliquid],
            "dex": [self._decode(row, "provenance_json") for row in dex],
            "whale_threshold": None,
            "whale_threshold_status": "unknown_unpublished",
        }

    def raw_flow_bulk(self, limit=1000):
        limit = _limit(limit)
        hyperliquid = self._rows(
            """SELECT * FROM hyperliquid_observation
               ORDER BY source_ms DESC,source_id ASC LIMIT ?""", (limit,))
        dex = self._rows(
            """SELECT * FROM dex_swap_observation
               ORDER BY source_ms DESC,source_id ASC LIMIT ?""", (limit,))
        return {
            "hyperliquid": [self._decode(row, "provenance_json") for row in hyperliquid],
            "dex": [self._decode(row, "provenance_json") for row in dex],
            "whale_threshold": None,
            "whale_threshold_status": "unknown_unpublished",
        }

    def capital_flow(self, symbol, limit=200):
        from catos.market_p1 import capital_flow_semantic_taxonomy

        _symbol(symbol)
        limit = _limit(limit)
        rows = self._rows(
            """SELECT * FROM capital_flow_event WHERE symbol=?
               ORDER BY observed_at_ms DESC,event_id ASC LIMIT ?""", (symbol, limit))
        raw = self.raw_flow(symbol, limit)
        return {
            "symbol": symbol,
            "status": "materialized" if rows else "materialized_empty",
            "score_contract": "nullable_unknown_private_formula",
            "taxonomy": capital_flow_semantic_taxonomy(),
            "events": [self._decode(row, "evidence_json", "source_snapshot_ids_json") for row in rows],
            "public_evidence": {
                "hyperliquid_observation_count": len(raw["hyperliquid"]),
                "dex_swap_count": len(raw["dex"]),
                "whale_threshold": None,
            },
        }

    def event_candidates(self, symbol=None, limit=200):
        limit = _limit(limit)
        if symbol is not None:
            _symbol(symbol)
            rows = self._rows(
                """SELECT * FROM public_event_candidate WHERE symbol=?
                   ORDER BY observed_at_ms DESC,candidate_id ASC LIMIT ?""",
                (symbol, limit),
            )
        else:
            rows = self._rows(
                """SELECT * FROM public_event_candidate
                   ORDER BY observed_at_ms DESC,candidate_id ASC LIMIT ?""",
                (limit,),
            )
        return {
            "symbol": symbol,
            "status": "materialized" if rows else "materialized_empty",
            "contract": "catos_public_event_candidate_v1",
            "promotion_contract": "evidence_only_never_auto_promote_to_yaozi_event",
            "items": [self._decode(
                row,
                "possible_yaozi_event_types_json",
                "evidence_json",
                "source_snapshot_ids_json",
            ) for row in rows],
        }

    def derivative_symbols_at(self, observed_at_ms):
        """Return the exact stored derivative symbol universe for one snapshot timestamp."""
        if type(observed_at_ms) is not int or not 0 <= observed_at_ms <= 2**63 - 1:
            raise ValueError("invalid_observed_at_ms")
        rows = self._rows(
            """SELECT symbol FROM derivative_snapshot WHERE observed_at_ms=?
               ORDER BY symbol ASC""",
            (observed_at_ms,),
        )
        return [row["symbol"] for row in rows]

    def event_candidates_for_windows(self, windows, *, limit=1000):
        """Read historical windows in one snapshot, with an explicit per-window cap.

        Windows are (symbol, inclusive_start_ms, inclusive_end_ms) tuples.
        Completeness describes stored rows only, never source/feed coverage.
        """
        limit = _limit(limit)
        if type(windows) is not list:
            raise ValueError("invalid_candidate_windows")
        for window in windows:
            if type(window) is not tuple or len(window) != 3:
                raise ValueError("invalid_candidate_windows")
            symbol, start_ms, end_ms = window
            _symbol(symbol)
            if (type(start_ms) is not int or type(end_ms) is not int
                    or not 0 <= start_ms <= end_ms <= 2**63 - 1):
                raise ValueError("invalid_candidate_windows")
        candidates = {}
        scopes = []
        with self._connect() as connection:
            connection.execute("BEGIN")
            for symbol, start_ms, end_ms in sorted(set(windows)):
                rows = connection.execute(
                    """SELECT * FROM public_event_candidate
                       WHERE symbol=? AND observed_at_ms BETWEEN ? AND ?
                       ORDER BY observed_at_ms DESC,candidate_id ASC LIMIT ?""",
                    (symbol, start_ms, end_ms, limit + 1),
                ).fetchall()
                truncated = len(rows) > limit
                for row in rows[:limit]:
                    candidates[row["candidate_id"]] = self._decode(
                        row, "possible_yaozi_event_types_json", "evidence_json",
                        "source_snapshot_ids_json",
                    )
                scopes.append({
                    "symbol": symbol,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "returned_count": min(len(rows), limit),
                    "truncated": truncated,
                })
        return {
            "items": sorted(candidates.values(), key=lambda row: (
                row["observed_at_ms"], row["candidate_id"])),
            "windows": scopes,
            "limit_per_window": limit,
            "truncated": any(scope["truncated"] for scope in scopes),
        }

    def dealer(self, symbol):
        _symbol(symbol)
        row = self._row(
            "SELECT * FROM dealer_snapshot WHERE symbol=? ORDER BY observed_at_ms DESC LIMIT 1", (symbol,))
        return {
            "symbol": symbol,
            "status": "materialized" if row is not None else "materialized_empty",
            "snapshot": self._decode(row, "position_json", "flow_json", "chip_json"),
            "direction_formula": None,
            "direction_formula_status": "unknown_unpublished",
            "flow_contract": "explicit_dealer_snapshot_only",
            "signal_dex_contract": "separate_observation_pipeline",
        }

    def onchain(self, limit=1000, symbol=None):
        limit = _limit(limit)
        params = []
        where = ""
        if symbol is not None:
            _symbol(symbol)
            where = "WHERE a.symbol=?"
            params.append(symbol)
        params.append(limit)
        rows = self._rows(
            f"""SELECT a.* FROM onchain_activity AS a
                {where}
                ORDER BY a.observed_at_ms DESC,a.symbol ASC,a.chain ASC LIMIT ?""",
            tuple(params),
        )
        linked_live = False
        if rows:
            latest = rows[0]
            run = self._row(
                """SELECT * FROM onchain_source_run
                   WHERE symbol=? AND chain=? AND observed_at_ms=? AND status='ok'
                   ORDER BY source ASC LIMIT 1""",
                (latest["symbol"], latest["chain"], latest["observed_at_ms"]),
            )
            if run is not None:
                decoded = self._decode(run, "source_scope_json")
                scope = decoded["source_scope_json"]
                linked_live = (
                    isinstance(scope, dict) and scope.get("collection_mode") == "live_public")
        return {
            "status": "materialized" if rows else "materialized_empty",
            "items": rows,
            "provider_status": (
                "materialized_live_source_run" if linked_live else "no_verified_live_source_run"),
            "plateau_contract": "published_rules_only",
            "resonance": self.resonance(limit, symbol),
        }

    def liquidity(self, limit=1000, symbol=None):
        """Read persisted public spot depth without inferring a trading signal."""
        limit = _limit(limit)
        if symbol is not None:
            _symbol(symbol)
            anchor = self._row(
                "SELECT MAX(observed_at_ms) AS observed_at_ms FROM liquidity_source_run WHERE symbol=?",
                (symbol,),
            )
            observed_at_ms = None if anchor is None else anchor["observed_at_ms"]
            if observed_at_ms is None:
                runs = []
                snapshots = []
            else:
                runs = self._rows(
                    """SELECT * FROM liquidity_source_run
                       WHERE symbol=? AND observed_at_ms=?
                       ORDER BY venue ASC,source ASC LIMIT ?""",
                    (symbol, observed_at_ms, limit),
                )
                snapshots = self._rows(
                    """SELECT * FROM liquidity_snapshot
                       WHERE symbol=? AND observed_at_ms=?
                       ORDER BY venue ASC,source ASC LIMIT ?""",
                    (symbol, observed_at_ms, limit),
                )
        else:
            observed_at_ms = None
            runs = self._rows(
                """SELECT r.* FROM liquidity_source_run AS r
                   WHERE r.observed_at_ms=(
                       SELECT MAX(r2.observed_at_ms) FROM liquidity_source_run AS r2
                       WHERE r2.source=r.source AND r2.symbol=r.symbol)
                   ORDER BY r.symbol ASC,r.venue ASC,r.source ASC LIMIT ?""",
                (limit,),
            )
            snapshots = self._rows(
                """SELECT s.* FROM liquidity_snapshot AS s
                   WHERE s.observed_at_ms=(
                       SELECT MAX(s2.observed_at_ms) FROM liquidity_snapshot AS s2
                       WHERE s2.venue=s.venue AND s2.symbol=s.symbol)
                   ORDER BY s.symbol ASC,s.venue ASC,s.source ASC LIMIT ?""",
                (limit,),
            )

        decoded_runs = [self._decode(row, "coverage_json", "issues_json") for row in runs]
        decoded_snapshots = [self._decode(row, "coverage_json") for row in snapshots]
        expected_venues = sorted({row["venue"] for row in decoded_runs})
        complete_venues = sorted({
            row["venue"] for row in decoded_snapshots
            if isinstance(row.get("coverage_json"), dict)
            and row["coverage_json"].get("status") == "complete_2pct"
        })
        all_runs_ok = bool(decoded_runs) and all(row["status"] == "ok" for row in decoded_runs)
        coverage_status = (
            "complete_configured_venues"
            if all_runs_ok and expected_venues == complete_venues
            else ("partial_configured_venues" if decoded_runs else "not_materialized")
        )
        return {
            "status": "materialized" if decoded_runs else "materialized_empty",
            "contract": "catos-spot-depth-2pct-v1",
            "symbol": symbol,
            "observed_at_ms": observed_at_ms,
            "ranking": None,
            "signal": None,
            "coverage": {
                "status": coverage_status,
                "expected_venues": expected_venues,
                "complete_venues": complete_venues,
            },
            "asymmetry_semantics": (
                "per_venue_descriptive_only_when_both_2pct_sides_are_complete"),
            "items": decoded_snapshots,
            "source_runs": decoded_runs,
        }

    def source_coverage(self, limit=500):
        """Expose latest persisted source-run diagnostics without wall-clock freshness inference."""
        limit = _limit(limit)
        items = []

        collector_runs = self._rows(
            """SELECT r.* FROM collector_run AS r
               WHERE r.observed_at_ms=(
                   SELECT MAX(r2.observed_at_ms) FROM collector_run AS r2
                   WHERE r2.symbol=r.symbol)
               ORDER BY r.symbol ASC"""
        )
        for row in collector_runs:
            decoded = self._decode(row, "issues_json")
            items.append({
                "domain": "market_collector",
                "source": None,
                "scope": decoded["symbol"],
                "observed_at_ms": decoded["observed_at_ms"],
                "status": "issues" if decoded["issues_json"] else "no_recorded_issues",
                "issues": decoded["issues_json"],
                "coverage_status": "run_boundary_only",
                "provider_identity_status": "venues_materialized_separately",
            })

        venue_market = self._rows(
            """SELECT v.* FROM venue_market_snapshot AS v
               WHERE v.observed_at_ms=(
                   SELECT MAX(v2.observed_at_ms) FROM venue_market_snapshot AS v2
                   WHERE v2.venue=v.venue AND v2.symbol=v.symbol)
               ORDER BY v.venue ASC,v.symbol ASC"""
        )
        for row in venue_market:
            items.append({
                "domain": "market_venue",
                "source": row["venue"],
                "scope": row["symbol"],
                "observed_at_ms": row["observed_at_ms"],
                "status": "snapshot_materialized",
                "issues": [],
                "coverage_status": None,
                "provider_identity_status": "venue_explicit",
            })

        venue_derivative = self._rows(
            """SELECT v.* FROM venue_derivative_snapshot AS v
               WHERE v.observed_at_ms=(
                   SELECT MAX(v2.observed_at_ms) FROM venue_derivative_snapshot AS v2
                   WHERE v2.venue=v.venue AND v2.symbol=v.symbol)
               ORDER BY v.venue ASC,v.symbol ASC"""
        )
        for row in venue_derivative:
            items.append({
                "domain": "derivative_venue",
                "source": row["venue"],
                "scope": row["symbol"],
                "observed_at_ms": row["observed_at_ms"],
                "status": "snapshot_materialized",
                "issues": [],
                "coverage_status": None,
                "provider_identity_status": "venue_explicit",
            })

        public_context = self._rows(
            """SELECT r.* FROM public_context_run AS r
               WHERE r.observed_at_ms=(
                   SELECT MAX(r2.observed_at_ms) FROM public_context_run AS r2
                   WHERE r2.source=r.source AND r2.context_kind=r.context_kind)
               ORDER BY r.context_kind ASC,r.source ASC"""
        )
        for row in public_context:
            decoded = self._decode(row, "issues_json")
            items.append({
                "domain": "public_context",
                "source": decoded["source"],
                "scope": decoded["context_kind"],
                "observed_at_ms": decoded["observed_at_ms"],
                "status": decoded["status"],
                "issues": decoded["issues_json"],
                "coverage_status": None,
                "provider_identity_status": "source_explicit",
            })

        option_runs = self._rows(
            """SELECT r.* FROM option_context_run AS r
               WHERE r.observed_at_ms=(
                   SELECT MAX(r2.observed_at_ms) FROM option_context_run AS r2
                   WHERE r2.source=r.source AND r2.inst_family=r.inst_family)
               ORDER BY r.inst_family ASC,r.source ASC"""
        )
        for row in option_runs:
            decoded = self._decode(row, "issues_json")
            items.append({
                "domain": "options",
                "source": decoded["source"],
                "scope": decoded["inst_family"],
                "observed_at_ms": decoded["observed_at_ms"],
                "status": decoded["status"],
                "issues": decoded["issues_json"],
                "coverage_status": None,
                "provider_identity_status": "source_explicit",
            })

        hyperliquid_runs = self._rows(
            """SELECT r.* FROM hyperliquid_collector_run AS r
               WHERE r.observed_at_ms=(
                   SELECT MAX(r2.observed_at_ms) FROM hyperliquid_collector_run AS r2
                   WHERE r2.symbol=r.symbol)
               ORDER BY r.symbol ASC"""
        )
        for row in hyperliquid_runs:
            decoded = self._decode(row, "issues_json")
            items.append({
                "domain": "hyperliquid",
                "source": "hyperliquid",
                "scope": decoded["symbol"],
                "observed_at_ms": decoded["observed_at_ms"],
                "status": "issues" if decoded["issues_json"] else "no_recorded_issues",
                "issues": decoded["issues_json"],
                "coverage_status": "run_boundary_only",
                "provider_identity_status": "source_explicit",
            })

        dex_runs = self._rows(
            """SELECT r.* FROM dex_collector_run AS r
               WHERE r.observed_at_ms=(
                   SELECT MAX(r2.observed_at_ms) FROM dex_collector_run AS r2
                   WHERE r2.symbol=r.symbol AND r2.chain=r.chain AND r2.source=r.source)
               ORDER BY r.symbol ASC,r.chain ASC,r.source ASC"""
        )
        for row in dex_runs:
            decoded = self._decode(row, "issues_json", "coverage_json")
            coverage = decoded["coverage_json"] if isinstance(decoded["coverage_json"], dict) else None
            items.append({
                "domain": "dex",
                "source": decoded["source"],
                "scope": f'{decoded["symbol"]}:{decoded["chain"]}',
                "observed_at_ms": decoded["observed_at_ms"],
                "status": "issues" if decoded["issues_json"] else "no_recorded_issues",
                "issues": decoded["issues_json"],
                "coverage_status": None if coverage is None else coverage.get("status"),
                "provider_identity_status": (
                    "explicit_pool_identity" if coverage is not None else "coverage_not_recorded"),
            })

        onchain_runs = self._rows(
            """SELECT r.* FROM onchain_source_run AS r
               WHERE r.observed_at_ms=(
                   SELECT MAX(r2.observed_at_ms) FROM onchain_source_run AS r2
                   WHERE r2.source=r.source AND r2.symbol=r.symbol AND r2.chain=r.chain)
               ORDER BY r.source ASC,r.symbol ASC,r.chain ASC"""
        )
        for row in onchain_runs:
            decoded = self._decode(row, "source_scope_json", "evidence_json", "issues_json")
            scope = decoded["source_scope_json"]
            evidence = decoded["evidence_json"]
            items.append({
                "domain": "onchain",
                "source": decoded["source"],
                "scope": f'{decoded["symbol"]}:{decoded["chain"]}',
                "observed_at_ms": decoded["observed_at_ms"],
                "status": decoded["status"],
                "issues": decoded["issues_json"],
                "coverage_status": (
                    evidence.get("coverage_status") if isinstance(evidence, dict) else None),
                "provider_identity_status": (
                    "explicit_live_source_scope"
                    if isinstance(scope, dict) and scope.get("collection_mode") == "live_public"
                    else "explicit_source_scope"),
            })

        liquidity_runs = self._rows(
            """SELECT r.* FROM liquidity_source_run AS r
               WHERE r.observed_at_ms=(
                   SELECT MAX(r2.observed_at_ms) FROM liquidity_source_run AS r2
                   WHERE r2.source=r.source AND r2.symbol=r.symbol)
               ORDER BY r.source ASC,r.symbol ASC"""
        )
        for row in liquidity_runs:
            decoded = self._decode(row, "coverage_json", "issues_json")
            coverage = decoded["coverage_json"]
            items.append({
                "domain": "liquidity",
                "source": decoded["source"],
                "scope": decoded["symbol"],
                "observed_at_ms": decoded["observed_at_ms"],
                "status": decoded["status"],
                "issues": decoded["issues_json"],
                "coverage_status": (
                    coverage.get("status") if isinstance(coverage, dict) else None),
                "provider_identity_status": "venue_explicit_public_orderbook",
            })

        social_runs = self._rows(
            """SELECT r.* FROM social_source_run AS r
               WHERE r.observed_at_ms=(
                   SELECT MAX(r2.observed_at_ms) FROM social_source_run AS r2
                   WHERE r2.source=r.source AND r2.symbol=r.symbol AND r2.asset_id=r.asset_id)
               ORDER BY r.source ASC,r.symbol ASC,r.asset_id ASC"""
        )
        for row in social_runs:
            decoded = self._decode(row, "issues_json")
            items.append({
                "domain": "social",
                "source": decoded["source"],
                "scope": decoded["symbol"],
                "observed_at_ms": decoded["observed_at_ms"],
                "status": decoded["status"],
                "issues": decoded["issues_json"],
                "coverage_status": (
                    "provider_reported_counts"
                    if decoded["status"] == "ok" and decoded["metric_count"] > 0
                    else "no_numeric_metric" if decoded["status"] == "empty" else None),
                "provider_identity_status": "caller_mapped_asset_id_provider_symbol_verified",
            })

        items.sort(key=lambda item: (
            -item["observed_at_ms"], item["domain"],
            "" if item["source"] is None else item["source"], item["scope"]))
        items = items[:limit]
        items.sort(key=lambda item: (
            item["domain"], "" if item["source"] is None else item["source"], item["scope"]))
        return {
            "status": "materialized" if items else "materialized_empty",
            "contract": "materialized_source_run_diagnostics_v1",
            "freshness_status": "not_evaluated_no_wall_clock",
            "live_equivalence_status": "not_inferred_from_persisted_run",
            "items": items,
            "gaps": [
                {"capability": "onchain_live_provider", "status": (
                    "source_run_schema_ready_live_not_verified"
                    if not any(
                        item["domain"] == "onchain"
                        and item["provider_identity_status"] == "explicit_live_source_scope"
                        and item["status"] == "ok"
                        for item in items)
                    else "materialized_live_source_run")},
                {"capability": "social_metric", "status": (
                    "materialized_public_count_source"
                    if any(
                        item["domain"] == "social"
                        and item["status"] == "ok"
                        and item["coverage_status"] == "provider_reported_counts"
                        for item in items)
                    else "not_materialized_or_empty")},
                {"capability": "multi_venue_liquidity", "status": (
                    "okx_binance_public_subset_materialized"
                    if {item["source"] for item in items
                        if item["domain"] == "liquidity"
                        and item["status"] == "ok"} >= {
                            "okx-spot-orderbook", "binance-spot-orderbook"}
                    else "not_materialized_or_partial")},
                {"capability": "yaozi_private_source_equivalence", "status": "unknown_unpublished"},
            ],
        }

    def social(self, limit=200, symbol=None):
        """Read latest provider-reported social counts without deriving heat or rank."""
        from catos.market_social import current_social_identity_registry

        limit = _limit(limit)
        if symbol is not None:
            symbol = _symbol(symbol)
        params = () if symbol is None else (symbol,)
        predicate = "" if symbol is None else " AND r.symbol=?"
        runs = self._rows(
            f"""SELECT r.* FROM social_source_run AS r
                 WHERE r.observed_at_ms=(
                     SELECT MAX(r2.observed_at_ms) FROM social_source_run AS r2
                     WHERE r2.source=r.source AND r2.symbol=r.symbol AND r2.asset_id=r.asset_id)
                 {predicate}
                 ORDER BY r.symbol ASC,r.source ASC,r.asset_id ASC LIMIT ?""",
            (*params, limit),
        )
        decoded_runs = [self._decode(row, "issues_json") for row in runs]

        metric_predicate = "" if symbol is None else " AND m.symbol=?"
        metrics = self._rows(
            f"""SELECT m.* FROM social_metric_snapshot AS m
                 WHERE m.observed_at_ms=(
                     SELECT MAX(r.observed_at_ms) FROM social_source_run AS r
                     WHERE r.source=m.source AND r.symbol=m.symbol AND r.asset_id=m.asset_id)
                 {metric_predicate}
                 ORDER BY m.symbol ASC,m.source ASC,m.asset_id ASC,m.metric_kind ASC LIMIT ?""",
            (*params, limit),
        )
        return {
            "status": "materialized" if decoded_runs else "materialized_empty",
            "contract": "catos-coinpaprika-social-metric-v1",
            "mapping_contract": "caller_supplied_coinpaprika_id_provider_symbol_verified",
            "metric_semantics": "provider_reported_raw_counts_only",
            "ranking": None,
            "social_heat": None,
            "yaozi_heat": None,
            "yaozi_formula_status": "unknown_unpublished",
            "identity_registry": current_social_identity_registry(),
            "items": metrics,
            "source_runs": decoded_runs,
        }

    def narrative(self, limit=200):
        limit = _limit(limit)
        rows = self._rows(
            """SELECT n.* FROM narrative_snapshot AS n
               WHERE n.source='coingecko-categories'
                 AND n.observed_at_ms=(
                   SELECT MAX(n2.observed_at_ms) FROM narrative_snapshot AS n2
                   WHERE n2.source=n.source)
               ORDER BY n.source ASC,n.name ASC,n.narrative_id ASC LIMIT ?""",
            (limit,),
        )
        return {
            "status": "materialized" if rows else "materialized_empty",
            "ranking": None,
            "yaozi_formula_status": "unknown_unpublished",
            "metric_semantics": "source_reported_only",
            "items": [self._decode(row, "top_assets_json") for row in rows],
        }

    def narrative_attention(self, limit=50):
        """Read CoinGecko trending-category membership as public attention evidence."""
        limit = _limit(limit)
        rows = self._rows(
            """SELECT n.* FROM narrative_snapshot AS n
               WHERE n.source='coingecko-trending-categories'
                 AND n.observed_at_ms=(
                     SELECT MAX(n2.observed_at_ms) FROM narrative_snapshot AS n2
                     WHERE n2.source=n.source)
               ORDER BY n.name ASC,n.narrative_id ASC LIMIT ?""",
            (limit,),
        )
        items = [self._decode(row, "top_assets_json") for row in rows]
        for item in items:
            item["source_rank"] = None
            item["social_heat"] = None
            item["yaozi_heat"] = None
        return {
            "status": "materialized_public_attention" if items else "materialized_empty",
            "source_contract": "coingecko_trending_category_membership",
            "source_rank": None,
            "social_heat": None,
            "yaozi_heat": None,
            "ranking_persisted": False,
            "yaozi_formula_status": "unknown_unpublished",
            "items": items,
        }

    def sectors(self, limit=200):
        """Expose CoinGecko category facts without reconstructing YAOZI rotation coordinates."""
        limit = _limit(limit)
        rows = self._rows(
            """SELECT n.* FROM narrative_snapshot AS n
               WHERE n.source='coingecko-categories'
                 AND n.observed_at_ms=(
                     SELECT MAX(n2.observed_at_ms) FROM narrative_snapshot AS n2
                     WHERE n2.source=n.source)
               ORDER BY n.name ASC,n.narrative_id ASC LIMIT ?""",
            (limit,),
        )
        items = []
        for row in rows:
            item = self._decode(row, "top_assets_json")
            item["relative_strength"] = None
            item["momentum"] = None
            item["rotation_position"] = None
            items.append(item)
        return {
            "status": "materialized_public_categories" if items else "materialized_empty",
            "source_contract": "coingecko_categories_source_facts",
            "ranking": None,
            "relative_strength": None,
            "momentum": None,
            "rotation_position": None,
            "yaozi_rotation_formula_status": "unknown_unpublished",
            "metric_semantics": "source_reported_market_cap_change_not_standardized_rotation",
            "items": items,
        }

    def news(self, limit=200):
        limit = _limit(limit)
        rows = self._rows(
            """SELECT n.* FROM news_event AS n
               WHERE n.observed_at_ms=(
                   SELECT MAX(n2.observed_at_ms) FROM news_event AS n2 WHERE n2.url=n.url)
               ORDER BY COALESCE(published_at_ms,observed_at_ms) DESC,news_id ASC LIMIT ?""",
            (limit,),
        )
        return {
            "status": "materialized" if rows else "materialized_empty",
            "ranking": None,
            "classification": None,
            "importance": None,
            "yaozi_formula_status": "unknown_unpublished",
            "items": [self._decode(row, "categories_json", "provenance_json") for row in rows],
        }

    def options(self, inst_family=None, limit=1000):
        limit = _limit(limit)
        if inst_family is not None:
            inst_family = _option_family(inst_family)
        summary_clause = "" if inst_family is None else "AND s.inst_family=?"
        oi_clause = "" if inst_family is None else "AND o.inst_family=?"
        params = () if inst_family is None else (inst_family,)
        summaries = self._rows(
            f"""SELECT s.* FROM option_summary_snapshot AS s
                WHERE s.observed_at_ms=(
                    SELECT MAX(s2.observed_at_ms) FROM option_summary_snapshot AS s2
                    WHERE s2.inst_family=s.inst_family)
                  {summary_clause}
                ORDER BY s.inst_family ASC,s.inst_id ASC LIMIT ?""",
            (*params, limit),
        )
        open_interest = self._rows(
            f"""SELECT o.* FROM option_open_interest_snapshot AS o
                WHERE o.observed_at_ms=(
                    SELECT MAX(o2.observed_at_ms) FROM option_open_interest_snapshot AS o2
                    WHERE o2.inst_family=o.inst_family)
                  {oi_clause}
                ORDER BY o.inst_family ASC,o.inst_id ASC LIMIT ?""",
            (*params, limit),
        )
        summary_by_id = {(row["inst_family"], row["inst_id"]): row for row in summaries}
        oi_by_id = {(row["inst_family"], row["inst_id"]): row for row in open_interest}
        items = []
        for key in sorted(set(summary_by_id) | set(oi_by_id))[:limit]:
            summary = summary_by_id.get(key)
            oi = oi_by_id.get(key)
            row = dict(summary) if summary is not None else {
                "inst_family": key[0], "inst_id": key[1], "observed_at_ms": None,
                "source_ms": None, "delta_bs_text": None, "delta_pa_text": None,
                "gamma_bs_text": None, "gamma_pa_text": None,
                "theta_bs_text": None, "theta_pa_text": None,
                "vega_bs_text": None, "vega_pa_text": None,
                "mark_vol_text": None, "bid_vol_text": None,
                "ask_vol_text": None, "fwd_px_text": None,
            }
            row["open_interest"] = oi
            items.append(row)
        run_clause = "" if inst_family is None else "AND r.inst_family=?"
        runs = self._rows(
            f"""SELECT r.* FROM option_context_run AS r
                WHERE r.observed_at_ms=(
                    SELECT MAX(r2.observed_at_ms) FROM option_context_run AS r2
                    WHERE r2.source=r.source AND r2.inst_family=r.inst_family)
                  {run_clause}
                ORDER BY r.inst_family ASC,r.source ASC""",
            params,
        )
        return {
            "status": "materialized" if items else "materialized_empty",
            "ranking": None,
            "signed_gex": None,
            "gamma_aggregation": None,
            "yaozi_gamma_formula_status": "unknown_unpublished",
            "source_semantics": "okx_public_option_facts_only",
            "items": items,
            "source_runs": [self._decode(row, "issues_json") for row in runs],
        }

    def resonance(self, limit=1000, symbol=None):
        """Materialize the published 2-of-3 resonance board without a new score."""
        limit = _limit(limit)
        if symbol is not None:
            _symbol(symbol)
        params = () if symbol is None else (symbol,)
        where_pattern = "" if symbol is None else "AND p.symbol=?"
        where_smf = "" if symbol is None else "AND s.symbol=?"
        where_chain = "" if symbol is None else "AND a.symbol=?"
        patterns = self._rows(
            f"""SELECT p.symbol,p.active,p.observed_at_ms FROM pattern_hit AS p
                WHERE p.pattern_type='COIL_BREAKOUT' {where_pattern}
                  AND p.observed_at_ms=(SELECT MAX(p2.observed_at_ms) FROM pattern_hit AS p2
                                        WHERE p2.symbol=p.symbol AND p2.pattern_type=p.pattern_type)""",
            params,
        )
        smf = self._rows(
            f"""SELECT s.symbol,s.grade,s.observed_at_ms FROM smf_snapshot AS s
                WHERE 1=1 {where_smf}
                  AND s.observed_at_ms=(SELECT MAX(s2.observed_at_ms) FROM smf_snapshot AS s2
                                        WHERE s2.symbol=s.symbol)""",
            params,
        )
        chain = self._rows(
            f"""SELECT a.* FROM onchain_activity AS a
                WHERE 1=1 {where_chain}
                  AND a.observed_at_ms=(SELECT MAX(a2.observed_at_ms) FROM onchain_activity AS a2
                                        WHERE a2.symbol=a.symbol AND a2.chain=a.chain)""",
            params,
        )
        coil_by_symbol = {row["symbol"]: bool(row["active"]) for row in patterns}
        smf_by_symbol = {row["symbol"]: row["grade"] == "S" if row["grade"] is not None else None
                         for row in smf}
        chain_by_symbol = {}
        for row in chain:
            active = row["state"] in ("ELEVATED", "FLAGGED") or row["plateau_started_at_ms"] is not None
            chain_by_symbol[row["symbol"]] = chain_by_symbol.get(row["symbol"], False) or active
        symbols = sorted(set(coil_by_symbol) | set(smf_by_symbol) | set(chain_by_symbol))
        items = []
        for item_symbol in symbols:
            components = {
                "coil": coil_by_symbol.get(item_symbol),
                "address_expansion": chain_by_symbol.get(item_symbol),
                "strong_smf": smf_by_symbol.get(item_symbol),
            }
            hit_count = sum(value is True for value in components.values())
            if hit_count < 2:
                continue
            items.append({
                "symbol": item_symbol,
                "components": components,
                "hit_count": hit_count,
                "full_resonance": hit_count == 3,
                "score": None,
            })
        return {"status": "materialized_view", "items": items[:limit], "score": None}


def create_app(db_path, *, strategy_status_provider=None, market_reader=None):
    """Create the read-only FastAPI adapter for one market-intelligence DB."""
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse
    from catos.app_shell import (
        read_strategy_status,
        render_app_shell,
        render_quant_surface,
        render_workbench_surface,
        render_yaozi_placeholder,
    )
    from catos.market_dashboard import render_dashboard

    reader = MarketIntelReader(db_path) if market_reader is None else market_reader
    app = FastAPI(title="catOS Market Intel", version="p1")

    def not_materialized(surface, phase):
        return {
            "surface": surface,
            "status": "not_materialized",
            "phase": phase,
            "items": [],
        }

    @app.get("/", response_class=HTMLResponse)
    def app_shell():
        return HTMLResponse(render_app_shell())

    @app.get("/quant", response_class=HTMLResponse)
    def quant_surface():
        return HTMLResponse(render_quant_surface(read_strategy_status(strategy_status_provider)))

    @app.get("/app/dashboard", response_class=HTMLResponse)
    def workbench_dashboard():
        return HTMLResponse(render_workbench_surface("/app/dashboard"))

    @app.get("/app/strategy", response_class=HTMLResponse)
    def workbench_strategy():
        return HTMLResponse(render_workbench_surface("/app/strategy"))

    @app.get("/app/strategy/{strategy_id}", response_class=HTMLResponse)
    def workbench_strategy_detail(strategy_id: str):
        return HTMLResponse(render_workbench_surface(f"/app/strategy/{strategy_id}"))

    @app.get("/app/bots", response_class=HTMLResponse)
    def workbench_bots():
        return HTMLResponse(render_workbench_surface("/app/bots"))

    @app.get("/app/bots/{bot_id}", response_class=HTMLResponse)
    def workbench_bot_detail(bot_id: str):
        return HTMLResponse(render_workbench_surface(f"/app/bots/{bot_id}"))

    @app.get("/app/risk", response_class=HTMLResponse)
    def workbench_risk():
        return HTMLResponse(render_workbench_surface("/app/risk"))

    @app.get("/app/logs", response_class=HTMLResponse)
    def workbench_logs():
        return HTMLResponse(render_workbench_surface("/app/logs"))

    @app.get("/app/yaozi", response_class=HTMLResponse)
    def workbench_yaozi():
        return HTMLResponse(render_workbench_surface("/app/yaozi"))

    @app.get("/app/settings", response_class=HTMLResponse)
    def workbench_settings():
        return HTMLResponse(render_workbench_surface("/app/settings"))

    @app.get("/yaozi", response_class=HTMLResponse)
    def yaozi_placeholder():
        return HTMLResponse(render_yaozi_placeholder())

    @app.get("/system/strategy-status")
    def strategy_status():
        return read_strategy_status(strategy_status_provider)

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(render_dashboard())

    @app.get("/intel/today")
    def today(limit: int = Query(default=1000, ge=1, le=1000)):
        return reader.today(limit)

    @app.get("/intel/decision-surface")
    def decision_surface(limit: int = Query(default=20, ge=1, le=100)):
        return reader.decision_surface(limit)

    @app.get("/intel/decision-surface/{symbol}")
    def symbol_decision(symbol: str):
        try:
            result = reader.symbol_decision(symbol)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        if result is None:
            raise HTTPException(status_code=404, detail="symbol_not_found")
        return result

    @app.get("/intel/decision-compare")
    def decision_compare(limit: int = Query(default=20, ge=1, le=100)):
        return reader.decision_compare(limit)

    @app.get("/intel/radar")
    def radar(limit: int = Query(default=1000, ge=1, le=1000)):
        return reader.radar(limit)

    @app.get("/intel/picks")
    def picks(view: str, limit: int = Query(default=1000, ge=1, le=1000)):
        try:
            return reader.picks(view, limit)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get("/intel/picks/{symbol}")
    def single_coin(symbol: str):
        try:
            result = reader.single_coin(symbol)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        if result is None:
            raise HTTPException(status_code=404, detail="symbol_not_found")
        return result

    @app.get("/intel/picks/{symbol}/candles")
    def candles(symbol: str, timeframe: str | None = None,
                limit: int = Query(default=200, ge=1, le=1000)):
        try:
            result = reader.kline_workbench(symbol, limit, timeframe)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        if result is None:
            raise HTTPException(status_code=404, detail="symbol_not_found")
        return result

    @app.get("/intel/picks/{symbol}/timeline")
    def timeline(symbol: str, limit: int = Query(default=200, ge=1, le=500)):
        try:
            return reader.timeline(symbol, limit)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get("/intel/picks/{symbol}/journey")
    def journey(symbol: str, limit: int = Query(default=50, ge=1, le=500)):
        try:
            return reader.journey(symbol, limit)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get("/intel/signals")
    def signals(
            limit: int = Query(default=100, ge=1, le=500),
            symbol: str | None = None,
            family: str | None = None,
            view: str | None = None,
            since_ms: int | None = None,
            until_ms: int | None = None):
        try:
            return reader.signals(limit, symbol, family, view, since_ms, until_ms)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get("/intel/alerts")
    def alerts(
            limit: int = Query(default=100, ge=1, le=500),
            symbol: str | None = None,
            family: str | None = None,
            view: str | None = None,
            since_ms: int | None = None,
            until_ms: int | None = None):
        try:
            return reader.alerts(limit, symbol, family, view, since_ms, until_ms)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get("/intel/cross-axis")
    def cross_axis(limit: int = Query(default=200, ge=1, le=1000), symbol: str | None = None):
        try:
            return reader.cross_axis(limit, symbol)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get("/intel/status-labels")
    def status_labels(limit: int = Query(default=200, ge=1, le=1000), symbol: str | None = None):
        try:
            return reader.status_labels(limit, symbol)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get("/intel/signal-dex/{symbol}")
    def signal_dex(symbol: str, end_ms: int | None = None):
        try:
            return reader.signal_dex_window(symbol, end_ms)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get("/intel/proof")
    def proof(limit: int = Query(default=100, ge=1, le=500), symbol: str | None = None):
        try:
            return reader.proof(limit, symbol)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get("/intel/raw-flow/{symbol}")
    def raw_flow(symbol: str, limit: int = Query(default=200, ge=1, le=500)):
        try:
            return reader.raw_flow(symbol, limit)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get("/intel/raw-flow")
    def raw_flow_bulk(limit: int = Query(default=1000, ge=1, le=1000)):
        return reader.raw_flow_bulk(limit)

    @app.get("/intel/capital-flow/{symbol}")
    def capital_flow(symbol: str, limit: int = Query(default=200, ge=1, le=1000)):
        try:
            return reader.capital_flow(symbol, limit)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get("/intel/event-candidates")
    def event_candidates(limit: int = Query(default=200, ge=1, le=1000)):
        return reader.event_candidates(limit=limit)

    @app.get("/intel/event-candidates/{symbol}")
    def event_candidates_symbol(symbol: str, limit: int = Query(default=200, ge=1, le=1000)):
        try:
            return reader.event_candidates(symbol, limit)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get("/intel/dealer/{symbol}")
    def dealer(symbol: str):
        try:
            return reader.dealer(symbol)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get("/intel/onchain")
    def onchain(limit: int = Query(default=1000, ge=1, le=1000)):
        return reader.onchain(limit)

    @app.get("/intel/onchain/{symbol}")
    def onchain_symbol(symbol: str, limit: int = Query(default=200, ge=1, le=1000)):
        try:
            return reader.onchain(limit, symbol)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get("/intel/source-coverage")
    def source_coverage(limit: int = Query(default=500, ge=1, le=1000)):
        return reader.source_coverage(limit)

    @app.get("/intel/social")
    def social(limit: int = Query(default=200, ge=1, le=1000)):
        return reader.social(limit=limit)

    @app.get("/intel/picks/{symbol}/social")
    def social_symbol(symbol: str, limit: int = Query(default=20, ge=1, le=1000)):
        try:
            return reader.social(limit=limit, symbol=symbol)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get("/intel/liquidity")
    def liquidity(limit: int = Query(default=1000, ge=1, le=1000)):
        return reader.liquidity(limit=limit)

    @app.get("/intel/picks/{symbol}/liquidity")
    def liquidity_symbol(symbol: str, limit: int = Query(default=20, ge=1, le=1000)):
        try:
            return reader.liquidity(limit=limit, symbol=symbol)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get("/intel/picks/{symbol}/money-flow")
    def money_flow(symbol: str, end_ms: int | None = None):
        try:
            return reader.money_flow(symbol, end_ms)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.get("/intel/narrative")
    def narrative(limit: int = Query(default=200, ge=1, le=1000)):
        return reader.narrative(limit)

    @app.get("/intel/narrative-attention")
    def narrative_attention(limit: int = Query(default=50, ge=1, le=1000)):
        return reader.narrative_attention(limit)

    @app.get("/intel/sectors")
    def sectors(limit: int = Query(default=200, ge=1, le=1000)):
        return reader.sectors(limit)

    @app.get("/intel/news")
    def news(limit: int = Query(default=200, ge=1, le=1000)):
        return reader.news(limit)

    @app.get("/intel/options")
    def options_all(limit: int = Query(default=1000, ge=1, le=1000)):
        return reader.options(limit=limit)

    @app.get("/intel/options/{underlying}")
    def options(underlying: str, limit: int = Query(default=1000, ge=1, le=1000)):
        try:
            return reader.options(underlying, limit)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    return app


def serve(db_path, *, host="127.0.0.1", port=8765):
    """Run the API only on the explicitly permitted loopback address."""
    if host != "127.0.0.1":
        raise ValueError("localhost_only")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("invalid_port")
    import uvicorn
    uvicorn.run(create_app(db_path), host=host, port=port)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Serve read-only catOS market intelligence")
    parser.add_argument("--db", default="outputs/catos-market-intel-v14.sqlite")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--check", action="store_true",
        help="read-only compatibility check; do not start the server",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    status = inspect_database(args.db)
    if args.check or status["status"] != "ready":
        print(json.dumps(status, ensure_ascii=False, sort_keys=True),
              file=sys.stdout if args.check else sys.stderr)
    if status["status"] != "ready":
        return 2
    if args.check:
        return 0
    try:
        serve(args.db, port=args.port)
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
