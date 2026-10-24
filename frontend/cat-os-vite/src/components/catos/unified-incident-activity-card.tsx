import { useState, useMemo, useRef, useEffect } from 'react';
import { usePreviewStore, type PreviewEvent } from '@/state/dashboard-demo-store';
import { CardHeaderTitle } from './card-header-title';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ShieldAlert,
  Lock,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatUsd, toneOf } from '@/lib/v0-engine';

export type EventCategoryFilter = string;

export interface CategoryTabItem {
  id: string;
  label: string;
  badgeCount: number;
  isAlert?: boolean;
  filterFn: (ev: PreviewEvent) => boolean;
}

// 輔助函式：安全取得事件領域 (Domain)
function getEventDomain(ev: PreviewEvent): string {
  if (ev.domain) return ev.domain;
  if (ev.category === 'FILL' || ev.severity === 'TRADE') return 'FILLS';
  if (ev.id.includes('p6') || ev.title.includes('停損') || ev.title.includes('保護')) return 'P6';
  if (ev.id.includes('unknown') || ev.title.includes('委託') || ev.title.includes('掛單') || ev.relatedOrderId) return 'ORDERS';
  if (ev.title.includes('風控') || ev.title.includes('槓桿') || ev.title.includes('日損') || ev.title.includes('熔斷')) return 'RISK';
  if (ev.title.includes('核對') || ev.title.includes('對帳') || ev.title.includes('陌生')) return 'RECON';
  return 'SYSTEM';
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

interface UnifiedIncidentActivityCardProps {
  className?: string;
}

export function UnifiedIncidentActivityCard({ className }: UnifiedIncidentActivityCardProps) {
  const { events } = usePreviewStore();

  // 預設展開最新的未解除告警 (Calico UNKNOWN)
  const [expandedId, setExpandedId] = useState<string | null>('evt_unknown_calico');
  const [category, setCategory] = useState<string>('ALL');


  // DOM 容器與節點座標引用
  const containerRef = useRef<HTMLDivElement>(null);
  const nodeRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  // 時序湧動：量測各節點真實 offsetTop 相對於底部的延遲 (秒)
  const [bottomUpDelays, setBottomUpDelays] = useState<Record<string, number>>({});

  // 統計未解除異常數
  const openCount = useMemo(() => {
    return events.filter((e) => e.resolution === 'open' && (e.category === 'ALERT' || e.severity === 'WARN')).length;
  }, [events]);

  // 2026-10-23 定案固化：詞組 2 極限二字 (Bloomberg / TradingView 零浪費極簡純粹風格)
  const availableTabs = useMemo<CategoryTabItem[]>(() => {
    const isOpen = (e: PreviewEvent) => e.resolution === 'open' && (e.category === 'ALERT' || e.severity === 'WARN');
    const countFills = events.filter((e) => ['FILLS', 'FUNDING'].includes(getEventDomain(e))).length;
    const countRisk = events.filter((e) => ['RISK', 'P6'].includes(getEventDomain(e))).length;
    const countOrders = events.filter((e) => ['ORDERS'].includes(getEventDomain(e))).length;
    const countSystem = events.filter((e) => ['SYSTEM', 'RECON'].includes(getEventDomain(e))).length;

    return [
      { id: 'OPEN', label: `未解除 (${openCount})`, badgeCount: openCount, isAlert: openCount > 0, filterFn: isOpen },
      { id: 'ALL', label: `全部 (${events.length})`, badgeCount: events.length, filterFn: () => true },
      { id: 'RISK_P6', label: `風控 (${countRisk})`, badgeCount: countRisk, filterFn: (e) => ['RISK', 'P6'].includes(getEventDomain(e)) },
      { id: 'FILLS_CASH', label: `成交 (${countFills})`, badgeCount: countFills, filterFn: (e) => ['FILLS', 'FUNDING'].includes(getEventDomain(e)) },
      { id: 'ORDERS_EXEC', label: `委託 (${countOrders})`, badgeCount: countOrders, filterFn: (e) => ['ORDERS'].includes(getEventDomain(e)) },
      { id: 'SYSTEM_RECON', label: `系統 (${countSystem})`, badgeCount: countSystem, filterFn: (e) => ['SYSTEM', 'RECON'].includes(getEventDomain(e)) },
    ];
  }, [events, openCount]);

  const currentTab = useMemo(() => {
    return availableTabs.find((t) => t.id === category) ?? availableTabs[1] ?? availableTabs[0];
  }, [availableTabs, category]);

  // 篩選後事件列表 (未解除優先置頂，保持時間序列)
  const filteredEvents = useMemo(() => {
    const list = events.filter((e) => {
      if (!currentTab) return true;
      return currentTab.filterFn(e);
    });

    return [...list].sort((a, b) => {
      const aOpen = Number(a.resolution === 'open' && (a.category === 'ALERT' || a.severity === 'WARN'));
      const bOpen = Number(b.resolution === 'open' && (b.category === 'ALERT' || b.severity === 'WARN'));
      return bOpen - aOpen;
    });
  }, [events, currentTab]);

  // 由下往上物理幾何計算：當前節點距離容器底部的真實像素距離比率
  useEffect(() => {
    if (!containerRef.current) return;
    const totalH = containerRef.current.scrollHeight;
    if (totalH <= 0) return;

    const newDelays: Record<string, number> = {};
    filteredEvents.forEach((ev) => {
      const el = nodeRefs.current.get(ev.id);
      if (el) {
        const nodeY = el.offsetTop + 8;
        // 由下往上：離底部的距離 = totalH - nodeY
        const distFromBottom = Math.max(0, totalH - nodeY);
        const ratio = Math.max(0, Math.min(1, distFromBottom / totalH));
        newDelays[ev.id] = Number((ratio * DURATION_SEC).toFixed(3));
      }
    });
    setBottomUpDelays(newDelays);
  }, [filteredEvents, expandedId]);

  const toggleIncident = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  // 小圓點與標籤樣式：定案固化方案 C (macOS Sequoia 晶透黑曜石微膠囊風格)
  const getBadgeMeta = (ev: PreviewEvent) => {
    // 1. 精準通知語意判定 (Strict Semantic Classification)
    const isAlert = ev.category === 'ALERT' || ev.severity === 'WARN';
    const isOpen = isAlert && ev.resolution === 'open';
    const isResolvedAlert = isAlert && ev.resolution === 'resolved';
    const isFill = ev.category === 'FILL' || ev.severity === 'TRADE';
    const isFillShort = isFill && (ev.action?.includes('空') || ev.action?.includes('賣') || ev.side === 'sell');
    const isSystemHeartbeat = ev.category === 'SYSTEM' && ev.severity === 'OK';

    // 定案固化方案 C：macOS Sequoia 晶透黑曜石 (Frosted Capsule HIG)
    if (isOpen) {
      return {
        label: 'WARN',
        badgeClass: 'bg-amber-500/15 text-amber-200 border border-amber-500/30 rounded-full px-2 font-medium backdrop-blur-xs',
        coreClass: 'bg-[#f59e0b] shadow-[0_0_8px_rgba(245,158,11,0.55)] ring-1 ring-amber-400/40',
        sonarClass: 'bg-amber-500/25',
        bloomAnimation: 'crystal-optical-bloom-amber',
      };
    }
    if (isResolvedAlert) {
      return {
        label: 'RESOLVED',
        badgeClass: 'bg-white/[0.04] text-zinc-400 border border-white/[0.06] rounded-full px-2 font-medium backdrop-blur-xs',
        coreClass: 'bg-zinc-600/70 ring-1 ring-zinc-600/40',
        sonarClass: 'bg-zinc-600/15',
        bloomAnimation: 'crystal-optical-bloom-neutral',
      };
    }
    if (isFill) {
      return {
        label: ev.action || '成交',
        badgeClass: isFillShort
          ? 'bg-rose-500/15 text-rose-200 border border-rose-500/25 rounded-full px-2 font-medium backdrop-blur-xs'
          : 'bg-emerald-500/15 text-emerald-200 border border-emerald-500/25 rounded-full px-2 font-medium backdrop-blur-xs',
        coreClass: isFillShort
          ? 'bg-[#f43f5e] shadow-[0_0_8px_rgba(244,63,94,0.45)] ring-1 ring-rose-400/30'
          : 'bg-[#10b981] shadow-[0_0_8px_rgba(16,185,129,0.45)] ring-1 ring-emerald-400/30',
        sonarClass: isFillShort ? 'bg-rose-500/20' : 'bg-emerald-500/20',
        bloomAnimation: isFillShort ? 'crystal-optical-bloom-rose' : 'crystal-optical-bloom-emerald',
      };
    }
    if (isSystemHeartbeat) {
      return {
        label: 'OK',
        badgeClass: 'bg-slate-500/15 text-slate-300 border border-slate-500/25 rounded-full px-2 font-medium backdrop-blur-xs',
        coreClass: 'bg-slate-500/70 shadow-[0_0_5px_rgba(100,116,139,0.3)] ring-1 ring-slate-600/40',
        sonarClass: 'bg-slate-500/15',
        bloomAnimation: 'crystal-optical-bloom-neutral',
      };
    }
    return {
      label: 'INFO',
      badgeClass: 'bg-white/[0.04] text-zinc-400 border border-white/[0.05] rounded-full px-2 font-medium backdrop-blur-xs',
      coreClass: 'bg-zinc-600/60 ring-1 ring-zinc-700/30',
      sonarClass: 'bg-zinc-600/10',
      bloomAnimation: 'crystal-optical-bloom-neutral',
    };
  };

  return (
    <div className={cn('flex flex-col h-full w-full select-none overflow-hidden bg-surface/40 font-mono', className)}>
      {/* 1. Header 區域：整合卡片標題 + 異常膠囊 (定案方案 C 固化) */}
      <div className="flex flex-wrap items-center justify-between px-3 py-2 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
        <div className="flex items-center gap-2">
          <CardHeaderTitle
            cardId="activity_deck"
            title="風險警報與交易日誌"
            subtext=""
          />
          {openCount > 0 ? (
            <span className="flex items-center gap-1 text-[8.5px] px-1.5 py-0.5 rounded-[3px] bg-amber-500/12 text-amber-200 border border-amber-500/30 animate-pulse font-medium">
              <ShieldAlert className="size-2.5" />
              <span>{openCount} 異常</span>
            </span>
          ) : (
            <span className="flex items-center gap-1 text-[8.5px] px-1.5 py-0.5 rounded-[3px] bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 font-medium">
              <CheckCircle2 className="size-2.5" />
              <span>系統正常</span>
            </span>
          )}
        </div>


      </div>

      {/* 2. 類別過濾工具列 + 分類架構對照切換 */}
      <div className="flex flex-wrap items-center justify-between px-3 py-1.5 bg-secondary/30 border-b border-border/60 text-[9.5px] shrink-0 gap-1.5">
        <div className="flex items-center gap-1 overflow-x-auto">
          <span className="text-zinc-500 mr-0.5 text-[8.5px]">分類：</span>
          {availableTabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setCategory(tab.id)}
              className={cn(
                'px-1.5 py-0.2 rounded transition-colors cursor-pointer text-[8.5px] whitespace-nowrap',
                category === tab.id
                  ? 'bg-white/[0.08] text-zinc-100 font-medium shadow-xs border border-white/10'
                  : tab.isAlert
                  ? 'text-amber-300/90 hover:text-amber-200 font-medium'
                  : 'text-zinc-400 hover:text-zinc-200 font-normal'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

      </div>

      {/* 3. 核心時間軸內容區 */}
      <div
        key={`timeline-${expandedId}`}
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
        {filteredEvents.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-muted-foreground text-xs gap-1">
            <CheckCircle2 className="size-6 text-emerald-400/80 mb-1" />
            <span className="font-semibold text-foreground text-[11px]">無符合條件之事件</span>
            <span className="text-[10px]">系統平穩運行中，所有風控指標正常</span>
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
                style={{ animation: `photon-travel-upward ${DURATION_SEC}s linear infinite` }}
              >
                <div
                  className="photon-aurora-glow-up"
                  style={{
                    width: `${GLOW_SPREAD}px`,
                    height: `${Math.round(PHOTON_LENGTH * 1.25)}px`,
                    opacity: PHOTON_BRIGHTNESS / 100,
                    filter: `blur(${Math.max(2, Math.round(GLOW_SPREAD * 0.28))}px)`,
                  }}
                />
                <div
                  className="photon-aurora-core-up"
                  style={{
                    width: `${PHOTON_WIDTH}px`,
                    height: `${PHOTON_LENGTH}px`,
                    opacity: 1,
                    boxShadow: `0 0 ${Math.round(8 * (BLOOM_INTENSITY / 100))}px ${Math.round(1 * (BLOOM_INTENSITY / 100))}px rgba(255, 255, 255, 0.7)`,
                  }}
                />
              </div>
            </div>

            {filteredEvents.map((ev) => {
              const isExp = expandedId === ev.id;
              const meta = getBadgeMeta(ev);
              const isFill = ev.category === 'FILL';
              const isWarn = ev.severity === 'WARN' || ev.category === 'ALERT';
              const isOpen = ev.resolution === 'open' && isWarn;

              // 取得該節點離底部的真實幾何延遲 (秒)
              const bottomDelay = bottomUpDelays[ev.id] ?? 0;

              return (
                <div
                  key={ev.id}
                  ref={(el) => {
                    if (el) nodeRefs.current.set(ev.id, el);
                    else nodeRefs.current.delete(ev.id);
                  }}
                  className="relative flex items-start gap-2.5 group"
                >
                  {/* 時間軸節點小圓點容器 */}
                  <div className="relative mt-1 shrink-0 z-10 flex items-center justify-center size-4 pointer-events-none">
                    {/* 由下往上光子穿透之次表面柔霧微光環 */}
                    <span
                      className={cn(
                        "absolute inline-flex size-2 rounded-full pointer-events-none",
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
                        isOpen && 'crystal-breathe-subtle'
                      )}
                      style={{
                        animation: `${meta.bloomAnimation} ${DURATION_SEC}s cubic-bezier(0.16, 1, 0.3, 1) infinite`,
                        animationDelay: `${bottomDelay}s`,
                      }}
                    />
                  </div>

                  {/* 事件行容器：完全無框純淨數據流 (Zero-Waste) */}
                  <div
                    onClick={() => toggleIncident(ev.id)}
                    className={cn(
                      'flex-1 min-w-0 transition-all duration-150 cursor-pointer p-2 rounded-md',
                      isOpen && !isExp
                        ? 'bg-amber-500/[0.02] hover:bg-amber-500/[0.04]'
                        : isExp
                        ? 'bg-white/[0.035]'
                        : 'hover:bg-white/[0.025]'
                    )}
                  >
                    {/* 表頭一行：時間 + 標籤 + 關聯 Bot + 標題 + 右側 PnL/狀態 + 箭頭 */}
                    <div className="flex items-center justify-between gap-2 text-[10px]">
                      <div className="flex items-center gap-1.5 min-w-0">
                        {/* 時間戳 */}
                        <span className="text-zinc-500 text-[9px] shrink-0 font-mono">{ev.time}</span>

                        {/* 類型 Badge (依風格即時切換) */}
                        <span className={cn('px-1.5 py-0.2 rounded text-[8px] shrink-0', meta.badgeClass)}>
                          {meta.label}
                        </span>

                        {/* 關聯 Bot 或來源 */}
                        {(ev.botName || ev.source) && (
                          <span className="text-zinc-500 text-[9px] shrink-0 font-mono hidden sm:inline">
                            [{ev.botName || ev.source}]
                          </span>
                        )}

                        {/* 事件主標題 */}
                        <span className={cn(
                          "truncate leading-tight tracking-tight",
                          isOpen ? "text-zinc-100 font-medium text-[10.5px]" : "text-zinc-300 font-normal text-[10.5px]"
                        )}>
                          {isFill && ev.symbol ? `${ev.symbol} · ${ev.qty} @ $${ev.price}` : ev.title}
                        </span>
                      </div>

                      {/* 右側：PnL 盈虧 / 狀態標籤 / 展開箭頭 */}
                      <div className="flex items-center gap-2 shrink-0">
                        {isFill ? (
                          ev.pnl && ev.pnl !== 0 ? (
                            <span className={cn('text-[10px] font-semibold font-mono tracking-tight', toneOf(ev.pnl))}>
                              {formatUsd(ev.pnl, true)}
                            </span>
                          ) : (
                            <span className="text-[8.5px] text-zinc-500">撮合</span>
                          )
                        ) : isOpen ? (
                          <span className="text-[8px] font-medium px-2 py-0.2 rounded-full animate-pulse bg-amber-500/15 border border-amber-500/30 text-amber-200 backdrop-blur-xs">
                            未解除
                          </span>
                        ) : ev.resolution === 'resolved' ? (
                          <span className="text-[8px] text-zinc-500 hidden sm:inline">已解除</span>
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
                        className="mt-2 pt-2 border-t border-white/[0.05] text-[9.5px] space-y-2 text-zinc-300 snap-accordion-enter"
                      >
                        {/* 詳細說明 */}
                        <p className="leading-relaxed text-zinc-300 font-normal pl-0.5">
                          {ev.detail}
                        </p>

                        {/* 事故衝擊與風控判定 (定案方案 C：macOS 晶透黑曜石微膠囊卡片) */}
                        {ev.impact && (
                          <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/25 backdrop-blur-xs text-[9px] flex items-start gap-2">
                            <AlertTriangle className="size-3 shrink-0 mt-0.5 text-amber-400" />
                            <div className="leading-relaxed">
                              <span className="font-semibold text-amber-200 mr-1">風控衝擊：</span>
                              <span className="text-zinc-200">{ev.impact}</span>
                            </div>
                          </div>
                        )}

                        {/* 下一步處置導引 (Next Step) */}
                        {ev.nextStep && (
                          <p className="text-[9px] text-zinc-400 leading-relaxed pl-1">
                            <span className="font-medium text-zinc-300 mr-1">下一步處置：</span>
                            <span>{ev.nextStep}</span>
                          </p>
                        )}

                        {/* 底部操作按鈕與來源列 */}
                        <div className="flex items-center justify-between pt-1 border-t border-white/[0.04] text-[8.5px] text-zinc-500">
                          <div className="flex items-center gap-1.5">
                            <span>來源:</span>
                            <code className="text-zinc-300 bg-white/[0.04] px-1 py-0.2 rounded border border-white/[0.06] font-mono">
                              {ev.source}
                            </code>
                            {ev.id === 'evt_unknown_calico' && (
                              <span className="flex items-center gap-1 text-amber-200/90 bg-amber-500/8 px-1.5 py-0.2 rounded border border-amber-500/20 font-medium">
                                <Lock className="size-2.5 text-amber-400/80" />
                                額度已鎖存 ($474.75)
                              </span>
                            )}
                          </div>
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
    </div>
  );
}
