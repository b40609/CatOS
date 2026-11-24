import { useState, useMemo, useRef, useEffect } from 'react';
import { useCatStore } from '@/state/catStore';
import type { EventDTO, EventLevel } from '@/contracts';
import { useOverviewSignals } from '@/lib/overview-signals';
import { useRouter } from '@/lib/router';
import { CardHeaderTitle } from './card-header-title';
import { CardHeaderTabs } from './card-header-tabs';
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Copy,
  Inbox,
  ShieldAlert,
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatClock, formatDateTime, formatDecimal, shortId } from '@/lib/format';

export type EventCategoryFilter = string;

export interface CategoryTabItem {
  id: string;
  label: string;
  shortLabel: string;
  badgeCount: number;
  isAlert?: boolean;
  isCritical?: boolean;
  filterFn: (ev: EventDTO) => boolean;
}

type ActionSeverity = 'p0' | 'p1' | 'p2' | 'p3';
type MetricTone = 'default' | 'warn' | 'up' | 'down' | 'blue' | 'teal';

interface ActionMetric {
  label: string;
  value: string;
  tone?: MetricTone;
}

interface ActionQueueItem {
  id: string;
  sev: ActionSeverity;
  tag: string;
  title: string;
  symbol?: string;
  fact: string;
  metrics?: ActionMetric[];
  primaryAction?: { label: string; route?: string; switchTab?: string; tone?: 'danger' | 'primary' };
  copyCommand?: { label: string; command: string };
}

const SEV_ORDER: Record<ActionSeverity, number> = { p0: 0, p1: 1, p2: 2, p3: 3 };

export const INCIDENT_ACTIVITY_PARAMS = {
  durationSec: 11,
  photonLength: 15,
  photonWidth: 0.5,
  photonBrightness: 100,
  glowSpread: 8,
  bloomIntensity: 30,
  glassBlur: 32,
  cardShimmer: 0,
  borderOpacity: 0,
} as const;

const {
  durationSec: DURATION_SEC,
  photonLength: PHOTON_LENGTH,
  photonWidth: PHOTON_WIDTH,
  photonBrightness: PHOTON_BRIGHTNESS,
  glowSpread: GLOW_SPREAD,
  bloomIntensity: BLOOM_INTENSITY,
  glassBlur: GLASS_BLUR,
  cardShimmer: CARD_SHIMMER,
} = INCIDENT_ACTIVITY_PARAMS;

const NA = '不適用';

type Rec = Record<string, unknown>;

function asRecord(value: unknown): Rec | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? (value as Rec) : null;
}

function asString(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

function asText(value: unknown): string {
  if (typeof value === 'string') return value || NA;
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  return NA;
}

function money(value: unknown, sign = false): string {
  return formatDecimal(asString(value), { prefix: '$', sign });
}

function qty(value: unknown): string {
  const text = asString(value);
  if (text === null) return NA;
  return formatDecimal(text, { digits: 0 }, text);
}

function joinList(value: unknown): string {
  if (!Array.isArray(value) || value.length === 0) return NA;
  return value.map((item) => asText(item)).join(', ');
}

type Side = 'buy' | 'sell' | null;

interface EventRow {
  key: string;
  event: EventDTO;
  time: string;
  syntheticLabel: string | null;
  title: string;
  rightText: string | null;
  side: Side;
  isAlert: boolean;
}

interface DetailField {
  label: string;
  value: string;
}

function sideOf(ev: EventDTO): Side {
  if (ev.kind !== 'fill') return null;
  const request = asRecord(ev.payload.request);
  const side = asString(request?.side);
  return side === 'buy' || side === 'sell' ? side : null;
}

export function eventTitle(ev: EventDTO, instLabel: string): string {
  const p = ev.payload;
  switch (ev.kind) {
    case 'run_state': {
      const previous = asString(p.previous);
      return `run ${shortId(ev.run_id)} · ${previous ?? '(新建)'} → ${asText(p.state)}`;
    }
    case 'stop_requested':
      return `已請求停止 · run ${shortId(ev.run_id)}`;
    case 'warmup':
      return `預熱 #${asText(p.seq)} · ${asText(p.disposition)}`;
    case 'day_basis': {
      const basis = asRecord(p.basis);
      return `日基準建立 · day ${asText(basis?.day)} · 權益 ${money(basis?.equity)}`;
    }
    case 'signal': {
      const reason = asString(p.reason);
      const target = asString(p.target);
      return `#${asText(p.seq)} ${asText(p.disposition)}${reason ? ' · ' + reason : ''}${target !== null ? ' · 目標 ' + qty(target) : ''}`;
    }
    case 'fill': {
      const request = asRecord(p.request);
      const fill = asRecord(p.fill);
      const verb = asString(request?.side) === 'sell' ? '賣出' : '買入';
      return `${instLabel} ${verb} ${qty(fill?.quantity)} 張 @ ${money(fill?.price)}`;
    }
    case 'final_account': {
      const account = asRecord(p.account);
      return `最終帳戶 · 權益 ${money(account?.equity)} · 部位 ${qty(account?.position)}`;
    }
    case 'stop':
    case 'anomaly':
      return `${ev.kind} · ${asString(p.error) ?? NA}`;
    default:
      return ev.kind;
  }
}

function buildDetailFields(ev: EventDTO): DetailField[] | null {
  const p = ev.payload;
  switch (ev.kind) {
    case 'fill': {
      const request = asRecord(p.request);
      const fill = asRecord(p.fill);
      return [
        { label: '成交數量', value: qty(fill?.quantity) },
        { label: '成交價', value: money(fill?.price) },
        { label: '手續費', value: money(fill?.fee) },
        { label: '成交後部位', value: qty(p.position) },
        { label: '成交後權益', value: money(p.equity) },
        { label: '累計手續費', value: money(p.fees) },
        { label: '委託 tag', value: asText(request?.tag) },
        { label: '狀態', value: asText(p.state) },
      ];
    }
    case 'signal': {
      const account = asRecord(p.account);
      const risk = asRecord(p.risk_state);
      return [
        { label: '處置', value: asText(p.disposition) },
        { label: '原因', value: asText(p.reason) },
        { label: '目標部位', value: qty(p.target) },
        { label: 'mark', value: money(p.mark) },
        { label: '權益', value: money(account?.equity) },
        { label: '未實現', value: money(account?.unrealized_pnl, true) },
        { label: '風控 mode', value: asText(risk?.mode) },
        { label: '風控 health', value: asText(risk?.health) },
      ];
    }
    case 'final_account': {
      const account = asRecord(p.account);
      const risk = asRecord(p.risk_state);
      return [
        { label: '權益', value: money(account?.equity) },
        { label: '已實現', value: money(account?.realized_pnl, true) },
        { label: '未實現', value: money(account?.unrealized_pnl, true) },
        { label: '手續費', value: money(account?.fees) },
        { label: '部位', value: qty(account?.position) },
        { label: '風控 reasons', value: joinList(risk?.reasons) },
      ];
    }
    default:
      return null;
  }
}

function toRow(ev: EventDTO, instLabel: string): EventRow {
  const isAlert = ev.level === 'WARN' || ev.level === 'ERROR';
  const rightText = ev.kind === 'fill' ? `權益 ${money(ev.payload.equity)}` : null;
  return {
    key: String(ev.seq),
    event: ev,
    time: formatClock(ev.wall_time_ms),
    syntheticLabel: ev.synthetic_time_ms ? formatDateTime(ev.synthetic_time_ms) : null,
    title: eventTitle(ev, instLabel),
    rightText,
    side: sideOf(ev),
    isAlert,
  };
}

function getBadgeMeta(ev: EventDTO, side: Side) {
  if (ev.level === 'ERROR') {
    return {
      label: '錯誤',
      tagClass: 'text-rose-300 font-semibold',
      coreClass: 'bg-[#f43f5e] shadow-[0_0_8px_rgba(244,63,94,0.55)] ring-1 ring-rose-400/40',
      sonarClass: 'bg-rose-500/25',
      bloomAnimation: 'crystal-optical-bloom-rose',
    };
  }
  if (ev.level === 'WARN') {
    return {
      label: '異常',
      tagClass: 'text-amber-300 font-semibold',
      coreClass: 'bg-[#f59e0b] shadow-[0_0_8px_rgba(245,158,11,0.55)] ring-1 ring-amber-400/40',
      sonarClass: 'bg-amber-500/25',
      bloomAnimation: 'crystal-optical-bloom-amber',
    };
  }
  if (ev.category === 'ORDER') {
    const isShort = side === 'sell';
    return {
      label: isShort ? '賣出' : '買入',
      tagClass: isShort ? 'text-rose-400 font-semibold' : 'text-emerald-400 font-semibold',
      coreClass: isShort
        ? 'bg-[#f43f5e] shadow-[0_0_8px_rgba(244,63,94,0.45)] ring-1 ring-rose-400/30'
        : 'bg-[#10b981] shadow-[0_0_8px_rgba(16,185,129,0.45)] ring-1 ring-emerald-400/30',
      sonarClass: isShort ? 'bg-rose-500/20' : 'bg-emerald-500/20',
      bloomAnimation: isShort ? 'crystal-optical-bloom-rose' : 'crystal-optical-bloom-emerald',
    };
  }
  if (ev.category === 'WORKER') {
    return {
      label: '訊號',
      tagClass: 'text-zinc-500 font-medium',
      coreClass: 'bg-zinc-600/70 ring-1 ring-zinc-600/40',
      sonarClass: 'bg-zinc-600/15',
      bloomAnimation: 'crystal-optical-bloom-neutral',
    };
  }
  return {
    label: ev.category === 'RISK' ? '風控' : '資訊',
    tagClass: ev.category === 'RISK' ? 'text-[#9ec2e6] font-semibold' : 'text-zinc-400 font-medium',
    coreClass: 'bg-[#7faee2] shadow-[0_0_6px_rgba(127,174,226,0.45)] ring-1 ring-[#7faee2]/40',
    sonarClass: 'bg-[#7faee2]/20',
    bloomAnimation: 'crystal-optical-bloom-neutral',
  };
}

function levelCapsuleClass(level: EventLevel): string {
  return level === 'ERROR'
    ? 'text-rose-300 font-semibold'
    : 'text-amber-300 font-semibold';
}

const SEVERITY_STYLE: Record<
  ActionSeverity,
  {
    cardClass: string;
    iconBoxClass: string;
    tagClass: string;
    Icon: typeof ShieldAlert;
  }
> = {
  p0: {
    cardClass: 'border-rose-500/40 bg-gradient-to-r from-rose-500/[0.08] via-secondary/45 to-secondary/35',
    iconBoxClass: 'bg-rose-500/15 border-rose-500/35 text-rose-400',
    tagClass: 'text-rose-400',
    Icon: ShieldAlert,
  },
  p1: {
    cardClass: 'border-border/80 bg-secondary/45 hover:border-amber-500/35',
    iconBoxClass: 'bg-amber-500/15 border-amber-500/35 text-amber-400',
    tagClass: 'text-amber-400',
    Icon: AlertTriangle,
  },
  p2: {
    cardClass: 'border-border/80 bg-secondary/45 hover:border-[#7faee2]/45',
    iconBoxClass: 'bg-[#7faee2]/15 border-[#7faee2]/35 text-[#9fc5ee]',
    tagClass: 'text-[#9fc5ee]',
    Icon: CheckCircle2,
  },
  p3: {
    cardClass: 'border-border/80 bg-secondary/45 hover:border-teal-400/35',
    iconBoxClass: 'bg-teal-400/15 border-teal-400/30 text-teal-300',
    tagClass: 'text-teal-300',
    Icon: Sparkles,
  },
};

function metricToneClass(tone?: MetricTone): string {
  switch (tone) {
    case 'warn': return 'text-amber-300';
    case 'up': return 'text-emerald-400';
    case 'down': return 'text-rose-400';
    case 'blue': return 'text-[#9fc5ee]';
    case 'teal': return 'text-teal-300';
    default: return 'text-foreground';
  }
}

const PREVIEW_ACTIONS: ActionQueueItem[] = [
  {
    id: 'preview-p1-rsi',
    sev: 'p1',
    tag: '偏差警戒',
    title: 'mean-reversion-rsi',
    symbol: 'ETH 1H',
    fact: '模擬偏差 -0.61%（警戒線 0.50% / 門檻 1.00%）· 近 3 筆滑價偏高',
    metrics: [
      { label: '模擬偏差', value: '-0.61%', tone: 'warn' },
      { label: '警戒線', value: '0.50%' },
      { label: '硬門檻', value: '1.00%' },
      { label: '異常原因', value: '近 3 筆滑價偏高' },
    ],
    primaryAction: { label: '檢視比對', route: '/demo-bot' },
  },
  {
    id: 'preview-p2-ens',
    sev: 'p2',
    tag: '待核准',
    title: 'donchian-ensemble',
    symbol: 'BTC 1D',
    fact: '4/4 驗證通過 · 年化 +13.9% · 最大回撤 -11.3% · PBO 22%',
    metrics: [
      { label: '驗證關卡', value: '4/4 通過', tone: 'blue' },
      { label: '年化', value: '+13.9%', tone: 'up' },
      { label: '最大回撤', value: '-11.3%' },
      { label: 'PBO', value: '22%' },
    ],
    primaryAction: { label: '檢視策略', route: '/strategies' },
    copyCommand: {
      label: '複製核准指令',
      command: '.venv\\Scripts\\python.exe -m catos.cli strategy approve --help',
    },
  },
  {
    id: 'preview-p3-vol',
    sev: 'p3',
    tag: '研究提案',
    title: 'vol-breakout',
    symbol: 'SOL 4H',
    fact: 'Agent 提交 · strategies/ 資料夾策略 · 依規則預設只做多',
    metrics: [
      { label: '來源', value: 'Agent 資料夾', tone: 'teal' },
      { label: '方向限制', value: '預設只做多' },
      { label: '狀態', value: '待排程回測' },
    ],
    primaryAction: { label: '檢視策略', route: '/strategies' },
  },
];

interface UnifiedIncidentActivityCardProps {
  className?: string;
}

/**
 * 待處理與事件審計卡片 (3A 定案：單欄待處理佇列＋下方近期審計流水)
 * - 固定維持單欄縱向結構，不於寬卡拆為左右兩欄
 * - 窄卡 (< 450px)：待處理項目按鈕自動換行至底部，文字不被擠壓截斷
 */
export function UnifiedIncidentActivityCard({ className }: UnifiedIncidentActivityCardProps) {
  const events = useCatStore((s) => s.events);
  const eventsOmitted = useCatStore((s) => s.eventsOmitted);
  const bots = useCatStore((s) => s.bots);
  const risk = useCatStore((s) => s.risk);
  const killSwitch = useCatStore((s) => s.killSwitch);
  const strategies = useCatStore((s) => s.strategies);
  const connectionStatus = useCatStore((s) => s.connection.status);
  const signals = useOverviewSignals();
  const { navigate } = useRouter();

  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [category, setCategory] = useState<string>('ACTION');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const userPickedTabRef = useRef(false);

  const cardRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const nodeRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const [dimensions, setDimensions] = useState({ width: 560, height: 320 });

  useEffect(() => {
    const el = cardRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const { width: cardW } = dimensions;
  const isNarrow = cardW < 440;
  const isStackActionBtns = cardW < 430;
  const isSuperNarrow = cardW < 360;

  const [bottomUpDelays, setBottomUpDelays] = useState<Record<string, number>>({});

  const instById = useMemo(() => {
    const map = new Map<string, string>();
    for (const bot of bots) {
      if (bot.inst_id) map.set(bot.bot_id, bot.inst_id);
    }
    return map;
  }, [bots]);

  const rows = useMemo<EventRow[]>(() => {
    return [...events]
      .sort((a, b) => b.seq - a.seq)
      .map((ev) => toRow(ev, instById.get(ev.bot_id) ?? '合約'));
  }, [events, instById]);

  const recentHighlights = useMemo<EventRow[]>(() => {
    const priority = rows.filter((r) => r.event.category === 'ORDER' || r.event.category === 'RISK' || r.isAlert);
    return priority.length >= 4 ? priority.slice(0, 6) : rows.slice(0, 6);
  }, [rows]);

  const actionItems = useMemo<ActionQueueItem[]>(() => {
    if (signals.previewPick) return PREVIEW_ACTIONS;

    const list: ActionQueueItem[] = [];

    if (killSwitch?.engaged) {
      const reason = killSwitch.engaged_record?.reason ?? killSwitch.error ?? 'fail-closed';
      list.push({
        id: 'p0-kill-switch',
        sev: 'p0',
        tag: '總開關觸發',
        title: 'Kill-Switch 已鎖存',
        symbol: 'ALL · 禁啟新 run',
        fact: `原因：${reason} · 需由使用者確認原因後人工解除`,
        metrics: [
          { label: '觸發原因', value: reason, tone: 'down' },
          { label: '解除方式', value: '風控頁人工解除' },
        ],
        primaryAction: { label: '前往風控', route: '/risk', tone: 'danger' },
      });
    }

    if (risk && (risk.derived.status === 'soft_latch' || risk.derived.status === 'hard_latch')) {
      const label = risk.derived.status === 'hard_latch' ? 'Hard Latch' : 'Soft Latch';
      const reasons = risk.reasons.length > 0 ? risk.reasons.join(', ') : '風控期間損益達門檻';
      list.push({
        id: `p0-risk-${risk.derived.status}`,
        sev: 'p0',
        tag: '風控鎖存',
        title: `帳戶 ${label} 已觸發`,
        symbol: 'ALL · 禁止增倉',
        fact: `原因：${reasons} · 需人工檢核並於 CLI 解除`,
        metrics: [
          { label: '風控原因', value: reasons, tone: 'down' },
          { label: '解除方式', value: 'CLI demo rearm' },
        ],
        primaryAction: { label: '前往風控', route: '/risk', tone: 'danger' },
      });
    }

    const demoRuns = signals.demoBot?.runs ?? [];
    const latestDemoByStrat = new Map<string, typeof demoRuns[number]>();
    for (const run of demoRuns) {
      const key = run.strategy_id ?? run.run_id;
      const prev = latestDemoByStrat.get(key);
      if (!prev || (run.created_at_ms ?? 0) > (prev.created_at_ms ?? 0)) {
        latestDemoByStrat.set(key, run);
      }
    }
    for (const run of latestDemoByStrat.values()) {
      if (run.state === 'failed') {
        list.push({
          id: `p0-demo-failed-${run.run_id}`,
          sev: 'p0',
          tag: '執行失敗',
          title: run.strategy_id ?? shortId(run.run_id),
          symbol: 'OKX Demo',
          fact: `run ${shortId(run.run_id)} · ${run.stop_reason ?? '執行錯誤'} · 部位 ${run.position ?? '0'} 張`,
          metrics: [
            { label: 'run', value: shortId(run.run_id) },
            { label: '原因', value: run.stop_reason ?? '執行錯誤', tone: 'down' },
            { label: '部位', value: `${run.position ?? '0'} 張` },
          ],
          primaryAction: { label: '檢視 Bot', route: '/demo-bot', tone: 'danger' },
        });
      } else if (run.state === 'running' && run.stale) {
        list.push({
          id: `p1-demo-stale-${run.run_id}`,
          sev: 'p1',
          tag: '無回應',
          title: run.strategy_id ?? shortId(run.run_id),
          symbol: 'OKX Demo',
          fact: `run ${shortId(run.run_id)} 超過兩根 K 線未寫入紀錄 · 當前部位 ${run.position ?? '0'} 張`,
          metrics: [
            { label: 'run', value: shortId(run.run_id) },
            { label: '狀態', value: '逾兩根 K 線未寫入', tone: 'warn' },
            { label: '部位', value: `${run.position ?? '0'} 張` },
          ],
          primaryAction: { label: '檢視 Bot', route: '/demo-bot' },
        });
      }
    }

    const approvals = signals.replay?.approvals ?? [];
    for (const approval of approvals) {
      if (approval.state === 'active' && approval.source === 'changed') {
        list.push({
          id: `p1-approval-changed-${approval.approval_id}`,
          sev: 'p1',
          tag: '來源異動',
          title: approval.strategy_id,
          symbol: '雜湊不符',
          fact: `核准 ${shortId(approval.approval_id)} 雜湊不符，Bot 與 IPC 已停止解析，需重審核准`,
          metrics: [
            { label: '核准 ID', value: shortId(approval.approval_id) },
            { label: '狀態', value: 'Bot 與 IPC 已停止解析', tone: 'warn' },
          ],
          primaryAction: { label: '檢視策略', route: '/strategies' },
        });
      }
    }

    const alertEvents = rows.filter((r) => r.isAlert);
    if (alertEvents.length > 0) {
      const latest = alertEvents[0];
      list.push({
        id: `p1-event-${latest.event.seq}`,
        sev: 'p1',
        tag: latest.event.level === 'ERROR' ? '事件錯誤' : '事件警戒',
        title: latest.title,
        symbol: `seq ${latest.event.seq}`,
        fact: `近期累計 ${alertEvents.length} 筆異常事件 · 最新 seq ${latest.event.seq} (${latest.time})`,
        metrics: [
          { label: '累計異常', value: `${alertEvents.length} 筆`, tone: 'warn' },
          { label: '最新時間', value: latest.time },
        ],
        primaryAction: { label: '檢視異常', switchTab: 'ALERT' },
      });
    }

    const activeApprovedIds = new Set(
      approvals.filter((a) => a.state === 'active' && a.source === 'current').map((a) => a.strategy_id)
    );
    const builtinApprovedIds = new Set(
      strategies.filter((s) => s.approval_state === 'approved').map((s) => s.strategy_id)
    );
    for (const s of signals.catalog?.strategies ?? []) {
      if (s.origin === 'folder' && !activeApprovedIds.has(s.id) && !builtinApprovedIds.has(s.id)) {
        list.push({
          id: `p2-folder-${s.id}`,
          sev: 'p2',
          tag: '待核准',
          title: s.name || s.id,
          symbol: `strategies/${s.id}/`,
          fact: `資料夾策略尚無有效核准紀錄，僅供研究回測；部署前須由使用者於 CLI 核准`,
          metrics: [
            { label: '來源', value: '資料夾策略', tone: 'blue' },
            { label: '目前階段', value: '僅供研究回測' },
            { label: '部署條件', value: 'CLI 人工核准' },
          ],
          primaryAction: { label: '檢視策略', route: '/strategies' },
          copyCommand: {
            label: '複製核准指令',
            command: `.venv\\Scripts\\python.exe -m catos.cli strategy approve --strategy ${s.id}`,
          },
        });
      }
    }

    return list.sort((a, b) => SEV_ORDER[a.sev] - SEV_ORDER[b.sev]);
  }, [signals, killSwitch, risk, rows, strategies]);

  useEffect(() => {
    if (userPickedTabRef.current) return;
    if (actionItems.length > 0) {
      setCategory('ACTION');
    } else if (signals.loaded) {
      setCategory('ALL');
    }
  }, [actionItems.length, signals.loaded]);

  const hasP0 = actionItems.some((a) => a.sev === 'p0');
  const hasP1 = actionItems.some((a) => a.sev === 'p1');

  const availableTabs = useMemo<CategoryTabItem[]>(() => {
    const isAlert = (e: EventDTO) => e.level === 'WARN' || e.level === 'ERROR';
    const countAlert = events.filter(isAlert).length;
    const countOrder = events.filter((e) => e.category === 'ORDER').length;
    const countRisk = events.filter((e) => e.category === 'RISK').length;

    return [
      {
        id: 'ACTION',
        label: '待處理',
        shortLabel: '待',
        badgeCount: actionItems.length,
        isCritical: hasP0,
        isAlert: !hasP0 && (hasP1 || actionItems.length > 0),
        filterFn: () => false,
      },
      { id: 'ALL', label: '全部', shortLabel: '全', badgeCount: events.length, filterFn: () => true },
      { id: 'ALERT', label: '異常', shortLabel: '異', badgeCount: countAlert, isAlert: countAlert > 0, filterFn: isAlert },
      { id: 'ORDER', label: '成交', shortLabel: '成', badgeCount: countOrder, filterFn: (e) => e.category === 'ORDER' },
      { id: 'RISK', label: '風控', shortLabel: '風', badgeCount: countRisk, filterFn: (e) => e.category === 'RISK' },
    ];
  }, [events, actionItems.length, hasP0, hasP1]);

  const currentTab = useMemo(() => {
    return availableTabs.find((t) => t.id === category) ?? availableTabs[0];
  }, [availableTabs, category]);

  const filteredRows = useMemo(() => {
    if (!currentTab || currentTab.id === 'ACTION') return [];
    return rows.filter((row) => currentTab.filterFn(row.event));
  }, [rows, currentTab]);

  useEffect(() => {
    if (!containerRef.current || category === 'ACTION') return;
    const totalH = containerRef.current.scrollHeight;
    if (totalH <= 0) return;

    const newDelays: Record<string, number> = {};
    filteredRows.forEach((row) => {
      const el = nodeRefs.current.get(row.key);
      if (el) {
        const nodeY = el.offsetTop + 8;
        const distFromBottom = Math.max(0, totalH - nodeY);
        const ratio = Math.max(0, Math.min(1, distFromBottom / totalH));
        newDelays[row.key] = Number((ratio * DURATION_SEC).toFixed(3));
      }
    });
    setBottomUpDelays(newDelays);
  }, [filteredRows, expandedKey, category]);

  const toggleRow = (key: string) => {
    setExpandedKey((prev) => (prev === key ? null : key));
  };

  const handleSelectTab = (tabId: string) => {
    userPickedTabRef.current = true;
    setCategory(tabId);
  };

  const handleCopyCommand = (id: string, command: string) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      void navigator.clipboard.writeText(command);
    }
    setCopiedId(id);
    window.setTimeout(() => {
      setCopiedId((cur) => (cur === id ? null : cur));
    }, 2000);
  };

  const emptyMessage =
    connectionStatus === 'mode_not_open'
      ? '此模式未開放（demo/live 不在 v1 範圍）'
      : events.length === 0
      ? '尚無事件 · 啟動模擬 run 後顯示'
      : '此分類無事件';

  const showEmpty = connectionStatus === 'mode_not_open' || filteredRows.length === 0;

  return (
    <div ref={cardRef} className={cn('flex flex-col h-full w-full select-none overflow-hidden bg-surface/40 font-mono', className)}>
      {/* 1. Header：自適應 5 核心分頁 */}
      <div className="flex items-center justify-between px-3 h-9 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
        <CardHeaderTitle
          cardId="activity_deck"
          title={isSuperNarrow ? '待處理 / 審計' : '待處理與事件審計'}
        />

        <CardHeaderTabs
          items={(isSuperNarrow ? availableTabs.slice(0, 4) : availableTabs).map((tab) => ({
            id: tab.id,
            label: isNarrow ? tab.shortLabel : tab.label,
            count: tab.badgeCount,
            tone: tab.isCritical ? 'critical' : tab.isAlert ? 'alert' : 'default',
          }))}
          value={category}
          onChange={handleSelectTab}
        />
      </div>

      {/* 2. 主內容區：單欄待處理內嵌圖示指標卡＋下方垂直時間軸近期流水 */}
      {category === 'ACTION' ? (
        <div className="flex-1 min-h-0 flex flex-col overflow-y-auto custom-scrollbar">
          {/* 上半：待處理佇列（融合結構化指標條與霧藍核准分流 × 內嵌微卡槽與語意圖示方塊） */}
          <div className="p-2.5 space-y-2 shrink-0">
            {actionItems.length === 0 ? (
              <div className="py-5 text-center text-t2 text-muted-foreground">
                無待處理項目
              </div>
            ) : (
              actionItems.map((item) => {
                const isCopied = copiedId === item.id;
                const style = SEVERITY_STYLE[item.sev];
                const IconComp = style.Icon;

                return (
                  <div
                    key={item.id}
                    className={cn(
                      'rounded-md border px-2.5 py-2 transition-colors flex flex-col gap-2',
                      style.cardClass
                    )}
                  >
                    {/* 上排：28px 語意圖示方塊 ＋ 分類／策略／標的晶片 ＋ 右側操作鈕 */}
                    <div
                      className={cn(
                        'flex gap-2.5',
                        isStackActionBtns ? 'flex-col items-stretch' : 'items-center justify-between'
                      )}
                    >
                      <div className="flex items-center gap-2.5 min-w-0 flex-1">
                        <div
                          className={cn(
                            'size-7 rounded-md border grid place-items-center shrink-0',
                            style.iconBoxClass
                          )}
                        >
                          <IconComp className="size-3.5" />
                        </div>

                        <div className="min-w-0 flex-1 flex items-center gap-1.5 flex-wrap">
                          <span className={cn('text-t1 font-mono font-bold shrink-0', style.tagClass)}>
                            {item.tag}
                          </span>
                          <span className="text-t3 font-semibold text-foreground truncate font-sans">
                            {item.title}
                          </span>
                          {item.symbol && (
                            <span className="px-1.5 py-0.5 rounded bg-white/[0.06] text-t1 font-mono text-muted-foreground leading-none shrink-0 truncate max-w-[170px]" title={item.symbol}>
                              {item.symbol}
                            </span>
                          )}
                        </div>
                      </div>

                      <div className={cn('flex items-center gap-1.5 shrink-0', isStackActionBtns && 'justify-end')}>
                        {item.primaryAction && (
                          <button
                            type="button"
                            onClick={() => {
                              if (item.primaryAction?.switchTab) {
                                handleSelectTab(item.primaryAction.switchTab);
                              } else if (item.primaryAction?.route) {
                                navigate(item.primaryAction.route);
                              }
                            }}
                            className={cn(
                              'px-2 py-1 rounded border text-t2 font-mono transition-colors cursor-pointer whitespace-nowrap',
                              item.primaryAction.tone === 'danger'
                                ? 'border-rose-500/45 bg-rose-500/15 text-rose-300 hover:bg-rose-500/25'
                                : 'border-border/90 bg-background/50 text-foreground hover:border-[#7faee2]/60 hover:text-[#b8d4f2]'
                            )}
                          >
                            {item.primaryAction.label}
                          </button>
                        )}

                        {item.copyCommand && (
                          <button
                            type="button"
                            onClick={() => handleCopyCommand(item.id, item.copyCommand!.command)}
                            title="複製 CLI 指令至剪貼簿（核准僅於終端機執行）"
                            className="px-2 py-1 rounded border border-[#7faee2]/45 bg-[#7faee2]/15 text-[#b8d4f2] hover:bg-[#7faee2] hover:text-[#111318] text-t2 font-mono font-semibold transition-colors cursor-pointer inline-flex items-center gap-1 whitespace-nowrap"
                          >
                            {isCopied ? <Check className="size-3" /> : <Copy className="size-3" />}
                            <span>{isCopied ? '已複製' : item.copyCommand.label}</span>
                          </button>
                        )}
                      </div>
                    </div>

                    {/* 下排：結構化指標條（免讀長句，關鍵數值一眼掃描） */}
                    {item.metrics && item.metrics.length > 0 ? (
                      <div className="rounded border border-border/50 bg-background/50 px-2.5 py-1 flex items-center flex-wrap gap-y-1 font-mono text-t1">
                        {item.metrics.map((m, idx) => (
                          <span
                            key={`${item.id}-m-${idx}`}
                            className={cn(
                              'inline-flex items-center gap-1.5',
                              idx < item.metrics!.length - 1 && 'pr-2.5 mr-2.5 border-r border-border/45'
                            )}
                          >
                            <span className="text-muted-foreground/80 font-sans">{m.label}</span>
                            <span className={cn('font-semibold tabular-nums', metricToneClass(m.tone))}>
                              {m.value}
                            </span>
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-t2 text-muted-foreground leading-snug truncate font-sans pl-9" title={item.fact}>
                        {item.fact}
                      </p>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {/* 下半：近期審計與成交流水（垂直時間軸導軌微光節點 × 無框中文分類色字） */}
          <div className="flex-1 min-h-0 flex flex-col border-t border-border/80 bg-background/20">
            <div className="flex items-center justify-between px-3 py-1.5 bg-background/40 border-b border-border/60 shrink-0">
              <span className="text-t1 font-mono text-muted-foreground">
                近期審計與成交流水 · {events.length} 筆
              </span>
              <button
                type="button"
                onClick={() => handleSelectTab('ALL')}
                className="text-t1 font-mono text-primary/85 hover:text-primary inline-flex items-center gap-0.5 cursor-pointer shrink-0"
              >
                <span>展開全部</span>
                <ArrowRight className="size-2.5" />
              </button>
            </div>

            {recentHighlights.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center py-6 text-muted-foreground/75 gap-1">
                <Inbox className="size-5 text-zinc-600" />
                <span className="text-t2 font-sans">{emptyMessage}</span>
              </div>
            ) : (
              <div className="relative px-3 py-2">
                <div className="absolute left-[18px] top-3.5 bottom-3.5 w-[1px] bg-white/[0.10] pointer-events-none" />
                <div className="space-y-0.5">
                  {recentHighlights.map((row) => {
                    const meta = getBadgeMeta(row.event, row.side);
                    return (
                      <div
                        key={row.key}
                        onClick={() => {
                          handleSelectTab('ALL');
                          setExpandedKey(row.key);
                        }}
                        className="relative flex items-center justify-between gap-2 pl-5 pr-1.5 py-1.5 rounded hover:bg-white/[0.03] transition-colors cursor-pointer text-t2"
                      >
                        <span
                          className={cn(
                            'absolute left-[3px] top-1/2 -translate-y-1/2 size-1.5 rounded-full pointer-events-none',
                            meta.coreClass
                          )}
                        />
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-zinc-500 text-t1 shrink-0 tabular-nums">{row.time}</span>
                          <span className={cn('text-t1 font-mono shrink-0 w-7', meta.tagClass)}>
                            {meta.label}
                          </span>
                          <span className={cn('truncate', row.isAlert ? 'text-zinc-100 font-medium' : 'text-zinc-300')}>
                            {row.title}
                          </span>
                        </div>
                        {row.rightText && cardW >= 420 && (
                          <span className="text-t1 text-muted-foreground shrink-0 tabular-nums">
                            {row.rightText}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div
          key={`timeline-${expandedKey}`}
          ref={containerRef}
          className="flex-1 min-h-0 overflow-y-auto p-3 pr-2 relative custom-scrollbar"
          style={{
            '--photon-duration': `${DURATION_SEC}s`,
            '--photon-length': `${PHOTON_LENGTH}px`,
            '--photon-width': `${PHOTON_WIDTH}px`,
            '--photon-opacity': `${(PHOTON_BRIGHTNESS / 100).toFixed(2)}`,
            '--bloom-intensity': `${(BLOOM_INTENSITY / 100).toFixed(2)}`,
            '--glass-blur': `${GLASS_BLUR}px`,
            '--card-shimmer-opacity': `${(CARD_SHIMMER / 100).toFixed(2)}`,
          } as React.CSSProperties}
        >
          {showEmpty ? (
            <div className="h-full flex flex-col items-center justify-center text-muted-foreground gap-1">
              <Inbox className="size-6 text-zinc-500/80 mb-1" />
              <span className="text-t2">{emptyMessage}</span>
            </div>
          ) : (
            <div className="relative pl-3 space-y-1.5">
              <div className="absolute left-[20px] -translate-x-1/2 top-2 bottom-2 w-[20px] pointer-events-none z-0 overflow-hidden">
                <div className="absolute left-[10px] -translate-x-1/2 top-0 bottom-0 w-[1px] bg-white/[0.10]" />
                <div className="absolute left-[2px] bottom-0 w-[20px]" style={{ display: 'none' }}>
                  <div
                    className="hidden"
                    style={{
                      width: `${GLOW_SPREAD}px`,
                      height: `${Math.round(PHOTON_LENGTH * 1.25)}px`,
                      opacity: PHOTON_BRIGHTNESS / 100,
                      filter: `blur(${Math.max(2, Math.round(GLOW_SPREAD * 0.28))}px)`,
                    }}
                  />
                  <div
                    className="hidden"
                    style={{
                      width: `${PHOTON_WIDTH}px`,
                      height: `${PHOTON_LENGTH}px`,
                      opacity: 1,
                      boxShadow: `0 0 ${Math.round(8 * (BLOOM_INTENSITY / 100))}px ${Math.round(1 * (BLOOM_INTENSITY / 100))}px rgba(255, 255, 255, 0.7)`,
                    }}
                  />
                </div>
              </div>

              {filteredRows.map((row) => {
                const ev = row.event;
                const isExp = expandedKey === row.key;
                const meta = getBadgeMeta(ev, row.side);
                const isWarn = ev.level === 'WARN';
                const isError = ev.level === 'ERROR';
                const detailFields = isExp ? buildDetailFields(ev) : null;
                const bottomDelay = bottomUpDelays[row.key] ?? 0;

                return (
                  <div
                    key={row.key}
                    ref={(el) => {
                      if (el) nodeRefs.current.set(row.key, el);
                      else nodeRefs.current.delete(row.key);
                    }}
                    className="relative flex items-start gap-2.5 group"
                  >
                    <div className="relative mt-1.5 shrink-0 z-10 flex items-center justify-center size-4 pointer-events-none">
                      <span
                        className={cn(
                          'absolute inline-flex size-2 rounded-full pointer-events-none',
                          meta.sonarClass
                        )}
                        style={{
                          animation: `optical-halation-fade ${DURATION_SEC}s cubic-bezier(0.16, 1, 0.3, 1) infinite`,
                          animationDelay: `${bottomDelay}s`,
                        }}
                      />
                      <span
                        className={cn(
                          'relative inline-flex size-1.5 rounded-full transition-all duration-150',
                          meta.coreClass,
                          row.isAlert && 'crystal-breathe-subtle'
                        )}
                        style={{
                          animation: `${meta.bloomAnimation} ${DURATION_SEC}s cubic-bezier(0.16, 1, 0.3, 1) infinite`,
                          animationDelay: `${bottomDelay}s`,
                        }}
                      />
                    </div>

                    <div
                      onClick={() => toggleRow(row.key)}
                      className={cn(
                        'flex-1 min-w-0 transition-all duration-150 cursor-pointer px-2 py-1.5 rounded-md',
                        isExp
                          ? 'bg-white/[0.035]'
                          : isError
                          ? 'bg-rose-500/[0.02] hover:bg-rose-500/[0.04]'
                          : isWarn
                          ? 'bg-amber-500/[0.02] hover:bg-amber-500/[0.04]'
                          : 'hover:bg-white/[0.025]'
                      )}
                    >
                      <div className="flex items-center justify-between gap-2 text-t2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-zinc-500 text-t1 shrink-0 font-mono tabular-nums">{row.time}</span>
                          <span className={cn('text-t1 font-mono shrink-0 w-7', meta.tagClass)}>
                            {meta.label}
                          </span>
                          {cardW >= 460 && (
                            <span className="text-zinc-500 text-t1 shrink-0 font-mono">
                              [{shortId(ev.run_id)}]
                            </span>
                          )}
                          <span
                            className={cn(
                              'truncate leading-tight tracking-tight text-t2',
                              row.isAlert ? 'text-zinc-100 font-medium' : 'text-zinc-300 font-normal'
                            )}
                          >
                            {row.title}
                          </span>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          {row.rightText && cardW >= 460 ? (
                            <span className="text-t2 font-mono tracking-tight text-zinc-300 tabular-nums">
                              {row.rightText}
                            </span>
                          ) : row.isAlert ? (
                            <span className={cn('text-t1 font-mono', levelCapsuleClass(ev.level))}>
                              {ev.level}
                            </span>
                          ) : null}

                          <button
                            type="button"
                            className="text-zinc-500 group-hover:text-zinc-300 shrink-0 transition-transform duration-200"
                            aria-label={isExp ? '收合' : '展開'}
                          >
                            {isExp ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
                          </button>
                        </div>
                      </div>

                      {isExp && (
                        <div
                          onClick={(e) => e.stopPropagation()}
                          className="mt-2 pt-2 border-t border-white/[0.05] text-t1 space-y-2 text-zinc-300 snap-accordion-enter"
                        >
                          {detailFields ? (
                            <div className={cn('grid gap-2 p-2 rounded-md bg-secondary/40 border border-border/60 text-t1 font-mono', cardW < 420 ? 'grid-cols-2' : 'grid-cols-4')}>
                              {detailFields.map((field) => (
                                <div key={field.label} className="min-w-0">
                                  <span className="text-muted-foreground block text-t1 uppercase tracking-wider">{field.label}</span>
                                  <span className="font-semibold text-foreground break-all">{field.value}</span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <pre className="text-t1 font-mono max-h-40 overflow-auto p-2 rounded-md bg-secondary/40 border border-border/60 text-zinc-300 whitespace-pre-wrap break-all custom-scrollbar">
                              {JSON.stringify(ev.payload, null, 1)}
                            </pre>
                          )}

                          <div className="flex items-center justify-between pt-1 border-t border-white/[0.04] text-t1 text-zinc-500">
                            <span className="truncate">
                              {`seq ${ev.seq} · ${row.syntheticLabel ? '合成時間 ' + row.syntheticLabel + ' · ' : ''}${ev.category}`}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {eventsOmitted > 0 && (
        <div className="shrink-0 px-3 py-1 border-t border-border/60 bg-secondary/30 text-t1 font-mono text-amber-300/90">
          後端環形緩衝已省略 {eventsOmitted} 筆
        </div>
      )}
    </div>
  );
}
