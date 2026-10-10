import { createFileRoute } from "@tanstack/react-router";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { ArrowDownLeft, ArrowUpRight } from "lucide-react";
import { AppShell, Panel } from "@/components/catos/shell";
import { UnifiedKpiStrip } from "@/components/catos/unified-kpi-strip";
import { RelaxedPositionsTable } from "@/components/catos/relaxed-positions-table";
import { RelaxedEquityChart } from "@/components/catos/relaxed-equity-chart";
import { allocation, cryptoMarkets, type Fill } from "@/lib/mock/data";
import { recentFills } from "@/lib/mock/terminal";
import { fmtMoney, fmtSigned, nowStamp, useLiveFeed } from "@/hooks/use-live";
import { useI18n } from "@/lib/i18n";
import { PulseBeacon } from "@/components/catos/pulse-beacon";
import { cn } from "@/lib/utils";

import { LayoutRibbon } from "@/components/catos/layout-ribbon";
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
    symbol: `${market.code}-PERP`,
    side: Math.random() > 0.5 ? "BUY" : "SELL",
    qty: Number((Math.random() * 2 + 0.1).toFixed(2)),
    price: market.price,
    pnl: Number(((Math.random() - 0.3) * 800).toFixed(2)),
  };
}

const assetNames: Record<string, { zh: string; en: string }> = {
  BTC: { zh: "BTC 現貨", en: "BTC Spot" },
  ETH: { zh: "ETH 現貨", en: "ETH Spot" },
  SOL: { zh: "SOL 永續", en: "SOL Perp" },
  Arbitrage: { zh: "套利保證金", en: "Arbitrage Margin" },
  Cash: { zh: "USDT 儲備", en: "USDT Reserve" },
};

function Dashboard() {
  const [fills] = useLiveFeed<Fill>(recentFills, makeFill, 6500, 5);
  const { t, language } = useI18n();

  // 卡片工廠函數：根據 cardId 動態渲染對應卡片
  const renderCard = (cardId: CardId) => {
    switch (cardId) {
      case "equity":
        return <RelaxedEquityChart className="h-full" />;

      case "positions":
        return <RelaxedPositionsTable className="h-full" />;

      case "allocation":
        return (
          <Panel
            className="h-full flex flex-col"
            title={t("asset_allocation")}
            meta={<span className="text-[10px] text-muted-foreground">5 {t("assets_count")}</span>}
          >
            <div className="relative h-[176px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={allocation} dataKey="value" nameKey="name" innerRadius={57} outerRadius={75} paddingAngle={3} stroke="var(--surface)" cornerRadius={2} isAnimationActive={false}>
                    {allocation.map((a, i) => (
                      <Cell key={a.name} fill={allocationColors[i]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => `${v}%`} />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-[9px] text-muted-foreground">{t("total_assets")}</span>
                <span className="mt-1 num text-lg">12.48M</span>
                <span className="mt-0.5 text-[9px] text-muted-foreground">USDT</span>
              </div>
            </div>
            <ul className="mt-2 space-y-2.5">
              {allocation.map((a, i) => (
                <li key={a.name} className="flex items-center gap-2 text-[11px]">
                  <span className={cn("size-1.5 rounded-full", allocationClasses[i])} />
                  <span className="text-muted-foreground">
                    {assetNames[a.name]?.[language === "zh-TW" ? "zh" : "en"] ?? a.name}
                  </span>
                  <span className="ml-auto num">{a.value.toFixed(1)}<span className="text-muted-foreground">%</span></span>
                </li>
              ))}
            </ul>
          </Panel>
        );

      case "fills":
        return (
          <Panel
            className="h-full flex flex-col"
            title={t("recent_fills")}
            meta={<span className="flex items-center gap-1.5 text-[9px] text-up"><PulseBeacon size={4.5} />{t("live")}</span>}
          >
            <ul className="-mt-2">
              {fills.map((f) => (
                <li key={f.id} className="slide-in-row flex items-center gap-2.5 border-b border-border/60 py-2.5 last:border-0">
                  <span className={cn("grid size-7 shrink-0 place-items-center rounded-md", f.side === "BUY" ? "bg-up/10 text-up" : "bg-down/10 text-down")}>
                    {f.side === "BUY" ? <ArrowDownLeft className="size-3.5" /> : <ArrowUpRight className="size-3.5" />}
                  </span>
                  <div className="min-w-0">
                    <p className="num text-[10px] font-medium text-foreground">{f.symbol} <span className={cn("text-[9px]", f.side === "BUY" ? "text-up" : "text-down")}>{f.side === "BUY" ? t("buy") : t("sell")}</span></p>
                    <p className="mt-0.5 num text-[9px] text-muted-foreground">{f.qty} @ {fmtMoney(f.price, f.price < 1 ? 4 : 2)}</p>
                  </div>
                  <div className="ml-auto text-right">
                    <p className={cn("num text-[10px] font-medium", f.pnl >= 0 ? "text-up" : "text-down")}>{fmtSigned(f.pnl)}</p>
                    <p className="mt-0.5 num text-[9px] text-muted-foreground">{f.time}</p>
                  </div>
                </li>
              ))}
            </ul>
          </Panel>
        );

      default:
        return null;
    }
  };

  return (
    <AppShell>
      {/* 1. 統一單條 4 欄核心指標帶 */}
      <UnifiedKpiStrip />

      {/* 2. 佈局調整工具列 (方案快捷切換 · 解鎖/完成鎖定 · 另存新方案) */}
      <LayoutRibbon />

      {/* 3. 自由調整卡片大小與位置的工作台 (120 FPS 流暢分割線拉伸 · 卡片換位) */}
      <WorkspaceGrid renderCard={renderCard} />
    </AppShell>
  );
}
