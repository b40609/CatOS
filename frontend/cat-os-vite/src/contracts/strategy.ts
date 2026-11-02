/**
 * Registered strategy entry (GET /api/workspace/simulation/strategies).
 * v1 exposes exactly one fixed, inspected SMA module; there is no upload flow,
 * so no source code travels over this contract.
 */
import type { BotMode } from './bot';

export interface RegisteredStrategyDTO {
  strategy_id: string;
  version: string;
  name: string;
  description: string;
  artifact_hash: string;
  entry: string;
  approval_state: 'approved';
  allowed_modes: BotMode[];
  defaults: {
    parameters: Record<string, string | number>;
    warmup_bars: number;
  };
  source_files: string[];
  kind: 'registered_python_module';
}
