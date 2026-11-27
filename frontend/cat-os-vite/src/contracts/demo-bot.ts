/**
 * Read-only OKX Demo Bot runs (GET /api/workspace/demo-bot, catos/demo_bot_view.py).
 * Starting and stopping the Bot stay in the terminal; nothing here mutates.
 */
import type { DecimalString } from './decimal';

export interface DemoBotRunSummaryDTO {
  run_id: string;
  created_at_ms: number | null;
  state: 'starting' | 'running' | 'stopped' | 'failed' | 'unknown' | string;
  /** Status says running, but nothing was written for over two bars: the process likely died. */
  stale: boolean;
  /** Running and holding a position with no confirmed disaster stop on OKX for over three minutes. */
  unprotected?: boolean;
  unprotected_why?: 'ratio_zero' | 'unconfirmed' | 'no_stop_recorded' | 'stop_removed' | string | null;
  stop_reason: string | null;
  bars: number;
  fills: number;
  position: DecimalString | null;
  updated_at_ms: number | null;
  finished_at_ms: number | null;
  strategy_id: string | null;
  version: string | null;
  parameters: Record<string, number> | null;
  timeframe_ms: number | null;
  quantity: DecimalString | null;
  inst_id: string | null;
  disaster_stop: DecimalString | null;
  approval_id: string | null;
  starting_equity: DecimalString | null;
  resumes: number;
}

export interface DemoBotFillDTO {
  time_ms: number | null;
  leg: string | null;
  cl_ord_id: string | null;
  state: string | null;
  quantity: DecimalString | null;
  side: 'buy' | 'sell';
  prices: DecimalString[];
  fees: DecimalString[];
}

export interface DemoBotEventDTO {
  time_ms: number | null;
  kind: string;
  [field: string]: unknown;
}

export interface DemoBotRunDetailDTO extends DemoBotRunSummaryDTO {
  last_bar: {
    open_time_ms: number | null;
    close: DecimalString | null;
    mark: DecimalString | null;
    equity: DecimalString | null;
    disposition: string | null;
    reason: string | null;
    target: DecimalString | null;
    risk_reasons: string[];
    time_ms: number | null;
  } | null;
  /** Last confirmed disaster stop on OKX; null when none is placed. */
  protection: { price: DecimalString; side: 'buy' | 'sell' | null; algo_id: string | null; since_ms: number | null } | null;
  fill_rows: DemoBotFillDTO[];
  events: DemoBotEventDTO[];
  stop_hint: string | null;
}

/** What a scheduled task last wrote; `stale` when it never ran here or has been silent for over 15 minutes. */
export interface DemoBotTaskDTO {
  checked_at_ms: number | null;
  stale: boolean;
}

export interface DemoBotWatchDTO {
  /** The Guardian: the outside check that tells the owner when the Bot stops or a position has no stop. */
  guardian: DemoBotTaskDTO & { verdict?: string | null; findings: { problem: string | null; message: string | null }[] };
  /** The autostart gate: continues the Bot after an interruption, never after a risk stop. */
  autostart: DemoBotTaskDTO & { action?: string | null; reason?: string | null; disabled: boolean };
}

export interface DemoBotOverviewDTO {
  contract: 'catos.demo-bot.v1';
  runs: DemoBotRunSummaryDTO[];
  current: DemoBotRunDetailDTO | null;
  watch?: DemoBotWatchDTO;
  observed_at_ms: number;
}
