import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import { Switch } from "@/components/ui/switch";
import { AppShell, PageHead, Panel } from "@/components/catos/shell";
import { strategies as SEED, type Strategy } from "@/lib/mock/data";
import { useLiveSeries } from "@/hooks/use-live";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/strategies")({
  head: () => ({
    meta: [
      { title: "策略中心 — catOS 量化策略庫" },
      {
        name: "description",
        content: "catOS 策略中心：檢視每個 AI 量化策略的年化報酬、夏普值、回撤與參數，並即時啟停。",
      },
      { property: "og:title", content: "策略中心 — catOS 量化策略庫" },
      {
        property: "og:description",
        content: "檢視 AI 量化策略的年化報酬、夏普值、回撤與參數，並即時啟停。",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: StrategyCenter,
});

function Metric({ label, value, tone }: { label: string; value: string; tone?: "up" | "down" }) {
  return (
    <div>
      <p className="label-xs">{label}</p>
      <p
        className={cn(
          "num mt-0.5 text-sm",
          tone === "up" ? "text-up" : tone === "down" ? "text-down" : "text-foreground/90",
        )}
      >
        {value}
      </p>
    </div>
  );
}

function StrategyCard({
  s,
  active,
  onSelect,
  onToggle,
}: {
  s: Strategy;
  active: boolean;
  onSelect: () => void;
  onToggle: (v: boolean) => void;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
      className={cn(
        "panel w-full cursor-pointer px-4 py-3.5 text-left transition-colors",
        active ? "border-gold/70 bg-surface-raised" : "hover:border-gold/40",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="label-xs">{s.code}</p>
          <h3 className="mt-0.5 text-base text-gold-bright">{s.name}</h3>
          <p className="mt-0.5 text-[0.7rem] text-muted-foreground">
            {s.kind} · {s.market}
          </p>
        </div>
        <span onClick={(e) => e.stopPropagation()}>
          <Switch checked={s.enabled} onCheckedChange={onToggle} />
        </span>
      </div>

      <div className="mt-3 grid grid-cols-4 gap-2 border-t border-border pt-3">
        <Metric label="年化" value={`${s.annual.toFixed(1)}%`} tone="up" />
        <Metric label="夏普" value={s.sharpe.toFixed(2)} />
        <Metric label="回撤" value={`${s.drawdown.toFixed(1)}%`} tone="down" />
        <Metric label="勝率" value={`${s.winRate.toFixed(1)}%`} />
      </div>
    </div>
  );
}

function StrategyCenter() {
  const [list, setList] = useState(SEED);
  const [activeId, setActiveId] = useState(SEED[0]!.id);
  const active = list.find((s) => s.id === activeId) ?? list[0]!;
  const live = useLiveSeries(active.curve, 1.4, 1800);
  const data = live.map((v, i) => ({ i, v }));

  return (
    <AppShell>
      <PageHead
        code="module / strategy-center"
        title="策略中心"
        desc="現貨、永續、跨所套利與鏈上訊號策略 · 模擬數據"
        right={
          <div className="num text-right text-[0.7rem] text-muted-foreground">
            <p>
              啟用中 <span className="text-gold-bright">{list.filter((s) => s.enabled).length}</span>{" "}
              / {list.length}
            </p>
            <p className="mt-0.5">組合夏普 2.14</p>
          </div>
        }
      />

      <div className="grid gap-3 xl:grid-cols-[1.45fr_1fr]">
        <div className="grid gap-3 sm:grid-cols-2">
          {list.map((s) => (
            <StrategyCard
              key={s.id}
              s={s}
              active={s.id === active.id}
              onSelect={() => setActiveId(s.id)}
              onToggle={(v) =>
                setList((prev) => prev.map((x) => (x.id === s.id ? { ...x, enabled: v } : x)))
              }
            />
          ))}
        </div>

        <div className="space-y-3">
          <Panel
            title={`backtest · ${active.code}`}
            meta={
              <span className="num text-[0.7rem] text-muted-foreground">
                {active.trades.toLocaleString()} trades
              </span>
            }
          >
            <div className="h-[13rem]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data} margin={{ top: 6, right: 4, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="bt" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--color-gold)" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="var(--color-gold)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <YAxis
                    domain={["dataMin - 4", "dataMax + 4"]}
                    tick={{ fontSize: 10, fill: "var(--color-muted-foreground)" }}
                    tickLine={false}
                    axisLine={false}
                    width={38}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--color-surface-raised)",
                      border: "1px solid var(--color-border)",
                      borderRadius: 2,
                      fontSize: 12,
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="v"
                    stroke="var(--color-gold)"
                    strokeWidth={1.5}
                    fill="url(#bt)"
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel title="parameters · 參數">
            <dl className="space-y-px">
              {active.params.map((p) => (
                <div
                  key={p.key}
                  className="flex items-center justify-between border-b border-border/60 py-1.5 text-xs"
                >
                  <dt className="num text-muted-foreground">{p.key}</dt>
                  <dd className="num text-gold-bright">{p.value}</dd>
                </div>
              ))}
            </dl>
          </Panel>

          <Panel title="performance · 績效指標">
            <div className="grid grid-cols-3 gap-3">
              <Metric label="annual" value={`${active.annual.toFixed(1)}%`} tone="up" />
              <Metric label="sharpe" value={active.sharpe.toFixed(2)} />
              <Metric label="sortino" value={(active.sharpe * 1.28).toFixed(2)} />
              <Metric label="max dd" value={`${active.drawdown.toFixed(1)}%`} tone="down" />
              <Metric label="win rate" value={`${active.winRate.toFixed(1)}%`} />
              <Metric
                label="profit factor"
                value={(1 + active.sharpe / 3.2).toFixed(2)}
              />
            </div>
          </Panel>
        </div>
      </div>
    </AppShell>
  );
}
