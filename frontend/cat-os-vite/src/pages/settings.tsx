import { createFileRoute } from "@tanstack/react-router";
import { WorkspacePage } from "@/components/catos/workspace-page";

export const Route = createFileRoute("/settings")({
  head: () => ({ meta: [
    { title: "Settings — catOS Quant Terminal" },
    { name: "description", content: "catOS 系統設定工作區，AI 加密貨幣量化交易平台。" },
    { property: "og:title", content: "Settings — catOS Quant Terminal" },
    { property: "og:description", content: "catOS 系統設定工作區，AI 加密貨幣量化交易平台。" },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: () => <WorkspacePage title="Settings" sub="系統設定" code="Workspace / Settings" />,
});
