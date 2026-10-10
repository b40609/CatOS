import { createFileRoute } from "@tanstack/react-router";
import { WorkspacePage } from "@/components/catos/workspace-page";

export const Route = createFileRoute("/optimization")({
  head: () => ({ meta: [
    { title: "Optimization — catOS Quant Terminal" },
    { name: "description", content: "catOS 參數優化工作區，AI 加密貨幣量化交易平台。" },
    { property: "og:title", content: "Optimization — catOS Quant Terminal" },
    { property: "og:description", content: "catOS 參數優化工作區，AI 加密貨幣量化交易平台。" },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: () => <WorkspacePage title="Optimization" sub="參數優化" code="Workspace / Optimization" />,
});
