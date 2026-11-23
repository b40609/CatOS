import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/catos/shell";
import { AccountEquityBand } from "@/components/catos/account-equity-band";
import { BotsPositionsCard } from "@/components/catos/bots-positions-card";
import { StrategyPipelineCard } from "@/components/catos/strategy-pipeline-card";
import { AllocationDonutCard } from "@/components/catos/allocation-donut-card";
import { LayoutModeToolbar } from "@/components/catos/layout-mode-toolbar";
import { UnifiedIncidentActivityCard } from "@/components/catos/unified-incident-activity-card";
import { WorkspaceGrid } from "@/components/catos/workspace-grid";
import type { CardId } from "@/state/layoutStore";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Dashboard · catOS Quant Terminal" },
      { name: "description", content: "catOS 系統總覽：帳戶權益、多視角曝險額度、策略實例與持倉、策略管線與待處理事件審計。" },
      { property: "og:title", content: "Dashboard · catOS Quant Terminal" },
      { property: "og:description", content: "Crypto portfolio equity, multi-view exposure, bots & positions, strategy pipeline and action audit log in catOS." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Dashboard,
});

function Dashboard() {
  const renderCard = (cardId: CardId) => {
    switch (cardId) {
      case "equity":
        return <AccountEquityBand className="h-full" />;

      case "allocation":
        return <AllocationDonutCard className="h-full" />;

      case "bots":
      case "positions":
        return <BotsPositionsCard className="h-full" />;

      case "pipeline":
        return <StrategyPipelineCard className="h-full" />;

      case "activity_deck":
      case "incidents":
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
      <WorkspaceGrid renderCard={renderCard} />
    </AppShell>
  );
}
