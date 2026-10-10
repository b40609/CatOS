import { createFileRoute } from "@tanstack/react-router";
import { WorkspacePage } from "@/components/catos/workspace-page";

export const Route = createFileRoute("/market-intel")({
  head: () => ({ meta: [
    { title: "Market Intel — catOS Quant Terminal" },
    { name: "description", content: "catOS 市場情報工作區，AI 加密貨幣量化交易平台。" },
    { property: "og:title", content: "Market Intel — catOS Quant Terminal" },
    { property: "og:description", content: "catOS 市場情報工作區，AI 加密貨幣量化交易平台。" },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: () => <WorkspacePage title="Market Intel" sub="市場情報" code="Workspace / Market Intel" />,
});
