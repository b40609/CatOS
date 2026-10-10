/**
 * Strategy contract definition
 * Strict adherence to catOS v1 Python strategy artifact:
 * contract = "catos.python-strategy.v1"
 */

export type BoundedJsonPrimitive = string | number | boolean | null;
export type BoundedJsonValue =
  | BoundedJsonPrimitive
  | BoundedJsonPrimitive[]
  | { [key: string]: BoundedJsonPrimitive | BoundedJsonPrimitive[] };

export interface StrategyArtifact {
  contract: 'catos.python-strategy.v1';
  strategy_id: string; // 1-64 ASCII token
  version: string;     // 1-64 ASCII token
  name: string;        // max 120 chars
  description: string; // max 2000 chars
  source: string;      // Python source code (max 12000 UTF-8 bytes)
  defaults: Record<string, BoundedJsonValue>; // Universal bounded JSON, Decimal as string, no floats
  warmup_bars: number; // 1-16
}

export interface StrategyEntry {
  artifact: StrategyArtifact;
  artifact_hash: string;
  allowed_modes: ('local' | 'demo' | 'live')[];
  created_at: string;
}

export interface StrategyContractInfo {
  contract: 'catos.python-strategy.v1';
  runtime: string;
  max_source_bytes: number;
  max_parameters_bytes: number;
  warmup_range: [number, number];
}

