import { useState, useEffect, Fragment } from "react";
import { cn } from "@/lib/utils";
import { INITIAL_BOTS, equitySeries, summarize, formatPct, toneOf, type Bot } from "@/lib/v0-engine";
import { CardHeaderTitle } from "./card-header-title";
import { BotMonitorTable, type BotMonitoringView } from "./bot-monitor-table";
import { useInspectorStore } from "@/state/inspectorStore";
import { InlineBotRow } from "./inspector/inline-bot-row";
import { useLiveMarketStore } from "@/state/liveMarketStore";
import { NumberTicker } from "./motion/number-ticker";
import { ChevronRight } from "lucide-react";

interface BotPosMeta {
  side: "long" | "short" | "idle";
  qtyText: string;
  notional: number;
  upnl: number;
  upnlPct: number;
  dd: number;
  p6StopPrice: string;
  p6DistPct: string;
  p6Status: "ACTIVE" | "STANDBY" | "ALERT" | "UPDATING";
  p6Rounding: string;
  p6BudgetPct: number;
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

  // 定案 B：行內展開 Accordion 狀態綁定
  const {
    selectedBotId,
    selectBot,
    expandedInlineBotIds,
    toggleInlineExpand,
  } = useInspectorStore();

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
    const w = 64;
    const h = 18;
    const n = pts.length;
    let d = "";
    pts.forEach((pt, k) => {
      const x = (k / (n - 1)) * w;
      const y = 2 + ((hi - pt) / span) * (h - 4);
      d += `${k === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    });
    return { path: d, isGain: sum.ret >= 0 };
  };

  const getPosMeta = (bot: Bot): BotPosMeta => {
    const live = botsLive[bot.id];

    switch (bot.id) {
      case "tabby":
        return {
          side: "long" as const,
          qtyText: "0.85 BTC",
          notional: live?.notional ?? 52820,
          upnl: live?.upnl ?? 561.43,
          upnlPct: live?.upnlPct ?? 1.07,
          dd: -1.24,
          p6StopPrice: "$59,500.00",
          p6DistPct: live?.p6DistPct ?? "-4.25%",
          p6Status: "ACTIVE",
          p6Rounding: "CEIL 向上取整",
          p6BudgetPct: 15,
        };
      case "calico":
        return {
          side: "long" as const,
          qtyText: "9.50 ETH",
          notional: live?.notional ?? 32060,
          upnl: live?.upnl ?? 524.40,
          upnlPct: live?.upnlPct ?? 1.66,
          dd: -2.15,
          p6StopPrice: "$3,210.00",
          p6DistPct: live?.p6DistPct ?? "-4.89%",
          p6Status: "ACTIVE",
          p6Rounding: "CEIL 向上取整",
          p6BudgetPct: 15,
        };
      case "mochi":
        return {
          side: "long" as const,
          qtyText: "95.0 SOL",
          notional: live?.notional ?? 14516,
          upnl: live?.upnl ?? 437.00,
          upnlPct: live?.upnlPct ?? 3.10,
          dd: -0.85,
          p6StopPrice: "$142.00",
          p6DistPct: live?.p6DistPct ?? "-7.07%",
          p6Status: "ACTIVE",
          p6Rounding: "CEIL 向上取整",
          p6BudgetPct: 15,
        };
      case "shiro":
      default:
        return {
          side: "idle" as const,
          qtyText: "0.00",
          notional: 0,
          upnl: 0,
          upnlPct: 0,
          dd: -3.42,
          p6StopPrice: "—",
          p6DistPct: "無持倉",
          p6Status: "STANDBY",
          p6Rounding: "待命",
          p6BudgetPct: 0,
        };
    }
  };

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40", className)}>
      {/* 1. 一體化 Header */}
      {showHeader && (
        <div className="flex items-center justify-between px-3 py-2 bg-secondary/50 border-b border-border/80 shrink-0">
          <CardHeaderTitle
            cardId="bots"
            title="策略機器人矩陣"
            subtext={
              <span className="text-[10px] font-mono text-muted-foreground ml-1">
                {runningCount} 運作 · {bots.length - runningCount} 暫停
              </span>
            }
          />

          <div className="flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground/80">
            <span className="px-1.5 py-0.5 rounded bg-background/60 border border-border/60">
              1 Bot : 1 SWAP 獨佔
            </span>
          </div>
        </div>
      )}

      {/* 2. 雙層高階版 (Dual-Layer) 矩陣表格 */}
      {monitoring ? <BotMonitorTable {...monitoring} /> : <div className="flex-1 min-h-0 overflow-y-auto overflow-x-auto min-w-0 max-w-full">
        <table className="w-full text-left border-collapse table-auto min-w-[520px]">
          <thead className="border-b border-border/80 bg-background/40 text-[9.5px] font-mono text-muted-foreground sticky top-0 z-10 backdrop-blur-sm">
            <tr>
              <th className="py-2 pl-3 pr-1.5 font-medium">BOT / STRATEGY</th>
              <th className="px-1.5 font-medium">POSITION / NOTIONAL</th>
              <th className="px-1.5 text-right font-medium">UNREALIZED PnL</th>
              <th className="px-1.5 text-right font-medium hidden sm:table-cell">DAILY / 7D</th>
              <th className="px-1.5 font-medium hidden md:table-cell">MAX DD / 停損錨定</th>
              <th className="py-2 pr-3 pl-1.5 text-right font-medium">TREND & ACT</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40 text-xs">
            {bots.map((bot) => {
              const pos = getPosMeta(bot);
              const spark = getSparkline(bot);
              const isPaused = bot.status === "paused";
              const isSelected = selectedBotId === bot.id;
              const isInlineExpanded = expandedInlineBotIds.includes(bot.id);

              return (
                <Fragment key={bot.id}>
                  <tr
                    onClick={() => {
                      selectBot(bot.id);
                      toggleInlineExpand(bot.id);
                    }}
                    className={cn(
                      "hover:bg-secondary/40 transition-all group cursor-pointer",
                      focusedBotId === bot.id && "bg-secondary/50",
                      isSelected && "bg-primary/10 border-l-2 border-primary shadow-[inset_2px_0_0_var(--color-primary)]",
                      isPaused && "opacity-60 bg-background/20",
                      flashBotId[bot.id] === "up" && "flash-up",
                      flashBotId[bot.id] === "down" && "flash-down"
                    )}
                    onMouseEnter={() => setFocusedBotId(bot.id)}
                    onMouseLeave={() => setFocusedBotId(null)}
                  >
                    {/* 1. 機器人與策略 */}
                    <td className="py-2.5 pl-3 pr-2">
                      <div className="flex items-center gap-2">
                        {/* 展開/收合箭頭指示 */}
                        <div
                          className="size-4 -ml-1 rounded flex items-center justify-center text-muted-foreground group-hover:text-primary transition-colors shrink-0"
                          title={isInlineExpanded ? "點擊收合詳情" : "點擊展開策略執行鏈與防線"}
                        >
                          <ChevronRight className={cn("size-3 transition-transform duration-200", isInlineExpanded && "rotate-90 text-primary")} />
                        </div>
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
                            {isInlineExpanded && (
                              <span className="text-[9px] text-primary font-mono font-bold">
                                [已展開]
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-1 text-[9.5px] font-mono text-muted-foreground leading-tight">
                            <span className="text-primary font-semibold">{bot.symbol}</span>
                            <span>{bot.timeframe}</span>
                            <span>· {bot.strategyId}</span>
                          </div>
                        </div>
                      </div>
                    </td>

                    {/* 2. 持倉規模與態勢 */}
                    <td className="px-2 py-2.5">
                      <div className="flex flex-col gap-0.5">
                        <div className="flex items-center gap-1.5">
                          <span
                            className={cn(
                              "inline-flex items-center gap-1 rounded-[3px] border px-1.5 py-0.2 num text-[9px] font-mono font-bold tracking-tight",
                              pos.side === "long"
                                ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-400"
                                : pos.side === "short"
                                ? "border-rose-400/30 bg-rose-400/10 text-rose-400"
                                : "border-border bg-background/50 text-muted-foreground"
                            )}
                          >
                            {pos.side === "long" ? "▲ LONG" : pos.side === "short" ? "▼ SHORT" : "○ FLAT"}
                          </span>
                          <span className="font-mono text-[11px] font-bold text-foreground">{pos.qtyText}</span>
                        </div>
                        <span className="text-[9.5px] font-mono text-muted-foreground">
                          {pos.notional > 0 ? `$${pos.notional.toLocaleString()} · 3x Cross` : "無部位"}
                        </span>
                      </div>
                    </td>

                    {/* 3. 未實現損益 (雙層棧 + 動態 NumberTicker 滾動) */}
                    <td className="px-2 py-2.5 text-right font-mono">
                      <div className="flex flex-col items-end">
                        <NumberTicker
                          value={Math.abs(pos.upnl)}
                          prefix={pos.upnl >= 0 ? "+$" : "-$"}
                          decimals={2}
                          duration={400}
                          className={cn("text-[11px] font-bold leading-tight", toneOf(pos.upnl))}
                        />
                        <span className={cn("text-[9.5px] leading-tight", toneOf(pos.upnl))}>
                          {formatPct(pos.upnlPct)}
                        </span>
                      </div>
                    </td>

                    {/* 4. 今日損益與週期報酬 */}
                    <td className="px-1.5 py-2 text-right font-mono hidden sm:table-cell">
                      <div className="flex flex-col items-end">
                        <span className="text-[10.5px] font-bold text-foreground leading-tight">+2.45%</span>
                        <span className="text-[9px] text-emerald-400 leading-tight">+8.12% 7D</span>
                      </div>
                    </td>

                    {/* 5. 最大回撤與停損錨定 */}
                    <td className="px-1.5 py-2 font-mono hidden md:table-cell">
                      <div className="flex flex-col gap-0.5">
                        <div className="flex items-center gap-1">
                          <span className="text-[9.5px] text-muted-foreground leading-tight">
                            DD: <span className="text-rose-400 font-semibold">{pos.dd.toFixed(2)}%</span>
                          </span>
                        </div>
                        <div className="flex items-center gap-1 text-[8.5px] text-muted-foreground leading-tight">
                          <span className="text-primary font-semibold">
                            停損: {pos.p6StopPrice}
                          </span>
                          {pos.p6Status === "ACTIVE" && (
                            <span className="text-emerald-400">({pos.p6DistPct})</span>
                          )}
                          {pos.p6Status === "UPDATING" && (
                            <span className="text-amber-400 font-semibold">(待確認)</span>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* 6. Sparkline 走勢微圖與暫停/重啟按鈕 */}
                    <td className="py-2.5 pr-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {spark.path ? (
                          <svg width={64} height={18} className="overflow-visible shrink-0">
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
                          className={cn(
                            "px-2 py-0.5 rounded text-[10px] font-mono border transition-all cursor-pointer flex items-center gap-1",
                            isPaused
                              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
                              : "border-border/80 bg-background/60 text-muted-foreground hover:text-foreground hover:bg-secondary"
                          )}
                        >
                          <span>{isPaused ? "重啟" : "暫停"}</span>
                        </button>
                      </div>
                    </td>
                  </tr>

                  {/* 方案 B：行內展開 Accordion 巢狀列 (定案固化) */}
                  {isInlineExpanded && (
                    <InlineBotRow
                      botId={bot.id}
                      colSpan={6}
                      onCollapse={() => toggleInlineExpand(bot.id)}
                    />
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>}
    </div>
  );
}
