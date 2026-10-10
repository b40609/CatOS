import { createFileRoute } from "@tanstack/react-router";
import { WorkspacePage } from "@/components/catos/workspace-page";

export const Route = createFileRoute("/backtest")({
  head: () => ({ meta: [
    { title: "Backtest — catOS Quant Terminal" },
    { name: "description", content: "catOS 歷史回測工作區，AI 加密貨幣量化交易平台。" },
    { property: "og:title", content: "Backtest — catOS Quant Terminal" },
    { property: "og:description", content: "catOS 歷史回測工作區，AI 加密貨幣量化交易平台。" },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: () => <WorkspacePage title="Backtest" sub="歷史回測" code="Workspace / Backtest" />,
});
