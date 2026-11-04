import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/catos/shell";
import { AccountEquityBand } from "@/components/catos/account-equity-band";
import { ActivityPanel } from "@/components/catos/activity-panel";
import { V0BotTable } from "@/components/catos/v0-bot-table";
import { AllocationDonutCard } from "@/components/catos/allocation-donut-card";
import { LayoutModeToolbar } from "@/components/catos/layout-mode-toolbar";

import { UnifiedIncidentActivityCard } from "@/components/catos/unified-incident-activity-card";

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

function Dashboard() {

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
        return <UnifiedIncidentActivityCard className="h-full" />;

      case "activity_deck":
        return <UnifiedIncidentActivityCard className="h-full" />;

      case "fills":
        return <UnifiedIncidentActivityCard className="h-full" />;

      default:
        return null;
    }
  };

  return (
    <AppShell
      dashboardTools={
        <div className="flex items-center gap-2 shrink min-w-0">
          <LayoutModeToolbar />
        </div>
      }
    >
      {/* 定案方案 2：上下分層 T-Split 解耦樹 (120 FPS 流暢分割線拉伸) */}
      <WorkspaceGrid renderCard={renderCard} />
    </AppShell>
  );
}
