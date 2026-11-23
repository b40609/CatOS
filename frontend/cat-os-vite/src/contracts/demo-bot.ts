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

export interface DemoBotOverviewDTO {
  contract: 'catos.demo-bot.v1';
  runs: DemoBotRunSummaryDTO[];
  current: DemoBotRunDetailDTO | null;
  observed_at_ms: number;
}
