import { useState, useEffect, useMemo } from "react";
import {
  Timer,
  Clock,
  TrendingUp,
  TrendingDown,
  Flame,
  X,
} from "lucide-react";
import { useLiveMarketStore } from "@/state/liveMarketStore";
import {
  useHeaderWidgetStore,
  POPULAR_SWAP_SYMBOLS,
  type BarTimeframe,
} from "@/state/microWidgetStore";
import { NumberTicker } from "./motion/number-ticker";
import { cn } from "@/lib/utils";

export function TopMarketTicker() {
  const { quotes, botsLive } = useLiveMarketStore();
  const {
    klineClockMounted,
    klineTimeframe,
    setKlineTimeframe,
    fundingClockMounted,
    marketTapeMounted,
    dismissSymbolFromBar,
    getActiveSymbols,
  } = useHeaderWidgetStore();

  const [now, setNow] = useState<Date>(new Date());

  // 1. 每秒更新時鐘
  useEffect(() => {
    const timer = setInterval(() => {
      setNow(new Date());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // 2. Closed Bar 收盤倒數運算
  const barCountdown = useMemo(() => {
    const minutes = now.getMinutes();
    const seconds = now.getSeconds();

    let totalSec = 15 * 60;
    let elapsedSec = 0;

    if (klineTimeframe === "15m") {
      totalSec = 15 * 60;
      elapsedSec = (minutes % 15) * 60 + seconds;
    } else if (klineTimeframe === "1H") {
      totalSec = 60 * 60;
      elapsedSec = minutes * 60 + seconds;
    } else if (klineTimeframe === "4H") {
      totalSec = 4 * 3600;
      elapsedSec = (now.getHours() % 4) * 3600 + minutes * 60 + seconds;
    }

    const remainingSec = Math.max(0, totalSec - elapsedSec);
    const m = Math.floor(remainingSec / 60);
    const s = remainingSec % 60;
    const progressPct = ((totalSec - remainingSec) / totalSec) * 100;
    const isClosingSoon = remainingSec <= 45;

    const nextBarDate = new Date(now.getTime() + remainingSec * 1000);
    const nextBarText = `${String(nextBarDate.getHours()).padStart(2, "0")}:${String(
      nextBarDate.getMinutes()
    ).padStart(2, "0")}:00`;

    return {
      text: `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`,
      progressPct: Math.min(100, Math.max(0, progressPct)),
      isClosingSoon,
      nextBarText,
    };
  }, [now, klineTimeframe]);

  // 3. OKX 8H 資金費結算倒數 (00:00, 08:00, 16:00 UTC)
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

  // 4. 動態標的清單 (跟隨活躍 Bot 策略或使用者自選標的池)
  const activeBotSymbols = useMemo(() => {
    const list: string[] = [];
    if (botsLive) {
      for (const bot of Object.values(botsLive)) {
        if (bot.qty > 0 || bot.symbol) {
          const code = bot.symbol.replace(/[-_]?(USDT|SWAP)?$/i, "");
          if (code && !list.includes(code)) list.push(code);
        }
      }
    }
    return list.length > 0 ? list : ["BTC", "ETH", "SOL"];
  }, [botsLive]);

  const activeSymbols = useMemo(() => {
    return getActiveSymbols(activeBotSymbols);
  }, [getActiveSymbols, activeBotSymbols]);

  // 若頂部所有組件皆未掛載，徹底留白不佔任何像素
  if (!klineClockMounted && !fundingClockMounted && (!marketTapeMounted || activeSymbols.length === 0)) {
    return null;
  }

  return (
    <div className="flex items-center gap-1.5 select-none font-mono">
      {/* 1. Closed Bar 收盤決策倒數組件 */}
      {klineClockMounted && (
        <div
          className={cn(
            "group relative flex items-center gap-1.5 h-7 px-2 rounded-md border text-[11px] transition-all bg-surface/80 shadow-2xs",
            barCountdown.isClosingSoon
              ? "border-amber-500/50 bg-amber-500/10 text-amber-400 shadow-[0_0_10px_rgba(245,158,11,0.2)] animate-pulse"
              : "border-border/70 text-foreground"
          )}
          title={`次根 K 線開盤: ${barCountdown.nextBarText} (點擊切換週期，可在模組工坊配置)`}
        >
          {barCountdown.isClosingSoon ? (
            <Flame className="size-3 text-amber-400 animate-bounce" />
          ) : (
            <Timer className="size-3 text-primary" />
          )}

          {/* 週期微切換 */}
          <div className="flex items-center gap-0.5 mr-0.5">
            {(["15m", "1H"] as BarTimeframe[]).map((tf) => (
              <button
                key={tf}
                type="button"
                onClick={() => setKlineTimeframe(tf)}
                className={cn(
                  "px-1 py-0.2 rounded text-[9.5px] cursor-pointer transition-colors",
                  klineTimeframe === tf
                    ? "bg-secondary text-primary font-bold"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {tf}
              </button>
            ))}
          </div>

          <span
            className={cn(
              "font-bold tracking-tight text-[11.5px]",
              barCountdown.isClosingSoon ? "text-amber-400 font-extrabold" : "text-foreground"
            )}
          >
            {barCountdown.text}
          </span>

          {/* 微型收盤進度條 (28px 寬) */}
          <div className="w-7 h-1 rounded-full bg-background/80 overflow-hidden border border-border/50 hidden sm:block">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-1000 ease-linear",
                barCountdown.isClosingSoon ? "bg-amber-400" : "bg-primary"
              )}
              style={{ width: `${barCountdown.progressPct}%` }}
            />
          </div>
        </div>
      )}

      {/* 2. 8H 資金費結算時鐘組件 */}
      {fundingClockMounted && (
        <div
          className="flex items-center gap-1.5 h-7 px-2 rounded-md border border-border/70 bg-surface/60 text-[10.5px] text-muted-foreground shadow-2xs"
          title="OKX 永續合約 8H 資金費率結算倒數 (00:00 / 08:00 / 16:00 UTC)"
        >
          <Clock className="size-2.5 text-primary/80" />
          <span className="text-[9.5px] hidden sm:inline">8H 費率結算</span>
          <span className="text-foreground font-semibold">{fundingCountdown}</span>
        </div>
      )}

      {/* 3. 動態標的行情總線 (自動跟隨策略或自選標的池，非硬編碼單幣) */}
      {marketTapeMounted &&
        activeSymbols.map((code) => {
          const liveQuote = quotes[code];
          const popular = POPULAR_SWAP_SYMBOLS.find((s) => s.code === code);
          const price = liveQuote?.price ?? popular?.defaultPrice ?? 10.0;
          const chg = liveQuote?.change24h ?? popular?.defaultChange ?? 0.0;
          const isUp = chg >= 0;
          const dir = liveQuote?.lastDir ?? (isUp ? "up" : "down");
          const decimals = price < 1 ? 4 : price < 10 ? 3 : 2;

          return (
            <div
              key={code}
              className="group relative flex items-center gap-1.5 h-7 px-2 rounded-md border border-border/60 bg-surface-raised/40 hover:bg-secondary/40 transition-colors text-[10.5px]"
              title={`${code}-USDT-SWAP 實時標記價 (懸停點擊 × 可快速隱藏，可至模組工坊管理標的池)`}
            >
              <span className="font-bold text-foreground text-[10.5px]">{code}</span>
              <NumberTicker
                value={price}
                decimals={decimals}
                prefix="$"
                duration={300}
                className={cn(
                  "font-semibold",
                  dir === "up" && "text-emerald-400",
                  dir === "down" && "text-rose-400"
                )}
              />
              <span
                className={cn(
                  "inline-flex items-center gap-0.5 text-[9.5px] font-semibold px-1 py-0.1 rounded",
                  isUp ? "text-emerald-400 bg-emerald-400/10" : "text-rose-400 bg-rose-400/10"
                )}
              >
                {isUp ? <TrendingUp className="size-2.5" /> : <TrendingDown className="size-2.5" />}
                {isUp ? "+" : ""}{chg.toFixed(1)}%
              </span>

              {/* 懸停快速隱藏此標的 */}
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  dismissSymbolFromBar(code);
                }}
                className="opacity-0 group-hover:opacity-100 size-3.5 -mr-0.5 rounded grid place-items-center text-muted-foreground/80 hover:text-rose-400 hover:bg-rose-400/10 transition-all cursor-pointer"
                title={`從頂部總線隱藏 ${code} (可在模組工坊隨時重新加入)`}
              >
                <X className="size-2.5" />
              </button>
            </div>
          );
        })}
    </div>
  );
}
