import { useState } from "react";
import { cn } from "@/lib/utils";
import { INITIAL_BOTS, equitySeries, summarize, formatPct, formatUsd, toneOf, type Bot } from "@/lib/v0-engine";
import { CardHeaderTitle } from "./card-header-title";

interface BotPosMeta {
  side: "long" | "short" | "idle";
  qtyText: string;
  notional: number;
  upnl: number;
  upnlPct: number;
  dd: number;
  p6Guard: number;
}

interface V0BotTableProps {
  className?: string;
  showHeader?: boolean;
}

export function V0BotTable({ className, showHeader = true }: V0BotTableProps) {
  const [bots, setBots] = useState<Bot[]>(INITIAL_BOTS);
  const [focusedBotId, setFocusedBotId] = useState<string | null>(null);

  const runningCount = bots.filter((b) => b.status === "running").length;

  const togglePause = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setBots((prev) =>
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
    switch (bot.id) {
      case "tabby":
        return {
          side: "long" as const,
          qtyText: "0.12 BTC",
          notional: 7457,
          upnl: 79.26,
          upnlPct: 1.06,
          dd: -1.24,
          p6Guard: -5.0,
        };
      case "calico":
        return {
          side: "long" as const,
          qtyText: "2.40 ETH",
          notional: 5880,
          upnl: 132.48,
          upnlPct: 2.3,
          dd: -2.15,
          p6Guard: -5.0,
        };
      case "mochi":
        return {
          side: "long" as const,
          qtyText: "18.0 SOL",
          notional: 2750,
          upnl: 52.5,
          upnlPct: 1.95,
          dd: -0.85,
          p6Guard: -4.0,
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
          p6Guard: -5.0,
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
            title="量化機器人 (Bots Matrix)"
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
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden">
        <table className="w-full text-left border-collapse table-auto">
          <thead className="border-b border-border/80 bg-background/40 text-[9.5px] font-mono text-muted-foreground sticky top-0 z-10 backdrop-blur-sm">
            <tr>
              <th className="py-2 pl-3 pr-1.5 font-medium">BOT / STRATEGY</th>
              <th className="px-1.5 font-medium">POSITION / NOTIONAL</th>
              <th className="px-1.5 text-right font-medium">UNREALIZED PnL</th>
              <th className="px-1.5 text-right font-medium hidden sm:table-cell">DAILY / 7D</th>
              <th className="px-1.5 font-medium hidden md:table-cell">DD / P6 GUARD</th>
              <th className="py-2 pr-3 pl-1.5 text-right font-medium">TREND & ACT</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40 text-xs">
            {bots.map((bot) => {
              const pos = getPosMeta(bot);
              const spark = getSparkline(bot);
              const isPaused = bot.status === "paused";

              return (
                <tr
                  key={bot.id}
                  className={cn(
                    "hover:bg-secondary/40 transition-colors group cursor-pointer",
                    focusedBotId === bot.id && "bg-secondary/50",
                    isPaused && "opacity-60 bg-background/20"
                  )}
                  onMouseEnter={() => setFocusedBotId(bot.id)}
                  onMouseLeave={() => setFocusedBotId(null)}
                >
                  {/* 1. 機器人與策略 (雙層) */}
                  <td className="py-2.5 pl-3 pr-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          "w-2 h-2 rounded-full shrink-0",
                          isPaused ? "bg-muted-foreground/50" : "bg-emerald-400 shadow-[0_0_6px_var(--emerald-400)]"
                        )}
                      />
                      <div className="flex flex-col">
                        <span className="text-[12px] font-bold text-foreground leading-tight">{bot.name}</span>
                        <div className="flex items-center gap-1 text-[9.5px] font-mono text-muted-foreground leading-tight">
                          <span className="text-primary font-semibold">{bot.symbol}</span>
                          <span>{bot.timeframe}</span>
                          <span>· {bot.strategyId}</span>
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* 2. 持倉規模與態勢 (TradingView 幾何箭頭風格 + 3x Cross) */}
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

                  {/* 3. 未實現損益 (雙層棧) */}
                  <td className="px-2 py-2.5 text-right font-mono">
                    <div className="flex flex-col items-end">
                      <span className={cn("text-[11px] font-bold leading-tight", toneOf(pos.upnl))}>
                        {formatUsd(pos.upnl, true)}
                      </span>
                      <span className={cn("text-[9.5px] leading-tight", toneOf(pos.upnl))}>
                        {formatPct(pos.upnlPct)}
                      </span>
                    </div>
                  </td>

                  {/* 4. 今日損益與週期報酬 (雙層棧) */}
                  <td className="px-1.5 py-2 text-right font-mono hidden sm:table-cell">
                    <div className="flex flex-col items-end">
                      <span className="text-[10.5px] font-bold text-foreground leading-tight">+2.45%</span>
                      <span className="text-[9px] text-emerald-400 leading-tight">+8.12% 7D</span>
                    </div>
                  </td>

                  {/* 5. 最大回撤 / P6 災難停損線 */}
                  <td className="px-1.5 py-2 font-mono hidden md:table-cell">
                    <div className="flex flex-col gap-0.5">
                      <span className="text-[9.5px] text-muted-foreground leading-tight">
                        DD: <span className="text-rose-400 font-semibold">{pos.dd.toFixed(2)}%</span>
                      </span>
                      <span className="text-[8.5px] text-amber-400/80 leading-tight">
                        P6: {pos.p6Guard.toFixed(1)}% OKX-SL
                      </span>
                    </div>
                  </td>

                  {/* 6. Sparkline 走勢微圖與暫停按鈕 */}
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
                      ) : (
                        <span className="w-16 text-center text-[9px] font-mono text-muted-foreground">—</span>
                      )}

                      <button
                        type="button"
                        onClick={(e) => togglePause(bot.id, e)}
                        className={cn(
                          "px-1.5 py-0.5 rounded text-[9.5px] font-mono font-medium border transition-colors cursor-pointer",
                          isPaused
                            ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
                            : "border-border/60 bg-background/60 text-muted-foreground hover:text-foreground hover:border-border"
                        )}
                        title={isPaused ? "恢復運行" : "暫停 Bot 策略"}
                      >
                        {isPaused ? "啟動" : "暫停"}
                      </button>
                    </div>
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
