import { useState, useMemo, useRef, useEffect } from 'react';
import { useCatStore } from '@/state/catStore';
import type { EventDTO, EventLevel } from '@/contracts';
import { CardHeaderTitle } from './card-header-title';
import { ChevronDown, ChevronUp, Inbox } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatClock, formatDateTime, formatDecimal, shortId } from '@/lib/format';

export type EventCategoryFilter = string;

export interface CategoryTabItem {
  id: string;
  label: string;
  shortLabel: string;
  badgeCount: number;
  isAlert?: boolean;
  filterFn: (ev: EventDTO) => boolean;
}

// 2026-10-22 使用者拍板定案參數 (純白光子 · 11s 時序湧動 · 完全無框)
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

// ---- payload 安全存取（payload 為 Record<string, unknown>，所有金額皆為 Decimal 字串） ----

type Rec = Record<string, unknown>;

function asRecord(value: unknown): Rec | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? (value as Rec) : null;
}

function asString(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

/** 顯示用文字：字串／數字／布林直接呈現，其餘顯示 不適用。 */
function asText(value: unknown): string {
  if (typeof value === 'string') return value || NA;
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  return NA;
}

/** Decimal 字串金額：只經 formatDecimal，缺失或格式錯誤顯示 不適用。 */
function money(value: unknown, sign = false): string {
  return formatDecimal(asString(value), { prefix: '$', sign });
}

/** 合約張數／部位：Decimal 字串，無法解析時原樣顯示，不轉 Number。 */
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

function buildTitle(ev: EventDTO, instLabel: string): string {
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
    title: buildTitle(ev, instLabel),
    rightText,
    side: sideOf(ev),
    isAlert,
  };
}

// 小圓點與標籤樣式：定案固化方案 C (macOS Sequoia 晶透黑曜石微膠囊風格)
function getBadgeMeta(ev: EventDTO, side: Side) {
  if (ev.level === 'ERROR') {
    return {
      label: 'ERROR',
      badgeClass: 'bg-rose-500/15 text-rose-200 border border-rose-500/30 rounded-full px-2 font-medium backdrop-blur-xs',
      coreClass: 'bg-[#f43f5e] shadow-[0_0_8px_rgba(244,63,94,0.55)] ring-1 ring-rose-400/40',
      sonarClass: 'bg-rose-500/25',
      bloomAnimation: 'crystal-optical-bloom-rose',
    };
  }
  if (ev.level === 'WARN') {
    return {
      label: 'WARN',
      badgeClass: 'bg-amber-500/15 text-amber-200 border border-amber-500/30 rounded-full px-2 font-medium backdrop-blur-xs',
      coreClass: 'bg-[#f59e0b] shadow-[0_0_8px_rgba(245,158,11,0.55)] ring-1 ring-amber-400/40',
      sonarClass: 'bg-amber-500/25',
      bloomAnimation: 'crystal-optical-bloom-amber',
    };
  }
  if (ev.category === 'ORDER') {
    const isShort = side === 'sell';
    return {
      label: '成交',
      badgeClass: isShort
        ? 'bg-rose-500/15 text-rose-200 border border-rose-500/25 rounded-full px-2 font-medium backdrop-blur-xs'
        : 'bg-emerald-500/15 text-emerald-200 border border-emerald-500/25 rounded-full px-2 font-medium backdrop-blur-xs',
      coreClass: isShort
        ? 'bg-[#f43f5e] shadow-[0_0_8px_rgba(244,63,94,0.45)] ring-1 ring-rose-400/30'
        : 'bg-[#10b981] shadow-[0_0_8px_rgba(16,185,129,0.45)] ring-1 ring-emerald-400/30',
      sonarClass: isShort ? 'bg-rose-500/20' : 'bg-emerald-500/20',
      bloomAnimation: isShort ? 'crystal-optical-bloom-rose' : 'crystal-optical-bloom-emerald',
    };
  }
  if (ev.category === 'WORKER') {
    return {
      label: 'INFO',
      badgeClass: 'bg-white/[0.04] text-zinc-400 border border-white/[0.06] rounded-full px-2 font-medium backdrop-blur-xs',
      coreClass: 'bg-zinc-600/70 ring-1 ring-zinc-600/40',
      sonarClass: 'bg-zinc-600/15',
      bloomAnimation: 'crystal-optical-bloom-neutral',
    };
  }
  // RISK / SYSTEM / SUPERVISOR
  return {
    label: ev.category === 'RISK' ? '風控' : 'INFO',
    badgeClass: 'bg-sky-500/15 text-sky-300 border border-sky-500/30 rounded-full px-2 font-medium backdrop-blur-xs',
    coreClass: 'bg-sky-400 shadow-[0_0_6px_rgba(56,189,248,0.5)] ring-1 ring-sky-400/40',
    sonarClass: 'bg-sky-500/20',
    bloomAnimation: 'crystal-optical-bloom-neutral',
  };
}

function levelCapsuleClass(level: EventLevel): string {
  return level === 'ERROR'
    ? 'bg-rose-500/15 border border-rose-500/30 text-rose-200'
    : 'bg-amber-500/15 border border-amber-500/30 text-amber-200 animate-pulse';
}

interface UnifiedIncidentActivityCardProps {
  className?: string;
}

export function UnifiedIncidentActivityCard({ className }: UnifiedIncidentActivityCardProps) {
  const events = useCatStore((s) => s.events);
  const eventsOmitted = useCatStore((s) => s.eventsOmitted);
  const bots = useCatStore((s) => s.bots);
  const connectionStatus = useCatStore((s) => s.connection.status);

  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [category, setCategory] = useState<string>('ALL');

  // DOM 容器與節點座標引用
  const cardRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const nodeRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  // 雙向物理尺寸監聽 (ResizeObserver 自適應 Header 與標籤)
  const [dimensions, setDimensions] = useState({ width: 600, height: 240 });

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

  const isNarrow = dimensions.width < 500;
  const isSuperNarrow = dimensions.width < 380;

  // 時序湧動：量測各節點真實 offsetTop 相對於底部的延遲 (秒)
  const [bottomUpDelays, setBottomUpDelays] = useState<Record<string, number>>({});

  // bot_id → inst_id，成交標題使用合約名稱
  const instById = useMemo(() => {
    const map = new Map<string, string>();
    for (const bot of bots) {
      if (bot.inst_id) map.set(bot.bot_id, bot.inst_id);
    }
    return map;
  }, [bots]);

  // 視圖模型：最新在前
  const rows = useMemo<EventRow[]>(() => {
    return [...events]
      .sort((a, b) => b.seq - a.seq)
      .map((ev) => toRow(ev, instById.get(ev.bot_id) ?? '合約'));
  }, [events, instById]);

  // 分類依 category／level 直接判定，不做字串推斷
  const availableTabs = useMemo<CategoryTabItem[]>(() => {
    const isAlert = (e: EventDTO) => e.level === 'WARN' || e.level === 'ERROR';
    const countAlert = events.filter(isAlert).length;
    const countRisk = events.filter((e) => e.category === 'RISK').length;
    const countOrder = events.filter((e) => e.category === 'ORDER').length;
    const countWorker = events.filter((e) => e.category === 'WORKER').length;
    const countSystem = events.filter((e) => e.category === 'SYSTEM').length;

    return [
      { id: 'ALL', label: `全部(${events.length})`, shortLabel: '全部', badgeCount: events.length, filterFn: () => true },
      { id: 'ALERT', label: `異常(${countAlert})`, shortLabel: countAlert > 0 ? `異常(${countAlert})` : '異常', badgeCount: countAlert, isAlert: countAlert > 0, filterFn: isAlert },
      { id: 'RISK', label: `風控(${countRisk})`, shortLabel: '風控', badgeCount: countRisk, filterFn: (e) => e.category === 'RISK' },
      { id: 'ORDER', label: `成交(${countOrder})`, shortLabel: '成交', badgeCount: countOrder, filterFn: (e) => e.category === 'ORDER' },
      { id: 'WORKER', label: `Worker(${countWorker})`, shortLabel: 'Worker', badgeCount: countWorker, filterFn: (e) => e.category === 'WORKER' },
      { id: 'SYSTEM', label: `系統(${countSystem})`, shortLabel: '系統', badgeCount: countSystem, filterFn: (e) => e.category === 'SYSTEM' },
    ];
  }, [events]);

  const currentTab = useMemo(() => {
    return availableTabs.find((t) => t.id === category) ?? availableTabs[0];
  }, [availableTabs, category]);

  const filteredRows = useMemo(() => {
    if (!currentTab) return rows;
    return rows.filter((row) => currentTab.filterFn(row.event));
  }, [rows, currentTab]);

  // 由下往上物理幾何計算：當前節點距離容器底部的真實像素距離比率
  useEffect(() => {
    if (!containerRef.current) return;
    const totalH = containerRef.current.scrollHeight;
    if (totalH <= 0) return;

    const newDelays: Record<string, number> = {};
    filteredRows.forEach((row) => {
      const el = nodeRefs.current.get(row.key);
      if (el) {
        const nodeY = el.offsetTop + 8;
        // 由下往上：離底部的距離 = totalH - nodeY
        const distFromBottom = Math.max(0, totalH - nodeY);
        const ratio = Math.max(0, Math.min(1, distFromBottom / totalH));
        newDelays[row.key] = Number((ratio * DURATION_SEC).toFixed(3));
      }
    });
    setBottomUpDelays(newDelays);
  }, [filteredRows, expandedKey]);

  const toggleRow = (key: string) => {
    setExpandedKey((prev) => (prev === key ? null : key));
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
      {/* 1. Header 區域：整合卡片標題 + 右上角統一微膠囊 (窄版自適應簡短標籤，杜絕標題截字) */}
      <div className="flex items-center justify-between px-3 h-9 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
        <CardHeaderTitle
          cardId="activity_deck"
          title="事件審計與成交流水"
          subtext={
            !isNarrow ? (
              <span className="text-t2 font-mono text-muted-foreground ml-1">
                {filteredRows.length} 筆
              </span>
            ) : undefined
          }
        />

        {/* 右上角切換膠囊：完全統一規格 (窄版自動切換為簡稱，超窄只顯示核心 4 標籤) */}
        <div className="flex items-center gap-0.5 bg-background/60 border border-border/60 rounded p-0.5 shrink-0 overflow-x-auto max-w-[65%] custom-scrollbar">
          {(isSuperNarrow ? availableTabs.slice(0, 4) : availableTabs).map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setCategory(tab.id)}
              className={cn(
                'px-1.5 sm:px-2 py-0.5 text-t2 font-mono rounded transition-colors cursor-pointer whitespace-nowrap shrink-0',
                category === tab.id
                  ? 'bg-secondary text-foreground font-semibold shadow-xs'
                  : tab.isAlert
                  ? 'text-amber-300/90 hover:text-amber-200'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {isNarrow ? tab.shortLabel : tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* 2. 核心時間軸內容區 */}
      <div
        key={`timeline-${expandedKey}`}
        ref={containerRef}
        className="flex-1 min-h-0 overflow-y-auto p-3 pr-2 relative"
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
          <div className="relative pl-3 space-y-2.5">
            {/* 導軌系統：由下往上向上湧動 */}
            <div className="absolute left-[20px] -translate-x-1/2 top-2 bottom-2 w-[20px] pointer-events-none z-0 overflow-hidden">
              {/* 1. 底層 1px 磨砂暗色導軌線 */}
              <div className="absolute left-[10px] -translate-x-1/2 top-0 bottom-0 w-[1px] bg-white/[0.08]" />

              {/* 2. 由下往上光子漫射流束 (純白光) */}
              <div
                className="absolute left-[2px] bottom-0 w-[20px]"
                style={{ display: 'none' }}
              >
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

              // 取得該節點離底部的真實幾何延遲 (秒)
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
                  {/* 時間軸節點小圓點容器 */}
                  <div className="relative mt-1 shrink-0 z-10 flex items-center justify-center size-4 pointer-events-none">
                    {/* 由下往上光子穿透之次表面柔霧微光環 */}
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

                    {/* 實心核心點：5px 寶石微核，光子經過時產生次表面 Bloom */}
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

                  {/* 事件行容器：完全無框純淨數據流 (Zero-Waste) */}
                  <div
                    onClick={() => toggleRow(row.key)}
                    className={cn(
                      'flex-1 min-w-0 transition-all duration-150 cursor-pointer p-2 rounded-md',
                      isExp
                        ? 'bg-white/[0.035]'
                        : isError
                        ? 'bg-rose-500/[0.02] hover:bg-rose-500/[0.04]'
                        : isWarn
                        ? 'bg-amber-500/[0.02] hover:bg-amber-500/[0.04]'
                        : 'hover:bg-white/[0.025]'
                    )}
                  >
                    {/* 表頭一行：時間 + 標籤 + 買賣方向 + run + 標題 + 右側權益/等級 + 箭頭 */}
                    <div className="flex items-center justify-between gap-2 text-t2">
                      <div className="flex items-center gap-1.5 min-w-0">
                        {/* 時間戳 (wall_time，Asia/Taipei) */}
                        <span className="text-zinc-500 text-t1 shrink-0 font-mono">{row.time}</span>

                        {/* 類型 Badge */}
                        <span className={cn('px-1.5 py-0.2 rounded text-t1 shrink-0', meta.badgeClass)}>
                          {meta.label}
                        </span>

                        {/* 買賣方向專屬微徽章 (僅成交顯示) */}
                        {row.side && (
                          <span
                            className={cn(
                              'px-1.5 py-0.2 rounded text-t1 font-mono shrink-0 font-semibold border',
                              row.side === 'buy'
                                ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                                : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                            )}
                          >
                            {row.side === 'buy' ? '買入' : '賣出'}
                          </span>
                        )}

                        {/* 關聯 run */}
                        <span className="text-zinc-500 text-t1 shrink-0 font-mono hidden sm:inline">
                          [{shortId(ev.run_id)}]
                        </span>

                        {/* 事件主標題 */}
                        <span
                          className={cn(
                            'truncate leading-tight tracking-tight text-t2',
                            row.isAlert ? 'text-zinc-100 font-medium' : 'text-zinc-300 font-normal'
                          )}
                        >
                          {row.title}
                        </span>
                      </div>

                      {/* 右側：成交後權益 / 等級膠囊 / 展開箭頭 */}
                      <div className="flex items-center gap-2 shrink-0">
                        {row.rightText ? (
                          <span className="text-t2 font-mono tracking-tight text-zinc-300 hidden sm:inline">
                            {row.rightText}
                          </span>
                        ) : row.isAlert ? (
                          <span className={cn('text-t1 font-medium px-2 py-0.2 rounded-full backdrop-blur-xs', levelCapsuleClass(ev.level))}>
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

                    {/* 展開詳情面板 */}
                    {isExp && (
                      <div
                        onClick={(e) => e.stopPropagation()}
                        className="mt-2 pt-2 border-t border-white/[0.05] text-t1 space-y-2 text-zinc-300 snap-accordion-enter"
                      >
                        {detailFields ? (
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 p-2 rounded-md bg-secondary/40 border border-border/60 text-t1 font-mono">
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

                        {/* 底部來源列 */}
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

      {/* 3. 後端環形緩衝省略提示：據實回報，不隱藏 */}
      {eventsOmitted > 0 && (
        <div className="shrink-0 px-3 py-1 border-t border-border/60 bg-secondary/30 text-t1 font-mono text-amber-300/90">
          後端環形緩衝已省略 {eventsOmitted} 筆
        </div>
      )}
    </div>
  );
}
