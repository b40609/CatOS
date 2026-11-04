import { createFileRoute, Link } from "@tanstack/react-router";
import { AppShell, PageHead, Panel } from "@/components/catos/shell";

export const Route = createFileRoute("/review")({
  head: () => ({
    meta: [
      { title: "策略覆盤 · catOS Quant Terminal" },
      { name: "description", content: "catOS 策略覆盤：需要 Demo／實盤成交與權益歷史；v1 只有本機合成模擬，本頁未啟用。" },
      { property: "og:title", content: "策略覆盤 · catOS Quant Terminal" },
      { property: "og:description", content: "Strategy performance review (not enabled in v1)." },
    ],
  }),
  component: StrategyReviewPage,
});

// v1 沒有 Demo／實盤歷史可覆盤；不顯示任何示範數字，只指向 v1 已有真資料的頁面
const WHERE_TO_LOOK = [
  { to: "/backtest", label: "回測", desc: "研究 HTTP 回測的權益、水下回撤與績效" },
  { to: "/bots", label: "實例監控", desc: "本機模擬 run 的狀態、部位、成交與風控投影" },
  { to: "/risk", label: "風控中心", desc: "R1 風控期間基準、鎖存狀態與曝險預算" },
];

function StrategyReviewPage() {
  return (
    <AppShell>
      <PageHead
        code="review // performance"
        title="策略覆盤"
        desc="Demo／實盤績效、回撤修復週期與月度收益"
        right={
          <span className="rounded border border-warn/30 bg-warn/10 px-2 py-0.5 font-mono text-t2 font-semibold text-warn">
            v1 未啟用
          </span>
        }
      />

      <Panel title="v1 沒有可覆盤的成交歷史">
        <p className="text-xs leading-relaxed text-muted-foreground">
          覆盤需要 Demo 或實盤的成交與權益歷史。v1 只提供本機合成模擬（FakeExchange），沒有可覆盤的資料，所以本頁不顯示任何數字。
        </p>
        <ul className="mt-3 space-y-1.5 font-mono text-xs">
          {WHERE_TO_LOOK.map((item) => (
            <li key={item.to} className="flex items-baseline gap-2">
              <Link to={item.to} className="font-semibold text-primary hover:underline">
                {item.label}
              </Link>
              <span className="text-muted-foreground">{item.desc}</span>
            </li>
          ))}
        </ul>
      </Panel>
    </AppShell>
  );
}
