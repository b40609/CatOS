/**
 * GET /api/workspace/demo-bot — read-only OKX Demo Bot runs.
 * There is deliberately no write method: the Bot is started and stopped in the terminal.
 */
import type { DemoBotOverviewDTO, DemoBotRunDetailDTO } from '@/contracts/demo-bot';

export type DemoBotResult<T> = { ok: true; data: T } | { ok: false; error: string };

async function getJson<T>(url: string, signal?: AbortSignal): Promise<DemoBotResult<T>> {
  try {
    const res = await fetch(url, { headers: { Accept: 'application/json' }, signal });
    if (!res.ok) return { ok: false, error: `http_${res.status}` };
    const data = await res.json();
    if (data?.contract !== 'catos.demo-bot.v1') return { ok: false, error: 'contract_mismatch' };
    return { ok: true, data };
  } catch (error) {
    if ((error as Error)?.name === 'AbortError') return { ok: false, error: 'aborted' };
    return { ok: false, error: 'network_error' };
  }
}

export function fetchDemoBotOverview(signal?: AbortSignal): Promise<DemoBotResult<DemoBotOverviewDTO>> {
  return getJson<DemoBotOverviewDTO>('/api/workspace/demo-bot', signal);
}

export async function fetchDemoBotRun(runId: string, signal?: AbortSignal): Promise<DemoBotResult<DemoBotRunDetailDTO>> {
  const result = await getJson<{ contract: string; run: DemoBotRunDetailDTO }>(
    `/api/workspace/demo-bot/runs/${encodeURIComponent(runId)}`, signal);
  return result.ok ? { ok: true, data: result.data.run } : result;
}
