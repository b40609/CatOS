import { useState } from "react";
import { cn } from "@/lib/utils";
import { CardHeaderTitle } from "./card-header-title";

export interface PositionLeg {
  id: string;
  botId: string;
  botName: string;
  side: "long" | "short";
  notional: number;
  isPaused?: boolean;
}

export interface SymbolExposure {
  symbol: string;
  base: string;
  chg: number;
  mark: number;
  legs: PositionLeg[];
  long: number;
  short: number;
  net: number;
}

interface ExposurePanelProps {
  className?: string;
  showHeader?: boolean;
  equity?: number;
  concentrationLimitPct?: number;
}

const DEFAULT_SYMBOLS: SymbolExposure[] = [
  {
    symbol: "BTC-USDT-SWAP",
    base: "BTC",
    chg: 1.42,
    mark: 62140.5,
    legs: [
      { id: "l1", botId: "tabby", botName: "Tabby", side: "long", notional: 7456.86, isPaused: false },
      { id: "l2", botId: "shiro", botName: "Shiro", side: "long", notional: 3107.03, isPaused: true },
    ],
    long: 10563.89,
    short: 0,
    net: 10563.89,
  },
  {
    symbol: "ETH-USDT-SWAP",
    base: "ETH",
    chg: -0.85,
    mark: 2450.2,
    legs: [
      { id: "l3", botId: "calico", botName: "Calico", side: "long", notional: 5880.48, isPaused: false },
      { id: "l4", botId: "shiro", botName: "Shiro", side: "short", notional: 3185.26, isPaused: true },
    ],
    long: 5880.48,
    short: 3185.26,
    net: 2695.22,
  },
  {
    symbol: "SOL-USDT-SWAP",
    base: "SOL",
    chg: 3.1,
    mark: 152.8,
    legs: [
      { id: "l5", botId: "mochi", botName: "Mochi", side: "long", notional: 2750.4, isPaused: false },
    ],
    long: 2750.4,
    short: 0,
    net: 2750.4,
  },
];

const SCALE_PCT = 50; // 尺規單向最大 50% (對齊 catOS 單幣曝險預算上限 50%)

export function ExposurePanel({
  className,
  showHeader = true,
  equity = 40272.5,
  concentrationLimitPct = 50,
}: ExposurePanelProps) {
  const [symbols] = useState<SymbolExposure[]>(DEFAULT_SYMBOLS);
  const [focusedBotId, setFocusedBotId] = useState<string | null>(null);

  const totalGross = symbols.reduce((acc, s) => acc + s.long + s.short, 0);
  const totalNet = symbols.reduce((acc, s) => acc + s.net, 0);
  const totalLong = symbols.reduce((acc, s) => acc + s.long, 0);
  const totalShort = symbols.reduce((acc, s) => acc + s.short, 0);
  const grossLeverage = (totalGross / equity).toFixed(2);
  const netLeverage = (Math.abs(totalNet) / equity).toFixed(2);
  const availableMargin = Math.max(0, equity - totalGross * 0.12);

  const getPct = (usd: number) => (usd / equity) * 100;

  const getSegmentWidth = (notional: number) => {
    const p = getPct(notional);
    const clamped = Math.min(p, SCALE_PCT);
    return `${((clamped / SCALE_PCT) * 100).toFixed(1)}%`;
  };

  const getPointerLeft = (netPct: number) => {
    const clamped = Math.max(-SCALE_PCT, Math.min(SCALE_PCT, netPct));
    return `${(50 + (clamped / SCALE_PCT) * 50).toFixed(1)}%`;
  };

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40", className)}>
      {/* 1. Header 列：一體化單層 Header */}
      {showHeader && (
        <div className="flex items-center justify-between px-3 py-2 bg-secondary/50 border-b border-border/80 shrink-0">
          <CardHeaderTitle
            cardId="exposure"
            title="多空曝險配置 (Exposure)"
            subtext={
              <span className="text-[10px] font-mono text-muted-foreground ml-1">
                總 {Math.round(totalGross).toLocaleString("en-US")} USDT · {grossLeverage}x 槓桿
              </span>
            }
          />

          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-amber-400/90 bg-amber-400/10 px-1.5 py-0.5 rounded border border-amber-400/20">
              單幣上限 ±{concentrationLimitPct}%
            </span>
          </div>
        </div>
      )}

      {/* 2. 標尺與多空條主體 */}
      <div className="flex-1 min-h-0 flex flex-col p-2.5 overflow-y-auto">
        {/* 標尺表頭刻度 */}
        <div className="flex items-center text-[9.5px] font-mono text-muted-foreground/80 pb-1.5 border-b border-border/50 shrink-0">
          <span className="w-16 shrink-0">標的 / 漲跌</span>
          <div className="flex-1 flex justify-between px-1.5 text-[9px]">
            <span className="text-rose-400/80">← 空頭</span>
            <span className="text-muted-foreground">0 基準 (±{SCALE_PCT}% 權益)</span>
            <span className="text-emerald-400/80">多頭 →</span>
          </div>
          <span className="w-20 shrink-0 text-right">淨額 · 佔比</span>
        </div>

        {/* 標的列表 */}
        <div className="flex-1 flex flex-col justify-around py-1 gap-2 min-h-0">
          {symbols.map((s) => {
            const netPct = getPct(s.net);
            const isOverLimit = Math.abs(netPct) > concentrationLimitPct;

            return (
              <div key={s.symbol} className="flex items-center gap-2 group">
                {/* 1. 標的代號與 24h 漲跌 */}
                <div className="w-20 shrink-0 flex flex-col">
                  <span className="text-[11px] font-mono font-semibold text-foreground leading-tight">
                    {s.base}
                  </span>
                  <span
                    className={cn(
                      "text-[9.5px] font-mono leading-tight",
                      s.chg >= 0 ? "text-emerald-400" : "text-rose-400"
                    )}
                  >
                    {s.chg >= 0 ? "+" : ""}
                    {s.chg.toFixed(2)}%
                  </span>
                </div>

                {/* 2. 雙向長條尺規 */}
                <div className="flex-1 h-6 bg-background/80 rounded border border-border/60 relative flex overflow-hidden">
                  {/* 空頭區 (向左) */}
                  <div className="w-1/2 h-full flex justify-end overflow-hidden pr-[1px]">
                    {s.legs
                      .filter((l) => l.side === "short")
                      .map((leg) => (
                        <div
                          key={leg.id}
                          style={{ width: getSegmentWidth(leg.notional) }}
                          className={cn(
                            "h-full bg-rose-500/35 border-r border-rose-400/60 flex items-center justify-end px-1 transition-all cursor-pointer",
                            leg.isPaused && "opacity-45 bg-rose-900/30",
                            focusedBotId === leg.botId && "bg-rose-500/60 ring-1 ring-rose-400"
                          )}
                          onMouseEnter={() => setFocusedBotId(leg.botId)}
                          onMouseLeave={() => setFocusedBotId(null)}
                          title={`${leg.botName} · 空頭 ${Math.round(leg.notional).toLocaleString()} USDT`}
                        >
                          <span className="text-[8.5px] font-mono text-rose-200/90 truncate">
                            {leg.botName}
                          </span>
                        </div>
                      ))}
                  </div>

                  {/* 多頭區 (向右) */}
                  <div className="w-1/2 h-full flex justify-start overflow-hidden pl-[1px]">
                    {s.legs
                      .filter((l) => l.side === "long")
                      .map((leg) => (
                        <div
                          key={leg.id}
                          style={{ width: getSegmentWidth(leg.notional) }}
                          className={cn(
                            "h-full bg-emerald-500/35 border-l border-emerald-400/60 flex items-center justify-start px-1 transition-all cursor-pointer",
                            leg.isPaused && "opacity-45 bg-emerald-900/30",
                            focusedBotId === leg.botId && "bg-emerald-500/60 ring-1 ring-emerald-400"
                          )}
                          onMouseEnter={() => setFocusedBotId(leg.botId)}
                          onMouseLeave={() => setFocusedBotId(null)}
                          title={`${leg.botName} · 多頭 ${Math.round(leg.notional).toLocaleString()} USDT`}
                        >
                          <span className="text-[8.5px] font-mono text-emerald-200/90 truncate">
                            {leg.botName}
                          </span>
                        </div>
                      ))}
                  </div>

                  {/* 中央 0 基準線 */}
                  <div className="absolute left-1/2 top-0 bottom-0 w-[1px] bg-border/90 z-10 pointer-events-none" />

                  {/* ±集中度上限警戒線 (紅虛線) */}
                  <div
                    style={{ left: `${50 - (concentrationLimitPct / SCALE_PCT) * 50}%` }}
                    className="absolute top-0 bottom-0 w-[1px] border-l border-dashed border-rose-400/70 z-10 pointer-events-none"
                    title="空頭集中度上限"
                  />
                  <div
                    style={{ left: `${50 + (concentrationLimitPct / SCALE_PCT) * 50}%` }}
                    className="absolute top-0 bottom-0 w-[1px] border-r border-dashed border-rose-400/70 z-10 pointer-events-none"
                    title="多頭集中度上限"
                  />

                  {/* 淨曝險三角指針 */}
                  {s.legs.length > 0 && (
                    <div
                      style={{ left: getPointerLeft(netPct) }}
                      className="absolute top-0 -translate-x-1/2 z-20 pointer-events-none"
                      title={`淨曝險 ${netPct.toFixed(1)}%`}
                    >
                      <div className="w-0 h-0 border-l-[3.5px] border-l-transparent border-r-[3.5px] border-r-transparent border-t-[5px] border-t-primary" />
                    </div>
                  )}
                </div>

                {/* 3. 淨額與佔比數值 */}
                <div className="w-24 shrink-0 flex flex-col items-end font-mono">
                  <span
                    className={cn(
                      "text-[11px] font-semibold leading-tight",
                      s.net >= 0 ? "text-emerald-400" : "text-rose-400"
                    )}
                  >
                    {s.net >= 0 ? "+" : ""}
                    {Math.round(s.net).toLocaleString("en-US")}
                  </span>
                  <span
                    className={cn(
                      "text-[9.5px] leading-tight",
                      isOverLimit ? "text-rose-400 font-bold" : "text-muted-foreground"
                    )}
                  >
                    {netPct >= 0 ? "+" : ""}
                    {netPct.toFixed(1)}%
                    {isOverLimit && " ⚠"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* 3. 底部風控與保證金匯總條 */}
        <div className="mt-auto pt-2.5 border-t border-border/60 grid grid-cols-4 gap-2 text-[10px] font-mono text-muted-foreground/80 shrink-0">
          <div className="flex flex-col">
            <span className="text-[9px]">多頭總額</span>
            <span className="text-emerald-400 font-semibold font-mono">
              ${Math.round(totalLong).toLocaleString()}
            </span>
          </div>

          <div className="flex flex-col">
            <span className="text-[9px]">空頭總額</span>
            <span className="text-rose-400 font-semibold font-mono">
              ${Math.round(totalShort).toLocaleString()}
            </span>
          </div>

          <div className="flex flex-col">
            <span className="text-[9px]">淨槓桿比率</span>
            <span className="text-foreground font-semibold font-mono">
              {netLeverage}x <span className="text-muted-foreground font-normal">/ 3.0x</span>
            </span>
          </div>

          <div className="flex flex-col items-end">
            <span className="text-[9px]">可用保證金</span>
            <span className="text-primary font-semibold font-mono">
              ${Math.round(availableMargin).toLocaleString()}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
