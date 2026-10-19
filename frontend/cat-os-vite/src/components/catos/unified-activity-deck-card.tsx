import { useState, useMemo } from "react";
import {
  ShieldAlert,
  Zap,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Database,
} from "lucide-react";
import { CardHeaderTitle } from "./card-header-title";
import { UNIFIED_EVENTS, type EventCategory } from "@/lib/mock/unified-events";
import { formatUsd, toneOf } from "@/lib/v0-engine";
import { cn } from "@/lib/utils";

interface UnifiedActivityDeckCardProps {
  className?: string;
  showHeader?: boolean;
}

export function UnifiedActivityDeckCard({
  className,
  showHeader = true,
}: UnifiedActivityDeckCardProps) {
  const [category, setCategory] = useState<EventCategory>("ALL");
  const [expandedId, setExpandedId] = useState<string | null>("evt_01");

  const filteredEvents = useMemo(() => {
    if (category === "ALL") return UNIFIED_EVENTS;
    return UNIFIED_EVENTS.filter((e) => e.category === category);
  }, [category]);

  const stats = useMemo(() => {
    const fills = UNIFIED_EVENTS.filter((e) => e.category === "FILL").length;
    const alerts = UNIFIED_EVENTS.filter((e) => e.category === "ALERT").length;
    const system = UNIFIED_EVENTS.filter((e) => e.category === "SYSTEM").length;
    return { fills, alerts, system, total: UNIFIED_EVENTS.length };
  }, []);

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40", className)}>
      {/* 1. 一體化 Header 與快速過濾列 */}
      {showHeader && (
        <div className="flex items-center justify-between px-3 py-2 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
          <div className="flex items-center gap-2">
            <CardHeaderTitle
              cardId="activity_deck"
              title="全域戰情日誌 (Activity Deck)"
              subtext={
                <div className="flex items-center gap-1.5 ml-1">
                  <span className="text-[10px] font-mono text-muted-foreground">
                    共 {stats.total} 筆事件
                  </span>
                  {stats.alerts > 0 && (
                    <span className="inline-flex items-center gap-1 text-[9px] font-mono text-amber-400 bg-amber-400/10 px-1.5 py-0.2 rounded border border-amber-400/25 animate-pulse">
                      <ShieldAlert className="size-2.5" />
                      {stats.alerts} 異常告警
                    </span>
                  )}
                </div>
              }
            />
          </div>

          {/* 4 大類別篩選標籤 */}
          <div className="flex items-center gap-1 bg-background/60 border border-border/60 rounded p-0.5">
            {[
              { id: "ALL", label: `全部 (${stats.total})` },
              { id: "FILL", label: `成交流 (${stats.fills})` },
              { id: "ALERT", label: `風控警報 (${stats.alerts})` },
              { id: "SYSTEM", label: `系統事件 (${stats.system})` },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setCategory(tab.id as EventCategory)}
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

              return (
                <tr
                  key={e.id}
                  onClick={() => setExpandedId(isExpanded ? null : e.id)}
                  className={cn(
                    "hover:bg-secondary/40 transition-colors cursor-pointer group",
                    isExpanded && "bg-secondary/50",
                    isAlert && "bg-amber-500/[0.04]"
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

                  {/* 3. 標題與事件詳情 (可展開) */}
                  <td className="px-1.5 py-2.5 align-top">
                    <div className="flex flex-col">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[11px] font-semibold text-foreground group-hover:text-primary transition-colors">
                          {isFill ? `${e.symbol} · ${e.qty} @ $${e.price}` : e.title}
                        </span>
                        {isExpanded ? (
                          <ChevronUp className="size-3 text-muted-foreground" />
                        ) : (
                          <ChevronDown className="size-3 text-muted-foreground opacity-60 group-hover:opacity-100" />
                        )}
                      </div>
                      <p className={cn("text-[9.5px] text-muted-foreground leading-relaxed mt-0.5", !isExpanded && "line-clamp-1")}>
                        {e.detail}
                      </p>
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

      {/* 3. 底部狀態條 */}
      <div className="px-3 py-1 bg-secondary/70 border-t border-border/80 flex items-center justify-between text-[9px] font-mono text-muted-foreground shrink-0">
        <div className="flex items-center gap-1.5 truncate">
          <Database className="size-3 text-primary shrink-0" />
          <span className="truncate">
            全域戰情日誌：成交流水 + 風控警報 + 系統生命週期 · 同步持久化 SQLite (WAL)
          </span>
        </div>
        <span className="text-foreground font-semibold shrink-0 hidden sm:inline">
          9 筆事件就緒
        </span>
      </div>
    </div>
  );
}
