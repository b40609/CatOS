/**
 * Shared authoritative status derivation helpers so UI surfaces never lie about
 * latched risk, abnormal stops, silent read failures, or offline sync (2026-11-27).
 */
import type { DemoBotRunSummaryDTO, DemoBotWatchDTO } from '@/contracts/demo-bot';
import type { RiskStatus } from '@/contracts/risk';
import { formatClock, shortId } from '@/lib/format';

/** Stop reasons initiated intentionally by the user (matches catos.demo_bot_liveness.OPERATOR_STOPS). */
export const OPERATOR_STOPS = new Set(['operator_stop', 'operator_stop_file', 'interrupted']);

export function isOperatorStop(stopReason: string | null | undefined): boolean {
  return typeof stopReason === 'string' && OPERATOR_STOPS.has(stopReason);
}

export function hasNonZeroPosition(position: string | null | undefined): boolean {
  if (position === null || position === undefined || position.trim() === '') return false;
  return !/^-?0+(\.0*)?$/.test(position.trim());
}

export function backendSyncText(
  online: boolean,
  researchVer: { restart_required?: boolean } | null | undefined,
  workspaceVer: { restart_required?: boolean } | null | undefined
): string {
  if (!online || !researchVer) return '不適用（後端未連接）';
  if (researchVer.restart_required || workspaceVer?.restart_required) {
    return '源碼已異動（需重啟服務）';
  }
  return '與磁碟源碼一致';
}

export interface CushionStatusInput {
  currentPct: number | null;
  softPct: number | null;
  hardPct: number | null;
  riskStatus: RiskStatus | null | undefined;
  riskMode: 'RUN' | 'NO_INCREASE' | 'FLAT' | null | undefined;
  killEngaged: boolean;
}

export interface CushionStatusResult {
  statusText: string;
  statusTone: string;
  pinTone: string;
  fillTone: string;
}

/**
 * Authoritative risk status takes precedence over any float-computed distance:
 * Soft/Hard latches do not clear on price rebound (AGENTS.md INVARIANTS).
 */
export function deriveCushionStatus(input: CushionStatusInput): CushionStatusResult {
  const { currentPct, softPct, hardPct, riskStatus, riskMode, killEngaged } = input;

  if (riskStatus === 'hard_latch') {
    return {
      statusText: 'Hard 鎖住',
      statusTone: 'text-rose-400',
      pinTone: 'bg-rose-400',
      fillTone: 'bg-rose-500/45',
    };
  }
  if (killEngaged) {
    return {
      statusText: 'Kill 鎖住',
      statusTone: 'text-rose-400',
      pinTone: 'bg-rose-400',
      fillTone: 'bg-rose-500/45',
    };
  }
  if (riskStatus === 'soft_latch') {
    return {
      statusText: 'Soft 鎖住',
      statusTone: 'text-rose-400',
      pinTone: 'bg-rose-400',
      fillTone: 'bg-rose-500/40',
    };
  }
  if (riskMode === 'FLAT') {
    return {
      statusText: '清倉鎖住',
      statusTone: 'text-rose-400',
      pinTone: 'bg-rose-400',
      fillTone: 'bg-rose-500/45',
    };
  }
  if (riskStatus === 'missing') {
    return {
      statusText: '基準待建立',
      statusTone: 'text-amber-400',
      pinTone: 'bg-amber-400',
      fillTone: 'bg-amber-400/35',
    };
  }
  if (riskMode === 'NO_INCREASE') {
    return {
      statusText: '禁增倉',
      statusTone: 'text-amber-400',
      pinTone: 'bg-amber-400',
      fillTone: 'bg-amber-400/35',
    };
  }

  if (currentPct !== null && softPct !== null) {
    const distToSoft = currentPct + softPct;
    if (hardPct !== null && currentPct <= -hardPct) {
      return {
        statusText: '已達 Hard',
        statusTone: 'text-rose-400',
        pinTone: 'bg-rose-400',
        fillTone: 'bg-rose-500/45',
      };
    }
    if (distToSoft <= 0) {
      return {
        statusText: '已達 Soft',
        statusTone: 'text-rose-400',
        pinTone: 'bg-rose-400',
        fillTone: 'bg-rose-500/40',
      };
    }
    if (currentPct < 0) {
      const warnClose = distToSoft <= softPct * 0.4;
      return {
        statusText: `距 Soft ${distToSoft.toFixed(2)}%`,
        statusTone: warnClose ? 'text-rose-400' : 'text-amber-400',
        pinTone: warnClose ? 'bg-rose-400' : 'bg-amber-400',
        fillTone: 'bg-amber-400/35',
      };
    }
    return {
      statusText: `距 Soft ${distToSoft.toFixed(2)}%`,
      statusTone: 'text-emerald-400',
      pinTone: 'bg-emerald-400',
      fillTone: 'bg-emerald-400/35',
    };
  }

  return {
    statusText: '不適用',
    statusTone: 'text-muted-foreground',
    pinTone: 'bg-emerald-400',
    fillTone: 'bg-emerald-400/35',
  };
}

export interface DemoBotActionItemSpec {
  id: string;
  sev: 'p0' | 'p1';
  code: string;
  tone: 'down' | 'warn';
  alert: boolean;
  time: string | null;
  tag: string;
  title: string;
  symbol: string;
  brief: string;
  hero: { value: string; tone?: 'down' | 'warn' };
  fact: string;
  metrics: { label: string; value: string; tone?: 'down' | 'warn' }[];
  primaryAction: { label: string; route: string; tone?: 'danger' };
}

function clockFromMs(ms: number | null | undefined): string | null {
  if (ms === null || ms === undefined) return null;
  return formatClock(ms);
}

const UNPROTECTED_WHY: Record<string, string> = {
  ratio_zero: '這個 run 的保底停損比例是 0%',
  unconfirmed: '條件單還沒確認或被 OKX 拒絕',
  no_stop_recorded: '紀錄裡沒有掛上條件單',
  stop_removed: '條件單已撤銷',
};

export function unprotectedText(why: string | null | undefined): string {
  return UNPROTECTED_WHY[why ?? ''] ?? 'OKX 上沒有已確認的條件單';
}

/** Nobody is watching a Bot that is running: the Guardian never ran here or went silent (review F3). */
export function guardianSilent(
  runs: DemoBotRunSummaryDTO[],
  watch: DemoBotWatchDTO | null | undefined
): boolean {
  return Boolean(watch?.guardian.stale) && runs.some((run) => run.state === 'running');
}

export function buildDemoBotActionItems(params: {
  runs: DemoBotRunSummaryDTO[];
  demoBotError: string | null;
  watch?: DemoBotWatchDTO | null;
}): DemoBotActionItemSpec[] {
  const { runs, demoBotError, watch } = params;
  const list: DemoBotActionItemSpec[] = [];

  if (demoBotError) {
    list.push({
      id: 'p1-demo-read-error',
      sev: 'p1',
      code: 'READ',
      tone: 'warn',
      alert: true,
      time: null,
      tag: '讀取失敗',
      title: '讀不到模擬盤 Bot',
      symbol: 'OKX Demo',
      brief: `無法讀取 /api/workspace/demo-bot（${demoBotError}）`,
      hero: { value: '讀取失敗', tone: 'warn' },
      fact: `無法取得模擬盤 Bot 狀態（${demoBotError}），請確認 8770 服務與資料目錄可讀`,
      metrics: [
        { label: '端點', value: '/api/workspace/demo-bot' },
        { label: '錯誤', value: demoBotError, tone: 'warn' },
      ],
      primaryAction: { label: '檢視 Bot', route: '/demo-bot' },
    });
    return list;
  }

  if (guardianSilent(runs, watch)) {
    const last = clockFromMs(watch?.guardian.checked_at_ms);
    list.push({
      id: 'p1-demo-guardian-silent',
      sev: 'p1',
      code: 'WATCH',
      tone: 'warn',
      alert: true,
      time: last,
      tag: '監看沒在跑',
      title: '模擬盤 Bot 沒有人監看',
      symbol: 'OKX Demo',
      brief: last ? `監看程式最後一次檢查 ${last}` : '監看程式在這台電腦沒有跑過',
      hero: { value: '監看沒在跑', tone: 'warn' },
      fact: 'Bot 停下或部位沒有停損時不會有人通知你；請到工作排程器確認 CatOS-DemoBot-Guardian-5m 還在',
      metrics: [
        { label: '最後檢查', value: last ?? '沒有紀錄', tone: 'warn' },
        { label: '排程', value: 'CatOS-DemoBot-Guardian-5m' },
      ],
      primaryAction: { label: '檢視 Bot', route: '/demo-bot' },
    });
  }

  const latestDemoByStrat = new Map<string, DemoBotRunSummaryDTO>();
  for (const run of runs) {
    const key = run.strategy_id ?? run.run_id;
    const prev = latestDemoByStrat.get(key);
    if (!prev || (run.created_at_ms ?? 0) > (prev.created_at_ms ?? 0)) {
      latestDemoByStrat.set(key, run);
    }
  }

  for (const run of latestDemoByStrat.values()) {
    const openPos = hasNonZeroPosition(run.position);
    if (run.state === 'failed') {
      list.push({
        id: `p0-demo-failed-${run.run_id}`,
        sev: 'p0',
        code: 'FAIL',
        tone: 'down',
        alert: true,
        time: clockFromMs(run.updated_at_ms),
        tag: '執行失敗',
        title: run.strategy_id ?? shortId(run.run_id),
        symbol: 'OKX Demo',
        brief: `run ${shortId(run.run_id)} · ${run.stop_reason ?? '執行錯誤'}`,
        hero: { value: `${run.position ?? '0'} 張`, tone: 'down' },
        fact: `run ${shortId(run.run_id)} · ${run.stop_reason ?? '執行錯誤'} · 部位 ${run.position ?? '0'} 張`,
        metrics: [
          { label: 'run', value: shortId(run.run_id) },
          { label: '原因', value: run.stop_reason ?? '執行錯誤', tone: 'down' },
          { label: '部位', value: `${run.position ?? '0'} 張` },
        ],
        primaryAction: { label: '檢視 Bot', route: '/demo-bot', tone: 'danger' },
      });
    } else if (run.state === 'running' && run.stale) {
      const sev = openPos ? 'p0' : 'p1';
      const tone = openPos ? 'down' : 'warn';
      list.push({
        id: `${sev}-demo-stale-${run.run_id}`,
        sev,
        code: 'STALE',
        tone,
        alert: true,
        time: clockFromMs(run.updated_at_ms),
        tag: openPos ? '帶倉無回應' : '無回應',
        title: run.strategy_id ?? shortId(run.run_id),
        symbol: 'OKX Demo',
        brief: `run ${shortId(run.run_id)} 逾時未更新 · 部位 ${run.position ?? '0'} 張`,
        hero: { value: '無回應', tone },
        fact: `run ${shortId(run.run_id)} 心跳或 K 線逾時未更新 · 當前部位 ${run.position ?? '0'} 張`,
        metrics: [
          { label: 'run', value: shortId(run.run_id) },
          { label: '狀態', value: '心跳或 K 線逾時未更新', tone },
          { label: '部位', value: `${run.position ?? '0'} 張`, tone: openPos ? 'down' : undefined },
        ],
        primaryAction: { label: '檢視 Bot', route: '/demo-bot', tone: openPos ? 'danger' : undefined },
      });
    } else if (run.state === 'running' && run.unprotected) {
      const why = unprotectedText(run.unprotected_why);
      list.push({
        id: `p0-demo-unprotected-${run.run_id}`,
        sev: 'p0',
        code: 'STOP',
        tone: 'down',
        alert: true,
        time: clockFromMs(run.updated_at_ms),
        tag: '帶倉無停損',
        title: run.strategy_id ?? shortId(run.run_id),
        symbol: 'OKX Demo',
        brief: `run ${shortId(run.run_id)} · 部位 ${run.position ?? '0'} 張 · ${why}`,
        hero: { value: '無停損', tone: 'down' },
        fact: `run ${shortId(run.run_id)} 有部位，但 OKX 上沒有已確認的保底停損條件單（${why}）`,
        metrics: [
          { label: 'run', value: shortId(run.run_id) },
          { label: '部位', value: `${run.position ?? '0'} 張`, tone: 'down' },
          { label: '保底停損', value: why, tone: 'down' },
        ],
        primaryAction: { label: '檢視 Bot', route: '/demo-bot', tone: 'danger' },
      });
    } else if (run.state === 'stopped' && !isOperatorStop(run.stop_reason)) {
      const critical =
        openPos ||
        String(run.stop_reason ?? '').startsWith('flatten_failed') ||
        String(run.stop_reason ?? '').startsWith('disaster_stop_incomplete') ||
        String(run.stop_reason ?? '').startsWith('position_mismatch');
      const sev = critical ? 'p0' : 'p1';
      const tone = critical ? 'down' : 'warn';
      const reason = run.stop_reason ?? '非人工停止';
      list.push({
        id: `${sev}-demo-stopped-${run.run_id}`,
        sev,
        code: 'STOP',
        tone,
        alert: true,
        time: clockFromMs(run.updated_at_ms),
        tag: '異常停止',
        title: run.strategy_id ?? shortId(run.run_id),
        symbol: 'OKX Demo',
        brief: `run ${shortId(run.run_id)} · ${reason}`,
        hero: { value: `${run.position ?? '0'} 張`, tone },
        fact: `run ${shortId(run.run_id)} 非人工停止（${reason}）· 部位 ${run.position ?? '0'} 張`,
        metrics: [
          { label: 'run', value: shortId(run.run_id) },
          { label: '停止原因', value: reason, tone },
          { label: '部位', value: `${run.position ?? '0'} 張` },
        ],
        primaryAction: { label: '檢視 Bot', route: '/demo-bot', tone: critical ? 'danger' : undefined },
      });
    }
  }

  return list;
}
