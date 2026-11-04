import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import { AppShell, PageHead, Panel } from "@/components/catos/shell";
import { BOT_STATE_LABEL } from "@/components/catos/v0-bot-table";
import { useCatStore } from "@/state/catStore";
import { StateAdapter } from "@/state/stateAdapter";
import type { RegisteredStrategyDTO } from "@/contracts";
import { formatDecimal, formatTimeframe, shortId, toPlotNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/strategies")({
  head: () => ({
    meta: [
      { title: "策略中心 — catOS 量化策略庫" },
      {
        name: "description",
        content: "catOS 策略中心：manifest 登錄策略的版本、預設參數、製品雜湊與綁定實例，以及本次模擬 run 的權益。",
      },
      { property: "og:title", content: "策略中心 — catOS 量化策略庫" },
      {
        property: "og:description",
        content: "檢視登錄策略的版本、參數、製品驗證與綁定實例。",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: StrategyCenter,
});

const keyOf = (s: RegisteredStrategyDTO) => `${s.strategy_id}@${s.version}`;

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="label-xs">{label}</p>
      <p className="num mt-0.5 truncate text-sm text-foreground/90">{value}</p>
    </div>
  );
}

function Row({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border/60 py-1.5 text-xs last:border-0">
      <dt className="num shrink-0 text-muted-foreground">{label}</dt>
      <dd className="num truncate text-gold-bright" title={title}>{value}</dd>
    </div>
  );
}

function StrategyCard({
  s,
  boundCount,
  active,
  onSelect,
}: {
  s: RegisteredStrategyDTO;
  boundCount: number;
  active: boolean;
  onSelect: () => void;
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
        <div className="min-w-0">
          <p className="label-xs">{s.strategy_id}</p>
          <h3 className="mt-0.5 text-base text-gold-bright">{s.name}</h3>
          <p className="mt-0.5 text-t3 text-muted-foreground">
            {s.version} · {s.allowed_modes.join(" / ")}
          </p>
        </div>
        <span className="shrink-0 rounded border border-up/40 px-1.5 py-0.5 font-mono text-t1 font-semibold text-up">
          {s.approval_state}
        </span>
      </div>
      {s.description && <p className="mt-2 line-clamp-2 text-t3 text-muted-foreground">{s.description}</p>}

      <div className="mt-3 grid grid-cols-4 gap-2 border-t border-border pt-3">
        <Metric label="預熱" value={`${s.defaults.warmup_bars} bars`} />
        <Metric label="參數" value={`${Object.keys(s.defaults.parameters).length} 個`} />
        <Metric label="綁定 Bot" value={String(boundCount)} />
        <Metric label="製品" value={shortId(s.artifact_hash)} />
      </div>
    </div>
  );
}

function StrategyCenter() {
  const strategies = useCatStore((s) => s.strategies);
  const bots = useCatStore((s) => s.bots);
  const events = useCatStore((s) => s.events);
  const connection = useCatStore((s) => s.connection);
  const [activeKey, setActiveKey] = useState<string | null>(null);

  const active = strategies.find((s) => keyOf(s) === activeKey) ?? strategies[0] ?? null;
  const boundOf = (s: RegisteredStrategyDTO) =>
    bots.filter((b) => b.strategy_id === s.strategy_id && b.strategy_version === s.version);
  const bound = active ? boundOf(active) : [];
  const runBot = bound.find((b) => b.current_run_id) ?? null;
  const runId = runBot?.current_run_id ?? null;

  // 圖形座標用 toPlotNumber；提示框顯示原始 Decimal 字串
  const curve = useMemo(
    () =>
      StateAdapter.equityCurve(events, runId).map((p, i) => ({ i, v: toPlotNumber(p.equity), equity: p.equity })),
    [events, runId],
  );

  const emptyText =
    connection.status === "mode_not_open" ? "此模式未開放（demo/live 不在 v1 範圍）"
    : connection.status === "unavailable" ? `模擬服務不可用：${connection.detail ?? "unknown"}`
    : connection.status === "error" ? `無法連線：${connection.detail ?? "network_error"}`
    : "等待模擬服務…";

  return (
    <AppShell>
      <PageHead
        code="module / strategy-center"
        title="策略中心"
        desc="manifest 登錄策略 · 載入前核對來源 sha256 · v1 無上傳"
        right={
          <span className="num text-t3 text-muted-foreground">
            登錄 <span className="text-gold-bright">{strategies.length}</span> · 綁定 Bot{" "}
            <span className="text-gold-bright">{bots.length}</span>
          </span>
        }
      />

      {!active ? (
        <Panel title="registered strategies">
          <p className="py-8 text-center font-mono text-xs text-muted-foreground">{emptyText}</p>
        </Panel>
      ) : (
        <div className="grid gap-3 xl:grid-cols-[22rem_1fr]">
          <div className="grid content-start gap-3">
            {strategies.map((s) => (
              <StrategyCard
                key={keyOf(s)}
                s={s}
                boundCount={boundOf(s).length}
                active={keyOf(s) === keyOf(active)}
                onSelect={() => setActiveKey(keyOf(s))}
              />
            ))}
          </div>

          <div className="space-y-3">
            <Panel
              title={`run 權益 · ${runBot?.bot_id ?? active.strategy_id}`}
              meta={
                <span className="num text-t3 text-muted-foreground">
                  {runId ? `${curve.length} 點 · run ${shortId(runId)}` : "無 run"}
                </span>
              }
            >
              {curve.length === 0 ? (
                <p className="py-10 text-center font-mono text-xs text-muted-foreground">
                  尚無 run 權益 · 在實例監控頁啟動模擬 run 後顯示
                </p>
              ) : (
                <div className="h-[13rem]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={curve} margin={{ top: 6, right: 4, bottom: 0, left: 0 }}>
                      <defs>
                        <linearGradient id="run-equity" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="var(--color-gold)" stopOpacity={0.4} />
                          <stop offset="100%" stopColor="var(--color-gold)" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <YAxis hide domain={["dataMin", "dataMax"]} />
                      <Tooltip
                        cursor={{ stroke: "var(--color-border)" }}
                        content={({ active: hovered, payload }) => {
                          if (!hovered || !payload?.length) return null;
                          const point = payload[0].payload as { i: number; equity: string };
                          return (
                            <div className="rounded border border-border bg-surface-raised px-2 py-1 font-mono text-t2">
                              #{point.i + 1} · {formatDecimal(point.equity, { prefix: "$" })}
                            </div>
                          );
                        }}
                      />
                      <Area
                        type="monotone"
                        dataKey="v"
                        stroke="var(--color-gold)"
                        strokeWidth={1.5}
                        fill="url(#run-equity)"
                        isAnimationActive={false}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
            </Panel>

            <div className="grid gap-3 lg:grid-cols-[1fr_1.4fr_1fr]">
              <Panel title="parameters · 預設參數" meta={<span className="label-xs">v1 不可修改</span>}>
                <dl className="space-y-px">
                  {Object.entries(active.defaults.parameters).map(([key, value]) => (
                    <Row key={key} label={key} value={String(value)} />
                  ))}
                  <Row label="warmup_bars" value={String(active.defaults.warmup_bars)} />
                </dl>
              </Panel>

              <Panel title="artifact · 製品與驗證">
                <dl className="space-y-px">
                  <Row label="entry" value={active.entry} />
                  <Row label="kind" value={active.kind} />
                  <Row label="artifact_hash" value={shortId(active.artifact_hash, 16)} title={active.artifact_hash} />
                  <Row label="source_files" value={active.source_files.join(", ")} title={active.source_files.join("\n")} />
                </dl>
                <p className="mt-2 text-t2 text-muted-foreground">
                  載入前核對 source_files 的 sha256，不符即拒絕載入（fail-closed）。
                </p>
              </Panel>

              <Panel title="bound bots · 綁定實例">
                {bound.length === 0 ? (
                  <p className="py-4 text-center font-mono text-xs text-muted-foreground">尚無綁定實例</p>
                ) : (
                  <dl className="space-y-px">
                    {bound.map((b) => (
                      <div key={b.bot_id} className="border-b border-border/60 py-1.5 text-xs last:border-0">
                        <div className="flex items-center justify-between">
                          <span className="num font-semibold text-foreground">{b.bot_id}</span>
                          <span className="num text-gold-bright">{BOT_STATE_LABEL[b.state] ?? b.state}</span>
                        </div>
                        <div className="num mt-0.5 flex flex-wrap gap-x-3 text-t2 text-muted-foreground">
                          <span>{b.inst_id ?? "不適用"} · {formatTimeframe(b.timeframe_ms)}</span>
                          <span>run {b.run_count} 次</span>
                          <span>成交 {b.fills}</span>
                          <span>權益 {formatDecimal(b.equity, { prefix: "$" }, "未啟動")}</span>
                        </div>
                      </div>
                    ))}
                  </dl>
                )}
              </Panel>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
