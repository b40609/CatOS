/**
 * Shared read-only workspace signal loader for Overview cards (Strategy Pipeline & Action Queue).
 * Fetches /api/research/catalog, /api/workspace/replay and /api/workspace/demo-bot in normal mode;
 * returns synchronized design-review fixtures only when `?preview=pick` is active.
 */
import { useEffect, useState } from 'react';
import { fetchDemoBotOverview } from '@/adapters/demo-bot-api-adapter';
import { isPreviewPickMode } from '@/adapters/preview-pick-fixture';
import { fetchReplayOverview } from '@/adapters/replay-api-adapter';
import type { ResearchCatalog } from '@/adapters/research-api-adapter';
import type { DemoBotOverviewDTO } from '@/contracts/demo-bot';
import type { ReplayOverviewDTO } from '@/contracts/replay';

export interface OverviewSignals {
  previewPick: boolean;
  loaded: boolean;
  catalog: ResearchCatalog | null;
  replay: ReplayOverviewDTO | null;
  demoBot: DemoBotOverviewDTO | null;
  catalogError: string | null;
  replayError: string | null;
  demoBotError: string | null;
}

const EMPTY_SIGNALS: OverviewSignals = {
  previewPick: false,
  loaded: false,
  catalog: null,
  replay: null,
  demoBot: null,
  catalogError: null,
  replayError: null,
  demoBotError: null,
};

const POLL_MS = 30_000;

let cached: OverviewSignals = EMPTY_SIGNALS;
let inflight: Promise<OverviewSignals> | null = null;
const listeners = new Set<(s: OverviewSignals) => void>();
let pollTimer: number | null = null;

function publish(next: OverviewSignals) {
  cached = next;
  for (const fn of listeners) fn(next);
}

async function fetchCatalogSafe(signal?: AbortSignal): Promise<{ data: ResearchCatalog | null; error: string | null }> {
  try {
    const res = await fetch('/api/research/catalog', { headers: { Accept: 'application/json' }, signal });
    if (!res.ok) return { data: null, error: `http_${res.status}` };
    return { data: (await res.json()) as ResearchCatalog, error: null };
  } catch {
    return { data: null, error: 'network_error' };
  }
}

async function refreshSignals(): Promise<OverviewSignals> {
  if (isPreviewPickMode()) {
    const next: OverviewSignals = { ...EMPTY_SIGNALS, previewPick: true, loaded: true };
    publish(next);
    return next;
  }
  if (inflight) return inflight;
  inflight = (async () => {
    const [catalogRes, replayRes, demoRes] = await Promise.all([
      fetchCatalogSafe(),
      fetchReplayOverview(),
      fetchDemoBotOverview(),
    ]);
    const next: OverviewSignals = {
      previewPick: false,
      loaded: true,
      catalog: catalogRes.data,
      replay: replayRes.ok ? replayRes.data : null,
      demoBot: demoRes.ok ? demoRes.data : null,
      catalogError: catalogRes.error,
      replayError: replayRes.ok || replayRes.error === 'aborted' ? null : replayRes.error,
      demoBotError: demoRes.ok || demoRes.error === 'aborted' ? null : demoRes.error,
    };
    publish(next);
    return next;
  })().finally(() => {
    inflight = null;
  });
  return inflight;
}

function ensurePolling() {
  if (typeof window === 'undefined' || isPreviewPickMode()) return;
  if (pollTimer === null) {
    pollTimer = window.setInterval(() => {
      if (!document.hidden && listeners.size > 0) void refreshSignals();
    }, POLL_MS);
  }
}

function stopPollingIfIdle() {
  if (listeners.size === 0 && pollTimer !== null) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

export function useOverviewSignals(): OverviewSignals {
  const [state, setState] = useState<OverviewSignals>(() =>
    isPreviewPickMode() ? { ...EMPTY_SIGNALS, previewPick: true, loaded: true } : cached
  );

  useEffect(() => {
    if (isPreviewPickMode()) {
      setState({ ...EMPTY_SIGNALS, previewPick: true, loaded: true });
      return;
    }
    listeners.add(setState);
    if (!cached.loaded) void refreshSignals();
    else setState(cached);
    ensurePolling();
    return () => {
      listeners.delete(setState);
      stopPollingIfIdle();
    };
  }, []);

  return state;
}
