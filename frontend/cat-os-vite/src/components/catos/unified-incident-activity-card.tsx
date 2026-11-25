import { useState, useMemo, useRef, useEffect } from 'react';
import type { KeyboardEvent, ReactNode } from 'react';
import { useCatStore } from '@/state/catStore';
import type { EventDTO } from '@/contracts';
import { useOverviewSignals } from '@/lib/overview-signals';
import { useRouter } from '@/lib/router';
import { CardHeaderTitle } from './card-header-title';
import { CardHeaderTabs } from './card-header-tabs';
import { ArrowRight, Check, ChevronDown, Copy, Inbox } from 'lucide-react';
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
type MetricTone = 'default' | 'warn' | 'up' | 'down' | 'blue' | 'teal' | 'muted';
/** 時間軸光珠與霧底標籤的語意色（對應 incident-feed.css 的 tl-tone-*） */
type FeedTone = 'info' | 'warn' | 'up' | 'down' | 'pri' | 'muted';

interface ActionMetric {
  label: string;
  value: string;
  tone?: MetricTone;
}

interface ActionQueueItem {
  id: string;
  sev: ActionSeverity;
  /** 霧底等寬英文標籤（DEV / GATE / KILL…） */
  code: string;
  tone: FeedTone;
  alert?: boolean;
  /** 已格式化的台北時間 HH:MM:SS；沒有時間戳的項目時間欄留空 */
  time: string | null;
  tag: string;
  title: string;
  symbol?: string;
  /** 列標頭上的一句話摘要 */
  brief: string;
  /** 列標頭右側的關鍵數值 */
  hero?: { value: string; tone?: MetricTone };
  fact: string;
  metrics?: ActionMetric[];
  primaryAction?: { label: string; route?: string; switchTab?: string; tone?: 'danger' | 'primary' };
  copyCommand?: { label: string; command: string };
}

const SEV_ORDER: Record<ActionSeverity, number> = { p0: 0, p1: 1, p2: 2, p3: 3 };

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
  /** 成交或收盤訊號後的帳戶權益（列標頭右側） */
  equity: string | null;
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

function isZeroQty(value: string | null): boolean {
  if (!value) return true;
  return /^-?0+(\.0*)?$/.test(value.trim());
}

function isQuietHeartbeat(ev: EventDTO): boolean {
  if (ev.category !== 'WORKER' || ev.level !== 'INFO') return false;
  if (ev.kind === 'warmup') return true;
  if (ev.kind !== 'signal') return false;
  return asString(ev.payload.reason) === 'bar_closed';
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
      return `預熱 #${asText(p.seq)} · ${instLabel} 指標暖機`;
    case 'day_basis': {
      const basis = asRecord(p.basis);
      return `日基準建立 · day ${asText(basis?.day)} · 權益 ${money(basis?.equity)}`;
    }
    case 'signal': {
      const reason = asString(p.reason);
      const target = asString(p.target);
      const disp = asString(p.disposition) ?? '';
      const hasPos = !isZeroQty(target);
      if (reason === 'bar_closed') {
        const shortInst = instLabel.replace('-USDT-SWAP', '');
        return hasPos
          ? `#${asText(p.seq)} ${shortInst} 收盤續抱 · 目標 ${qty(target)} 張`
          : `#${asText(p.seq)} ${shortInst} 收盤觀望 · 空手`;
      }
      return `#${asText(p.seq)} ${disp || '訊號'}${reason ? ' · ' + reason : ''}${target !== null ? ' · 目標 ' + qty(target) : ''}`;
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
  const account = asRecord(ev.payload.account);
  const equity =
    ev.kind === 'fill'
      ? money(ev.payload.equity)
      : ev.kind === 'signal' && asString(account?.equity)
      ? money(account?.equity)
      : null;
  return {
    key: String(ev.seq),
    event: ev,
    time: formatClock(ev.wall_time_ms),
    syntheticLabel: ev.synthetic_time_ms ? formatDateTime(ev.synthetic_time_ms) : null,
    title: eventTitle(ev, instLabel),
    equity,
    side: sideOf(ev),
    isAlert,
  };
}

/** 事件 → 霧底等寬英文標籤與光珠色 */
function eventTag(ev: EventDTO, side: Side): { code: string; tone: FeedTone } {
  if (ev.level === 'ERROR') return { code: 'ERROR', tone: 'down' };
  if (ev.level === 'WARN') return { code: 'WARN', tone: 'warn' };
  if (ev.category === 'ORDER') {
    if (side === 'sell') return { code: 'SELL', tone: 'down' };
    if (side === 'buy') return { code: 'BUY', tone: 'up' };
    return { code: 'ORDER', tone: 'info' };
  }
  if (ev.category === 'WORKER') {
    if (ev.kind === 'warmup') return { code: 'WARM', tone: 'muted' };
    const disp = (asString(ev.payload.disposition) ?? '').toUpperCase();
    const hasPos = !isZeroQty(asString(ev.payload.target));
    if (disp && disp !== 'NO_INTENT' && disp !== 'HOLD') return { code: 'SIG', tone: 'info' };
    if (disp === 'HOLD' || hasPos) return { code: 'HOLD', tone: 'pri' };
    return { code: 'FLAT', tone: 'muted' };
  }
  if (ev.category === 'RISK') return { code: 'RISK', tone: 'info' };
  if (ev.category === 'SUPERVISOR') return { code: 'RUN', tone: 'muted' };
  return { code: 'SYS', tone: 'muted' };
}

function metricToneClass(tone?: MetricTone): string {
  switch (tone) {
    case 'warn': return 'text-warn';
    case 'up': return 'text-up';
    case 'down': return 'text-down';
    case 'blue': return 'text-primary';
    case 'teal': return 'text-teal-300';
    case 'muted': return 'text-muted-foreground';
    default: return 'text-foreground';
  }
}

function clockFromIso(value: string | null | undefined): string | null {
  if (!value) return null;
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? formatClock(ms) : null;
}

function clockFromMs(ms: number | null | undefined): string | null {
  return ms === null || ms === undefined || !Number.isFinite(ms) ? null : formatClock(ms);
}

const PREVIEW_ACTIONS: ActionQueueItem[] = [
  {
    id: 'preview-p1-rsi',
    sev: 'p1',
    code: 'DEV',
    tone: 'warn',
    alert: true,
    time: '07:59:58',
    tag: '偏差警戒',
    title: 'mean-reversion-rsi',
    symbol: 'ETH 1H',
    brief: '模擬偏差逾 0.50% 警戒線',
    hero: { value: '-0.61%', tone: 'warn' },
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
    code: 'GATE',
    tone: 'pri',
    time: '06:40:12',
    tag: '待核准',
    title: 'donchian-ensemble',
    symbol: 'BTC 1D',
    brief: '4/4 驗證通過 · 待終端機核准',
    hero: { value: '+13.9%', tone: 'up' },
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
    code: 'IDEA',
    tone: 'muted',
    time: '04:15:00',
    tag: '研究提案',
    title: 'vol-breakout',
    symbol: 'SOL 4H',
    brief: 'strategies/ 提案 · 預設只做多',
    hero: { value: '待回測', tone: 'muted' },
    fact: 'Agent 提交 · strategies/ 資料夾策略 · 依規則預設只做多',
    metrics: [
      { label: '來源', value: 'Agent 資料夾', tone: 'teal' },
      { label: '方向限制', value: '預設只做多' },
      { label: '狀態', value: '待排程回測' },
    ],
    primaryAction: { label: '檢視策略', route: '/strategies' },
  },
];

/* ------------------------------------------------------------------
 * 同軌時間軸列（架構 8）：時間 ─●─ 標籤 · 內容，展開面板沿用同一條光軌
 * 樣式與動畫在 src/styles/incident-feed.css
 * ------------------------------------------------------------------ */

const CLOCK_RE = /^\d{2}:\d{2}:\d{2}$/;

function ClockCell({ value }: { value: string | null }) {
  // 沒有時間戳（例如資料夾策略待核准）就留空，不放 --:--:-- 佔位符
  if (!value || !CLOCK_RE.test(value)) return <span className="tl-time" />;
  return (
    <span className="tl-time">
      {value.slice(0, 5)}
      <span className="tl-time-sec">{value.slice(5)}</span>
    </span>
  );
}

/** 光軌在列標頭拆成上下兩段，在實心點上下各留 3px 切口 */
function FeedNode() {
  return (
    <span className="tl-node" aria-hidden="true">
      <span className="tl-rail tl-rail-t" />
      <span className="tl-rail tl-rail-b" />
      <span className="tl-dot" />
    </span>
  );
}

interface FeedRowProps {
  tone: FeedTone;
  time: string | null;
  alert?: boolean;
  /** 有展開面板的列才傳；沒傳代表點擊只做導覽 */
  expandable?: boolean;
  open?: boolean;
  onActivate: () => void;
  children: ReactNode;
  panel?: ReactNode;
}

function FeedRow({ tone, time, alert, expandable, open, onActivate, children, panel }: FeedRowProps) {
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onActivate();
    }
  };
  return (
    <div className={cn('tl-row', `tl-tone-${tone}`, alert && 'is-alert', open && 'is-open')}>
      <div
        role="button"
        tabIndex={0}
        aria-expanded={expandable ? Boolean(open) : undefined}
        className="tl-head"
        onClick={onActivate}
        onKeyDown={onKeyDown}
      >
        <ClockCell value={time} />
        <FeedNode />
        <div className="tl-main">{children}</div>
      </div>
      {open && panel ? (
        <div className="tl-body">
          <span aria-hidden="true" />
          <span className="tl-node" aria-hidden="true">
            <span className="tl-rail" />
          </span>
          <div className="tl-panel">{panel}</div>
        </div>
      ) : null}
    </div>
  );
}

interface UnifiedIncidentActivityCardProps {
  className?: string;
}

/**
 * 待處理與事件審計卡片（2026-11-25 定案架構 8：同軌手風琴一體流）
 * - 待處理與下方審計流水共用同一條光軌、同一種實心光珠與霧底等寬標籤
 * - 待處理預設展開最急的一筆；點選列展開或收合。光點是靜態實心點，不做動畫（2026-11-25 使用者定案）
 * - 「全部／異常／成交／風控」分頁沿用同一種列，點選展開欄位明細
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
  /** undefined：使用者還沒點過，預設展開最急的一筆；null：全部收合 */
  const [pickedActionId, setPickedActionId] = useState<string | null | undefined>(undefined);
  const [category, setCategory] = useState<string>('ACTION');
  const [showHeartbeats, setShowHeartbeats] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const userPickedTabRef = useRef(false);

  const cardRef = useRef<HTMLDivElement>(null);
  const [cardW, setCardW] = useState(560);

  useEffect(() => {
    const el = cardRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) setCardW(entry.contentRect.width);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const isNarrow = cardW < 440;
  const isSuperNarrow = cardW < 360;

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
        code: 'KILL',
        tone: 'down',
        alert: true,
        time: clockFromIso(killSwitch.engaged_record?.created_at),
        tag: '總開關觸發',
        title: 'Kill-Switch 已鎖存',
        symbol: 'ALL · 禁啟新 run',
        brief: `原因：${reason}`,
        hero: { value: '已鎖存', tone: 'down' },
        fact: `原因：${reason} · 需由使用者確認原因後人工解除`,
        metrics: [
          { label: '觸發原因', value: reason, tone: 'down' },
          { label: '解除方式', value: '風控頁人工解除' },
        ],
        primaryAction: { label: '前往風控', route: '/risk', tone: 'danger' },
      });
    }

    if (risk && (risk.derived.status === 'soft_latch' || risk.derived.status === 'hard_latch')) {
      const isHard = risk.derived.status === 'hard_latch';
      const label = isHard ? 'Hard Latch' : 'Soft Latch';
      const reasons = risk.reasons.length > 0 ? risk.reasons.join(', ') : '風控期間損益達門檻';
      list.push({
        id: `p0-risk-${risk.derived.status}`,
        sev: 'p0',
        code: 'LATCH',
        tone: 'down',
        alert: true,
        time: null,
        tag: '風控鎖存',
        title: `帳戶 ${label} 已觸發`,
        symbol: 'ALL · 禁止增倉',
        brief: `原因：${reasons}`,
        hero: { value: isHard ? 'HARD' : 'SOFT', tone: 'down' },
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
          code: 'FAIL',
          tone: 'down',
          alert: true,
          time: clockFromMs(run.updated_at_ms),
          tag: '執行失敗',
          title: run.strategy_id ?? shortId(run.run_id),
          symbol: 'OKX Demo',
          brief: `run ${shortId(run.run_id)} · ${run.stop_reason ?? '執行錯誤'}`,
          hero: { value: `${run.position ?? '0'} 張` },
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
          code: 'STALE',
          tone: 'warn',
          alert: true,
          time: clockFromMs(run.updated_at_ms),
          tag: '無回應',
          title: run.strategy_id ?? shortId(run.run_id),
          symbol: 'OKX Demo',
          brief: `run ${shortId(run.run_id)} 逾兩根 K 線未寫入`,
          hero: { value: '無回應', tone: 'warn' },
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
          code: 'HASH',
          tone: 'warn',
          alert: true,
          time: null,
          tag: '來源異動',
          title: approval.strategy_id,
          symbol: '雜湊不符',
          brief: `核准 ${shortId(approval.approval_id)} · Bot 與 IPC 已停止解析`,
          hero: { value: '需重審', tone: 'warn' },
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
      const isError = latest.event.level === 'ERROR';
      list.push({
        id: `p1-event-${latest.event.seq}`,
        sev: 'p1',
        code: isError ? 'ERROR' : 'WARN',
        tone: isError ? 'down' : 'warn',
        alert: true,
        time: latest.time,
        tag: isError ? '事件錯誤' : '事件警戒',
        title: latest.title,
        symbol: `seq ${latest.event.seq}`,
        brief: `近期累計 ${alertEvents.length} 筆異常`,
        hero: { value: `${alertEvents.length} 筆`, tone: 'warn' },
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
          code: 'GATE',
          tone: 'pri',
          time: null,
          tag: '待核准',
          title: s.name || s.id,
          symbol: `strategies/${s.id}/`,
          brief: '資料夾策略 · 部署前須 CLI 核准',
          hero: { value: '待核准', tone: 'blue' },
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

  const quietHeartbeatCount = useMemo(
    () => rows.filter((r) => isQuietHeartbeat(r.event)).length,
    [rows]
  );

  const filteredRows = useMemo(() => {
    if (!currentTab || currentTab.id === 'ACTION') return [];
    const base = rows.filter((row) => currentTab.filterFn(row.event));
    if (currentTab.id === 'ALL' && !showHeartbeats && quietHeartbeatCount > 0) {
      const important = base.filter((row) => !isQuietHeartbeat(row.event));
      if (important.length > 0) return important;
    }
    return base;
  }, [rows, currentTab, showHeartbeats, quietHeartbeatCount]);

  const openActionId = pickedActionId === undefined ? actionItems[0]?.id ?? null : pickedActionId;

  const toggleRow = (key: string) => {
    setExpandedKey((prev) => (prev === key ? null : key));
  };

  /** 點已展開的那筆就收合（含預設展開的第一筆），點其他筆就換展開 */
  const pickAction = (id: string) => {
    setPickedActionId(openActionId === id ? null : id);
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
  const showEquity = cardW >= 420;

  const renderActionPanel = (item: ActionQueueItem) => {
    const isCopied = copiedId === item.id;
    return (
      <>
        <div className="flex items-center justify-between gap-2.5 flex-wrap">
          {item.metrics && item.metrics.length > 0 ? (
            <div className="min-w-0 flex items-center flex-wrap gap-y-1 font-mono text-t2">
              {item.metrics.map((m, idx) => (
                <span
                  key={`${item.id}-m-${idx}`}
                  className={cn(
                    'inline-flex items-center gap-1.5',
                    idx < item.metrics!.length - 1 && 'pr-2.5 mr-2.5 border-r border-border/45'
                  )}
                >
                  <span className="text-muted-foreground/80 font-sans">{m.label}</span>
                  <span className={cn('font-semibold tabular-nums', metricToneClass(m.tone))}>{m.value}</span>
                </span>
              ))}
            </div>
          ) : (
            <p className="min-w-0 text-t2 text-muted-foreground leading-snug font-sans">{item.fact}</p>
          )}

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
                'shrink-0 px-2 py-1 rounded border text-t2 font-mono transition-colors cursor-pointer whitespace-nowrap inline-flex items-center gap-1 outline-none focus-visible:ring-1 focus-visible:ring-ring',
                item.primaryAction.tone === 'danger'
                  ? 'border-down/45 bg-down/15 text-down hover:bg-down/25'
                  : 'border-border bg-white/[0.03] text-foreground hover:border-primary/50 hover:text-primary'
              )}
            >
              <span>{item.primaryAction.label}</span>
              <ArrowRight className="size-2.5" />
            </button>
          )}
        </div>

        {item.copyCommand && (
          <div className="flex items-center justify-between gap-2.5 rounded border border-border bg-background/90 px-2.5 py-1.5 font-mono text-t2 text-muted-foreground">
            <code className="min-w-0 truncate text-foreground select-text">$ {item.copyCommand.command}</code>
            <button
              type="button"
              onClick={() => handleCopyCommand(item.id, item.copyCommand!.command)}
              title="複製 CLI 指令至剪貼簿（核准僅於終端機執行）"
              className="shrink-0 px-1.5 py-0.5 rounded text-primary font-semibold hover:bg-primary/15 transition-colors cursor-pointer inline-flex items-center gap-1 whitespace-nowrap outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {isCopied ? <Check className="size-3" /> : <Copy className="size-3" />}
              <span>{isCopied ? '已複製' : item.copyCommand.label}</span>
            </button>
          </div>
        )}
      </>
    );
  };

  const renderEventPanel = (row: EventRow) => {
    const ev = row.event;
    const detailFields = buildDetailFields(ev);
    return (
      <>
        {detailFields ? (
          <div className={cn('grid gap-2 text-t1 font-mono', cardW < 420 ? 'grid-cols-2' : 'grid-cols-4')}>
            {detailFields.map((field) => (
              <div key={field.label} className="min-w-0">
                <span className="text-muted-foreground block text-t1 uppercase tracking-wider">{field.label}</span>
                <span className="font-semibold text-foreground break-all">{field.value}</span>
              </div>
            ))}
          </div>
        ) : (
          <pre className="text-t1 font-mono max-h-40 overflow-auto text-zinc-300 whitespace-pre-wrap break-all custom-scrollbar select-text">
            {JSON.stringify(ev.payload, null, 1)}
          </pre>
        )}
        <div className="pt-1.5 border-t border-white/[0.05] text-t1 text-muted-foreground/80 truncate">
          {`seq ${ev.seq} · run ${shortId(ev.run_id)} · ${row.syntheticLabel ? '合成時間 ' + row.syntheticLabel + ' · ' : ''}${ev.category}`}
        </div>
      </>
    );
  };

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

      {/* 2. 主內容區 */}
      {category === 'ACTION' ? (
        <div className="flex-1 min-h-0 flex flex-col overflow-y-auto overscroll-contain custom-scrollbar">
          {/* 上半：待處理手風琴（與下方流水共用同一條光軌） */}
          <div className="tl-zone shrink-0 border-b border-border/60 px-3 pt-1.5 pb-2">
            {actionItems.length === 0 ? (
              <div className="py-4 text-center text-t2 text-muted-foreground font-sans">無待處理項目</div>
            ) : (
              <div className="tl-feed">
                {actionItems.map((item) => {
                  const isOpen = openActionId === item.id;
                  return (
                    <FeedRow
                      key={item.id}
                      tone={item.tone}
                      time={item.time}
                      alert={item.alert}
                      expandable
                      open={isOpen}
                      onActivate={() => pickAction(item.id)}
                      panel={renderActionPanel(item)}
                    >
                      <span className="tl-tag">{item.code}</span>
                      <span
                        className="min-w-0 flex-1 truncate text-t3 font-sans text-foreground/75"
                        title={`${item.tag} · ${item.title}${item.symbol ? ' · ' + item.symbol : ''} · ${item.brief}`}
                      >
                        <strong className="font-mono font-semibold text-foreground">{item.title}</strong>
                        {item.symbol ? ` · ${item.symbol}` : ''}
                        {item.brief ? ` · ${item.brief}` : ''}
                      </span>
                      {item.hero && (
                        <span className={cn('shrink-0 font-mono text-t3 font-bold tabular-nums', metricToneClass(item.hero.tone))}>
                          {item.hero.value}
                        </span>
                      )}
                    </FeedRow>
                  );
                })}
              </div>
            )}
          </div>

          {/* 下半：近期審計與成交流水 */}
          <div className="flex-1 min-h-0 flex flex-col">
            <div className="flex items-center justify-between px-3 py-1.5 border-b border-border/60 shrink-0">
              <span className="text-t1 font-mono text-muted-foreground">
                近期審計與成交流水 · {events.length} 筆
              </span>
              <button
                type="button"
                onClick={() => handleSelectTab('ALL')}
                className="text-t1 font-mono text-muted-foreground hover:text-primary inline-flex items-center gap-0.5 cursor-pointer shrink-0"
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
              <div className="tl-feed px-3 pt-1.5 pb-2.5">
                {recentHighlights.map((row) => {
                  const tag = eventTag(row.event, row.side);
                  return (
                    <FeedRow
                      key={row.key}
                      tone={tag.tone}
                      time={row.time}
                      alert={row.isAlert}
                      onActivate={() => {
                        handleSelectTab('ALL');
                        setExpandedKey(row.key);
                      }}
                    >
                      <span className="tl-tag">{tag.code}</span>
                      <span
                        className={cn(
                          'min-w-0 flex-1 truncate text-t3 font-sans',
                          row.isAlert ? 'text-foreground font-medium' : 'text-foreground/80'
                        )}
                        title={row.title}
                      >
                        {row.title}
                      </span>
                      {row.equity && showEquity && (
                        <span className="shrink-0 text-t2 font-mono text-muted-foreground tabular-nums" title="權益">
                          {row.equity}
                        </span>
                      )}
                    </FeedRow>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
          {category === 'ALL' && quietHeartbeatCount > 0 && (
            <div className="flex items-center justify-between px-3 py-1.5 bg-background/40 border-b border-border/60 shrink-0 gap-2">
              <span className="text-t1 font-mono text-muted-foreground truncate">
                {showHeartbeats
                  ? `完整事件流水 · ${filteredRows.length} 筆（含 ${quietHeartbeatCount} 筆收盤心跳）`
                  : `重點交易與審計事件 · ${filteredRows.length} 筆（已隱藏 ${quietHeartbeatCount} 筆收盤心跳）`}
              </span>
              <button
                type="button"
                onClick={() => setShowHeartbeats((v) => !v)}
                className={cn(
                  'px-2 py-0.5 rounded border text-t1 font-mono transition-colors cursor-pointer whitespace-nowrap shrink-0 outline-none focus:outline-none',
                  showHeartbeats
                    ? 'border-primary/45 bg-primary/15 text-primary'
                    : 'border-border/80 bg-secondary/50 text-muted-foreground hover:text-foreground hover:border-primary/45'
                )}
              >
                {showHeartbeats ? '隱藏 K 線心跳' : `顯示 K 線心跳 (${quietHeartbeatCount})`}
              </button>
            </div>
          )}
          <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-3 py-2 custom-scrollbar">
            {showEmpty ? (
              <div className="h-full flex flex-col items-center justify-center text-muted-foreground gap-1">
                <Inbox className="size-6 text-zinc-500/80 mb-1" />
                <span className="text-t2">{emptyMessage}</span>
              </div>
            ) : (
              <div className="tl-feed">
                {filteredRows.map((row) => {
                  const ev = row.event;
                  const isExp = expandedKey === row.key;
                  const tag = eventTag(ev, row.side);
                  return (
                    <FeedRow
                      key={row.key}
                      tone={tag.tone}
                      time={row.time}
                      alert={row.isAlert}
                      expandable
                      open={isExp}
                      onActivate={() => toggleRow(row.key)}
                      panel={isExp ? renderEventPanel(row) : undefined}
                    >
                      <span className="tl-tag">{tag.code}</span>
                      {cardW >= 460 && ev.bot_id && (
                        <span className="px-1.5 py-0.5 rounded bg-white/[0.06] text-zinc-300 text-t1 leading-none shrink-0 font-mono">
                          {ev.bot_id}
                        </span>
                      )}
                      <span
                        className={cn(
                          'min-w-0 flex-1 truncate text-t3 font-sans',
                          row.isAlert ? 'text-foreground font-medium' : 'text-foreground/80'
                        )}
                        title={row.title}
                      >
                        {row.title}
                      </span>
                      {row.equity && cardW >= 460 && (
                        <span className="shrink-0 text-t2 font-mono text-muted-foreground tabular-nums" title="權益">
                          {row.equity}
                        </span>
                      )}
                      <ChevronDown
                        className={cn(
                          'size-3 shrink-0 text-muted-foreground/70 transition-transform duration-200',
                          isExp && 'rotate-180'
                        )}
                        aria-hidden="true"
                      />
                    </FeedRow>
                  );
                })}
              </div>
            )}
          </div>
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
