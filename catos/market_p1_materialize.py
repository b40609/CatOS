"""Supervisor-owned local P1 materialization over existing public evidence.

This command performs no network I/O and owns no credential or trading path.
Opening the market-intel store applies its separate schema migration before
materializing Dealer position/flow axes from rows already present in the DB.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import json
from pathlib import Path

from catos import ipc
from catos.market_api import MarketIntelReader
from catos.market_hyperliquid import HyperliquidObservation, HyperliquidObservationBatch
from catos.market_intel import MarketIntelStore, SCHEMA_VERSION
from catos.market_p1 import (
    make_hyperliquid_activity_candidate,
    make_oi_event_candidate,
    make_public_dex_event_candidate,
)


@dataclass(frozen=True, slots=True)
class P1MaterializeSummary:
    schema_version: int
    active_symbols: int
    dealer_snapshots: int
    dealer_with_axes: int
    capital_flow_events: int
    public_event_candidates: int
    onchain_rows: int


def _stored_json(value):
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        raise ValueError("stored_snapshot_invalid") from None


def _hyperliquid_batch(store, symbol, observed_at_ms, issues_json):
    issues_raw = _stored_json(issues_json)
    if type(issues_raw) is not list or any(
            type(item) is not list or len(item) != 2
            or any(type(value) is not str for value in item)
            for item in issues_raw):
        raise ValueError("stored_snapshot_invalid")
    observations = []
    rows = store.connection.execute(
        """SELECT * FROM hyperliquid_observation
           WHERE symbol=? AND observed_at_ms=? ORDER BY source_id ASC""",
        (symbol, observed_at_ms),
    ).fetchall()
    for row in rows:
        provenance = _stored_json(row["provenance_json"])
        if type(provenance) is not dict:
            raise ValueError("stored_snapshot_invalid")
        try:
            notional = ipc.decimal_text(row["notional_text"], "stored notional", derived=True)
        except ipc.ProtocolError:
            raise ValueError("stored_snapshot_invalid") from None
        observations.append(HyperliquidObservation(
            symbol=row["symbol"], observed_at_ms=row["observed_at_ms"],
            source_ms=row["source_ms"], wallet_or_trader=row["wallet_or_trader"],
            direction=row["direction"], notional=notional,
            notional_currency=row["notional_currency"],
            position_or_flow_type=row["position_or_flow_type"], source=row["source"],
            source_id=row["source_id"], provenance=provenance,
        ))
    return HyperliquidObservationBatch(
        symbol=symbol,
        observed_at_ms=observed_at_ms,
        observations=tuple(observations),
        issues=tuple(tuple(item) for item in issues_raw),
    )


def _materialize_public_event_candidates(store):
    for row in store.connection.execute(
            "SELECT * FROM derivative_snapshot ORDER BY observed_at_ms ASC,symbol ASC").fetchall():
        candidate = make_oi_event_candidate(dict(row))
        if candidate is not None:
            store.record_public_event_candidate(candidate)

    for row in store.connection.execute(
            """SELECT symbol,observed_at_ms,issues_json FROM hyperliquid_collector_run
               ORDER BY observed_at_ms ASC,symbol ASC""").fetchall():
        batch = _hyperliquid_batch(
            store, row["symbol"], row["observed_at_ms"], row["issues_json"])
        candidate = make_hyperliquid_activity_candidate(batch)
        if candidate is not None:
            store.record_public_event_candidate(candidate)

    reader = MarketIntelReader(store.path)
    for row in store.connection.execute(
            """SELECT symbol,observed_at_ms FROM dex_collector_run
               GROUP BY symbol,observed_at_ms ORDER BY observed_at_ms ASC,symbol ASC""").fetchall():
        window = reader.signal_dex_window(row["symbol"], row["observed_at_ms"])
        candidate = make_public_dex_event_candidate(window)
        if candidate is not None:
            store.record_public_event_candidate(candidate)


def materialize_existing(db_path) -> P1MaterializeSummary:
    store = MarketIntelStore(db_path)
    try:
        symbols = [row[0] for row in store.connection.execute(
            "SELECT symbol FROM instrument WHERE active=1 ORDER BY symbol ASC").fetchall()]
        dealer_snapshots = 0
        dealer_with_axes = 0
        for symbol in symbols:
            snapshot = store.materialize_dealer_snapshot(symbol)
            dealer_snapshots += 1
            if snapshot.axis_count:
                dealer_with_axes += 1
        _materialize_public_event_candidates(store)
        capital_flow_events = store.connection.execute(
            "SELECT count(*) FROM capital_flow_event").fetchone()[0]
        public_event_candidates = store.connection.execute(
            "SELECT count(*) FROM public_event_candidate").fetchone()[0]
        onchain_rows = store.connection.execute(
            "SELECT count(*) FROM onchain_activity").fetchone()[0]
        return P1MaterializeSummary(
            schema_version=SCHEMA_VERSION,
            active_symbols=len(symbols),
            dealer_snapshots=dealer_snapshots,
            dealer_with_axes=dealer_with_axes,
            capital_flow_events=capital_flow_events,
            public_event_candidates=public_event_candidates,
            onchain_rows=onchain_rows,
        )
    finally:
        store.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Materialize P1 from existing public evidence")
    parser.add_argument("--db", default="outputs/catos-market-intel-v14.sqlite")
    args = parser.parse_args(argv)
    summary = materialize_existing(Path(args.db))
    print(json.dumps(asdict(summary), ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
