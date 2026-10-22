import { useState, useMemo } from "react";
import {
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  ShieldAlert,
} from "lucide-react";
import { CardHeaderTitle } from "./card-header-title";
import { cn } from "@/lib/utils";

export type IncidentSeverity = "CRIT" | "WARN" | "INFO" | "OK";

export interface IncidentItem {
  id: string;
  time: string;
  severity: IncidentSeverity;
  title: string;
  reason: string;
  source: string;
  targetBotId?: string | null;
  logQuery?: string;
}

const DEFAULT_INCIDENTS: IncidentItem[] = [
  {
    id: "inc_01",
    time: "11:10:02",
    severity: "WARN",
    title: "ETH 震盪網格 Alpha 03 撮合滑價偏離",
    reason: "最近一筆買單成交價滑價達 0.08%，高於預設容忍值 0.05%。已記錄並維持運行，未觸發硬終止。",
    targetBotId: "bot_eth_grid_03",
    source: "RiskEngine",
    logQuery: "bot_eth_grid_03",
  },
  {
    id: "inc_02",
    time: "10:24:15",
    severity: "INFO",
    title: "外部 Agent 生成新研究草稿 v1.2-draft",
    reason: "Antigravity IDE 透過 MCP 提交候選草稿，已隔離儲存於策略中心，未影響在線運行之 v1.1 生產版本。",
    targetBotId: null,
    source: "MCP-Server",
    logQuery: "strat_atr_breakout",
  },
  {
    id: "inc_03",
    time: "09:30:10",
    severity: "INFO",
    title: "SOL 試驗波段 04 切換為手動維護停機",
    reason: "操作者於 15m 週期回測校準前手動發出暫停指令，現有持倉保持 FLAT 零部位。",
    targetBotId: "bot_sol_test_04",
    source: "Supervisor",
    logQuery: "bot_sol_test_04",
  },
  {
    id: "inc_04",
    time: "08:00:00",
    severity: "OK",
    title: "OKX P6 交易所端整倉災難停損更新完成",
    reason: "部位平均成本微幅改變，交易所端整倉停損單已重新錨定 (BTC @ 59,500, ETH @ 3,210)。保護狀態 ACTIVE。",
    targetBotId: null,
    source: "OKX-P6-Guard",
    logQuery: "disaster_stop_p6",
  },
  {
    id: "inc_05",
    time: "00:00:01",
    severity: "INFO",
    title: "每日日損防線分母切日歸位 (Asia/Taipei)",
    reason: "依 Asia/Taipei 00:00 基準，日初權益分母更新為 $40,272.50。Soft 10% / Hard 20% 防線重設就位。",
    targetBotId: null,
    source: "RiskGuardian",
    logQuery: "daily_drawdown_reset",
  },
];

interface IncidentTimelineCardProps {
  className?: string;
}

export function IncidentTimelineCard({ className }: IncidentTimelineCardProps) {
  const [incidents] = useState<IncidentItem[]>(DEFAULT_INCIDENTS);
  const [expandedId, setExpandedId] = useState<string | null>("inc_01"); // 預設展開最新的告警
  const [filterSeverity, setFilterSeverity] = useState<string>("ALL");

  const toggleIncident = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  const filteredIncidents = useMemo(() => {
    if (filterSeverity === "ALL") return incidents;
    if (filterSeverity === "ALERT") return incidents.filter((i) => i.severity === "WARN" || i.severity === "CRIT");
    return incidents.filter((i) => i.severity === filterSeverity);
  }, [incidents, filterSeverity]);

  const alertCount = useMemo(() => {
    return incidents.filter((i) => i.severity === "WARN" || i.severity === "CRIT").length;
  }, [incidents]);

  const getSeverityBadge = (severity: IncidentSeverity) => {
    switch (severity) {
      case "CRIT":
        return {
          label: "CRIT",
          badgeClass: "bg-rose-500/15 text-rose-300 border-rose-500/40",
          dotClass: "bg-rose-400 shadow-[0_0_8px_rgba(244,63,94,0.6)] ring-rose-400/30",
          icon: AlertCircle,
        };
      case "WARN":
        return {
          label: "WARN",
          badgeClass: "bg-amber-500/15 text-amber-300 border-amber-500/40",
          dotClass: "bg-amber-400 shadow-[0_0_8px_rgba(245,158,11,0.6)] ring-amber-400/30",
          icon: AlertTriangle,
        };
      case "OK":
        return {
          label: "OK",
          badgeClass: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
          dotClass: "bg-emerald-400 shadow-[0_0_6px_rgba(16,185,129,0.5)] ring-emerald-400/30",
          icon: CheckCircle2,
        };
      case "INFO":
      default:
        return {
          label: "INFO",
          badgeClass: "bg-sky-500/15 text-sky-300 border-sky-500/40",
          dotClass: "bg-sky-400 shadow-[0_0_6px_rgba(56,189,248,0.5)] ring-sky-400/30",
          icon: Info,
        };
    }
  };

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40", className)}>
      {/* 1. 卡片頂部 Header */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
        <div className="flex items-center gap-2">
          <CardHeaderTitle
            cardId="incidents"
            title="風險警報與異常事件"
            subtext=""
          />
          {alertCount > 0 && (
            <span className="flex items-center gap-1 text-[8.5px] font-mono px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse">
              <ShieldAlert className="size-2.5" />
              <span>{alertCount} 異常</span>
            </span>
          )}
        </div>

        {/* 篩選與完整日誌連結 */}
        <div className="flex items-center gap-2 shrink-0">
          <div className="flex items-center bg-background/60 border border-border/60 rounded p-0.5 gap-0.5">
            {[
              { id: "ALL", label: "全部" },
              { id: "ALERT", label: "告警" },
              { id: "INFO", label: "資訊" },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setFilterSeverity(tab.id)}
                className={cn(
                  "px-1.5 py-0.5 text-[9px] font-mono rounded transition-colors cursor-pointer",
                  filterSeverity === tab.id
                    ? "bg-secondary text-primary font-semibold border border-border shadow-xs"
                    : "text-muted-foreground hover:text-foreground border border-transparent"
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={() => alert("日誌系統運行正常：Supervisor & Worker IPC 日誌同步寫入 SQLite WAL。")}
            className="flex items-center gap-1 text-[10px] font-mono text-amber-400/90 hover:text-amber-300 transition-colors cursor-pointer"
          >
            <span>完整日誌</span>
            <span>&rarr;</span>
          </button>
        </div>
      </div>

      {/* 2. 垂直時間軸內容區 */}
      <div className="flex-1 min-h-0 overflow-y-auto p-3 pr-2 font-mono">
        {filteredIncidents.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-muted-foreground text-xs gap-1">
            <CheckCircle2 className="size-6 text-emerald-400/80 mb-1" />
            <span className="font-semibold text-foreground text-[11px]">無異常事件</span>
            <span className="text-[10px]">系統平穩運行中，所有風控指標正常</span>
          </div>
        ) : (
          <div className="relative pl-3 space-y-2.5 before:absolute before:left-[17px] before:top-2 before:bottom-2 before:w-[1px] before:bg-border/60">
            {filteredIncidents.map((inc) => {
              const isExp = expandedId === inc.id;
              const meta = getSeverityBadge(inc.severity);

              return (
                <div key={inc.id} className="relative flex items-start gap-2.5 group">
                  {/* 時間軸節點小圓點 */}
                  <div className="relative mt-1 shrink-0 z-10 flex items-center justify-center size-2.5 rounded-full ring-2 ring-background">
                    <div className={cn("size-2 rounded-full transition-all duration-200", meta.dotClass)} />
                  </div>

                  {/* 事件卡片本體 */}
                  <div
                    onClick={() => toggleIncident(inc.id)}
                    className={cn(
                      "flex-1 min-w-0 rounded-md border transition-all cursor-pointer p-2",
                      isExp
                        ? "bg-secondary/60 border-border/90 shadow-sm"
                        : "bg-background/40 hover:bg-secondary/40 border-border/40 hover:border-border/70"
                    )}
                  >
                    {/* 表頭：時間 + 等級 Badge + 標題 + 箭頭 */}
                    <div className="flex items-center justify-between gap-1.5 text-[10px]">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className="text-zinc-400 text-[9px] shrink-0 font-medium">{inc.time}</span>
                        <span className={cn("px-1 py-0.2 rounded text-[8px] font-bold border shrink-0", meta.badgeClass)}>
                          {meta.label}
                        </span>
                        <span className="font-semibold text-foreground text-[10.5px] truncate leading-tight">
                          {inc.title}
                        </span>
                      </div>

                      <button
                        type="button"
                        className="text-muted-foreground group-hover:text-foreground shrink-0 transition-transform duration-200 ml-1"
                        aria-label={isExp ? "收合" : "展開"}
                      >
                        {isExp ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
                      </button>
                    </div>

                    {/* 展開詳情面板 */}
                    {isExp && (
                      <div
                        onClick={(e) => e.stopPropagation()}
                        className="mt-2 pt-2 border-t border-border/50 text-[9.5px] space-y-1.5 text-zinc-300 animate-in fade-in-50 duration-150"
                      >
                        <p className="leading-relaxed text-foreground/90 font-normal">
                          {inc.reason}
                        </p>

                        <div className="flex items-center justify-between pt-1 border-t border-border/40 text-[8.5px] text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <span>來源:</span>
                            <code className="text-primary bg-primary/10 px-1 py-0.2 rounded font-mono">
                              {inc.source}
                            </code>
                          </span>

                          <div className="flex items-center gap-2">
                            {inc.targetBotId && (
                              <button
                                type="button"
                                onClick={() => alert(`跳轉至機器人詳情：${inc.targetBotId}`)}
                                className="text-amber-400 hover:text-amber-300 font-semibold flex items-center gap-0.5 cursor-pointer"
                              >
                                <span>查看 Bot</span>
                                <ExternalLink className="size-2.5" />
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={() => alert(`篩選日誌：target=${inc.logQuery}`)}
                              className="text-zinc-400 hover:text-foreground flex items-center gap-0.5 cursor-pointer"
                            >
                              <span>相關日誌</span>
                              <ExternalLink className="size-2.5" />
                            </button>
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
