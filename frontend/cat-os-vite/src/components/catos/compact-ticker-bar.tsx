import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";

interface MarketQuote {
  code: string;
  name: string;
  symbol: string;
  price: string;
  change: string;
  isPositive: boolean;
}

const INITIAL_MARKETS: MarketQuote[] = [
  { code: "BTC", name: "BTC/USDT", symbol: "₿", price: "64,188.50", change: "+2.82%", isPositive: true },
  { code: "ETH", name: "ETH/USDT", symbol: "Ξ", price: "3,183.20", change: "+1.44%", isPositive: true },
  { code: "SOL", name: "SOL/USDT", symbol: "◎", price: "142.45", change: "-1.92%", isPositive: false },
  { code: "DOGE", name: "DOGE/USDT", symbol: "Ð", price: "0.1742", change: "+4.21%", isPositive: true },
];

export function CompactTickerBar() {
  const [markets, setMarkets] = useState<MarketQuote[]>(INITIAL_MARKETS);

  useEffect(() => {
    const timer = setInterval(() => {
      setMarkets((prev) =>
        prev.map((m) => {
          const rawNum = parseFloat(m.price.replace(/,/g, ""));
          const delta = (Math.random() - 0.49) * 0.0006;
          const next = rawNum * (1 + delta);
          const formatted =
            next < 1
              ? next.toFixed(4)
              : next.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
          return {
            ...m,
            price: formatted,
          };
        })
      );
    }, 3200);

    return () => clearInterval(timer);
  }, []);

  return (
    <div className="mb-4 grid h-[42px] grid-cols-1 overflow-hidden rounded-md border border-border bg-surface sm:grid-cols-2 xl:grid-cols-4">
      {markets.map((m) => (
        <div
          key={m.code}
          className="flex min-w-0 items-center justify-between border-r border-border px-4 py-2 last:border-r-0 hover:bg-secondary/40 transition-colors"
        >
          {/* Left badge & pair */}
          <div className="flex items-center gap-2.5">
            <span className="grid size-6 shrink-0 place-items-center rounded-full border border-border bg-background/50 num text-xs text-foreground">
              {m.symbol}
            </span>
            <div className="flex flex-col">
              <span className="text-[11px] font-medium text-foreground">
                {m.code}
                <span className="text-[10px] text-muted-foreground">/USDT</span>
              </span>
            </div>
          </div>

          {/* Right price & change */}
          <div className="text-right">
            <p className="num text-[11px] font-medium text-foreground leading-none">{m.price}</p>
            <p className={cn("num text-[9px] font-medium leading-none mt-1", m.isPositive ? "text-up" : "text-down")}>
              {m.change}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
