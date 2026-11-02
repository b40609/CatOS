import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { INITIAL_BOTS, equitySeries, summarize, formatPct, toneOf, type Bot } from "@/lib/v0-engine";
import { CardHeaderTitle } from "./card-header-title";
import { BotMonitorTable, type BotMonitoringView } from "./bot-monitor-table";
import { useInspectorStore } from "@/state/inspectorStore";
import { useLiveMarketStore } from "@/state/liveMarketStore";
import { useBotLensStore } from "@/state/botLensStore";
import { NumberTicker } from "./motion/number-ticker";
import { useRouter } from "@/lib/router";
import { ArrowUpRight } from "lucide-react";

interface BotFleetMeta {
  strategyName: string;
  budgetUsageText: string;
  todayPnl: number;
  todayPnlPct: number;
  sevenDayRet: string;
  riskStatusText: string;
  riskStatusTone: "safe" | "warn" | "idle";
}

interface V0BotTableProps {
  className?: string;
  showHeader?: boolean;
  monitoring?: BotMonitoringView;
}

export function V0BotTable({ className, showHeader = true, monitoring }: V0BotTableProps) {
  const [localBots, setLocalBots] = useState<Bot[]>(INITIAL_BOTS);
  const [focusedBotId, setFocusedBotId] = useState<string | null>(null);
  const [flashBotId, setFlashBotId] = useState<Record<string, "up" | "down">>({});
  const [botFilter, setBotFilter] = useState<"all" | "running" | "paused">("all");

  const { selectedBotId, selectBot } = useInspectorStore();
  const { activeLens, setActiveLens } = useBotLensStore();
  const { navigate } = useRouter();

  // 即時市場撮合心跳 Store
  const { botsLive } = useLiveMarketStore();

  const bots = localBots;

  // 模擬 Tick 波動微光跳動
  useEffect(() => {
    if (monitoring) return;
    const timer = setInterval(() => {
      const targetIdx = Math.floor(Math.random() * INITIAL_BOTS.length);
      const isUp = Math.random() > 0.45;
      const targetBot = INITIAL_BOTS[targetIdx];
      if (!targetBot) return;

      setFlashBotId((prev) => ({ ...prev, [targetBot.id]: isUp ? "up" : "down" }));
      setTimeout(() => {
        setFlashBotId((prev) => {
          const next = { ...prev };
          delete next[targetBot.id];
          return next;
        });
      }, 700);
    }, 3200);
    return () => clearInterval(timer);
  }, [monitoring]);

  const runningCount = bots.filter((b) => b.status === "running").length;

  const togglePause = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setLocalBots((prev) =>
      prev.map((b) => (b.id === id ? { ...b, status: b.status === "running" ? "paused" : "running" } : b))
    );
  };

  // 生成 Sparkline SVG 迷你走勢線路徑
  const getSparkline = (bot: Bot) => {
    const series = equitySeries(bot);
    const sum = summarize(series, "7D", 32);
    const pts = sum.points.filter((v) => !Number.isNaN(v));
    if (pts.length < 2) return { path: "", isGain: true };
    const lo = Math.min(...pts);
    const hi = Math.max(...pts);
    const span = hi - lo || 1;
    const w = 56;
    const h = 16;
    const n = pts.length;
    let d = "";
    pts.forEach((pt, k) => {
      const x = (k / (n - 1)) * w;
      const y = 2 + ((hi - pt) / span) * (h - 4);
      d += `${k === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    });
    return { path: d, isGain: sum.ret >= 0 };
  };

  const getFleetMeta = (bot: Bot): BotFleetMeta => {
    const live = botsLive[bot.id];

    switch (bot.id) {
      case "tabby":
        return {
          strategyName: "突破唐奇安",
          budgetUsageText: `$${(live?.notional ?? 74535).toLocaleString()} (預算 35.6%)`,
          todayPnl: 1285.50 + ((live?.upnl ?? 759.36) - 759.36),
          todayPnlPct: 1.72,
          sevenDayRet: "+8.12%",
          riskStatusText: "正常 (槓桿 2.1x)",
          riskStatusTone: "safe",
        };
      case "calico":
        return {
          strategyName: "趨勢追蹤",
          budgetUsageText: `$${(live?.notional ?? 45515).toLocaleString()} (預算 21.7%)`,
          todayPnl: 1120.20 + ((live?.upnl ?? 695.25) - 695.25),
          todayPnlPct: 2.50,
          sevenDayRet: "+12.45%",
          riskStatusText: "正常 (槓桿 1.3x)",
          riskStatusTone: "safe",
        };
      case "mochi":
        return {
          strategyName: "自適應網格",
          budgetUsageText: `$${(live?.notional ?? 20574).toLocaleString()} (預算 9.8%)`,
          todayPnl: 845.00 + ((live?.upnl ?? 567.00) - 567.00),
          todayPnlPct: 4.16,
          sevenDayRet: "+6.30%",
          riskStatusText: "正常 (槓桿 0.6x)",
          riskStatusTone: "safe",
        };
      case "shiro":
      default:
        return {
          strategyName: "跨所統計套利",
          budgetUsageText: "無持倉 (待命)",
          todayPnl: 0,
          todayPnlPct: 0,
          sevenDayRet: "0.00%",
          riskStatusText: "待命 (無曝險)",
          riskStatusTone: "idle",
        };
    }
  };

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40", className)}>
      {/* 1. 一體化 Header */}
      {showHeader && (
        <div className="flex items-center justify-between px-3 h-9 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
          <CardHeaderTitle
            cardId="bots"
            title="策略實例監控矩陣"
          />

          <div className="flex items-center gap-0.5 bg-background/60 border border-border/60 rounded p-0.5 shrink-0 whitespace-nowrap flex-nowrap">
            {[
              { id: "all", label: `全部(${bots.length})` },
              { id: "running", label: `運作(${runningCount})` },
              { id: "paused", label: `暫停(${bots.length - runningCount})` },
            ].map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setBotFilter(f.id as any)}
                className={cn(
                  "px-2 py-0.5 text-[10.5px] font-mono rounded transition-colors cursor-pointer whitespace-nowrap shrink-0",
                  botFilter === f.id
                    ? "bg-secondary text-foreground font-semibold shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 2. 方案 A：策略資產管理視角 (零合約微觀冗餘 · 100% 職責分離) */}
      {monitoring ? (
        <BotMonitorTable {...monitoring} />
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto overflow-x-auto min-w-0 max-w-full">
          <table className="w-full text-left border-collapse table-auto min-w-[540px]">
            <thead className="border-b border-border/80 bg-background/40 text-[9.5px] font-mono text-muted-foreground sticky top-0 z-10 backdrop-blur-sm">
              <tr>
                <th className="py-2.5 pl-3 pr-2 font-medium">實例 / 標的</th>
                <th className="px-2 font-medium">策略模型 / 曝險</th>
                <th className="px-2 text-right font-medium">今日總損益</th>
                <th className="px-2 text-right font-medium hidden sm:table-cell">7日報酬率</th>
                <th className="px-2 font-medium hidden md:table-cell">風控狀態</th>
                <th className="py-2.5 pr-3 pl-2 text-right font-medium">走勢與操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40 text-xs">
              {bots
                .filter((b) => (botFilter === "all" ? true : b.status === botFilter))
                .map((bot) => {
                  const meta = getFleetMeta(bot);
                  const spark = getSparkline(bot);
                  const isPaused = bot.status === "paused";
                  const isSelected = selectedBotId === bot.id;

                  const isLensActive = activeLens === bot.id;
                  return (
                    <tr
                      key={bot.id}
                      onClick={() => {
                        selectBot(bot.id);
                        setActiveLens(activeLens === bot.id ? "ALL" : (bot.id as any));
                      }}
                      className={cn(
                        "hover:bg-secondary/30 transition-all group cursor-pointer",
                        focusedBotId === bot.id && "bg-secondary/40",
                        isLensActive && "bg-primary/[0.08] ring-1 ring-primary/40",
                        isSelected && !isLensActive && "bg-secondary/40",
                        isPaused && "opacity-60 bg-background/20",
                        flashBotId[bot.id] === "up" && "flash-up",
                        flashBotId[bot.id] === "down" && "flash-down"
                      )}
                      onMouseEnter={() => setFocusedBotId(bot.id)}
                      onMouseLeave={() => setFocusedBotId(null)}
                      title="點擊切換上方權益卡為此策略專屬視角"
                    >
                      {/* 1. 策略實例與合約標的 */}
                      <td className="py-2.5 pl-3 pr-2">
                        <div className="flex items-center gap-2">
                          <span
                            className={cn(
                              "w-2 h-2 rounded-full shrink-0",
                              isPaused ? "bg-muted-foreground/50" : "bg-emerald-400 shadow-[0_0_6px_var(--emerald-400)]"
                            )}
                          />
                          <div className="flex flex-col min-w-0">
                            <div className="flex items-center gap-1.5">
                              <span className="text-[12px] font-bold text-foreground leading-tight group-hover:text-primary transition-colors">
                                {bot.name}
                              </span>
                              {isLensActive && (
                                <span className="px-1 py-0.2 rounded text-[8px] font-mono font-bold bg-primary/20 text-primary border border-primary/30 shrink-0">
                                  聚焦中 ↑
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-1 text-[9.5px] font-mono text-muted-foreground leading-tight">
                              <span className="text-primary font-semibold">{bot.symbol}</span>
                              <span>{bot.timeframe}</span>
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* 2. 策略模型與曝險占比 */}
                      <td className="px-2 py-2.5">
                        <div className="flex flex-col gap-0.5">
                          <span className="text-[11.5px] font-semibold text-foreground leading-tight">
                            {meta.strategyName}
                          </span>
                          <span className="text-[9.5px] font-mono text-muted-foreground leading-tight">
                            {meta.budgetUsageText}
                          </span>
                        </div>
                      </td>

                      {/* 3. 今日總損益 (策略層級淨損益 · 醒目大字) */}
                      <td className="px-2 py-2.5 text-right font-mono">
                        <div className="flex flex-col items-end">
                          <NumberTicker
                            value={Math.abs(meta.todayPnl)}
                            prefix={meta.todayPnl >= 0 ? "+$" : "-$"}
                            decimals={2}
                            duration={400}
                            className={cn("text-[12.5px] font-bold leading-tight", toneOf(meta.todayPnl))}
                          />
                          <span className={cn("text-[9.5px] leading-tight font-semibold", toneOf(meta.todayPnl))}>
                            {formatPct(meta.todayPnlPct)}
                          </span>
                        </div>
                      </td>

                      {/* 4. 7日報酬率 */}
                      <td className="px-2 py-2.5 text-right font-mono hidden sm:table-cell">
                        <span className={cn("text-[11px] font-bold leading-tight", meta.sevenDayRet.startsWith("+") ? "text-emerald-400" : "text-muted-foreground")}>
                          {meta.sevenDayRet}
                        </span>
                      </td>

                      {/* 5. 策略級風控健康狀態 */}
                      <td className="px-2 py-2.5 font-mono hidden md:table-cell">
                        {meta.riskStatusTone === "safe" ? (
                          <div className="flex items-center gap-1.5 leading-tight">
                            <span className="px-1.5 py-0.2 rounded bg-emerald-400/10 text-emerald-400 border border-emerald-400/30 text-[9px] font-semibold">
                              {meta.riskStatusText}
                            </span>
                          </div>
                        ) : (
                          <span className="text-[10px] text-muted-foreground">{meta.riskStatusText}</span>
                        )}
                      </td>

                      {/* 6. Sparkline 走勢微圖與操作/詳情按鈕 */}
                      <td className="py-2.5 pr-3 pl-2 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {spark.path ? (
                            <svg width={56} height={16} className="overflow-visible shrink-0 hidden xl:block">
                              <path
                                d={spark.path}
                                fill="none"
                                stroke={spark.isGain ? "var(--primary)" : "#f43f5e"}
                                strokeWidth={1.5}
                                strokeLinecap="round"
                                strokeLinejoin="round"
                              />
                            </svg>
                          ) : null}
                          <button
                            type="button"
                            onClick={(e) => togglePause(bot.id, e)}
                            title="切換展示運作/暫停狀態"
                            className={cn(
                              "px-2 py-0.5 rounded text-[10px] font-mono border transition-all cursor-pointer",
                              isPaused
                                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
                                : "border-border/80 bg-background/60 text-muted-foreground hover:text-foreground hover:bg-secondary"
                            )}
                          >
                            {isPaused ? "重啟" : "暫停"}
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              selectBot(bot.id);
                              navigate("/bots");
                            }}
                            title="開啟策略專屬監控與五階段管線審計"
                            className="px-2 py-0.5 rounded text-[10px] font-mono border border-primary/40 bg-primary/10 text-primary hover:bg-primary hover:text-primary-foreground transition-all cursor-pointer flex items-center gap-0.5"
                          >
                            <span>詳情</span>
                            <ArrowUpRight className="size-2.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
