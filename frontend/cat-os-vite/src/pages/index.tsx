import { createFileRoute } from "@tanstack/react-router";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { ArrowDownLeft, ArrowUpRight } from "lucide-react";
import { AppShell } from "@/components/catos/shell";
import { CardHeaderTitle } from "@/components/catos/card-header-title";
import { AccountEquityBand } from "@/components/catos/account-equity-band";
import { ActivityPanel } from "@/components/catos/activity-panel";
import { ExposurePanel } from "@/components/catos/exposure-panel";
import { V0BotTable } from "@/components/catos/v0-bot-table";
import { allocation, cryptoMarkets, type Fill } from "@/lib/mock/data";
import { recentFills } from "@/lib/mock/terminal";
import { fmtMoney, fmtSigned, nowStamp, useLiveFeed } from "@/hooks/use-live";
import { useI18n } from "@/lib/i18n";
import { PulseBeacon } from "@/components/catos/pulse-beacon";
import { cn } from "@/lib/utils";

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

const allocationColors = ["var(--allocation-btc)", "var(--allocation-eth)", "var(--allocation-sol)", "var(--allocation-arb)", "var(--allocation-cash)"];
const allocationClasses = ["allocation-btc", "allocation-eth", "allocation-sol", "allocation-arb", "allocation-cash"];
const tooltipStyle = { background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 6, color: "var(--foreground)", fontSize: 11 };

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

const assetNames: Record<string, { zh: string; en: string }> = {
  BTC: { zh: "BTC-USDT-SWAP", en: "BTC SWAP" },
  ETH: { zh: "ETH-USDT-SWAP", en: "ETH SWAP" },
  SOL: { zh: "SOL-USDT-SWAP", en: "SOL SWAP" },
  Arbitrage: { zh: "跨期對沖保證金", en: "Arbitrage Margin" },
  Cash: { zh: "USDT 閒置保證金", en: "USDT Margin Reserve" },
};

function Dashboard() {
  const [fills] = useLiveFeed<Fill>(recentFills, makeFill, 6500, 5);
  const { t, language } = useI18n();

  // 卡片工廠函數：根據 cardId 動態渲染對應卡片
  const renderCard = (cardId: CardId) => {
    switch (cardId) {
      case "equity":
        return <AccountEquityBand className="h-full" />;

      case "positions":
        return <ActivityPanel className="h-full" />;

      case "exposure":
        return <ExposurePanel className="h-full" />;

      case "bots":
        return <V0BotTable className="h-full" />;

      case "allocation":
        return (
          <div className="flex flex-col h-full w-full select-none overflow-hidden bg-surface/40">
            <div className="flex items-center justify-between px-3 py-2 bg-secondary/50 border-b border-border/80 shrink-0">
              <CardHeaderTitle
                cardId="allocation"
                title="合約曝險與保證金 (Exposure Donut)"
                subtext={<span className="text-[10px] text-muted-foreground font-mono ml-1">5 合約標的</span>}
              />
              <span className="text-[10px] font-mono text-muted-foreground/80 px-1.5 py-0.5 rounded bg-background/60 border border-border/60">
                總權益 10,240 USDT
              </span>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto p-2.5 flex flex-col">
              <div className="relative h-[130px] shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={allocation} dataKey="value" nameKey="name" innerRadius={42} outerRadius={56} paddingAngle={3} stroke="var(--surface)" cornerRadius={2} isAnimationActive={false}>
                      {allocation.map((a, i) => (
                        <Cell key={a.name} fill={allocationColors[i]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => `${v}%`} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-[8.5px] text-muted-foreground">總風控權益</span>
                  <span className="mt-0.5 num text-sm font-semibold">10,240</span>
                  <span className="text-[8.5px] text-muted-foreground">USDT</span>
                </div>
              </div>
              <ul className="mt-1 space-y-1.5">
                {allocation.map((a, i) => (
                  <li key={a.name} className="flex items-center gap-2 text-[10.5px]">
                    <span className={cn("size-1.5 rounded-full", allocationClasses[i])} />
                    <span className="text-muted-foreground font-mono">
                      {assetNames[a.name]?.[language === "zh-TW" ? "zh" : "en"] ?? a.name}
                    </span>
                    <span className="ml-auto num">{a.value.toFixed(1)}<span className="text-muted-foreground">%</span></span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        );

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
                    {t("live")} · KOL Tag
                  </span>
                }
              />
              <span className="text-[10px] font-mono text-primary bg-primary/10 px-1.5 py-0.5 rounded border border-primary/20">
                Tag: 41cb53c5
              </span>
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
                      <p className="mt-0.5 num text-[8.5px] text-muted-foreground leading-tight">{f.qty} @ {fmtMoney(f.price, f.price < 1 ? 4 : 2)} · <span className="text-primary font-mono">Tag: 41cb53c5</span></p>
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
