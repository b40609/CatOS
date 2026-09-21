"""SQLite persistence for market-intelligence snapshots.

This database is deliberately separate from the financial Journal. It is owned
by the Supervisor's single writer but has no cross-database atomicity claim.
"""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import sqlite3

from catos import ipc, research
from catos.market_collectors import BINANCE, OKX, InstrumentRef, PublicMarketBatch


SCHEMA_VERSION = 14


class MarketIntelError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


_SCHEMA = (
    """CREATE TABLE metadata (
       id INTEGER PRIMARY KEY CHECK(id=1), format TEXT NOT NULL CHECK(format='catos-market-intel-v1')) STRICT""",
    """CREATE TABLE instrument (
       symbol TEXT PRIMARY KEY, primary_inst_id TEXT NOT NULL, venues_json TEXT NOT NULL,
       sector_json TEXT NOT NULL, active INTEGER NOT NULL CHECK(active IN (0,1)),
       first_seen_ms INTEGER NOT NULL, updated_at_ms INTEGER NOT NULL) STRICT""",
    """CREATE TABLE collector_run (
       symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL, issues_json TEXT NOT NULL,
       PRIMARY KEY(symbol, observed_at_ms)) STRICT""",
    """CREATE TABLE venue_market_snapshot (
       venue TEXT NOT NULL, symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       source_ms INTEGER, price_text TEXT NOT NULL, volume_24h_text TEXT,
       volume_unit TEXT, change_24h_text TEXT,
       PRIMARY KEY(venue, symbol, observed_at_ms)) STRICT""",
    """CREATE TABLE venue_derivative_snapshot (
       venue TEXT NOT NULL, symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       source_ms INTEGER, oi_text TEXT, oi_unit TEXT, oi_notional_usd_text TEXT,
       funding_text TEXT, top_lsr_text TEXT, taker_buy_ratio_text TEXT,
       PRIMARY KEY(venue, symbol, observed_at_ms)) STRICT""",
    """CREATE TABLE market_snapshot (
       snapshot_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       price_text TEXT NOT NULL, volume_24h_text TEXT, change_1h_text TEXT,
       change_24h_text TEXT, market_cap_text TEXT, source_health_json TEXT NOT NULL,
       UNIQUE(symbol, observed_at_ms)) STRICT""",
    """CREATE TABLE derivative_snapshot (
       symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL, oi_text TEXT,
       oi_delta_5m_text TEXT, oi_delta_1h_text TEXT, oi_delta_4h_text TEXT,
       funding_text TEXT, top_lsr_text TEXT, taker_buy_ratio_text TEXT,
       concentration_json TEXT, provenance_json TEXT NOT NULL,
       PRIMARY KEY(symbol, observed_at_ms)) STRICT""",
    """CREATE TABLE feature_snapshot (
       symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL, feature_version TEXT NOT NULL,
       payload_json TEXT NOT NULL, PRIMARY KEY(symbol, observed_at_ms, feature_version)) STRICT""",
    """CREATE TABLE signal_hit (
       hit_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       signal_type TEXT NOT NULL, signal_version TEXT NOT NULL, evidence_json TEXT NOT NULL,
       threshold_json TEXT NOT NULL, source_snapshot_ids_json TEXT NOT NULL) STRICT""",
    """CREATE TABLE pattern_hit (
       hit_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       pattern_type TEXT NOT NULL, active INTEGER NOT NULL CHECK(active IN (0,1)),
       evidence_json TEXT NOT NULL) STRICT""",
    """CREATE TABLE smf_snapshot (
       symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL, score_text TEXT,
       grade TEXT, model_version TEXT NOT NULL, component_json TEXT,
       confidence_text TEXT, PRIMARY KEY(symbol, observed_at_ms, model_version)) STRICT""",
    """CREATE TABLE view_state (
       symbol TEXT NOT NULL, view_name TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       state TEXT NOT NULL, score_text TEXT, consecutive_count INTEGER NOT NULL,
       evidence_json TEXT NOT NULL, PRIMARY KEY(symbol, view_name, observed_at_ms)) STRICT""",
    """CREATE TABLE cycle (
       cycle_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, started_at_ms INTEGER NOT NULL,
       ended_at_ms INTEGER, first_push_price_text TEXT NOT NULL, latest_push_at_ms INTEGER NOT NULL,
       push_count INTEGER NOT NULL, peak_price_text TEXT, trough_price_text TEXT,
       mfe_text TEXT, mae_text TEXT, end_reason TEXT) STRICT""",
    """CREATE TABLE cycle_event (
       event_id TEXT PRIMARY KEY, cycle_id TEXT NOT NULL, symbol TEXT NOT NULL,
       observed_at_ms INTEGER NOT NULL, event_type TEXT NOT NULL, view_name TEXT,
       payload_json TEXT NOT NULL) STRICT""",
    """CREATE TABLE push_snapshot (
       push_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, pushed_at_ms INTEGER NOT NULL,
       push_type TEXT NOT NULL, cycle_id TEXT, frozen_payload_json TEXT NOT NULL,
       feature_version TEXT NOT NULL, signal_version TEXT NOT NULL) STRICT""",
    """CREATE TABLE forward_return (
       push_id TEXT NOT NULL, horizon TEXT NOT NULL, measured_at_ms INTEGER NOT NULL,
       return_text TEXT NOT NULL, mfe_text TEXT NOT NULL, mae_text TEXT NOT NULL,
       market_baseline_text TEXT, vol_matched_baseline_text TEXT,
       PRIMARY KEY(push_id, horizon)) STRICT""",
    """CREATE TABLE reflection_result (
       push_id TEXT NOT NULL, evaluated_at_ms INTEGER NOT NULL, cohort TEXT NOT NULL,
       metric_json TEXT NOT NULL, PRIMARY KEY(push_id, evaluated_at_ms, cohort)) STRICT""",
)

_SCHEMA_V2 = (
    """CREATE TABLE market_candle (
       venue TEXT NOT NULL, symbol TEXT NOT NULL, interval TEXT NOT NULL,
       open_time_ms INTEGER NOT NULL, timeframe_ms INTEGER NOT NULL,
       open_text TEXT NOT NULL, high_text TEXT NOT NULL, low_text TEXT NOT NULL, close_text TEXT NOT NULL,
       volume_text TEXT, volume_unit TEXT, closed INTEGER NOT NULL CHECK(closed=1),
       PRIMARY KEY(venue,symbol,interval,open_time_ms)) STRICT""",
    """CREATE TABLE flow_snapshot (
       symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       cvd_quote_text TEXT, taker_buy_ratio_text TEXT, trade_count INTEGER,
       trade_window_start_ms INTEGER, trade_window_end_ms INTEGER,
       trade_window_complete INTEGER NOT NULL CHECK(trade_window_complete IN (0,1)),
       provenance_json TEXT NOT NULL, PRIMARY KEY(symbol,observed_at_ms)) STRICT""",
)

_SCHEMA_V3 = (
    """CREATE TABLE signal_state (
       symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL, signal_type TEXT NOT NULL,
       status TEXT NOT NULL, signal_version TEXT NOT NULL, evidence_json TEXT NOT NULL,
       threshold_json TEXT NOT NULL, source_snapshot_ids_json TEXT NOT NULL,
       PRIMARY KEY(symbol,observed_at_ms,signal_type,signal_version)) STRICT""",
)

_SCHEMA_V4 = (
    """CREATE TABLE hyperliquid_collector_run (
       symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL, issues_json TEXT NOT NULL,
       PRIMARY KEY(symbol,observed_at_ms)) STRICT""",
    """CREATE TABLE hyperliquid_observation (
       source_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       source_ms INTEGER NOT NULL, wallet_or_trader TEXT NOT NULL,
       direction TEXT NOT NULL CHECK(direction IN ('BUY','SELL')),
       notional_text TEXT NOT NULL, notional_currency TEXT NOT NULL,
       position_or_flow_type TEXT NOT NULL,
       source TEXT NOT NULL CHECK(source='hyperliquid'), provenance_json TEXT NOT NULL) STRICT""",
)

_SCHEMA_V5 = (
    """CREATE TABLE dex_collector_run (
       symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL, chain TEXT NOT NULL,
       source TEXT NOT NULL, issues_json TEXT NOT NULL,
       PRIMARY KEY(symbol,observed_at_ms,chain,source)) STRICT""",
    """CREATE TABLE dex_swap_observation (
       source_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       source_ms INTEGER NOT NULL, chain TEXT NOT NULL, venue TEXT NOT NULL,
       router TEXT, wallet TEXT, side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
       base_quantity_text TEXT NOT NULL, quote_notional_text TEXT, quote_currency TEXT,
       tx_hash TEXT NOT NULL, log_index INTEGER NOT NULL, block_number INTEGER,
       source TEXT NOT NULL, provenance_json TEXT NOT NULL) STRICT""",
)

_SCHEMA_V6 = (
    """CREATE TABLE capital_flow_event (
       event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, symbol TEXT NOT NULL,
       observed_at_ms INTEGER NOT NULL, score_text TEXT, cycle_state TEXT,
       evidence_json TEXT NOT NULL, source_snapshot_ids_json TEXT NOT NULL) STRICT""",
    """CREATE TABLE dealer_snapshot (
       symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL, phase TEXT,
       direction_score_text TEXT, direction_label TEXT, coverage_mask TEXT NOT NULL,
       axis_count INTEGER NOT NULL CHECK(axis_count BETWEEN 0 AND 3),
       position_json TEXT, flow_json TEXT, chip_json TEXT,
       PRIMARY KEY(symbol, observed_at_ms)) STRICT""",
    """CREATE TABLE onchain_activity (
       symbol TEXT NOT NULL, chain TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       outgoing_distinct INTEGER NOT NULL, baseline_days INTEGER NOT NULL,
       baseline_live_text TEXT, baseline_anchor_text TEXT, live_ratio_text TEXT,
       anchored_ratio_text TEXT, state TEXT NOT NULL, first_flag_at_ms INTEGER,
       plateau_started_at_ms INTEGER, consecutive_days INTEGER NOT NULL,
       PRIMARY KEY(symbol, chain, observed_at_ms)) STRICT""",
)

_SCHEMA_V7 = (
    "ALTER TABLE dex_collector_run ADD COLUMN coverage_json TEXT",
)

_SCHEMA_V8 = (
    """CREATE TABLE public_event_candidate (
       candidate_id TEXT PRIMARY KEY, candidate_type TEXT NOT NULL,
       symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       possible_yaozi_event_types_json TEXT NOT NULL,
       evidence_json TEXT NOT NULL, source_snapshot_ids_json TEXT NOT NULL) STRICT""",
)

_SCHEMA_V9 = (
    """CREATE TABLE public_context_run (
       source TEXT NOT NULL, context_kind TEXT NOT NULL,
       observed_at_ms INTEGER NOT NULL, status TEXT NOT NULL,
       issues_json TEXT NOT NULL,
       PRIMARY KEY(source,context_kind,observed_at_ms)) STRICT""",
    """CREATE TABLE narrative_snapshot (
       source TEXT NOT NULL, narrative_id TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       name TEXT NOT NULL, market_cap_text TEXT, market_cap_change_24h_text TEXT,
       volume_24h_text TEXT, content TEXT, top_assets_json TEXT NOT NULL,
       PRIMARY KEY(source,narrative_id,observed_at_ms)) STRICT""",
    """CREATE TABLE news_event (
       news_id TEXT PRIMARY KEY, source TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       published_at_ms INTEGER, title TEXT NOT NULL, url TEXT NOT NULL, summary TEXT,
       categories_json TEXT NOT NULL, provenance_json TEXT NOT NULL) STRICT""",
)

_SCHEMA_V10 = (
    """CREATE TABLE cross_axis_evaluation (
       symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       axis_type TEXT NOT NULL CHECK(axis_type IN ('ALPHA_PLUS','ALPHA')),
       status TEXT NOT NULL, selected INTEGER NOT NULL CHECK(selected IN (0,1)),
       cross_axis_version TEXT NOT NULL, evidence_json TEXT NOT NULL,
       threshold_json TEXT NOT NULL, source_snapshot_ids_json TEXT NOT NULL,
       PRIMARY KEY(symbol,observed_at_ms,axis_type,cross_axis_version)) STRICT""",
    """CREATE TABLE status_label_snapshot (
       symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       label_type TEXT NOT NULL CHECK(label_type IN ('OBSERVE','DUMP_WARNING','NEW_CANDIDATE')),
       status TEXT NOT NULL, label_version TEXT NOT NULL,
       evidence_json TEXT NOT NULL, threshold_json TEXT NOT NULL,
       source_snapshot_ids_json TEXT NOT NULL,
       PRIMARY KEY(symbol,observed_at_ms,label_type,label_version)) STRICT""",
)

_SCHEMA_V11 = (
    """CREATE TABLE option_context_run (
       source TEXT NOT NULL, inst_family TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       status TEXT NOT NULL, issues_json TEXT NOT NULL,
       PRIMARY KEY(source,inst_family,observed_at_ms)) STRICT""",
    """CREATE TABLE option_summary_snapshot (
       inst_family TEXT NOT NULL, inst_id TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       source_ms INTEGER, delta_bs_text TEXT, delta_pa_text TEXT,
       gamma_bs_text TEXT, gamma_pa_text TEXT, theta_bs_text TEXT, theta_pa_text TEXT,
       vega_bs_text TEXT, vega_pa_text TEXT, mark_vol_text TEXT, bid_vol_text TEXT,
       ask_vol_text TEXT, fwd_px_text TEXT,
       PRIMARY KEY(inst_family,inst_id,observed_at_ms)) STRICT""",
    """CREATE TABLE option_open_interest_snapshot (
       inst_family TEXT NOT NULL, inst_id TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       source_ms INTEGER, oi_text TEXT, oi_ccy_text TEXT,
       PRIMARY KEY(inst_family,inst_id,observed_at_ms)) STRICT""",
)

_SCHEMA_V12 = (
    """CREATE TABLE onchain_source_run (
       source TEXT NOT NULL, symbol TEXT NOT NULL, chain TEXT NOT NULL,
       observed_at_ms INTEGER NOT NULL,
       status TEXT NOT NULL CHECK(status IN ('ok','issues')),
       source_scope_json TEXT NOT NULL, evidence_json TEXT NOT NULL,
       issues_json TEXT NOT NULL,
       PRIMARY KEY(source,symbol,chain,observed_at_ms)) STRICT""",
)

_SCHEMA_V13 = (
    """CREATE TABLE liquidity_source_run (
       source TEXT NOT NULL, venue TEXT NOT NULL, symbol TEXT NOT NULL,
       pair TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       status TEXT NOT NULL CHECK(status IN ('ok','issues')),
       coverage_json TEXT NOT NULL, issues_json TEXT NOT NULL,
       PRIMARY KEY(source,symbol,observed_at_ms)) STRICT""",
    """CREATE TABLE liquidity_snapshot (
       source TEXT NOT NULL, venue TEXT NOT NULL, symbol TEXT NOT NULL,
       pair TEXT NOT NULL, observed_at_ms INTEGER NOT NULL, source_ms INTEGER,
       quote_currency TEXT NOT NULL,
       best_bid_text TEXT NOT NULL, best_ask_text TEXT NOT NULL, mid_text TEXT NOT NULL,
       down_2pct_cost_text TEXT, up_2pct_cost_text TEXT,
       down_2pct_lower_bound_text TEXT NOT NULL, up_2pct_lower_bound_text TEXT NOT NULL,
       asymmetry_text TEXT, bid_levels INTEGER NOT NULL, ask_levels INTEGER NOT NULL,
       coverage_json TEXT NOT NULL,
       PRIMARY KEY(venue,symbol,observed_at_ms)) STRICT""",
)

_SCHEMA_V14 = (
    """CREATE TABLE social_source_run (
       source TEXT NOT NULL, symbol TEXT NOT NULL, asset_id TEXT NOT NULL,
       provider_symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       status TEXT NOT NULL CHECK(status IN ('ok','empty','issues')),
       metric_count INTEGER NOT NULL CHECK(metric_count >= 0), issues_json TEXT NOT NULL,
       PRIMARY KEY(source,symbol,asset_id,observed_at_ms)) STRICT""",
    """CREATE TABLE social_metric_snapshot (
       source TEXT NOT NULL, symbol TEXT NOT NULL, asset_id TEXT NOT NULL,
       provider_symbol TEXT NOT NULL, observed_at_ms INTEGER NOT NULL,
       metric_kind TEXT NOT NULL CHECK(metric_kind IN (
           'twitter_followers','reddit_subscribers','telegram_members')),
       metric_value INTEGER NOT NULL CHECK(metric_value >= 0), source_url TEXT NOT NULL,
       PRIMARY KEY(source,symbol,asset_id,observed_at_ms,metric_kind)) STRICT""",
)


def _json(value):
    ipc.encode_frame({"v": value})
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _text(value):
    if value is None:
        return None
    if not isinstance(value, Decimal):
        raise MarketIntelError("invalid_decimal")
    return str(ipc.decimal_text(str(value), "market value", derived=True))


def _wire(value):
    if isinstance(value, Decimal):
        return _text(value)
    if isinstance(value, tuple):
        return [_wire(item) for item in value]
    if isinstance(value, list):
        return [_wire(item) for item in value]
    if isinstance(value, dict):
        return {key: _wire(item) for key, item in value.items()}
    return value


def _snapshot_id(symbol, observed_at_ms):
    return hashlib.sha256(f"market:{symbol}:{observed_at_ms}".encode("ascii")).hexdigest()


class MarketIntelStore:
    """Single-writer local market cache; no trading or account authority."""

    def __init__(self, path):
        if sqlite3.sqlite_version_info < (3, 37, 0):
            raise MarketIntelError("sqlite_3_37_required")
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path, isolation_level=None, timeout=0.25)
        self.connection.row_factory = sqlite3.Row
        try:
            version = self.connection.execute("PRAGMA user_version").fetchone()[0]
            if version == 0 and self.connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchone():
                raise MarketIntelError("unrecognized_nonempty_database")
            if version not in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, SCHEMA_VERSION):
                raise MarketIntelError("unsupported_schema")
            mode = self.connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            self.connection.execute("PRAGMA synchronous=FULL")
            self.connection.execute("PRAGMA foreign_keys=ON")
            if mode.lower() != "wal" or self.connection.execute("PRAGMA synchronous").fetchone()[0] != 2:
                raise MarketIntelError("wal_full_unavailable")
            if version == 0:
                self.connection.execute("BEGIN IMMEDIATE")
                try:
                    for statement in _SCHEMA:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V2:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V3:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V4:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V5:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V6:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V7:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V8:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V9:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V10:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V11:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V12:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V13:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V14:
                        self.connection.execute(statement)
                    self.connection.execute("INSERT INTO metadata VALUES (1,'catos-market-intel-v1')")
                    self.connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                    self.connection.commit()
                except BaseException:
                    self.connection.rollback()
                    raise
            elif version == 1:
                self.connection.execute("BEGIN IMMEDIATE")
                try:
                    for statement in _SCHEMA_V2:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V3:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V4:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V5:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V6:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V7:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V8:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V9:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V10:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V11:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V12:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V13:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V14:
                        self.connection.execute(statement)
                    self.connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                    self.connection.commit()
                except BaseException:
                    self.connection.rollback()
                    raise
            elif version == 2:
                self.connection.execute("BEGIN IMMEDIATE")
                try:
                    for statement in _SCHEMA_V3:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V4:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V5:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V6:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V7:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V8:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V9:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V10:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V11:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V12:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V13:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V14:
                        self.connection.execute(statement)
                    self.connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                    self.connection.commit()
                except BaseException:
                    self.connection.rollback()
                    raise
            elif version == 3:
                self.connection.execute("BEGIN IMMEDIATE")
                try:
                    for statement in _SCHEMA_V4:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V5:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V6:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V7:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V8:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V9:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V10:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V11:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V12:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V13:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V14:
                        self.connection.execute(statement)
                    self.connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                    self.connection.commit()
                except BaseException:
                    self.connection.rollback()
                    raise
            elif version == 4:
                self.connection.execute("BEGIN IMMEDIATE")
                try:
                    for statement in _SCHEMA_V5:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V6:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V7:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V8:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V9:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V10:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V11:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V12:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V13:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V14:
                        self.connection.execute(statement)
                    self.connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                    self.connection.commit()
                except BaseException:
                    self.connection.rollback()
                    raise
            elif version == 5:
                self.connection.execute("BEGIN IMMEDIATE")
                try:
                    for statement in _SCHEMA_V6:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V7:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V8:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V9:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V10:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V11:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V12:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V13:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V14:
                        self.connection.execute(statement)
                    self.connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                    self.connection.commit()
                except BaseException:
                    self.connection.rollback()
                    raise
            elif version == 6:
                self.connection.execute("BEGIN IMMEDIATE")
                try:
                    for statement in _SCHEMA_V7:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V8:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V9:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V10:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V11:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V12:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V13:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V14:
                        self.connection.execute(statement)
                    self.connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                    self.connection.commit()
                except BaseException:
                    self.connection.rollback()
                    raise
            elif version == 7:
                self.connection.execute("BEGIN IMMEDIATE")
                try:
                    for statement in _SCHEMA_V8:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V9:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V10:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V11:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V12:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V13:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V14:
                        self.connection.execute(statement)
                    self.connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                    self.connection.commit()
                except BaseException:
                    self.connection.rollback()
                    raise
            elif version == 8:
                self.connection.execute("BEGIN IMMEDIATE")
                try:
                    for statement in _SCHEMA_V9:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V10:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V11:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V12:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V13:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V14:
                        self.connection.execute(statement)
                    self.connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                    self.connection.commit()
                except BaseException:
                    self.connection.rollback()
                    raise
            elif version == 9:
                self.connection.execute("BEGIN IMMEDIATE")
                try:
                    for statement in _SCHEMA_V10:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V11:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V12:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V13:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V14:
                        self.connection.execute(statement)
                    self.connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                    self.connection.commit()
                except BaseException:
                    self.connection.rollback()
                    raise
            elif version == 10:
                self.connection.execute("BEGIN IMMEDIATE")
                try:
                    for statement in _SCHEMA_V11:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V12:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V13:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V14:
                        self.connection.execute(statement)
                    self.connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                    self.connection.commit()
                except BaseException:
                    self.connection.rollback()
                    raise
            elif version == 11:
                self.connection.execute("BEGIN IMMEDIATE")
                try:
                    for statement in _SCHEMA_V12:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V13:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V14:
                        self.connection.execute(statement)
                    self.connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                    self.connection.commit()
                except BaseException:
                    self.connection.rollback()
                    raise
            elif version == 12:
                self.connection.execute("BEGIN IMMEDIATE")
                try:
                    for statement in _SCHEMA_V13:
                        self.connection.execute(statement)
                    for statement in _SCHEMA_V14:
                        self.connection.execute(statement)
                    self.connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                    self.connection.commit()
                except BaseException:
                    self.connection.rollback()
                    raise
            elif version == 13:
                self.connection.execute("BEGIN IMMEDIATE")
                try:
                    for statement in _SCHEMA_V14:
                        self.connection.execute(statement)
                    self.connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                    self.connection.commit()
                except BaseException:
                    self.connection.rollback()
                    raise
            metadata = self.connection.execute("SELECT format FROM metadata WHERE id=1").fetchone()
            if metadata is None or metadata[0] != "catos-market-intel-v1":
                raise MarketIntelError("metadata_mismatch")
        except BaseException:
            self.connection.close()
            raise

    def close(self):
        self.connection.close()

    def _insert_exact(self, table, columns, values, key_where, key_values):
        placeholders = ",".join("?" for _ in columns)
        try:
            self.connection.execute(
                f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})", values)
            return
        except sqlite3.IntegrityError:
            row = self.connection.execute(
                f"SELECT {','.join(columns)} FROM {table} WHERE {key_where}", key_values).fetchone()
            if row is None or tuple(row) != tuple(values):
                raise MarketIntelError("snapshot_conflict") from None

    def _insert_replayable_source_fact(self, table, columns, values):
        """Deduplicate immutable source facts replayed under a later collection anchor."""
        placeholders = ",".join("?" for _ in columns)
        try:
            self.connection.execute(
                f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})", values)
            return
        except sqlite3.IntegrityError:
            source_id_index = columns.index("source_id")
            row = self.connection.execute(
                f"SELECT {','.join(columns)} FROM {table} WHERE source_id=?",
                (values[source_id_index],),
            ).fetchone()
            if row is None:
                raise MarketIntelError("snapshot_conflict") from None
            stable_indexes = tuple(
                index for index, column in enumerate(columns) if column != "observed_at_ms")
            if any(row[index] != values[index] for index in stable_indexes):
                raise MarketIntelError("snapshot_conflict") from None

    def _oi_delta_percent(self, symbol, observed_at_ms, current, source, window_ms, max_lag_ms=120_000):
        if current is None or source is None:
            return None
        target = observed_at_ms - window_ms
        row = self.connection.execute(
            """SELECT observed_at_ms,oi_text,provenance_json FROM derivative_snapshot
               WHERE symbol=? AND observed_at_ms<=? ORDER BY observed_at_ms DESC LIMIT 1""",
            (symbol, target)).fetchone()
        if row is None or target - row["observed_at_ms"] > max_lag_ms or row["oi_text"] is None:
            return None
        try:
            provenance = json.loads(row["provenance_json"])
        except (TypeError, ValueError, json.JSONDecodeError):
            raise MarketIntelError("stored_snapshot_invalid") from None
        if provenance.get("oi") != source:
            return None
        reference = ipc.decimal_text(row["oi_text"], "stored OI", derived=True)
        if reference == 0:
            return None
        with localcontext(research._CONTEXT):
            return (current - reference) * Decimal("100") / reference

    def record_universe(self, instruments, observed_at_ms):
        """Materialize the latest public instrument universe without trade authority."""
        ipc.integer(observed_at_ms, "observed_at_ms")
        if type(instruments) is not tuple or not instruments:
            raise MarketIntelError("invalid_universe")
        grouped = {}
        for item in instruments:
            if not isinstance(item, InstrumentRef):
                raise MarketIntelError("invalid_universe")
            grouped.setdefault(item.symbol, []).append(item)
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self.connection.execute(
                "UPDATE instrument SET active=0,updated_at_ms=? WHERE active=1", (observed_at_ms,))
            for symbol in sorted(grouped):
                refs = grouped[symbol]
                venues = sorted({item.venue for item in refs})
                active = 1 if any(item.active for item in refs) else 0
                preferred = next((item.venue_inst_id for item in refs if item.venue == OKX), symbol)
                existing = self.connection.execute(
                    "SELECT first_seen_ms,sector_json FROM instrument WHERE symbol=?", (symbol,)).fetchone()
                first_seen = observed_at_ms if existing is None else existing["first_seen_ms"]
                sector_json = "[]" if existing is None else existing["sector_json"]
                self.connection.execute(
                    """INSERT INTO instrument(symbol,primary_inst_id,venues_json,sector_json,active,
                                               first_seen_ms,updated_at_ms)
                       VALUES (?,?,?,?,?,?,?)
                       ON CONFLICT(symbol) DO UPDATE SET primary_inst_id=excluded.primary_inst_id,
                       venues_json=excluded.venues_json,active=excluded.active,
                       updated_at_ms=excluded.updated_at_ms""",
                    (symbol, preferred, _json(venues), sector_json, active, first_seen, observed_at_ms),
                )
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def record_public_batch(self, batch: PublicMarketBatch):
        if not isinstance(batch, PublicMarketBatch):
            raise MarketIntelError("invalid_batch")
        ipc.token(batch.symbol.replace("-USDT-SWAP", ""), "symbol base")
        ipc.integer(batch.observed_at_ms, "observed_at_ms")
        if any(item.symbol != batch.symbol or item.observed_at_ms != batch.observed_at_ms
               for item in (*batch.markets, *batch.derivatives)):
            raise MarketIntelError("scope_mismatch")
        if not batch.markets:
            raise MarketIntelError("market_source_required")
        venues = sorted({item.venue for item in (*batch.markets, *batch.derivatives)})
        issues_json = _json([list(item) for item in batch.issues])
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            existing = self.connection.execute("SELECT first_seen_ms FROM instrument WHERE symbol=?",
                                               (batch.symbol,)).fetchone()
            first_seen = batch.observed_at_ms if existing is None else existing[0]
            self.connection.execute(
                """INSERT INTO instrument(symbol,primary_inst_id,venues_json,sector_json,active,first_seen_ms,updated_at_ms)
                   VALUES (?,?,?,?,1,?,?)
                   ON CONFLICT(symbol) DO UPDATE SET primary_inst_id=excluded.primary_inst_id,
                   venues_json=excluded.venues_json,active=1,updated_at_ms=excluded.updated_at_ms""",
                (batch.symbol, batch.symbol, _json(venues), "[]", first_seen, batch.observed_at_ms))
            self._insert_exact("collector_run", ("symbol", "observed_at_ms", "issues_json"),
                               (batch.symbol, batch.observed_at_ms, issues_json),
                               "symbol=? AND observed_at_ms=?", (batch.symbol, batch.observed_at_ms))

            for row in batch.markets:
                values = (row.venue, row.symbol, row.observed_at_ms, row.source_ms, _text(row.price),
                          _text(row.volume_24h), row.volume_unit, _text(row.change_24h_pct))
                self._insert_exact("venue_market_snapshot",
                    ("venue", "symbol", "observed_at_ms", "source_ms", "price_text",
                     "volume_24h_text", "volume_unit", "change_24h_text"), values,
                    "venue=? AND symbol=? AND observed_at_ms=?", values[:3])
            for row in batch.derivatives:
                values = (row.venue, row.symbol, row.observed_at_ms, row.source_ms, _text(row.oi), row.oi_unit,
                          _text(row.oi_notional_usd), _text(row.funding), _text(row.top_position_lsr),
                          _text(row.taker_buy_ratio))
                self._insert_exact("venue_derivative_snapshot",
                    ("venue", "symbol", "observed_at_ms", "source_ms", "oi_text", "oi_unit",
                     "oi_notional_usd_text", "funding_text", "top_lsr_text", "taker_buy_ratio_text"), values,
                    "venue=? AND symbol=? AND observed_at_ms=?", values[:3])

            market = next((item for item in batch.markets if item.venue == OKX), batch.markets[0])
            source_health = _json({"venues": venues, "issues": [list(item) for item in batch.issues],
                                   "primary_market": market.venue, "volume_unit": market.volume_unit})
            market_values = (_snapshot_id(batch.symbol, batch.observed_at_ms), batch.symbol,
                             batch.observed_at_ms, _text(market.price), _text(market.volume_24h), None,
                             _text(market.change_24h_pct), None, source_health)
            self._insert_exact("market_snapshot",
                ("snapshot_id", "symbol", "observed_at_ms", "price_text", "volume_24h_text",
                 "change_1h_text", "change_24h_text", "market_cap_text", "source_health_json"),
                market_values, "symbol=? AND observed_at_ms=?", (batch.symbol, batch.observed_at_ms))

            okx = next((item for item in batch.derivatives if item.venue == OKX), None)
            binance = next((item for item in batch.derivatives if item.venue == BINANCE), None)
            primary = okx or binance
            if primary is not None:
                oi_source = okx if okx is not None and okx.oi is not None else binance
                funding_source = okx if okx is not None and okx.funding is not None else binance
                provenance = _json({
                    "oi": None if oi_source is None else oi_source.venue,
                    "funding": None if funding_source is None else funding_source.venue,
                    "top_lsr": BINANCE if binance is not None and binance.top_position_lsr is not None else None,
                    "taker": BINANCE if binance is not None and binance.taker_buy_ratio is not None else None,
                })
                current_oi = None if oi_source is None else oi_source.oi
                oi_5m = self._oi_delta_percent(batch.symbol, batch.observed_at_ms, current_oi,
                                               None if oi_source is None else oi_source.venue, 300_000)
                oi_1h = self._oi_delta_percent(batch.symbol, batch.observed_at_ms, current_oi,
                                               None if oi_source is None else oi_source.venue, 3_600_000)
                oi_4h = self._oi_delta_percent(batch.symbol, batch.observed_at_ms, current_oi,
                                               None if oi_source is None else oi_source.venue, 14_400_000)
                values = (batch.symbol, batch.observed_at_ms,
                          _text(current_oi), _text(oi_5m), _text(oi_1h), _text(oi_4h),
                          _text(None if funding_source is None else funding_source.funding),
                          _text(None if binance is None else binance.top_position_lsr),
                          _text(None if binance is None else binance.taker_buy_ratio), None, provenance)
                self._insert_exact("derivative_snapshot",
                    ("symbol", "observed_at_ms", "oi_text", "oi_delta_5m_text", "oi_delta_1h_text",
                     "oi_delta_4h_text", "funding_text", "top_lsr_text", "taker_buy_ratio_text",
                     "concentration_json", "provenance_json"), values,
                    "symbol=? AND observed_at_ms=?", values[:2])
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def record_liquidity_batch(self, batch):
        from catos.market_liquidity import LiquidityBatch, LiquiditySnapshot, LiquiditySourceRun
        if not isinstance(batch, LiquidityBatch):
            raise MarketIntelError("invalid_liquidity_batch")
        ipc.token(batch.symbol.replace("-USDT-SWAP", ""), "symbol base")
        ipc.integer(batch.observed_at_ms, "observed_at_ms")
        if not batch.source_runs:
            raise MarketIntelError("liquidity_source_run_required")
        if any(not isinstance(run, LiquiditySourceRun) for run in batch.source_runs):
            raise MarketIntelError("invalid_liquidity_batch")
        if any(not isinstance(snapshot, LiquiditySnapshot) for snapshot in batch.snapshots):
            raise MarketIntelError("invalid_liquidity_batch")
        if any(run.symbol != batch.symbol or run.observed_at_ms != batch.observed_at_ms
               for run in batch.source_runs):
            raise MarketIntelError("scope_mismatch")
        if any(snapshot.symbol != batch.symbol or snapshot.observed_at_ms != batch.observed_at_ms
               for snapshot in batch.snapshots):
            raise MarketIntelError("scope_mismatch")
        run_by_source = {run.source: run for run in batch.source_runs}
        snapshot_by_source = {snapshot.source: snapshot for snapshot in batch.snapshots}
        if len(run_by_source) != len(batch.source_runs) or len(snapshot_by_source) != len(batch.snapshots):
            raise MarketIntelError("duplicate_liquidity_source")
        ok_sources = {run.source for run in batch.source_runs if run.status == "ok"}
        if any(run.status not in ("ok", "issues") for run in batch.source_runs):
            raise MarketIntelError("invalid_liquidity_status")
        if ok_sources != set(snapshot_by_source):
            raise MarketIntelError("scope_mismatch")
        for source, snapshot in snapshot_by_source.items():
            run = run_by_source[source]
            if snapshot.venue != run.venue or snapshot.pair != run.pair:
                raise MarketIntelError("scope_mismatch")

        self.connection.execute("BEGIN IMMEDIATE")
        try:
            for run in batch.source_runs:
                values = (
                    run.source, run.venue, run.symbol, run.pair, run.observed_at_ms,
                    run.status, _json(_wire(run.coverage)), _json(list(run.issues)),
                )
                self._insert_exact(
                    "liquidity_source_run",
                    ("source", "venue", "symbol", "pair", "observed_at_ms", "status",
                     "coverage_json", "issues_json"),
                    values,
                    "source=? AND symbol=? AND observed_at_ms=?",
                    (run.source, run.symbol, run.observed_at_ms),
                )
            for snapshot in batch.snapshots:
                values = (
                    snapshot.source, snapshot.venue, snapshot.symbol, snapshot.pair,
                    snapshot.observed_at_ms, snapshot.source_ms, snapshot.quote_currency,
                    _text(snapshot.best_bid), _text(snapshot.best_ask), _text(snapshot.mid),
                    _text(snapshot.down_2pct_cost), _text(snapshot.up_2pct_cost),
                    _text(snapshot.down_2pct_lower_bound), _text(snapshot.up_2pct_lower_bound),
                    _text(snapshot.asymmetry), snapshot.bid_levels, snapshot.ask_levels,
                    _json(_wire(snapshot.coverage)),
                )
                self._insert_exact(
                    "liquidity_snapshot",
                    ("source", "venue", "symbol", "pair", "observed_at_ms", "source_ms",
                     "quote_currency", "best_bid_text", "best_ask_text", "mid_text",
                     "down_2pct_cost_text", "up_2pct_cost_text",
                     "down_2pct_lower_bound_text", "up_2pct_lower_bound_text",
                     "asymmetry_text", "bid_levels", "ask_levels", "coverage_json"),
                    values,
                    "venue=? AND symbol=? AND observed_at_ms=?",
                    (snapshot.venue, snapshot.symbol, snapshot.observed_at_ms),
                )
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def record_candles(self, candles):
        from catos.market_collectors import MarketCandle
        if type(candles) is not tuple or not candles:
            raise MarketIntelError("invalid_candles")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            for candle in candles:
                if not isinstance(candle, MarketCandle) or candle.closed is not True:
                    raise MarketIntelError("invalid_candles")
                values = (candle.venue, candle.symbol, candle.interval, candle.open_time_ms,
                          candle.timeframe_ms, _text(candle.open), _text(candle.high), _text(candle.low),
                          _text(candle.close), _text(candle.volume), candle.volume_unit, 1)
                self._insert_exact("market_candle",
                    ("venue", "symbol", "interval", "open_time_ms", "timeframe_ms", "open_text",
                     "high_text", "low_text", "close_text", "volume_text", "volume_unit", "closed"),
                    values, "venue=? AND symbol=? AND interval=? AND open_time_ms=?", values[:4])
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def record_hyperliquid_batch(self, batch):
        from catos.market_hyperliquid import HyperliquidObservationBatch
        if not isinstance(batch, HyperliquidObservationBatch):
            raise MarketIntelError("invalid_hyperliquid_batch")
        ipc.token(batch.symbol.replace("-USDT-SWAP", ""), "symbol base")
        ipc.integer(batch.observed_at_ms, "observed_at_ms")
        for observation in batch.observations:
            if (observation.symbol != batch.symbol
                    or observation.observed_at_ms != batch.observed_at_ms
                    or observation.source != "hyperliquid"):
                raise MarketIntelError("scope_mismatch")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            issues_json = _json([list(item) for item in batch.issues])
            self._insert_exact(
                "hyperliquid_collector_run",
                ("symbol", "observed_at_ms", "issues_json"),
                (batch.symbol, batch.observed_at_ms, issues_json),
                "symbol=? AND observed_at_ms=?", (batch.symbol, batch.observed_at_ms),
            )
            for observation in batch.observations:
                values = (
                    observation.source_id,
                    observation.symbol,
                    observation.observed_at_ms,
                    observation.source_ms,
                    observation.wallet_or_trader,
                    observation.direction,
                    _text(observation.notional),
                    observation.notional_currency,
                    observation.position_or_flow_type,
                    observation.source,
                    _json(_wire(observation.provenance)),
                )
                self._insert_replayable_source_fact(
                    "hyperliquid_observation",
                    ("source_id", "symbol", "observed_at_ms", "source_ms", "wallet_or_trader",
                     "direction", "notional_text", "notional_currency", "position_or_flow_type",
                     "source", "provenance_json"),
                    values,
                )
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def record_dex_batch(self, batch):
        from catos.market_dex import DexSwapBatch
        if not isinstance(batch, DexSwapBatch):
            raise MarketIntelError("invalid_dex_batch")
        ipc.token(batch.symbol.replace("-USDT-SWAP", ""), "symbol base")
        ipc.integer(batch.observed_at_ms, "observed_at_ms")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self._insert_exact(
                "dex_collector_run",
                ("symbol", "observed_at_ms", "chain", "source", "issues_json", "coverage_json"),
                (batch.symbol, batch.observed_at_ms, batch.chain, batch.source,
                 _json([list(item) for item in batch.issues]), _json(_wire(batch.coverage))),
                "symbol=? AND observed_at_ms=? AND chain=? AND source=?",
                (batch.symbol, batch.observed_at_ms, batch.chain, batch.source),
            )
            for observation in batch.observations:
                if (observation.symbol != batch.symbol
                        or observation.observed_at_ms != batch.observed_at_ms
                        or observation.chain != batch.chain
                        or observation.source != batch.source):
                    raise MarketIntelError("scope_mismatch")
                values = (
                    observation.source_id, observation.symbol, observation.observed_at_ms,
                    observation.source_ms, observation.chain, observation.venue,
                    observation.router, observation.wallet, observation.side,
                    _text(observation.base_quantity), _text(observation.quote_notional),
                    observation.quote_currency, observation.tx_hash, observation.log_index,
                    observation.block_number, observation.source,
                    _json(_wire(observation.provenance)),
                )
                self._insert_replayable_source_fact(
                    "dex_swap_observation",
                    ("source_id", "symbol", "observed_at_ms", "source_ms", "chain", "venue",
                     "router", "wallet", "side", "base_quantity_text", "quote_notional_text",
                     "quote_currency", "tx_hash", "log_index", "block_number", "source",
                     "provenance_json"),
                    values,
                )
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def record_capital_flow_event(self, event):
        from catos.market_p1 import CapitalFlowEvent
        if not isinstance(event, CapitalFlowEvent):
            raise MarketIntelError("invalid_capital_flow_event")
        values = (
            event.event_id, event.event_type, event.symbol, event.observed_at_ms,
            _text(event.score), event.cycle_state, _json(_wire(event.evidence)),
            _json(list(event.source_snapshot_ids)),
        )
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self._insert_exact(
                "capital_flow_event",
                ("event_id", "event_type", "symbol", "observed_at_ms", "score_text",
                 "cycle_state", "evidence_json", "source_snapshot_ids_json"),
                values, "event_id=?", (event.event_id,),
            )
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def record_public_event_candidate(self, candidate):
        from catos.market_p1 import PublicEventCandidate
        if not isinstance(candidate, PublicEventCandidate):
            raise MarketIntelError("invalid_public_event_candidate")
        values = (
            candidate.candidate_id,
            candidate.candidate_type,
            candidate.symbol,
            candidate.observed_at_ms,
            _json(list(candidate.possible_yaozi_event_types)),
            _json(_wire(candidate.evidence)),
            _json(list(candidate.source_snapshot_ids)),
        )
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self._insert_exact(
                "public_event_candidate",
                ("candidate_id", "candidate_type", "symbol", "observed_at_ms",
                 "possible_yaozi_event_types_json", "evidence_json",
                 "source_snapshot_ids_json"),
                values, "candidate_id=?", (candidate.candidate_id,),
            )
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def _record_context_run(self, source, context_kind, observed_at_ms, items, issues):
        status = "partial" if issues else ("ok" if items else "empty")
        values = (
            source,
            context_kind,
            observed_at_ms,
            status,
            _json([list(issue) for issue in issues]),
        )
        self._insert_exact(
            "public_context_run",
            ("source", "context_kind", "observed_at_ms", "status", "issues_json"),
            values,
            "source=? AND context_kind=? AND observed_at_ms=?",
            values[:3],
        )

    def record_narrative_batch(self, batch):
        from catos.market_narrative_news import NarrativeBatch, NarrativeSnapshot
        if not isinstance(batch, NarrativeBatch):
            raise MarketIntelError("invalid_narrative_batch")
        ipc.integer(batch.observed_at_ms, "observed_at_ms")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self._record_context_run(
                batch.source, "narrative", batch.observed_at_ms, batch.items, batch.issues)
            for item in batch.items:
                if (not isinstance(item, NarrativeSnapshot)
                        or item.source != batch.source
                        or item.observed_at_ms != batch.observed_at_ms):
                    raise MarketIntelError("scope_mismatch")
                values = (
                    item.source,
                    item.narrative_id,
                    item.observed_at_ms,
                    item.name,
                    _text(item.market_cap),
                    _text(item.market_cap_change_24h),
                    _text(item.volume_24h),
                    item.content,
                    _json(list(item.top_assets)),
                )
                self._insert_exact(
                    "narrative_snapshot",
                    ("source", "narrative_id", "observed_at_ms", "name", "market_cap_text",
                     "market_cap_change_24h_text", "volume_24h_text", "content",
                     "top_assets_json"),
                    values,
                    "source=? AND narrative_id=? AND observed_at_ms=?",
                    values[:3],
                )
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def record_news_batch(self, batch):
        from catos.market_narrative_news import COINDESK_RSS_URL, NewsBatch, NewsEvent
        if not isinstance(batch, NewsBatch):
            raise MarketIntelError("invalid_news_batch")
        ipc.integer(batch.observed_at_ms, "observed_at_ms")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self._record_context_run(batch.source, "news", batch.observed_at_ms, batch.items, batch.issues)
            columns = (
                "news_id", "source", "observed_at_ms", "published_at_ms", "title", "url",
                "summary", "categories_json", "provenance_json",
            )
            for item in batch.items:
                if (not isinstance(item, NewsEvent)
                        or item.source != batch.source
                        or item.observed_at_ms != batch.observed_at_ms):
                    raise MarketIntelError("scope_mismatch")
                values = (
                    item.news_id,
                    item.source,
                    item.observed_at_ms,
                    item.published_at_ms,
                    item.title,
                    item.url,
                    item.summary,
                    _json(list(item.categories)),
                    _json({
                        "contract": "catos_public_news_source_fact_v1",
                        "source_url": COINDESK_RSS_URL,
                        "classification": None,
                        "importance": None,
                    }),
                )
                existing = self.connection.execute(
                    f"SELECT {','.join(columns)} FROM news_event WHERE news_id=?",
                    (item.news_id,),
                ).fetchone()
                if existing is None:
                    self.connection.execute(
                        f"INSERT INTO news_event ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                        values,
                    )
                    continue
                stable_indexes = tuple(index for index, column in enumerate(columns)
                                       if column != "observed_at_ms")
                if any(existing[index] != values[index] for index in stable_indexes):
                    raise MarketIntelError("snapshot_conflict")
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def record_social_batch(self, batch):
        from catos.market_collectors import MarketCollectionError
        from catos.market_social import (
            SOCIAL_SOURCE, SocialAssetRef, SocialBatch, SocialMetricSnapshot,
            _METRIC_FIELDS, _source_url,
        )
        if not isinstance(batch, SocialBatch) or batch.source != SOCIAL_SOURCE:
            raise MarketIntelError("invalid_social_batch")
        try:
            SocialAssetRef(batch.symbol, batch.asset_id)
        except ValueError:
            raise MarketIntelError("invalid_social_batch") from None
        base = batch.symbol.removesuffix("-USDT-SWAP")
        if not base or batch.provider_symbol != base:
            raise MarketIntelError("scope_mismatch")
        ipc.token(base, "symbol base")
        ipc.integer(batch.observed_at_ms, "observed_at_ms")
        if (type(batch.asset_id) is not str or not batch.asset_id
                or type(batch.metrics) is not tuple
                or type(batch.issues) is not tuple
                or (batch.issues and batch.metrics)
                or any(type(issue) is not str or not issue for issue in batch.issues)):
            raise MarketIntelError("invalid_social_batch")
        seen = set()
        for metric in batch.metrics:
            if (not isinstance(metric, SocialMetricSnapshot)
                    or type(metric.metric_kind) is not str
                    or metric.metric_kind not in {pair[0] for pair in _METRIC_FIELDS.values()}
                    or metric.metric_kind in seen
                    or type(metric.metric_value) is not int
                    or not 0 <= metric.metric_value <= 2**63 - 1):
                raise MarketIntelError("invalid_social_batch")
            try:
                _source_url(metric.source_url)
            except MarketCollectionError:
                raise MarketIntelError("invalid_social_batch") from None
            seen.add(metric.metric_kind)
        status = "issues" if batch.issues else ("ok" if batch.metrics else "empty")
        run_values = (
            batch.source, batch.symbol, batch.asset_id, batch.provider_symbol,
            batch.observed_at_ms, status, len(batch.metrics), _json(list(batch.issues)),
        )
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self._insert_exact(
                "social_source_run",
                ("source", "symbol", "asset_id", "provider_symbol", "observed_at_ms",
                 "status", "metric_count", "issues_json"),
                run_values,
                "source=? AND symbol=? AND asset_id=? AND observed_at_ms=?",
                (batch.source, batch.symbol, batch.asset_id, batch.observed_at_ms),
            )
            for metric in batch.metrics:
                if (not isinstance(metric, SocialMetricSnapshot)
                        or metric.source != batch.source
                        or metric.symbol != batch.symbol
                        or metric.asset_id != batch.asset_id
                        or metric.observed_at_ms != batch.observed_at_ms
                        or type(metric.metric_value) is not int
                        or metric.metric_value < 0):
                    raise MarketIntelError("scope_mismatch")
                values = (
                    metric.source, metric.symbol, metric.asset_id, batch.provider_symbol,
                    metric.observed_at_ms, metric.metric_kind, metric.metric_value,
                    metric.source_url,
                )
                self._insert_exact(
                    "social_metric_snapshot",
                    ("source", "symbol", "asset_id", "provider_symbol", "observed_at_ms",
                     "metric_kind", "metric_value", "source_url"),
                    values,
                    "source=? AND symbol=? AND asset_id=? AND observed_at_ms=? AND metric_kind=?",
                    (metric.source, metric.symbol, metric.asset_id,
                     metric.observed_at_ms, metric.metric_kind),
                )
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def _record_option_run(self, source, inst_family, observed_at_ms, item_count, issues):
        status = "partial" if issues else ("ok" if item_count else "empty")
        values = (source, inst_family, observed_at_ms, status,
                  _json([list(issue) for issue in issues]))
        self._insert_exact(
            "option_context_run",
            ("source", "inst_family", "observed_at_ms", "status", "issues_json"),
            values,
            "source=? AND inst_family=? AND observed_at_ms=?",
            values[:3],
        )

    def record_option_context_run(self, *, source, inst_family, observed_at_ms,
                                  item_count, issues=()):
        """Persist provider evidence without forcing venue facts into OKX snapshots."""
        from catos.market_options import option_family
        if type(source) is not str or not source.strip():
            raise MarketIntelError("invalid_option_context_run")
        try:
            inst_family = option_family(inst_family)
        except Exception:
            raise MarketIntelError("invalid_option_context_run") from None
        ipc.integer(observed_at_ms, "observed_at_ms")
        if type(item_count) is not int or item_count < 0:
            raise MarketIntelError("invalid_option_context_run")
        if type(issues) not in (tuple, list) or any(
                type(issue) not in (tuple, list) or len(issue) != 2
                or type(issue[0]) is not str or type(issue[1]) is not str
                for issue in issues):
            raise MarketIntelError("invalid_option_context_run")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self._record_option_run(
                source.strip(), inst_family, observed_at_ms, item_count, tuple(issues))
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def record_option_summary_batch(self, batch):
        from catos.market_options import OptionSummaryBatch, OptionSummaryFact
        if not isinstance(batch, OptionSummaryBatch):
            raise MarketIntelError("invalid_option_summary_batch")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self._record_option_run(
                batch.source, batch.inst_family, batch.observed_at_ms,
                len(batch.items), batch.issues)
            for item in batch.items:
                if (not isinstance(item, OptionSummaryFact)
                        or item.inst_family != batch.inst_family
                        or item.observed_at_ms != batch.observed_at_ms):
                    raise MarketIntelError("scope_mismatch")
                values = (
                    item.inst_family, item.inst_id, item.observed_at_ms, item.source_ms,
                    _text(item.delta_bs), _text(item.delta_pa),
                    _text(item.gamma_bs), _text(item.gamma_pa),
                    _text(item.theta_bs), _text(item.theta_pa),
                    _text(item.vega_bs), _text(item.vega_pa),
                    _text(item.mark_vol), _text(item.bid_vol), _text(item.ask_vol),
                    _text(item.fwd_px),
                )
                self._insert_exact(
                    "option_summary_snapshot",
                    ("inst_family", "inst_id", "observed_at_ms", "source_ms",
                     "delta_bs_text", "delta_pa_text", "gamma_bs_text", "gamma_pa_text",
                     "theta_bs_text", "theta_pa_text", "vega_bs_text", "vega_pa_text",
                     "mark_vol_text", "bid_vol_text", "ask_vol_text", "fwd_px_text"),
                    values,
                    "inst_family=? AND inst_id=? AND observed_at_ms=?",
                    values[:3],
                )
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def record_option_open_interest_batch(self, batch):
        from catos.market_options import OptionOpenInterestBatch, OptionOpenInterestFact
        if not isinstance(batch, OptionOpenInterestBatch):
            raise MarketIntelError("invalid_option_open_interest_batch")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self._record_option_run(
                batch.source, batch.inst_family, batch.observed_at_ms,
                len(batch.items), batch.issues)
            for item in batch.items:
                if (not isinstance(item, OptionOpenInterestFact)
                        or item.inst_family != batch.inst_family
                        or item.observed_at_ms != batch.observed_at_ms):
                    raise MarketIntelError("scope_mismatch")
                values = (
                    item.inst_family, item.inst_id, item.observed_at_ms, item.source_ms,
                    _text(item.oi), _text(item.oi_ccy),
                )
                self._insert_exact(
                    "option_open_interest_snapshot",
                    ("inst_family", "inst_id", "observed_at_ms", "source_ms",
                     "oi_text", "oi_ccy_text"),
                    values,
                    "inst_family=? AND inst_id=? AND observed_at_ms=?",
                    values[:3],
                )
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def record_dealer_snapshot(self, snapshot):
        from catos.market_p1 import DealerSnapshot
        if not isinstance(snapshot, DealerSnapshot):
            raise MarketIntelError("invalid_dealer_snapshot")
        values = (
            snapshot.symbol, snapshot.observed_at_ms, snapshot.phase,
            _text(snapshot.direction_score), snapshot.direction_label, snapshot.coverage_mask,
            snapshot.axis_count,
            None if snapshot.position is None else _json(_wire(snapshot.position)),
            None if snapshot.flow is None else _json(_wire(snapshot.flow)),
            None if snapshot.chip is None else _json(_wire(snapshot.chip)),
        )
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self._insert_exact(
                "dealer_snapshot",
                ("symbol", "observed_at_ms", "phase", "direction_score_text",
                 "direction_label", "coverage_mask", "axis_count", "position_json",
                 "flow_json", "chip_json"),
                values, "symbol=? AND observed_at_ms=?", values[:2],
            )
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def materialize_dealer_snapshot(self, symbol, observed_at_ms=None, *, chip=None):
        """Build only Dealer axes backed by an explicit verified Dealer contract.

        Raw DEX swaps are signal/on-chain observations. They are deliberately
        not promoted into Dealer FLOW because Yaozi exposes those two pipelines
        independently and no verified mapping between them is available.
        """
        from catos.market_p1 import make_dealer_snapshot
        ipc.token(symbol.replace("-USDT-SWAP", ""), "symbol base")
        if not symbol.endswith("-USDT-SWAP"):
            raise MarketIntelError("invalid_symbol")
        if observed_at_ms is None:
            row = self.connection.execute(
                """SELECT MAX(observed_at_ms) FROM (
                   SELECT observed_at_ms FROM market_snapshot WHERE symbol=?
                   UNION ALL SELECT observed_at_ms FROM derivative_snapshot WHERE symbol=?)""",
                (symbol, symbol),
            ).fetchone()
            observed_at_ms = None if row is None else row[0]
        if observed_at_ms is None:
            raise MarketIntelError("missing_dealer_evidence")
        ipc.integer(observed_at_ms, "observed_at_ms")

        derivative = self.connection.execute(
            """SELECT * FROM derivative_snapshot WHERE symbol=? AND observed_at_ms<=?
               ORDER BY observed_at_ms DESC LIMIT 1""", (symbol, observed_at_ms)).fetchone()
        position = {
            "top_trader_lsr": None,
            "top_trader_long_pct": None,
            "retail_lsr": None,
            "taker_buy_pct": None,
            "funding_rate": None,
        }
        if derivative is not None:
            if derivative["top_lsr_text"] is not None:
                position["top_trader_lsr"] = ipc.decimal_text(
                    derivative["top_lsr_text"], "top_lsr", derived=True)
            if derivative["taker_buy_ratio_text"] is not None:
                ratio = ipc.decimal_text(derivative["taker_buy_ratio_text"], "taker_buy_ratio", derived=True)
                with localcontext(research._CONTEXT):
                    position["taker_buy_pct"] = ratio * Decimal("100")
            if derivative["funding_text"] is not None:
                position["funding_rate"] = ipc.decimal_text(
                    derivative["funding_text"], "funding", derived=True)

        if chip is not None and type(chip) is not dict:
            raise MarketIntelError("invalid_dealer_chip")
        snapshot = make_dealer_snapshot(
            symbol=symbol, observed_at_ms=observed_at_ms, position=position, chip=chip)
        self.record_dealer_snapshot(snapshot)
        return snapshot

    def record_onchain_activity(self, activity):
        from catos.market_p1 import OnchainActivity
        if not isinstance(activity, OnchainActivity):
            raise MarketIntelError("invalid_onchain_activity")
        values = (
            activity.symbol, activity.chain, activity.observed_at_ms, activity.outgoing_distinct,
            activity.baseline_days, _text(activity.baseline_live), _text(activity.baseline_anchor),
            _text(activity.live_ratio), _text(activity.anchored_ratio), activity.state,
            activity.first_flag_at_ms, activity.plateau_started_at_ms, activity.consecutive_days,
        )
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self._insert_exact(
                "onchain_activity",
                ("symbol", "chain", "observed_at_ms", "outgoing_distinct", "baseline_days",
                 "baseline_live_text", "baseline_anchor_text", "live_ratio_text",
                 "anchored_ratio_text", "state", "first_flag_at_ms", "plateau_started_at_ms",
                 "consecutive_days"),
                values, "symbol=? AND chain=? AND observed_at_ms=?", values[:3],
            )
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def record_onchain_source_run(self, *, source, symbol, chain, observed_at_ms,
                                  status, source_scope, evidence, issues=()):
        """Persist immutable provider/source evidence separately from the reducer output."""
        if type(source) is not str or not source.strip():
            raise MarketIntelError("invalid_onchain_source_run")
        if type(symbol) is not str or not symbol.endswith("-USDT-SWAP"):
            raise MarketIntelError("invalid_onchain_source_run")
        if type(chain) is not str or not chain.strip():
            raise MarketIntelError("invalid_onchain_source_run")
        ipc.integer(observed_at_ms, "observed_at_ms")
        if status not in ("ok", "issues"):
            raise MarketIntelError("invalid_onchain_source_run")
        if type(source_scope) is not dict or type(evidence) is not dict:
            raise MarketIntelError("invalid_onchain_source_run")
        if type(issues) not in (tuple, list):
            raise MarketIntelError("invalid_onchain_source_run")
        values = (
            source.strip(), symbol, chain.strip(), observed_at_ms, status,
            _json(_wire(source_scope)), _json(_wire(evidence)), _json(_wire(list(issues))),
        )
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self._insert_exact(
                "onchain_source_run",
                ("source", "symbol", "chain", "observed_at_ms", "status",
                 "source_scope_json", "evidence_json", "issues_json"),
                values,
                "source=? AND symbol=? AND chain=? AND observed_at_ms=?",
                values[:4],
            )
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def record_feature_set(self, features, *, trade_window=None, provenance=None):
        from catos.market_features import FeatureSet, TradeWindow
        if not isinstance(features, FeatureSet):
            raise MarketIntelError("invalid_feature_set")
        if trade_window is not None and not isinstance(trade_window, TradeWindow):
            raise MarketIntelError("invalid_trade_window")
        payload = _json(_wire(asdict(features)))
        provenance_json = _json(_wire({} if provenance is None else provenance))
        complete = bool(trade_window is not None and trade_window.complete)
        flow_values = (
            features.symbol, features.observed_at_ms, _text(features.cvd_quote),
            _text(features.taker_buy_ratio), features.trade_count,
            None if trade_window is None else trade_window.start_ms,
            None if trade_window is None else trade_window.end_ms,
            1 if complete else 0, provenance_json)
        feature_values = (features.symbol, features.observed_at_ms, features.feature_version, payload)
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self._insert_exact("feature_snapshot",
                ("symbol", "observed_at_ms", "feature_version", "payload_json"), feature_values,
                "symbol=? AND observed_at_ms=? AND feature_version=?", feature_values[:3])
            self._insert_exact("flow_snapshot",
                ("symbol", "observed_at_ms", "cvd_quote_text", "taker_buy_ratio_text", "trade_count",
                 "trade_window_start_ms", "trade_window_end_ms", "trade_window_complete", "provenance_json"),
                flow_values, "symbol=? AND observed_at_ms=?", flow_values[:2])
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def record_signal_bundle(self, bundle, *, source_snapshot_ids=()):
        """Persist all L2 states, confirmed hits, and all pattern evaluation states.

        `signal_state` retains every one of the 14 L2 evaluations for each scan.
        `signal_hit` intentionally remains hits-only. Pattern rows retain
        MISS/MISSING_DATA in evidence_json so missing input is never collapsed.
        """
        from catos.market_signals import Evaluation, HIT, SignalBundle
        if not isinstance(bundle, SignalBundle) or type(source_snapshot_ids) is not tuple:
            raise MarketIntelError("invalid_signal_bundle")
        if any(type(value) is not str or not value for value in source_snapshot_ids):
            raise MarketIntelError("invalid_source_snapshot_ids")

        def identity(prefix, kind, version):
            raw = f"{prefix}:{bundle.symbol}:{bundle.observed_at_ms}:{version}:{kind}"
            return hashlib.sha256(raw.encode("utf-8")).hexdigest()

        source_json = _json(list(source_snapshot_ids))
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            for item in bundle.signals:
                if not isinstance(item, Evaluation):
                    raise MarketIntelError("invalid_signal_bundle")
                evidence = _json(_wire(dict(item.evidence) | {"evaluation_status": item.status}))
                thresholds = _json(_wire(dict(item.thresholds)))
                state_values = (
                    bundle.symbol, bundle.observed_at_ms, item.kind, item.status,
                    bundle.signal_version, evidence, thresholds, source_json,
                )
                self._insert_exact(
                    "signal_state",
                    ("symbol", "observed_at_ms", "signal_type", "status", "signal_version",
                     "evidence_json", "threshold_json", "source_snapshot_ids_json"),
                    state_values,
                    "symbol=? AND observed_at_ms=? AND signal_type=? AND signal_version=?",
                    (bundle.symbol, bundle.observed_at_ms, item.kind, bundle.signal_version),
                )
                if item.status != HIT:
                    continue
                values = (identity("signal", item.kind, bundle.signal_version), bundle.symbol,
                          bundle.observed_at_ms, item.kind, bundle.signal_version,
                          evidence, thresholds, source_json)
                self._insert_exact("signal_hit",
                    ("hit_id", "symbol", "observed_at_ms", "signal_type", "signal_version",
                     "evidence_json", "threshold_json", "source_snapshot_ids_json"), values,
                    "hit_id=?", (values[0],))
            for item in bundle.patterns:
                if not isinstance(item, Evaluation):
                    raise MarketIntelError("invalid_signal_bundle")
                evidence = _json(_wire(dict(item.evidence) | {
                    "evaluation_status": item.status,
                    "thresholds": dict(item.thresholds),
                    "pattern_version": bundle.pattern_version,
                }))
                values = (identity("pattern", item.kind, bundle.pattern_version), bundle.symbol,
                          bundle.observed_at_ms, item.kind, 1 if item.status == HIT else 0, evidence)
                self._insert_exact("pattern_hit",
                    ("hit_id", "symbol", "observed_at_ms", "pattern_type", "active", "evidence_json"),
                    values, "hit_id=?", (values[0],))
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def record_cross_axis(self, symbol, observed_at_ms, selection, *, source_snapshot_ids=()):
        """Persist published Alpha+/Alpha eligibility without adding a ranking score."""
        from catos.market_signals import CROSS_AXIS_TYPES, CrossAxisSelection, Evaluation
        if (type(symbol) is not str or not symbol.endswith("-USDT-SWAP")
                or type(observed_at_ms) is not int
                or not isinstance(selection, CrossAxisSelection)
                or type(source_snapshot_ids) is not tuple):
            raise MarketIntelError("invalid_cross_axis_selection")
        if any(type(value) is not str or not value for value in source_snapshot_ids):
            raise MarketIntelError("invalid_source_snapshot_ids")
        if selection.selected is not None and selection.selected not in CROSS_AXIS_TYPES:
            raise MarketIntelError("invalid_cross_axis_selection")
        if (len(selection.evaluations) != len(CROSS_AXIS_TYPES)
                or {item.kind for item in selection.evaluations} != set(CROSS_AXIS_TYPES)
                or any(not isinstance(item, Evaluation) for item in selection.evaluations)):
            raise MarketIntelError("invalid_cross_axis_selection")

        source_json = _json(list(source_snapshot_ids))
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            for item in selection.evaluations:
                values = (
                    symbol,
                    observed_at_ms,
                    item.kind,
                    item.status,
                    1 if selection.selected == item.kind else 0,
                    selection.version,
                    _json(_wire(dict(item.evidence))),
                    _json(_wire(dict(item.thresholds))),
                    source_json,
                )
                self._insert_exact(
                    "cross_axis_evaluation",
                    ("symbol", "observed_at_ms", "axis_type", "status", "selected",
                     "cross_axis_version", "evidence_json", "threshold_json",
                     "source_snapshot_ids_json"),
                    values,
                    "symbol=? AND observed_at_ms=? AND axis_type=? AND cross_axis_version=?",
                    (symbol, observed_at_ms, item.kind, selection.version),
                )
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def record_status_labels(self, symbol, observed_at_ms, bundle, *, source_snapshot_ids=()):
        """Persist versioned Guide status-label evaluations."""
        from catos.market_signals import STATUS_LABEL_TYPES, Evaluation, StatusLabelBundle
        if (type(symbol) is not str or not symbol.endswith("-USDT-SWAP")
                or type(observed_at_ms) is not int
                or not isinstance(bundle, StatusLabelBundle)
                or type(source_snapshot_ids) is not tuple):
            raise MarketIntelError("invalid_status_label_bundle")
        if any(type(value) is not str or not value for value in source_snapshot_ids):
            raise MarketIntelError("invalid_source_snapshot_ids")
        if (len(bundle.labels) != len(STATUS_LABEL_TYPES)
                or {item.kind for item in bundle.labels} != set(STATUS_LABEL_TYPES)
                or any(not isinstance(item, Evaluation) for item in bundle.labels)):
            raise MarketIntelError("invalid_status_label_bundle")

        source_json = _json(list(source_snapshot_ids))
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            for item in bundle.labels:
                values = (
                    symbol,
                    observed_at_ms,
                    item.kind,
                    item.status,
                    bundle.version,
                    _json(_wire(dict(item.evidence))),
                    _json(_wire(dict(item.thresholds))),
                    source_json,
                )
                self._insert_exact(
                    "status_label_snapshot",
                    ("symbol", "observed_at_ms", "label_type", "status", "label_version",
                     "evidence_json", "threshold_json", "source_snapshot_ids_json"),
                    values,
                    "symbol=? AND observed_at_ms=? AND label_type=? AND label_version=?",
                    (symbol, observed_at_ms, item.kind, bundle.version),
                )
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def record_scan_transition(self, transition):
        """Materialize a pure P0-D transition without recomputing lifecycle state."""
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self._record_scan_transition_uncommitted(transition)
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def _record_scan_transition_uncommitted(self, transition):
        from catos.market_lifecycle import ScanTransition, ViewTransition
        if not isinstance(transition, ScanTransition):
            raise MarketIntelError("invalid_scan_transition")
        if any(not isinstance(item, ViewTransition)
               for item in (transition.flow, transition.opportunity, transition.risk)):
            raise MarketIntelError("invalid_scan_transition")

        smf = transition.smf
        component_json = None if smf.components is None else _json(_wire(dict(smf.components)))
        smf_values = (
            smf.symbol, smf.observed_at_ms, _text(smf.score), smf.grade,
            smf.model_version, component_json, _text(smf.confidence),
        )
        self._insert_exact(
            "smf_snapshot",
            ("symbol", "observed_at_ms", "score_text", "grade", "model_version",
             "component_json", "confidence_text"),
            smf_values,
            "symbol=? AND observed_at_ms=? AND model_version=?",
            (smf.symbol, smf.observed_at_ms, smf.model_version),
        )
        for item in (transition.flow, transition.opportunity, transition.risk):
            evidence = _json(_wire(dict(item.evidence) | {
                "event": item.event,
                "lifecycle_version": transition.lifecycle_version,
            }))
            values = (
                transition.symbol, item.view_name, item.observed_at_ms, item.state,
                _text(item.score), item.consecutive_count, evidence,
            )
            self._insert_exact(
                "view_state",
                ("symbol", "view_name", "observed_at_ms", "state", "score_text",
                 "consecutive_count", "evidence_json"),
                values,
                "symbol=? AND view_name=? AND observed_at_ms=?",
                values[:3],
            )

    def _record_cycle_uncommitted(self, transition):
        from catos.market_proof import CycleTransition
        if not isinstance(transition, CycleTransition):
            raise MarketIntelError("invalid_cycle_transition")
        before = transition.before
        after = transition.after
        if after is None:
            if before is not None or transition.event is not None:
                raise MarketIntelError("invalid_cycle_transition")
            return
        values = (
            after.cycle_id, after.symbol, after.started_at_ms, after.ended_at_ms, _text(after.first_push_price),
            after.latest_push_at_ms, after.push_count, _text(after.peak_price),
            _text(after.trough_price), _text(after.mfe_pct), _text(after.mae_pct), after.end_reason,
        )
        row = self.connection.execute("SELECT * FROM cycle WHERE cycle_id=?", (after.cycle_id,)).fetchone()
        if row is None:
            if before is not None and before.cycle_id == after.cycle_id:
                raise MarketIntelError("cycle_state_conflict")
            self.connection.execute(
                """INSERT INTO cycle(cycle_id,symbol,started_at_ms,ended_at_ms,first_push_price_text,
                   latest_push_at_ms,push_count,peak_price_text,trough_price_text,mfe_text,mae_text,end_reason)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", values)
        else:
            current = dict(row)
            next_wire = dict(zip((
                "cycle_id", "symbol", "started_at_ms", "ended_at_ms", "first_push_price_text", "latest_push_at_ms",
                "push_count", "peak_price_text", "trough_price_text", "mfe_text", "mae_text", "end_reason",
            ), values))
            if all(current[key] == value for key, value in next_wire.items()):
                pass
            else:
                if before is None:
                    raise MarketIntelError("cycle_state_conflict")
                before_wire = {
                    "symbol": before.symbol,
                    "started_at_ms": before.started_at_ms,
                    "ended_at_ms": before.ended_at_ms,
                    "first_push_price_text": _text(before.first_push_price),
                    "latest_push_at_ms": before.latest_push_at_ms,
                    "push_count": before.push_count,
                    "peak_price_text": _text(before.peak_price),
                    "trough_price_text": _text(before.trough_price),
                    "mfe_text": _text(before.mfe_pct),
                    "mae_text": _text(before.mae_pct),
                    "end_reason": before.end_reason,
                }
                if any(current[key] != value for key, value in before_wire.items()):
                    raise MarketIntelError("cycle_state_conflict")
                self.connection.execute(
                    """UPDATE cycle SET ended_at_ms=?,latest_push_at_ms=?,push_count=?,peak_price_text=?,
                       trough_price_text=?,mfe_text=?,mae_text=?,end_reason=? WHERE cycle_id=?""",
                    (after.ended_at_ms, after.latest_push_at_ms, after.push_count, _text(after.peak_price),
                     _text(after.trough_price), _text(after.mfe_pct), _text(after.mae_pct),
                     after.end_reason, after.cycle_id),
                )
        if transition.event is not None:
            event = transition.event
            event_values = (
                event.event_id, event.cycle_id, event.symbol, event.observed_at_ms,
                event.event_type, event.view_name, _json(_wire(dict(event.payload))),
            )
            self._insert_exact(
                "cycle_event",
                ("event_id", "cycle_id", "symbol", "observed_at_ms", "event_type", "view_name", "payload_json"),
                event_values, "event_id=?", (event.event_id,),
            )

    def _record_push_uncommitted(self, push):
        from catos.market_proof import FrozenPush
        if not isinstance(push, FrozenPush):
            raise MarketIntelError("invalid_push_snapshot")
        payload = _json(_wire({
            "proof_version": push.proof_version,
            "price": push.price,
            "active_l2": list(push.active_l2),
            "patterns": dict(push.patterns),
            "smf": dict(push.smf),
            "views": dict(push.views),
            "source_freshness": dict(push.source_freshness),
            "market_regime": dict(push.market_regime),
            "pre_entry_volatility": push.pre_entry_volatility,
        }))
        natural = self.connection.execute(
            """SELECT push_id,frozen_payload_json,feature_version,signal_version FROM push_snapshot
               WHERE symbol=? AND pushed_at_ms=? AND push_type=? AND cycle_id IS ?""",
            (push.symbol, push.pushed_at_ms, push.push_type, push.cycle_id),
        ).fetchone()
        if natural is not None and tuple(natural) != (push.push_id, payload, push.feature_version, push.signal_version):
            raise MarketIntelError("snapshot_conflict")
        if natural is not None:
            return False
        values = (push.push_id, push.symbol, push.pushed_at_ms, push.push_type, push.cycle_id,
                  payload, push.feature_version, push.signal_version)
        self._insert_exact(
            "push_snapshot",
            ("push_id", "symbol", "pushed_at_ms", "push_type", "cycle_id", "frozen_payload_json",
             "feature_version", "signal_version"),
            values, "push_id=?", (push.push_id,),
        )
        return True

    def record_p0e_scan(self, lifecycle, cycle, push=None):
        """Atomically persist scan/lifecycle/cycle and any frozen push before notification."""
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self._record_scan_transition_uncommitted(lifecycle)
            self._record_cycle_uncommitted(cycle)
            inserted = False
            if push is not None:
                inserted = self._record_push_uncommitted(push)
            self.connection.commit()
            return inserted
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def record_proof_result(self, result):
        from catos.market_proof import ProofResult
        if not isinstance(result, ProofResult):
            raise MarketIntelError("invalid_proof_result")
        values = (
            result.push_id, result.horizon, result.measured_at_ms, _text(result.return_pct),
            _text(result.mfe_pct), _text(result.mae_pct), _text(result.market_baseline_pct),
            _text(result.vol_matched_baseline_pct),
        )
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            if self.connection.execute(
                    "SELECT 1 FROM push_snapshot WHERE push_id=?", (result.push_id,)).fetchone() is None:
                raise MarketIntelError("unknown_push")
            self._insert_exact(
                "forward_return",
                ("push_id", "horizon", "measured_at_ms", "return_text", "mfe_text", "mae_text",
                 "market_baseline_text", "vol_matched_baseline_text"),
                values, "push_id=? AND horizon=?", values[:2],
            )
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def latest(self, symbol):
        """Return latest materialized market/derivative rows for read-only UI code."""
        market = self.connection.execute(
            "SELECT * FROM market_snapshot WHERE symbol=? ORDER BY observed_at_ms DESC LIMIT 1", (symbol,)).fetchone()
        derivative = self.connection.execute(
            "SELECT * FROM derivative_snapshot WHERE symbol=? ORDER BY observed_at_ms DESC LIMIT 1", (symbol,)).fetchone()
        return {
            "market": None if market is None else dict(market),
            "derivative": None if derivative is None else dict(derivative),
        }
