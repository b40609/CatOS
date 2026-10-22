import { useState, useMemo } from "react";
import {
  ShieldAlert,
  Zap,
  CheckCircle2,
} from "lucide-react";
import { CardHeaderTitle } from "./card-header-title";
import { UNIFIED_EVENTS, type EventCategory, type UnifiedEvent } from "@/lib/mock/unified-events";
import { formatUsd, toneOf } from "@/lib/v0-engine";
import { cn } from "@/lib/utils";
import { usePreviewStore } from "@/preview/preview-store";

export interface MonitoredEvent extends UnifiedEvent {
  resolution?: 'open' | 'resolved';
  impact?: string;
  nextStep?: string;
}

interface UnifiedActivityDeckCardProps {
  className?: string;
  showHeader?: boolean;
  events?: MonitoredEvent[];
  isIntegratedPreview?: boolean;
}

export function UnifiedActivityDeckCard({
  className,
  showHeader = true,
  events: propEvents,
  isIntegratedPreview,
}: UnifiedActivityDeckCardProps) {
  const [localCategory, setLocalCategory] = useState<EventCategory | 'OPEN'>("ALL");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // 預覽 Store 綁定
  const {
    events: previewEvents,
    openInspector,
    highlightTarget,
  } = usePreviewStore();

  const sourceEvents: MonitoredEvent[] = isIntegratedPreview
    ? (previewEvents as unknown as MonitoredEvent[])
    : (propEvents ?? UNIFIED_EVENTS);

  const category = localCategory;
  const setCategory = setLocalCategory;

  const filteredEvents = useMemo(() => {
    const filtered = sourceEvents.filter((e) =>
      category === 'ALL'
        ? true
        : category === 'OPEN'
        ? e.resolution === 'open'
        : e.category === category
    );

    // 未解除事件置頂，已解除保留歷史
    return [...filtered].sort((a, b) => Number(b.resolution === 'open') - Number(a.resolution === 'open'));
  }, [category, sourceEvents]);

  const stats = useMemo(() => {
    const fills = sourceEvents.filter((e) => e.category === "FILL").length;
    const alerts = sourceEvents.filter((e) => e.category === "ALERT").length;
    const system = sourceEvents.filter((e) => e.category === "SYSTEM").length;
    const open = sourceEvents.filter((e) => e.resolution === 'open').length;
    return { fills, alerts, system, open, total: sourceEvents.length };
  }, [sourceEvents]);

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40", className)}>
      {/* 1. 一體化 Header 與快速過濾列 */}
      {showHeader && (
        <div className="flex flex-wrap items-center justify-between px-3 py-2 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
          <div className="flex items-center gap-2">
            <CardHeaderTitle
              cardId="activity_deck"
              title="交易日誌與風險事件"
              subtext={
                <div className="flex items-center gap-1.5 ml-1">
                  <span className="text-[10px] font-mono text-muted-foreground">
                    共 {stats.total} 筆事件
                  </span>
                  {stats.open > 0 ? (
                    <span className="inline-flex items-center gap-1 text-[9px] font-mono text-amber-400 bg-amber-400/10 px-1.5 py-0.2 rounded border border-amber-400/25 animate-pulse font-semibold">
                      <ShieldAlert className="size-2.5" />
                      {stats.open} 未解除
                    </span>
                  ) : stats.alerts > 0 ? (
                    <span className="inline-flex items-center gap-1 text-[9px] font-mono text-amber-400 bg-amber-400/10 px-1.5 py-0.2 rounded border border-amber-400/25">
                      <ShieldAlert className="size-2.5" />
                      {stats.alerts} 異常告警
                    </span>
                  ) : null}
                </div>
              }
            />
          </div>

          {/* 5 大類別篩選標籤 (含未解除獨立篩選與數量) */}
          <div className="flex items-center gap-1 bg-background/60 border border-border/60 rounded p-0.5">
            {[
              { id: 'OPEN', label: `未解除 (${stats.open})` },
              { id: "ALL", label: `全部 (${stats.total})` },
              { id: "FILL", label: `成交流 (${stats.fills})` },
              { id: "ALERT", label: `風控警報 (${stats.alerts})` },
              { id: "SYSTEM", label: `系統事件 (${stats.system})` },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setCategory(tab.id as EventCategory | 'OPEN')}
                aria-pressed={category === tab.id}
                className={cn(
                  "px-2 py-0.5 text-[10px] font-mono font-medium rounded transition-colors cursor-pointer",
                  category === tab.id
                    ? "bg-secondary text-primary border border-border font-semibold shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 2. 高密度事件時間軸清單 */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        <table className="w-full text-left border-collapse table-auto">
          <thead className="border-b border-border/80 bg-background/40 text-[9.5px] font-mono text-muted-foreground sticky top-0 z-10 backdrop-blur-sm">
            <tr>
              <th className="py-2 pl-3 pr-1.5 font-medium">TIME / SOURCE</th>
              <th className="px-1.5 font-medium">TYPE & BOT</th>
              <th className="px-1.5 font-medium">TITLE & EVENT DETAILS</th>
              <th className="py-2 pr-3 pl-1.5 text-right font-medium">PnL / STATUS</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40 text-xs font-mono">
            {filteredEvents.map((e) => {
              const isExpanded = expandedId === e.id;
              const isFill = e.category === "FILL";
              const isAlert = e.category === "ALERT";
              const isOpen = e.resolution === 'open';
              const isHighlighted = isIntegratedPreview && highlightTarget.type === 'event' && highlightTarget.id === e.id;

              return (
                <tr
                  key={e.id}
                  onClick={() => {
                    if (isIntegratedPreview) {
                      openInspector('event', e.id);
                    } else {
                      setExpandedId(isExpanded ? null : e.id);
                    }
                  }}
                  className={cn(
                    "hover:bg-secondary/40 transition-all cursor-pointer group",
                    isExpanded && "bg-secondary/50",
                    isOpen && "bg-amber-500/[0.04]",
                    isHighlighted && "ring-1 ring-primary bg-primary/10 shadow-[0_0_12px_rgba(232,180,94,0.3)] animate-pulse"
                  )}
                >
                  {/* 1. 時間與來源 */}
                  <td className="py-2.5 pl-3 pr-1.5 align-top">
                    <div className="flex flex-col">
                      <span className="text-[10.5px] font-bold text-foreground leading-tight">{e.time}</span>
                      <span className="text-[9px] text-muted-foreground leading-tight mt-0.5">{e.source}</span>
                    </div>
                  </td>

                  {/* 2. 類型與關聯 Bot */}
                  <td className="px-1.5 py-2.5 align-top">
                    <div className="flex flex-col gap-0.5">
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 px-1.5 py-0.2 rounded text-[9px] font-bold w-fit",
                          isFill
                            ? e.action?.includes("多")
                              ? "bg-emerald-400/10 text-emerald-400 border border-emerald-400/30"
                              : "bg-rose-400/10 text-rose-400 border border-rose-400/30"
                            : isAlert
                            ? "bg-amber-400/15 text-amber-300 border border-amber-400/40"
                            : "bg-sky-400/10 text-sky-300 border border-sky-400/30"
                        )}
                      >
                        {isFill ? (
                          <>
                            <Zap className="size-2.5" />
                            {e.action}
                          </>
                        ) : isAlert ? (
                          <>
                            <ShieldAlert className="size-2.5" />
                            WARN 警報
                          </>
                        ) : (
                          <>
                            <CheckCircle2 className="size-2.5" />
                            {e.severity} 系統
                          </>
                        )}
                      </span>
                      <span className="text-[9px] text-muted-foreground mt-0.5">
                        {e.botName || "Supervisor"}
                      </span>
                    </div>
                  </td>

                  {/* 3. 標題與事件詳情 */}
                  <td className="px-1.5 py-2.5 align-top">
                    <div className="flex flex-col">
                      <div className="flex items-center gap-1.5">
                        <span className="text-left text-[11px] font-semibold text-foreground group-hover:text-primary transition-colors">
                          {isFill ? `${e.symbol} · ${e.qty} @ $${e.price}` : e.title}
                        </span>
                        {isIntegratedPreview && (
                          <span className="text-[9px] text-muted-foreground font-mono opacity-60 group-hover:opacity-100">
                            [詳情 ↗]
                          </span>
                        )}
                      </div>
                      <p className={cn("text-[9.5px] text-muted-foreground leading-relaxed mt-0.5", !isExpanded && "line-clamp-1")}>
                        {e.detail}
                      </p>
                      {isExpanded && e.impact && <p className="mt-2 text-[10px] text-amber-400">影響：{e.impact}</p>}
                      {isExpanded && e.nextStep && <p className="mt-1 text-[10px] leading-relaxed text-foreground">下一步：{e.nextStep}</p>}
                    </div>
                  </td>

                  {/* 4. 盈虧或狀態 */}
                  <td className="py-2.5 pr-3 pl-1.5 text-right align-top">
                    {isFill ? (
                      e.pnl && e.pnl !== 0 ? (
                        <div className="flex flex-col items-end">
                          <span className={cn("text-[11px] font-bold leading-tight", toneOf(e.pnl))}>
                            {formatUsd(e.pnl, true)}
                          </span>
                          <span className="text-[8.5px] text-muted-foreground">已平倉結算</span>
                        </div>
                      ) : (
                        <span className="text-[9.5px] text-muted-foreground">開倉撮合</span>
                      )
                    ) : e.resolution === 'resolved' ? (
                      <span className="whitespace-nowrap text-[9px] text-muted-foreground">已解除 · 歷程</span>
                    ) : isOpen ? (
                      <span className="text-[9px] font-bold text-amber-400 bg-amber-400/10 px-1.5 py-0.5 rounded border border-amber-400/30 animate-pulse">
                        未解除
                      </span>
                    ) : isAlert ? (
                      <span className="text-[9px] font-bold text-amber-400 bg-amber-400/10 px-1.5 py-0.5 rounded border border-amber-400/30">
                        風控告警
                      </span>
                    ) : (
                      <span className="text-[9.5px] text-emerald-400">
                        正常登錄
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
