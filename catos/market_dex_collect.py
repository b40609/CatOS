"""Supervisor-owned public DEX collection entry point.

Only fixed-host GeckoTerminal public GET requests are used. No credential,
private key, account endpoint, or trade path is accessed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import json
from pathlib import Path
import time

from catos.market_api import MarketIntelReader
from catos.market_dex import (
    DexScope,
    GeckoTerminalPool,
    GeckoTerminalPublicTransport,
    collect_public_swaps,
)
from catos.market_intel import MarketIntelStore, SCHEMA_VERSION
from catos.market_p1 import make_dex_capital_flow_event, make_public_dex_event_candidate


@dataclass(frozen=True, slots=True)
class DexCollectionSummary:
    schema_version: int
    symbol: str
    observed_at_ms: int
    source: str
    observation_count: int
    coverage_status: str
    coverage_scope: str | None
    net_flow_text: str | None
    quote_currency: str | None
    capital_flow_event: str | None
    public_event_candidate: str | None


def collect_geckoterminal_pool(*, db_path, symbol, chain, network_id, pool_address,
                               venue, base_token_address, observed_at_ms=None):
    observed_at_ms = time.time_ns() // 1_000_000 if observed_at_ms is None else observed_at_ms
    pool = GeckoTerminalPool(
        symbol=symbol,
        chain=chain,
        network_id=network_id,
        pool_address=pool_address,
        venue=venue,
        base_token_address=base_token_address,
    )
    scope = DexScope(symbol, observed_at_ms, chain)
    transport = GeckoTerminalPublicTransport((pool,))
    batch = collect_public_swaps(scope, transport, source=pool.source)
    store = MarketIntelStore(db_path)
    try:
        store.record_dex_batch(batch)
        window = MarketIntelReader(db_path).signal_dex_window(symbol, observed_at_ms)
        event = make_dex_capital_flow_event(window)
        if event is not None:
            store.record_capital_flow_event(event)
        candidate = make_public_dex_event_candidate(window)
        if candidate is not None:
            store.record_public_event_candidate(candidate)
        return DexCollectionSummary(
            schema_version=SCHEMA_VERSION,
            symbol=symbol,
            observed_at_ms=observed_at_ms,
            source=pool.source,
            observation_count=len(batch.observations),
            coverage_status=window["coverage_status"],
            coverage_scope=window["coverage_scope"],
            net_flow_text=window["net_flow_text"],
            quote_currency=window["quote_currency"],
            capital_flow_event=None if event is None else event.event_type,
            public_event_candidate=None if candidate is None else candidate.candidate_type,
        )
    finally:
        store.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Collect one keyless GeckoTerminal DEX pool")
    parser.add_argument("--db", default="outputs/catos-market-intel-v14.sqlite")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--chain", required=True)
    parser.add_argument("--network-id", required=True)
    parser.add_argument("--pool", required=True)
    parser.add_argument("--venue", required=True)
    parser.add_argument("--base-token", required=True)
    args = parser.parse_args(argv)
    summary = collect_geckoterminal_pool(
        db_path=Path(args.db),
        symbol=args.symbol,
        chain=args.chain,
        network_id=args.network_id,
        pool_address=args.pool,
        venue=args.venue,
        base_token_address=args.base_token,
    )
    print(json.dumps(asdict(summary), ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
