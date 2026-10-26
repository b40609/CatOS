import { useState, useEffect, useMemo } from "react";
import {
  Timer,
  Clock,
  TrendingUp,
  TrendingDown,
  Flame,
} from "lucide-react";
import { CardHeaderTitle } from "./card-header-title";
import { useLiveMarketStore } from "@/state/liveMarketStore";
import { NumberTicker } from "./motion/number-ticker";
import { cn } from "@/lib/utils";

export type BarTimeframe = "15m" | "1H" | "4H";

interface MarketItem {
  symbol: string;
  code: string;
  price: number;
  change24h: number;
  high24h: number;
  low24h: number;
  funding: number;
  fundingTimeLeft: string;
  spreadBps: number;
  volUsd: string;
  tickDirection: "up" | "down" | "flat";
  openInterest: string;
}

const INITIAL_MARKETS: MarketItem[] = [
  {
    symbol: "BTC-USDT-SWAP",
    code: "BTC",
    price: 62140.5,
    change24h: 1.42,
    high24h: 62850.0,
    low24h: 61120.0,
    funding: 0.0102,
    fundingTimeLeft: "03:39:15",
    spreadBps: 0.8,
    volUsd: "$12.8B",
    tickDirection: "up",
    openInterest: "$4.12B",
  },
  {
    symbol: "ETH-USDT-SWAP",
    code: "ETH",
    price: 3375.2,
    change24h: 1.66,
    high24h: 3440.0,
    low24h: 3280.0,
    funding: 0.0084,
    fundingTimeLeft: "03:39:15",
    spreadBps: 0.3,
    volUsd: "$5.4B",
    tickDirection: "up",
    openInterest: "$1.89B",
  },
  {
    symbol: "SOL-USDT-SWAP",
    code: "SOL",
    price: 152.8,
    change24h: 3.10,
    high24h: 156.5,
    low24h: 146.2,
    funding: -0.0031,
    fundingTimeLeft: "03:39:15",
    spreadBps: 1.4,
    volUsd: "$1.9B",
    tickDirection: "down",
    openInterest: "$640M",
  },
  {
    symbol: "DOGE-USDT-SWAP",
    code: "DOGE",
    price: 0.1742,
    change24h: 4.21,
    high24h: 0.181,
    low24h: 0.165,
    funding: 0.0148,
    fundingTimeLeft: "03:39:15",
    spreadBps: 5.7,
    volUsd: "$812M",
    tickDirection: "up",
    openInterest: "$210M",
  },
];

interface MarketWatchCardProps {
  className?: string;
}

export function MarketWatchCard({ className }: MarketWatchCardProps) {
  const { quotes } = useLiveMarketStore();
  const [timeframe, setTimeframe] = useState<BarTimeframe>("15m");
  const [selectedSymbol, setSelectedSymbol] = useState<string>("BTC-USDT-SWAP");
  const [markets] = useState<MarketItem[]>(INITIAL_MARKETS);
  const [now, setNow] = useState<Date>(new Date());

  // 1. 每秒更新時鐘與計算 K 線倒數
  useEffect(() => {
    const timer = setInterval(() => {
      setNow(new Date());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // 計算 K 線倒數 (Closed Bar Countdown)
  const barCountdown = useMemo(() => {
    const minutes = now.getMinutes();
    const seconds = now.getSeconds();

    let totalSec = 15 * 60;
    let elapsedSec = 0;

    if (timeframe === "15m") {
      totalSec = 15 * 60;
      elapsedSec = (minutes % 15) * 60 + seconds;
    } else if (timeframe === "1H") {
      totalSec = 60 * 60;
      elapsedSec = minutes * 60 + seconds;
    } else if (timeframe === "4H") {
      totalSec = 4 * 3600;
      elapsedSec = (now.getHours() % 4) * 3600 + minutes * 60 + seconds;
    }

    const remainingSec = Math.max(0, totalSec - elapsedSec);
    const m = Math.floor(remainingSec / 60);
    const s = remainingSec % 60;
    const progressPct = ((totalSec - remainingSec) / totalSec) * 100;
    const isClosingSoon = remainingSec <= 45; // 收盤前 45 秒預警

    // 次根開盤時間
    const nextBarDate = new Date(now.getTime() + remainingSec * 1000);
    const nextBarText = `${String(nextBarDate.getHours()).padStart(2, "0")}:${String(
      nextBarDate.getMinutes()
    ).padStart(2, "0")}:00`;

    return {
      text: `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`,
      progressPct: Math.min(100, Math.max(0, progressPct)),
      isClosingSoon,
      remainingSec,
      nextBarText,
    };
  }, [now, timeframe]);

  // 計算 8H 資金費率結算倒數 (00:00, 08:00, 16:00 UTC)
  const fundingCountdown = useMemo(() => {
    const utcHours = now.getUTCHours();
    const nextFundingUtcHour = (Math.floor(utcHours / 8) + 1) * 8;
    const targetDate = new Date(now);
    targetDate.setUTCHours(nextFundingUtcHour, 0, 0, 0);

    const diffMs = targetDate.getTime() - now.getTime();
    const diffSec = Math.max(0, Math.floor(diffMs / 1000));
    const h = Math.floor(diffSec / 3600);
    const m = Math.floor((diffSec % 3600) / 60);
    const s = diffSec % 60;

    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }, [now]);

  const activeMarket = markets.find((m) => m.symbol === selectedSymbol) || markets[0];
  const activeQuote = quotes[activeMarket.code];
  const activeFunding = activeQuote?.funding ?? activeMarket.funding;

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40", className)}>
      {/* 1. Header 標題列 (Zero-Waste 統一規格) */}
      <div className="flex items-center justify-between px-3 h-9 bg-secondary/50 border-b border-border/80 shrink-0">
        <CardHeaderTitle
          cardId="market_watch"
          title="標的行情與資金費率"
        />

        {/* 週期切換膠囊 (15m / 1H / 4H) - 統一微膠囊風格 */}
        <div className="flex items-center gap-0.5 bg-background/60 border border-border/60 rounded p-0.5 shrink-0">
          {(["15m", "1H", "4H"] as BarTimeframe[]).map((tf) => (
            <button
              key={tf}
              type="button"
              onClick={() => setTimeframe(tf)}
              className={cn(
                "px-2 py-0.5 text-[10.5px] font-mono rounded transition-colors cursor-pointer",
                timeframe === tf
                  ? "bg-secondary text-foreground font-semibold shadow-xs"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* 2. Closed Bar 收盤倒數 HUD 監控台 */}
      <div className="px-3 py-2.5 bg-surface-raised/40 border-b border-border/70 flex flex-col gap-2 shrink-0">
        <div className="flex items-center justify-between">
          {/* 左側：倒數核心計時器 */}
          <div className="flex items-center gap-2.5">
            <div
              className={cn(
                "grid size-8 place-items-center rounded-lg border transition-all",
                barCountdown.isClosingSoon
                  ? "bg-amber-500/20 border-amber-500/60 text-amber-400 animate-pulse shadow-[0_0_12px_rgba(245,158,11,0.3)]"
                  : "bg-surface border-border/80 text-primary"
              )}
            >
              {barCountdown.isClosingSoon ? (
                <Flame className="size-4 animate-bounce" />
              ) : (
                <Timer className="size-4" />
              )}
            </div>

            <div className="flex flex-col">
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] font-mono text-muted-foreground uppercase">
                  {timeframe} K 線收盤倒數
                </span>
                {barCountdown.isClosingSoon ? (
                  <span className="text-[9px] font-mono font-semibold text-amber-400 bg-amber-500/15 px-1 rounded border border-amber-500/30">
                    ⚡ 結算就緒
                  </span>
                ) : (
                  <span className="text-[9px] font-mono text-muted-foreground/80">
                    盤中運算中
                  </span>
                )}
              </div>
              <div className="flex items-baseline gap-2">
                <span
                  className={cn(
                    "text-xl font-mono font-bold tracking-tight",
                    barCountdown.isClosingSoon ? "text-amber-400" : "text-foreground"
                  )}
                >
                  {barCountdown.text}
                </span>
                <span className="text-[10px] font-mono text-muted-foreground">
                  次根開盤: <span className="text-primary font-semibold">{barCountdown.nextBarText}</span>
                </span>
              </div>
            </div>
          </div>

          {/* 右側：8H 資金費率結算倒數 */}
          <div className="flex flex-col items-end text-right">
            <div className="flex items-center gap-1 text-[9.5px] font-mono text-muted-foreground">
              <Clock className="size-2.5 text-primary/80" />
              <span>OKX 資金費率結算</span>
            </div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-sm font-mono font-bold text-foreground">
                {fundingCountdown}
              </span>
              <span
                className={cn(
                  "text-[10px] font-mono font-semibold px-1 py-0.2 rounded",
                  activeFunding >= 0
                    ? "text-emerald-400 bg-emerald-400/10"
                    : "text-rose-400 bg-rose-400/10"
                )}
              >
                {activeFunding >= 0 ? "+" : ""}
                {(activeFunding * 100).toFixed(4)}%
              </span>
            </div>
          </div>
        </div>

        {/* 倒數進度條 (收盤前 45 秒切換為琥珀金色呼吸波) */}
        <div className="w-full bg-background/80 h-1.5 rounded-full overflow-hidden border border-border/60">
          <div
            className={cn(
              "h-full transition-all duration-1000 ease-linear rounded-full",
              barCountdown.isClosingSoon
                ? "bg-gradient-to-r from-amber-500 via-primary to-emerald-400 animate-pulse shadow-[0_0_8px_rgba(245,158,11,0.5)]"
                : "bg-gradient-to-r from-primary/40 to-primary"
            )}
            style={{ width: `${barCountdown.progressPct}%` }}
          />
        </div>
      </div>

      {/* 3. 高密度 OKX SWAP 報價清單 */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        <table className="w-full border-collapse text-left font-mono text-[11px]">
          <thead className="sticky top-0 z-10 bg-surface border-b border-border/80 text-[10px] text-muted-foreground">
            <tr>
              <th className="py-1.5 px-3 font-medium">合約標的</th>
              <th className="py-1.5 px-2 font-medium text-right">最新價 (USDT)</th>
              <th className="py-1.5 px-2 font-medium text-right">24H 漲跌</th>
              <th className="py-1.5 px-2 font-medium text-right hidden sm:table-cell">盤口點差</th>
              <th className="py-1.5 px-2 font-medium text-right hidden md:table-cell">8H 費率</th>
              <th className="py-1.5 px-3 font-medium text-right">24H 成交額</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50">
            {markets.map((m) => {
              const isSelected = selectedSymbol === m.symbol;
              const quote = quotes[m.code];
              const currentPrice = quote?.price ?? m.price;
              const currentChg = quote?.change24h ?? m.change24h;
              const isPositive = currentChg >= 0;
              const tickDir = quote?.lastDir ?? m.tickDirection;

              return (
                <tr
                  key={m.symbol}
                  onClick={() => setSelectedSymbol(m.symbol)}
                  className={cn(
                    "cursor-pointer transition-colors group hover:bg-secondary/40",
                    isSelected ? "bg-primary/[0.07]" : ""
                  )}
                >
                  {/* 合約名稱 */}
                  <td className="py-2 px-3">
                    <div className="flex items-center gap-1.5">
                      <div
                        className={cn(
                          "size-1.5 rounded-full",
                          isSelected ? "bg-primary" : "bg-muted-foreground/50 group-hover:bg-primary/70"
                        )}
                      />
                      <span className="font-semibold text-foreground tracking-tight">
                        {m.code}
                      </span>
                      <span className="text-[9px] text-muted-foreground">
                        SWAP
                      </span>
                    </div>
                  </td>

                  {/* 最新價與微跳動指示 (NumberTicker) */}
                  <td className="py-2 px-2 text-right">
                    <NumberTicker
                      value={currentPrice}
                      decimals={m.code === "DOGE" ? 4 : 2}
                      prefix="$"
                      duration={400}
                      className={cn(
                        "font-semibold",
                        tickDir === "up" && "text-emerald-400",
                        tickDir === "down" && "text-rose-400"
                      )}
                    />
                  </td>

                  {/* 24h 漲跌幅 */}
                  <td className="py-2 px-2 text-right">
                    <span
                      className={cn(
                        "inline-flex items-center justify-end gap-0.5 px-1.5 py-0.2 rounded font-medium text-[10.5px]",
                        isPositive ? "text-emerald-400 bg-emerald-400/10" : "text-rose-400 bg-rose-400/10"
                      )}
                    >
                      {isPositive ? <TrendingUp className="size-2.5" /> : <TrendingDown className="size-2.5" />}
                      <NumberTicker
                        value={Math.abs(currentChg)}
                        prefix={isPositive ? "+" : "-"}
                        suffix="%"
                        decimals={2}
                        duration={400}
                        flashOnChange={false}
                      />
                    </span>
                  </td>

                  {/* 盤口點差 */}
                  <td className="py-2 px-2 text-right text-muted-foreground text-[10px] hidden sm:table-cell">
                    <span className="text-foreground/90 font-mono">{m.spreadBps}</span> bps
                  </td>

                  {/* 8H 資金費率 */}
                  <td className="py-2 px-2 text-right text-[10px] hidden md:table-cell">
                    <span
                      className={cn(
                        m.funding >= 0 ? "text-emerald-400/90" : "text-rose-400/90"
                      )}
                    >
                      {m.funding >= 0 ? "+" : ""}
                      {(m.funding * 100).toFixed(4)}%
                    </span>
                  </td>

                  {/* 24H 成交量 */}
                  <td className="py-2 px-3 text-right text-muted-foreground text-[10.5px]">
                    {m.volUsd}
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
