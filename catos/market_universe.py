"""Supervisor-owned public market-universe materializer.

This runner performs only fixed-host public GET collection and writes the
separate market_intel database. It has no credential, account or trading path.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import json
from pathlib import Path
import time

from catos.market_collectors import HTTPSPublicTransport, OKX, collect_universe_markets
from catos.market_intel import MarketIntelStore
from catos.market_signals import HIT, SignalInputs, evaluate


@dataclass(frozen=True, slots=True)
class UniverseScanSummary:
    observed_at_ms: int
    instrument_refs: int
    active_symbols: int
    materialized_symbols: int
    missing_market_symbols: int
    momentum_hits: int
    collection_issues: tuple[tuple[str, str], ...]


def scan_once(db_path, *, transport=None, observed_at_ms=None) -> UniverseScanSummary:
    """Collect and materialize one full public USDT-perpetual market snapshot."""
    if observed_at_ms is None:
        observed_at_ms = time.time_ns() // 1_000_000
    if type(observed_at_ms) is not int or observed_at_ms < 0:
        raise ValueError("invalid_observed_at_ms")
    active_transport = HTTPSPublicTransport() if transport is None else transport
    collected = collect_universe_markets(active_transport, observed_at_ms)
    active_symbols = {item.symbol for item in collected.instruments if item.active}
    materialized = 0
    missing = 0
    momentum_hits = 0
    store = MarketIntelStore(db_path)
    try:
        store.record_universe(collected.instruments, observed_at_ms)
        for batch in collected.batches:
            if not batch.markets:
                missing += 1
                continue
            store.record_public_batch(batch)
            primary = next((item for item in batch.markets if item.venue == OKX), batch.markets[0])
            bundle = evaluate(SignalInputs(
                symbol=batch.symbol,
                observed_at_ms=observed_at_ms,
                return_24h_pct=primary.change_24h_pct,
            ))
            store.record_signal_bundle(bundle)
            store.materialize_dealer_snapshot(batch.symbol, observed_at_ms)
            materialized += 1
            if bundle.signal("MOMENTUM").status == HIT:
                momentum_hits += 1
    finally:
        store.close()
    return UniverseScanSummary(
        observed_at_ms=observed_at_ms,
        instrument_refs=len(collected.instruments),
        active_symbols=len(active_symbols),
        materialized_symbols=materialized,
        missing_market_symbols=missing,
        momentum_hits=momentum_hits,
        collection_issues=collected.issues,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Materialize public catOS market universe")
    parser.add_argument("--db", default="outputs/catos-market-intel-v14.sqlite")
    parser.add_argument("--timestamp-ms", type=int)
    args = parser.parse_args(argv)
    summary = scan_once(Path(args.db), observed_at_ms=args.timestamp_ms)
    print(json.dumps(asdict(summary), ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
