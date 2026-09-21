"""Bounded Supervisor-owned collection for public event evidence.

The runner is intentionally watchlist-based rather than a full-universe 5m
fan-out. OI uses an OKX-first two-request snapshot and the existing persistence
contract derives same-venue 5m/1h/4h deltas. Hyperliquid and GeckoTerminal are
optional public-only sources. No credentials, account endpoints, or trading
paths exist in this module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import json
from pathlib import Path
import time

from catos.market_api import MarketIntelReader
from catos.market_collectors import (
    CollectorScope,
    HTTPSPublicTransport,
    collect_oi_snapshot,
)
from catos.market_dex import (
    DexScope,
    GeckoTerminalPool,
    GeckoTerminalPublicTransport,
    collect_public_swaps,
)
from catos.market_hyperliquid import HyperliquidScope, collect_bounded_trades
from catos.market_intel import MarketIntelStore, SCHEMA_VERSION
from catos.market_narrative_news import collect_public_context
from catos.market_p1 import (
    make_dex_capital_flow_event,
    make_hyperliquid_activity_candidate,
    make_oi_event_candidate,
    make_public_dex_event_candidate,
)


OI_CADENCE_MS = 300_000


@dataclass(frozen=True, slots=True)
class EvidenceCollectionSummary:
    schema_version: int
    observed_at_ms: int
    oi_symbols: int
    oi_snapshots: int
    oi_delta_5m_available: int
    oi_candidates: int
    hyperliquid_runs: int
    hyperliquid_observations: int
    hyperliquid_candidates: int
    dex_runs: int
    dex_observations: int
    dex_candidates: int
    narrative_runs: int
    narrative_items: int
    attention_runs: int
    attention_items: int
    news_runs: int
    news_items: int
    issues: tuple[tuple[str, str], ...]


def _symbols(values, name):
    if type(values) is not tuple:
        raise ValueError(f"invalid_{name}")
    result = []
    seen = set()
    for value in values:
        CollectorScope(value, 0)
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def _dex_pools(values):
    if type(values) is not tuple or any(not isinstance(item, GeckoTerminalPool) for item in values):
        raise ValueError("invalid_dex_pools")
    return values


def _default_hyperliquid_collector(scope, *, max_frames, recv_timeout_s):
    return collect_bounded_trades(
        scope, max_frames=max_frames, recv_timeout_s=recv_timeout_s)


def _default_dex_collector(pool, observed_at_ms):
    scope = DexScope(pool.symbol, observed_at_ms, pool.chain)
    return collect_public_swaps(
        scope, GeckoTerminalPublicTransport((pool,)), source=pool.source)


def collect_once(*, db_path, symbols, observed_at_ms=None, market_transport=None,
                 hyperliquid_symbols=(), hyperliquid_collector=None,
                 hyperliquid_max_frames=20, hyperliquid_recv_timeout_s=2,
                 dex_pools=(), dex_collector=None,
                 public_context=False, public_context_get_bytes=None,
                 public_context_news_limit=100) -> EvidenceCollectionSummary:
    """Collect one bounded evidence cycle and materialize candidates immediately."""
    if observed_at_ms is None:
        observed_at_ms = time.time_ns() // 1_000_000
    if type(observed_at_ms) is not int or observed_at_ms < 0:
        raise ValueError("invalid_observed_at_ms")
    oi_symbols = _symbols(symbols, "symbols")
    hl_symbols = _symbols(hyperliquid_symbols, "hyperliquid_symbols")
    pools = _dex_pools(dex_pools)
    if type(public_context) is not bool:
        raise ValueError("invalid_public_context")
    if not oi_symbols and not hl_symbols and not pools and not public_context:
        raise ValueError("evidence_source_required")
    if type(hyperliquid_max_frames) is not int or not 1 <= hyperliquid_max_frames <= 200:
        raise ValueError("invalid_hyperliquid_max_frames")
    if (type(hyperliquid_recv_timeout_s) not in (int, float)
            or not 0 < hyperliquid_recv_timeout_s <= 30):
        raise ValueError("invalid_hyperliquid_recv_timeout")

    transport = HTTPSPublicTransport() if market_transport is None else market_transport
    if not callable(getattr(transport, "fetch", None)):
        raise ValueError("invalid_market_transport")
    hl_collect = _default_hyperliquid_collector if hyperliquid_collector is None else hyperliquid_collector
    dex_collect = _default_dex_collector if dex_collector is None else dex_collector
    if not callable(hl_collect) or not callable(dex_collect):
        raise ValueError("invalid_evidence_collector")

    issues = []
    oi_snapshots = 0
    oi_delta_5m_available = 0
    oi_candidates = 0
    hyperliquid_runs = 0
    hyperliquid_observations = 0
    hyperliquid_candidates = 0
    dex_runs = 0
    dex_observations = 0
    dex_candidates = 0
    narrative_runs = 0
    narrative_items = 0
    attention_runs = 0
    attention_items = 0
    news_runs = 0
    news_items = 0

    store = MarketIntelStore(db_path)
    try:
        for symbol in oi_symbols:
            batch = collect_oi_snapshot(CollectorScope(symbol, observed_at_ms), transport)
            issues.extend((f"oi:{symbol}:{source}", code) for source, code in batch.issues)
            if not batch.markets:
                continue
            store.record_public_batch(batch)
            row = store.connection.execute(
                "SELECT * FROM derivative_snapshot WHERE symbol=? AND observed_at_ms=?",
                (symbol, observed_at_ms),
            ).fetchone()
            if row is None:
                continue
            oi_snapshots += 1
            snapshot = dict(row)
            if snapshot["oi_delta_5m_text"] is not None:
                oi_delta_5m_available += 1
            candidate = make_oi_event_candidate(snapshot)
            if candidate is not None:
                store.record_public_event_candidate(candidate)
                oi_candidates += 1

        for symbol in hl_symbols:
            scope = HyperliquidScope(symbol, observed_at_ms)
            if hyperliquid_collector is None:
                batch = hl_collect(
                    scope,
                    max_frames=hyperliquid_max_frames,
                    recv_timeout_s=hyperliquid_recv_timeout_s,
                )
            else:
                batch = hl_collect(scope)
            store.record_hyperliquid_batch(batch)
            hyperliquid_runs += 1
            hyperliquid_observations += len(batch.observations)
            issues.extend((f"hyperliquid:{symbol}:{source}", code) for source, code in batch.issues)
            candidate = make_hyperliquid_activity_candidate(batch)
            if candidate is not None:
                store.record_public_event_candidate(candidate)
                hyperliquid_candidates += 1

        dex_symbols = set()
        for pool in pools:
            batch = dex_collect(pool, observed_at_ms)
            store.record_dex_batch(batch)
            dex_runs += 1
            dex_observations += len(batch.observations)
            dex_symbols.add(pool.symbol)
            issues.extend((f"dex:{pool.symbol}:{source}", code) for source, code in batch.issues)

        if dex_symbols:
            reader = MarketIntelReader(db_path)
            for symbol in sorted(dex_symbols):
                window = reader.signal_dex_window(symbol, observed_at_ms)
                event = make_dex_capital_flow_event(window)
                if event is not None:
                    store.record_capital_flow_event(event)
                candidate = make_public_dex_event_candidate(window)
                if candidate is not None:
                    store.record_public_event_candidate(candidate)
                    dex_candidates += 1

        if public_context:
            kwargs = {"news_limit": public_context_news_limit}
            if public_context_get_bytes is not None:
                if not callable(public_context_get_bytes):
                    raise ValueError("invalid_public_context_transport")
                kwargs["get_bytes"] = public_context_get_bytes
            narratives, attention, news = collect_public_context(store, observed_at_ms, **kwargs)
            narrative_runs = 1
            narrative_items = len(narratives.items)
            attention_runs = 1
            attention_items = len(attention.items)
            news_runs = 1
            news_items = len(news.items)
            issues.extend((f"narrative:{source}", code) for source, code in narratives.issues)
            issues.extend((f"attention:{source}", code) for source, code in attention.issues)
            issues.extend((f"news:{source}", code) for source, code in news.issues)
    finally:
        store.close()

    return EvidenceCollectionSummary(
        schema_version=SCHEMA_VERSION,
        observed_at_ms=observed_at_ms,
        oi_symbols=len(oi_symbols),
        oi_snapshots=oi_snapshots,
        oi_delta_5m_available=oi_delta_5m_available,
        oi_candidates=oi_candidates,
        hyperliquid_runs=hyperliquid_runs,
        hyperliquid_observations=hyperliquid_observations,
        hyperliquid_candidates=hyperliquid_candidates,
        dex_runs=dex_runs,
        dex_observations=dex_observations,
        dex_candidates=dex_candidates,
        narrative_runs=narrative_runs,
        narrative_items=narrative_items,
        attention_runs=attention_runs,
        attention_items=attention_items,
        news_runs=news_runs,
        news_items=news_items,
        issues=tuple(issues),
    )


def run_bounded_cadence(*, db_path, symbols, rounds,
                        hyperliquid_symbols=(), dex_pools=(),
                        market_transport=None, hyperliquid_collector=None,
                        dex_collector=None, clock_ms=None, sleeper=None,
                        public_context=False, public_context_every_rounds=3,
                        public_context_get_bytes=None, public_context_news_limit=100):
    """Run a synchronous bounded 5m cadence; never creates a background service."""
    if type(rounds) is not int or not 1 <= rounds <= 288:
        raise ValueError("invalid_rounds")
    if type(public_context) is not bool:
        raise ValueError("invalid_public_context")
    if type(public_context_every_rounds) is not int or not 1 <= public_context_every_rounds <= 288:
        raise ValueError("invalid_public_context_cadence")
    clock = (lambda: time.time_ns() // 1_000_000) if clock_ms is None else clock_ms
    sleep = time.sleep if sleeper is None else sleeper
    if not callable(clock) or not callable(sleep):
        raise ValueError("invalid_cadence_clock")
    summaries = []
    next_due = None
    for round_index in range(rounds):
        now = clock()
        if type(now) is not int or now < 0:
            raise ValueError("invalid_clock_value")
        if next_due is not None and now < next_due:
            sleep((next_due - now) / 1000)
            now = clock()
            if type(now) is not int or now < next_due:
                raise ValueError("cadence_clock_did_not_advance")
        context_due = public_context and round_index % public_context_every_rounds == 0
        if symbols == () and hyperliquid_symbols == () and dex_pools == () and not context_due:
            summary = EvidenceCollectionSummary(
                schema_version=SCHEMA_VERSION, observed_at_ms=now,
                oi_symbols=0, oi_snapshots=0, oi_delta_5m_available=0, oi_candidates=0,
                hyperliquid_runs=0, hyperliquid_observations=0, hyperliquid_candidates=0,
                dex_runs=0, dex_observations=0, dex_candidates=0,
                narrative_runs=0, narrative_items=0, attention_runs=0, attention_items=0,
                news_runs=0, news_items=0, issues=(),
            )
        else:
            summary = collect_once(
                db_path=db_path,
                symbols=symbols,
                observed_at_ms=now,
                market_transport=market_transport,
                hyperliquid_symbols=hyperliquid_symbols,
                hyperliquid_collector=hyperliquid_collector,
                dex_pools=dex_pools,
                dex_collector=dex_collector,
                public_context=context_due,
                public_context_get_bytes=public_context_get_bytes,
                public_context_news_limit=public_context_news_limit,
            )
        summaries.append(summary)
        next_due = now + OI_CADENCE_MS
    return tuple(summaries)


def _load_dex_config(path):
    if path is None:
        return ()
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if type(payload) is not list or any(type(item) is not dict for item in payload):
        raise ValueError("invalid_dex_config")
    try:
        return tuple(GeckoTerminalPool(
            symbol=item["symbol"],
            chain=item["chain"],
            network_id=item["network_id"],
            pool_address=item["pool_address"],
            venue=item["venue"],
            base_token_address=item["base_token_address"],
        ) for item in payload)
    except (KeyError, TypeError, ValueError):
        raise ValueError("invalid_dex_config") from None


def _load_watchlist_config(path):
    if path is None:
        return (), ()
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if type(payload) is not dict or set(payload) - {"symbols", "hyperliquid_symbols"}:
        raise ValueError("invalid_watchlist_config")
    symbols = payload.get("symbols", [])
    hyperliquid_symbols = payload.get("hyperliquid_symbols", [])
    if type(symbols) is not list or type(hyperliquid_symbols) is not list:
        raise ValueError("invalid_watchlist_config")
    try:
        return (
            _symbols(tuple(symbols), "symbols"),
            _symbols(tuple(hyperliquid_symbols), "hyperliquid_symbols"),
        )
    except ValueError:
        raise ValueError("invalid_watchlist_config") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Collect bounded public evidence on a 5m cadence")
    parser.add_argument("--db", default="outputs/catos-market-intel-v14.sqlite")
    parser.add_argument("--symbol", action="append", default=[])
    parser.add_argument("--hyperliquid-symbol", action="append", default=[])
    parser.add_argument("--watchlist-config")
    parser.add_argument("--dex-config")
    parser.add_argument("--public-context", action="store_true")
    parser.add_argument("--public-context-every-rounds", type=int, default=3)
    parser.add_argument("--public-context-news-limit", type=int, default=100)
    parser.add_argument("--rounds", type=int, default=1)
    args = parser.parse_args(argv)
    watchlist_symbols, watchlist_hyperliquid_symbols = _load_watchlist_config(args.watchlist_config)
    pools = _load_dex_config(args.dex_config)
    summaries = run_bounded_cadence(
        db_path=Path(args.db),
        symbols=tuple(args.symbol) + watchlist_symbols,
        rounds=args.rounds,
        hyperliquid_symbols=tuple(args.hyperliquid_symbol) + watchlist_hyperliquid_symbols,
        dex_pools=pools,
        public_context=args.public_context,
        public_context_every_rounds=args.public_context_every_rounds,
        public_context_news_limit=args.public_context_news_limit,
    )
    print(json.dumps([asdict(item) for item in summaries], ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
