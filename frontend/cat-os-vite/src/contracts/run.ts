/**
 * Run snapshot (GET /api/workspace/simulation/runs/{run_id}); unchanged
 * backend contract plus the additive `lifecycle` list.
 */
import type { BotControlState } from './bot';

export interface RawRunEvent {
  kind: string;
  wall_time: string;
  wall_time_ms?: number;
  event_seq?: number;
  [key: string]: unknown;
}

export interface RunDTO {
  run_id: string;
  request_id: string;
  config: Record<string, unknown>;
  build_id: string;
  instance_id: string;
  created_at: string;
  control_state: BotControlState;
  cleanup_confirmed: boolean;
  stop_requested: boolean;
  stop_requested_at: string | null;
  bars: number;
  warmup_bars: number;
  fills: number;
  events: RawRunEvent[];
  events_omitted: number;
  error: string | null;
  finished_at: string | null;
  worker_closed: boolean;
  still_finishing: boolean;
  lifecycle?: RawRunEvent[];
  last_signal?: RawRunEvent;
  last_fill?: RawRunEvent;
  worker_pid?: number;
  last_synthetic_time_ms?: number;
}

export interface RunsResponseDTO {
  items: RunDTO[];
  state: 'available' | 'unavailable';
  issues: string[];
}
