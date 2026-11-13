/**
 * GET /api/workspace/replay — read-only approvals and Bot replay progress.
 * There is deliberately no write method: approvals and replays are CLI-only.
 */
import type { ReplayOverviewDTO } from '@/contracts/replay';

export type ReplayResult = { ok: true; data: ReplayOverviewDTO } | { ok: false; error: string };

export async function fetchReplayOverview(signal?: AbortSignal): Promise<ReplayResult> {
  try {
    const res = await fetch('/api/workspace/replay', { headers: { Accept: 'application/json' }, signal });
    if (!res.ok) return { ok: false, error: `http_${res.status}` };
    const data = (await res.json()) as ReplayOverviewDTO;
    if (data?.contract !== 'catos.replay.v1') return { ok: false, error: 'contract_mismatch' };
    return { ok: true, data };
  } catch (error) {
    if ((error as Error)?.name === 'AbortError') return { ok: false, error: 'aborted' };
    return { ok: false, error: 'network_error' };
  }
}
