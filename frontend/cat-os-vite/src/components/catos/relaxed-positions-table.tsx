import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { ArrowUpRight } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export interface PositionItem {
  code: string;
  symbol: string;
  venue: string;
  side: "LONG" | "SHORT";
  size: string;
  entry: string;
  mark: string;
  pnl: string;
  pnlPct: string;
  isProfit: boolean;
}

const DEFAULT_POSITIONS: PositionItem[] = [
  {
    code: "BTC",
    symbol: "BTC-PERP",
    venue: "OKX",
    side: "LONG",
    size: "0.12",
    entry: "61,480.00",
    mark: "62,140.50",
    pnl: "+79.26",
    pnlPct: "+1.06%",
    isProfit: true,
  },
  {
    code: "ETH",
    symbol: "ETH-PERP",
    venue: "OKX",
    side: "LONG",
    size: "2.40",
    entry: "3,320.00",
    mark: "3,375.20",
    pnl: "+132.48",
    pnlPct: "+1.66%",
    isProfit: true,
  },
  {
    code: "SOL",
    symbol: "SOL-PERP",
    venue: "Binance",
    side: "SHORT",
    size: "15.00",
    entry: "152.40",
    mark: "148.90",
    pnl: "+52.50",
    pnlPct: "+2.30%",
    isProfit: true,
  },
  {
    code: "DOGE",
    symbol: "DOGE-PERP",
    venue: "OKX",
    side: "LONG",
    size: "8,000",
    entry: "0.1680",
    mark: "0.1740",
    pnl: "+48.00",
    pnlPct: "+3.57%",
    isProfit: true,
  },
];

function getCoinIcon(code: string): string {
  if (code.includes("BTC")) return "₿";
  if (code.includes("ETH")) return "Ξ";
  if (code.includes("SOL")) return "◎";
  return "Ð";
}

export function RelaxedPositionsTable({ className }: { className?: string } = {}) {
  const [filter, setFilter] = useState<"All" | "Long" | "Short">("All");
  const { t, language } = useI18n();

  const filteredPositions = DEFAULT_POSITIONS.filter((p) => {
    if (filter === "All") return true;
    return p.side === filter.toUpperCase();
  });

  const filterTabs: { id: "All" | "Long" | "Short"; label: string }[] = [
    { id: "All", label: t("filter_all") },
    { id: "Long", label: t("filter_long") },
    { id: "Short", label: t("filter_short") },
  ];

  return (
    <section className={cn("panel min-w-0 flex flex-col overflow-hidden", className)}>
      {/* Header bar with counter badge and filter tabs */}
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-xs font-medium text-foreground">{t("open_positions")}</h2>
          <span className="grid size-4 place-items-center rounded bg-secondary num text-[9px] text-muted-foreground font-medium">
            {DEFAULT_POSITIONS.length}
          </span>
        </div>

        <div className="flex items-center gap-1">
          {filterTabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setFilter(tab.id)}
              className={cn(
                "h-6 rounded px-2.5 text-[10px] transition-colors",
                filter === tab.id
                  ? "bg-secondary text-foreground font-medium"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </header>

      {/* Laser-aligned positions table */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[620px] text-left border-collapse">
          <thead className="border-b border-border bg-background/25 text-[9px] text-muted-foreground">
            <tr>
              <th className="py-2.5 pl-4 font-normal text-left">{t("th_symbol")}</th>
              <th className="px-3 font-normal text-left">{t("th_side")}</th>
              <th className="px-3 text-right font-normal">{t("th_size")}</th>
              <th className="px-3 text-right font-normal">{t("th_entry")}</th>
              <th className="px-3 text-right font-normal">{t("th_mark")}</th>
              <th className="px-4 text-right font-normal">{t("th_pnl")}</th>
            </tr>
          </thead>
          <tbody>
            {filteredPositions.map((pos) => (
              <tr
                key={pos.symbol + pos.venue}
                className="border-b border-border/60 last:border-0 hover:bg-secondary/30 transition-colors"
              >
                {/* Symbol with coin badge & venue */}
                <td className="py-3 pl-4 pr-3">
                  <div className="flex items-center gap-2.5">
                    <span className="grid size-6 shrink-0 place-items-center rounded-full border border-border bg-secondary num text-xs text-foreground font-mono">
                      {getCoinIcon(pos.code)}
                    </span>
                    <div>
                      <p className="num text-[11px] font-medium text-foreground leading-none">{pos.symbol}</p>
                      <p className="mt-1 text-[9px] text-muted-foreground leading-none">
                        {pos.venue} · {t("perpetual")}
                      </p>
                    </div>
                  </div>
                </td>

                {/* 9px TradingView Posture Side Pill */}
                <td className="px-3">
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 rounded-[3px] border px-1.5 py-0.5 num text-[9px] font-medium tracking-tight",
                      pos.side === "LONG"
                        ? "border-up/20 bg-up/10 text-up"
                        : "border-down/20 bg-down/10 text-down"
                    )}
                  >
                    {pos.side === "LONG"
                      ? (language === "zh-TW" ? "▲ 做多" : "▲ LONG")
                      : (language === "zh-TW" ? "▼ 做空" : "▼ SHORT")}
                  </span>
                </td>

                {/* Size (Right aligned) */}
                <td className="px-3 text-right num text-[11px] text-foreground">
                  {pos.size}
                  <span className="ml-1 text-[9px] text-muted-foreground">{pos.code}</span>
                </td>

                {/* Entry Price (Right aligned) */}
                <td className="px-3 text-right num text-[11px] text-foreground">
                  {pos.entry}
                </td>

                {/* Mark Price (Right aligned) */}
                <td className="px-3 text-right num text-[11px] text-foreground">
                  {pos.mark}
                </td>

                {/* Unrealized PnL (Double-Stack Right Aligned) */}
                <td className="px-4 text-right num text-[11px]">
                  <div className="flex flex-col items-end">
                    <span className={cn("font-medium", pos.isProfit ? "text-up" : "text-down")}>
                      {pos.pnl}
                    </span>
                    <span className={cn("text-[9px] mt-0.5", pos.isProfit ? "text-up" : "text-down")}>
                      {pos.pnlPct}
                    </span>
                  </div>
                </td>
              </tr>
            ))}

            {filteredPositions.length === 0 && (
              <tr>
                <td colSpan={6} className="py-8 text-center text-xs text-muted-foreground">
                  {language === "zh-TW" ? `無符合 ${filterTabs.find(t => t.id === filter)?.label} 條件之持倉` : `No positions matching ${filter}`}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Card footer summary & manage link */}
      <footer className="flex items-center justify-between border-t border-border px-4 py-3 text-[10px] text-muted-foreground">
        <span>{filteredPositions.length} {t("positions_summary")}</span>
        <Link
          to="/bots"
          className="flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors"
        >
          <span>{t("manage_bots")}</span>
          <ArrowUpRight className="size-3" />
        </Link>
      </footer>
    </section>
  );
}
