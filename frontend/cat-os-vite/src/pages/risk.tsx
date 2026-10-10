import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { AppShell, PageHead, Panel } from "@/components/catos/shell";
import { DerivativesMetrics } from "@/components/catos/derivatives-metrics";
import { riskAlerts, riskRules as SEED } from "@/lib/mock/data";
import { useLiveNumber } from "@/hooks/use-live";
import { PulseBeacon } from "@/components/catos/pulse-beacon";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/risk")({
  head: () => ({
    meta: [
      { title: "風險控管 — catOS 曝險與熔斷儀表" },
      {
        name: "description",
        content: "catOS 風險控管：模擬曝險、槓桿、資金費率、未平倉量及爆倉量，搭配風控規則與警報時間軸。",
      },
      { property: "og:title", content: "風險控管 — catOS 曝險與熔斷儀表" },
      {
        property: "og:description",
        content: "模擬曝險、槓桿、資金費率、未平倉量及爆倉量，搭配風控規則與警報時間軸。",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: RiskManagement,
});

function Gauge({
  label,
  seed,
  vol,
  max,
  suffix,
  danger,
}: {
  label: string;
  seed: number;
  vol: number;
  max: number;
  suffix: string;
  danger: number;
}) {
  const { value } = useLiveNumber(seed, vol, 1700);
  const pct = Math.min(100, (value / max) * 100);
  const hot = value >= danger;
  const data = [
    { v: pct },
    { v: 100 - pct },
  ];

  return (
    <div className="panel flex flex-col items-center px-4 py-4">
      <p className="label-xs">{label}</p>
      <div className="relative h-[7.5rem] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="v"
              startAngle={210}
              endAngle={-30}
              innerRadius={42}
              outerRadius={56}
              stroke="none"
              isAnimationActive={false}
            >
              <Cell fill={hot ? "var(--color-down)" : "var(--color-gold)"} />
              <Cell fill="var(--color-surface-raised)" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <span
          className={cn(
            "num absolute inset-0 flex items-center justify-center pt-3 text-lg",
            hot ? "text-down" : "text-gold-bright",
          )}
        >
          {value.toFixed(2)}
          {suffix}
        </span>
      </div>
      <p className="num text-[0.65rem] text-muted-foreground">
        限額 {max}
        {suffix}
      </p>
    </div>
  );
}

const ALERT_TONE = {
  error: "border-down/60 text-down",
  warn: "border-warn/60 text-warn",
  info: "border-border text-muted-foreground",
} as const;

function RiskManagement() {
  const [rules, setRules] = useState(SEED);

  return (
    <AppShell>
      <PageHead
        code="module / risk-management"
        title="風險控管"
        desc="永續合約曝險、槓桿熔斷與鏈上風險追蹤 · 模擬數據"
        right={
          <div className="flex items-center gap-2 border border-warn/40 px-3 py-1.5">
            <PulseBeacon size={5} variant="warn" />
            <span className="label-xs !text-warn">2 項規則接近門檻</span>
          </div>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Gauge label="total exposure" seed={18.42} vol={0.004} max={30} suffix="M" danger={26} />
        <Gauge label="leverage" seed={2.81} vol={0.006} max={3} suffix="x" danger={2.9} />
        <Gauge label="var 95% (1d)" seed={412} vol={0.005} max={800} suffix="k" danger={700} />
        <Gauge label="concentration" seed={23.4} vol={0.005} max={25} suffix="%" danger={24} />
      </div>

      <div className="mt-3"><DerivativesMetrics /></div>

      <div className="mt-3 grid gap-3 xl:grid-cols-[1.5fr_1fr]">
        <Panel title="risk rules · 風控規則">
          <ul className="space-y-4">
            {rules.map((r) => (
              <li key={r.id} className="border-b border-border/60 pb-4 last:border-0 last:pb-0">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm text-foreground/90">{r.name}</p>
                    <p className="text-[0.7rem] text-muted-foreground">{r.desc}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="num text-sm text-gold-bright">
                      {r.value}
                      {r.unit}
                    </span>
                    <Switch
                      checked={r.enabled}
                      onCheckedChange={(v) =>
                        setRules((prev) =>
                          prev.map((x) => (x.id === r.id ? { ...x, enabled: v } : x)),
                        )
                      }
                    />
                  </div>
                </div>
                <Slider
                  className="mt-3"
                  value={[r.value]}
                  min={r.min}
                  max={r.max}
                  step={r.unit === "/min" ? 10 : r.unit === "x" ? 0.5 : 1}
                  disabled={!r.enabled}
                  onValueChange={([v]) =>
                    setRules((prev) =>
                      prev.map((x) => (x.id === r.id ? { ...x, value: v ?? x.value } : x)),
                    )
                  }
                />
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="alert timeline · 警報時間軸" meta={<span className="label-xs">today</span>}>
          <ol className="relative space-y-4 border-l border-border pl-4">
            {riskAlerts.map((a) => (
              <li key={a.id} className="relative">
                <span
                  className={cn(
                    "absolute -left-[1.32rem] top-1.5 size-1.5 rounded-full",
                    a.level === "error"
                      ? "bg-down"
                      : a.level === "warn"
                        ? "bg-warn"
                        : "bg-muted-foreground",
                  )}
                />
                <div className="flex items-center gap-2">
                  <span className="num text-[0.7rem] text-muted-foreground">{a.time}</span>
                  <span
                    className={cn(
                      "num border px-1.5 py-0.5 text-[0.6rem] uppercase",
                      ALERT_TONE[a.level],
                    )}
                  >
                    {a.level}
                  </span>
                </div>
                <p className="mt-1 text-xs text-foreground/85">{a.text}</p>
              </li>
            ))}
          </ol>
        </Panel>
      </div>
    </AppShell>
  );
}
