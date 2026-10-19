import { createFileRoute } from "@tanstack/react-router";
import { ArrowDownLeft, ArrowUpRight } from "lucide-react";
import { AppShell } from "@/components/catos/shell";
import { CardHeaderTitle } from "@/components/catos/card-header-title";
import { AccountEquityBand } from "@/components/catos/account-equity-band";
import { ActivityPanel } from "@/components/catos/activity-panel";
import { V0BotTable } from "@/components/catos/v0-bot-table";
import { AllocationDonutCard } from "@/components/catos/allocation-donut-card";
import { cryptoMarkets, type Fill } from "@/lib/mock/data";
import { recentFills } from "@/lib/mock/terminal";
import { fmtMoney, fmtSigned, nowStamp, useLiveFeed } from "@/hooks/use-live";
import { useI18n } from "@/lib/i18n";
import { PulseBeacon } from "@/components/catos/pulse-beacon";
import { cn } from "@/lib/utils";

import { IncidentTimelineCard } from "@/components/catos/incident-timeline-card";
import { MarketWatchCard } from "@/components/catos/market-watch-card";
import { StrategyIntentsRadarCard } from "@/components/catos/strategy-intents-radar-card";
import { UnifiedActivityDeckCard } from "@/components/catos/unified-activity-deck-card";

import { WorkspaceGrid } from "@/components/catos/workspace-grid";
import type { CardId } from "@/state/layoutStore";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Dashboard · catOS Quant Terminal" },
      { name: "description", content: "catOS 戰情總覽：即時權益、持倉明細、成交動態、資產配置與風控狀態。模擬交易終端。" },
      { property: "og:title", content: "Dashboard · catOS Quant Terminal" },
      { property: "og:description", content: "Crypto portfolio equity, drawdown, open positions, recent fills and risk posture in the catOS simulated quant terminal." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Dashboard,
});

function makeFill(): Fill {
  const market = cryptoMarkets[Math.floor(Math.random() * cryptoMarkets.length)] ?? cryptoMarkets[0];
  return {
    id: crypto.randomUUID(),
    time: nowStamp(),
    symbol: `${market.code}-USDT-SWAP`,
    side: Math.random() > 0.5 ? "BUY" : "SELL",
    qty: Number((Math.random() * 2 + 0.1).toFixed(2)),
    price: market.price,
    pnl: Number(((Math.random() - 0.3) * 800).toFixed(2)),
  };
}

function Dashboard() {
  const [fills] = useLiveFeed<Fill>(recentFills, makeFill, 6500, 5);
  const { t } = useI18n();

  // 卡片工廠函數：根據 cardId 動態渲染對應卡片
  const renderCard = (cardId: CardId) => {
    switch (cardId) {
      case "equity":
        return <AccountEquityBand className="h-full" />;

      case "positions":
        return <ActivityPanel className="h-full" />;

      case "bots":
        return <V0BotTable className="h-full" />;

      case "allocation":
        return <AllocationDonutCard className="h-full" />;

      case "incidents":
        return <IncidentTimelineCard className="h-full" />;

      case "market_watch":
        return <MarketWatchCard className="h-full" />;

      case "strategy_intents":
        return <StrategyIntentsRadarCard className="h-full" />;

      case "activity_deck":
        return <UnifiedActivityDeckCard className="h-full" />;

      case "fills":
        return (
          <div className="flex flex-col h-full w-full select-none overflow-hidden bg-surface/40">
            <div className="flex items-center justify-between px-3 py-2 bg-secondary/50 border-b border-border/80 shrink-0">
              <CardHeaderTitle
                cardId="fills"
                title={t("recent_fills")}
                subtext={
                  <span className="flex items-center gap-1.5 text-[9px] text-up font-mono ml-1">
                    <PulseBeacon size={4.5} />
                    {t("live")}
                  </span>
                }
              />
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto p-2.5">
              <ul className="-mt-1">
                {fills.map((f) => (
                  <li key={f.id} className="slide-in-row flex items-center gap-2 border-b border-border/60 py-1.5 last:border-0">
                    <span className={cn("grid size-5 shrink-0 place-items-center rounded", f.side === "BUY" ? "bg-up/10 text-up" : "bg-down/10 text-down")}>
                      {f.side === "BUY" ? <ArrowDownLeft className="size-2.5" /> : <ArrowUpRight className="size-2.5" />}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="num text-[10px] font-medium text-foreground leading-tight">{f.symbol} <span className={cn("text-[8.5px]", f.side === "BUY" ? "text-up" : "text-down")}>{f.side === "BUY" ? t("buy") : t("sell")}</span></p>
                      <p className="mt-0.5 num text-[8.5px] text-muted-foreground leading-tight">{f.qty} @ {fmtMoney(f.price, f.price < 1 ? 4 : 2)}</p>
                    </div>
                    <div className="ml-auto text-right">
                      <p className={cn("num text-[10px] font-medium leading-tight", f.pnl >= 0 ? "text-up" : "text-down")}>{fmtSigned(f.pnl)}</p>
                      <p className="mt-0.5 num text-[8.5px] text-muted-foreground leading-tight">{f.time}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <AppShell>
      {/* 定案方案 3：常態拖曳零按鈕工作台 (120 FPS 流暢分割線拉伸 · 雙擊中線還原 60:40) */}
      <WorkspaceGrid renderCard={renderCard} />
    </AppShell>
  );
}
