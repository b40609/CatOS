import { createFileRoute } from "@tanstack/react-router";
import { WorkspacePage } from "@/components/catos/workspace-page";

export const Route = createFileRoute("/review")({
  head: () => ({ meta: [
    { title: "Review — catOS Quant Terminal" },
    { name: "description", content: "catOS 策略覆盤工作區，AI 加密貨幣量化交易平台。" },
    { property: "og:title", content: "Review — catOS Quant Terminal" },
    { property: "og:description", content: "catOS 策略覆盤工作區，AI 加密貨幣量化交易平台。" },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: () => <WorkspacePage title="Review" sub="策略覆盤" code="Workspace / Review" />,
});
