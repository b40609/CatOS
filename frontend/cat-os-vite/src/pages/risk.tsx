import { createFileRoute } from "@tanstack/react-router";
import { useMemo } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { Lock, OctagonX, ShieldCheck, Unlock } from "lucide-react";
import { AppShell, PageHead, Panel } from "@/components/catos/shell";
import { KillSwitchPanel } from "@/components/catos/kill-switch-panel";
import { RISK_STATUS_META } from "@/components/catos/v0-bot-table";
import { eventTitle } from "@/components/catos/unified-incident-activity-card";
import { useCatStore } from "@/state/catStore";
import type { DecimalString, EventLevel } from "@/contracts";
import {
  compareDecimal,
  formatClock,
  formatDateTime,
  formatDecimal,
  formatRatioPct,
  shortId,
  signOf,
  toPlotNumber,
  toneOf,
} from "@/lib/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/risk")({
  head: () => ({
    meta: [
      { title: "風險控管 — catOS 曝險與熔斷儀表" },
      {
        name: "description",
        content: "catOS 風險控管：本機模擬 run 的 R1 風控期間基準、鎖存狀態、曝險與槓桿預算，以及風控事件。",
      },
    ],
  }),
  component: RiskManagement,
});

/** 弧形填色比例（value / limit，夾在 0～100），只作圖形幾何；文字一律用後端 Decimal 字串。 */
function fillPct(value: DecimalString | null | undefined, limit: DecimalString | null | undefined): number {
  const v = toPlotNumber(value);
  const l = toPlotNumber(limit);
  if (!Number.isFinite(v) || !Number.isFinite(l) || l <= 0) return 0;
  return Math.min(100, Math.max(0, (v / l) * 100));
}

function Gauge({
  label,
  fill,
  valueText,
  limitText,
  hot,
}: {
  label: string;
  fill: number;
  valueText: string;
  limitText: string;
  hot: boolean;
}) {
  const data = [{ v: fill }, { v: 100 - fill }];

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
            "num absolute inset-0 flex items-center justify-center pt-3 text-lg font-bold font-mono",
            hot ? "text-down" : "text-gold-bright",
          )}
        >
          {valueText}
        </span>
      </div>
      <p className="num text-t2 text-muted-foreground font-mono">上限 {limitText}</p>
    </div>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex items-center justify-between border-b border-border/40 py-1.5 last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("font-semibold", tone ?? "text-foreground")}>{value}</span>
    </div>
  );
}

const ALERT_TONE: Record<EventLevel, string> = {
  ERROR: "border-down/60 text-down",
  WARN: "border-warn/60 text-warn",
  INFO: "border-border text-muted-foreground",
};

// risk.Snapshot 事實旗標（fail-closed：未宣告即為 false）
const FACTS = [
  { key: "valuation_known", label: "估值已知" },
  { key: "flows_known", label: "資金流已知" },
  { key: "margin_ok", label: "保證金正常" },
  { key: "position_verified", label: "部位已核對" },
] as const;

const RISK_EVENT_LIMIT = 50;

function qty(value: DecimalString | null | undefined): string {
  return value === null || value === undefined ? "不適用" : formatDecimal(value, { digits: 0 }, value);
}

function RiskManagement() {
  const risk = useCatStore((s) => s.risk);
  const bots = useCatStore((s) => s.bots);
  const events = useCatStore((s) => s.events);
  const connection = useCatStore((s) => s.connection);

  const statusMeta = risk ? RISK_STATUS_META[risk.derived.status] : null;
  const latched = risk?.derived.status === "soft_latch" || risk?.derived.status === "hard_latch";
  const derived = risk?.derived;
  const limits = risk?.limits;
  const basis = risk?.basis ?? null;
  const obs = risk?.snapshot ?? null;

  const instById = useMemo(() => {
    const map = new Map<string, string>();
    for (const bot of bots) if (bot.inst_id) map.set(bot.bot_id, bot.inst_id);
    return map;
  }, [bots]);

  // 風控類與 WARN／ERROR 事件，最新在前
  const riskEvents = useMemo(
    () =>
      events
        .filter((e) => e.category === "RISK" || e.level !== "INFO")
        .sort((a, b) => b.seq - a.seq)
        .slice(0, RISK_EVENT_LIMIT),
    [events],
  );

  const ratio = derived?.period_pnl_ratio ?? null;
  const lossMagnitude = ratio !== null && signOf(ratio) === "negative" ? ratio.replace(/^-/, "") : "0";

  const emptyText =
    connection.status === "mode_not_open" ? "此模式未開放（demo/live 不在 v1 範圍）"
    : connection.status === "unavailable" ? `模擬服務不可用：${connection.detail ?? "unknown"}`
    : connection.status === "error" ? `無法連線：${connection.detail ?? "network_error"}`
    : "尚無風控觀測 · 在實例監控頁啟動模擬 run 後顯示";

  return (
    <AppShell>
      <PageHead
        code="guardian // risk-engine"
        title="風險控管中心"
        desc="E_risk = E_verified · Asia/Taipei 00:00 風控期間基準 · 鎖存僅人工恢復"
        right={
          statusMeta && risk ? (
            <span className={cn("rounded border px-2 py-0.5 font-mono text-t2 font-bold", statusMeta.className)}>
              {statusMeta.label} · {risk.derived.can_increase ? "可增倉" : "禁增倉"}
            </span>
          ) : (
            <span className="rounded border border-border/80 bg-secondary/80 px-2 py-0.5 font-mono text-t2 text-muted-foreground">
              尚無風控觀測
            </span>
          )
        }
      />

      {/* ==================== Kill-Switch（工作包 B） ==================== */}
      <Panel
        title={
          <div className="flex items-center gap-2">
            <OctagonX className="size-4 text-red-400" />
            <span>Kill-Switch 總開關</span>
          </div>
        }
        meta={<span className="font-mono text-t2 text-muted-foreground">觸發任何人可按 · 解除只限你本人</span>}
      >
        <KillSwitchPanel />
      </Panel>

      {/* ==================== R1 風控期間基準 ==================== */}
      <Panel
        title={
          <div className="flex items-center gap-2">
            <ShieldCheck className="size-4 text-primary" />
            <span>R1 風控期間基準 (Risk Period Baseline)</span>
          </div>
        }
        meta={
          <span
            className="font-mono text-t2 text-muted-foreground"
            title="單一 Bot 的人工 re-arm 在接 OKX Demo 的工作包接上；本機模擬 run 被停止後是終態"
          >
            單一 Bot re-arm · Demo 工作包再接
          </span>
        }
      >
        {risk && derived && limits ? (
          <>
            <div className="grid grid-cols-1 gap-3 font-mono text-xs md:grid-cols-4">
              <div className="space-y-1 rounded-lg border border-border/60 bg-background/40 p-3">
                <span className="block text-t2 text-muted-foreground">起算時間 (合成)</span>
                <span className="block text-sm font-bold text-foreground">
                  {basis ? formatDateTime(basis.period_start_ms) : "尚無基準"}
                </span>
                <span className="text-t1 text-muted-foreground">
                  {basis ? `day ${basis.day} · evidence ${shortId(basis.evidence_id)}` : "首次合格觀測後建立"}
                </span>
              </div>

              <div className="space-y-1 rounded-lg border border-border/60 bg-background/40 p-3">
                <span className="block text-t2 text-muted-foreground">風控期間基準權益</span>
                <span className="block text-sm font-bold text-primary">
                  {formatDecimal(basis?.equity, { prefix: "$" }, "尚無基準")}
                </span>
                <span className="text-t1 text-muted-foreground">同日基準不因虧損或入金替換</span>
              </div>

              <div className="space-y-1 rounded-lg border border-border/60 bg-background/40 p-3">
                <span className="block text-t2 text-muted-foreground">風控期間損益</span>
                <span className={cn("block text-sm font-bold", toneOf(derived.period_pnl))}>
                  {formatDecimal(derived.period_pnl, { sign: true, prefix: "$" })}
                </span>
                <span className="text-t1 text-muted-foreground">{formatRatioPct(derived.period_pnl_ratio)}</span>
              </div>

              <div className="space-y-1 rounded-lg border border-border/60 bg-background/40 p-3">
                <span className="block text-t2 text-muted-foreground">鎖存狀態</span>
                <span
                  className={cn(
                    "flex items-center gap-1 text-sm font-bold",
                    derived.status === "normal" ? "text-up" : latched ? "text-down" : "text-muted-foreground",
                  )}
                >
                  {derived.status === "normal" ? <Unlock className="size-3.5" /> : <Lock className="size-3.5" />}
                  {statusMeta?.label ?? derived.status}
                </span>
                <span className="text-t1 text-muted-foreground">
                  {derived.can_increase ? "允許增倉" : "禁增倉"}
                  {risk.reasons.length ? ` · ${risk.reasons.join(", ")}` : ""}
                </span>
              </div>
            </div>

            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border/40 pt-2.5 font-mono text-t2 text-muted-foreground">
              <span>
                門檻：<strong className="text-foreground">Soft {formatRatioPct(limits.soft_loss, { sign: false })}</strong>（禁增倉）·{" "}
                <strong className="text-foreground">Hard {formatRatioPct(limits.hard_loss, { sign: false })}</strong>（清倉＋熔斷）
              </span>
              <span>
                {risk.mode} / {risk.health} / {risk.phase} · 觀測 seq {risk.seq} · 合成 {formatClock(risk.time_ms)}
              </span>
            </div>
          </>
        ) : (
          <p className="py-6 text-center font-mono text-xs text-muted-foreground">{emptyText}</p>
        )}
      </Panel>

      {/* 曝險、槓桿與期間虧損 */}
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Gauge
          label="名目曝險 / 總曝險預算"
          fill={fillPct(derived?.notional, derived?.exposure_budget)}
          valueText={formatDecimal(derived?.notional, { prefix: "$" })}
          limitText={formatDecimal(derived?.exposure_budget, { prefix: "$", digits: 0 })}
          hot={compareDecimal(derived?.notional, derived?.exposure_budget) === 1}
        />
        <Gauge
          label="帳戶有效槓桿"
          fill={fillPct(derived?.effective_leverage, limits?.leverage)}
          valueText={formatDecimal(derived?.effective_leverage, { digits: 2, suffix: "x" })}
          limitText={formatDecimal(limits?.leverage, { digits: 1, suffix: "x" })}
          hot={compareDecimal(derived?.effective_leverage, limits?.leverage) === 1}
        />
        <Gauge
          label="單幣曝險 / 單幣預算"
          fill={fillPct(derived?.notional, derived?.symbol_budget)}
          valueText={formatDecimal(derived?.notional, { prefix: "$" })}
          limitText={formatDecimal(derived?.symbol_budget, { prefix: "$", digits: 0 })}
          hot={compareDecimal(derived?.notional, derived?.symbol_budget) === 1}
        />
        <Gauge
          label="風控期間損益 / Hard 日損"
          fill={fillPct(lossMagnitude, limits?.hard_loss)}
          valueText={formatRatioPct(ratio)}
          limitText={`Soft ${formatRatioPct(limits?.soft_loss, { sign: false })} · Hard ${formatRatioPct(limits?.hard_loss, { sign: false })}`}
          hot={latched}
        />
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-[1.5fr_1fr]">
        <Panel
          title="風控參數與最後一次觀測"
          meta={
            <span className="font-mono text-t2 text-muted-foreground">
              {risk ? `觀測 seq ${risk.seq} · 合成 ${formatClock(risk.time_ms)} · ` : ""}門檻修改 · Demo 工作包再接
            </span>
          }
        >
          {risk && derived && limits ? (
            <div className="grid gap-x-6 font-mono text-t2 md:grid-cols-2">
              <div>
                <Row label="有效槓桿上限" value={formatDecimal(limits.leverage, { digits: 1, suffix: "x" })} />
                <Row label="單幣預算占比" value={formatRatioPct(limits.symbol_share, { sign: false })} />
                <Row
                  label="Soft / Hard 日損"
                  value={`${formatRatioPct(limits.soft_loss, { sign: false })} / ${formatRatioPct(limits.hard_loss, { sign: false })}`}
                />
                <Row label="總曝險預算" value={formatDecimal(derived.exposure_budget, { prefix: "$" })} />
                <Row label="單幣預算上限" value={formatDecimal(derived.symbol_budget, { prefix: "$" })} />
                <Row label="風控 epoch" value={String(risk.epoch)} />
              </div>
              <div>
                <Row label="風控權益 E_risk" value={formatDecimal(obs?.risk_equity, { prefix: "$" })} />
                <Row label="帳戶權益" value={formatDecimal(obs?.equity, { prefix: "$" })} />
                <Row label="部位 / mark" value={`${qty(obs?.position)} 張 / ${formatDecimal(obs?.mark, { prefix: "$" })}`} />
                <Row label="在途 買 / 賣" value={`${qty(obs?.pending_buy)} / ${qty(obs?.pending_sell)}`} />
                <Row
                  label="外部淨資金流"
                  value={formatDecimal(obs?.external_net, { sign: true, prefix: "$" })}
                  tone={toneOf(obs?.external_net)}
                />
                <Row
                  label="減倉衝突"
                  value={obs ? (obs.reduction_conflict ? "有" : "無") : "不適用"}
                  tone={obs?.reduction_conflict ? "text-down" : undefined}
                />
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-1.5 md:col-span-2">
                {FACTS.map((f) => {
                  const ok = obs ? obs[f.key] : null;
                  return (
                    <span
                      key={f.key}
                      className={cn(
                        "rounded border px-1.5 py-0.5 text-t1 font-semibold",
                        ok === null
                          ? "border-border text-muted-foreground"
                          : ok
                            ? "border-up/40 text-up"
                            : "border-down/50 text-down",
                      )}
                    >
                      {f.label}：{ok === null ? "不適用" : ok ? "是" : "否"}
                    </span>
                  );
                })}
                <span className="text-t1 text-muted-foreground">未宣告即視為未知（fail-closed）</span>
              </div>
            </div>
          ) : (
            <p className="py-6 text-center font-mono text-xs text-muted-foreground">{emptyText}</p>
          )}
        </Panel>

        <Panel
          title="風控事件"
          meta={<span className="label-xs">{riskEvents.length} 筆 · 風控與 WARN／ERROR</span>}
        >
          <div className="max-h-[22rem] overflow-y-auto pr-1">
            {riskEvents.length === 0 ? (
              <p className="py-6 text-center font-mono text-xs text-muted-foreground">尚無風控事件</p>
            ) : (
              <ol className="relative space-y-3 border-l border-border pl-4">
                {riskEvents.map((ev) => (
                  <li key={ev.seq} className="relative">
                    <span
                      className={cn(
                        "absolute -left-[1.32rem] top-1.5 size-1.5 rounded-full",
                        ev.level === "ERROR" ? "bg-down" : ev.level === "WARN" ? "bg-warn" : "bg-muted-foreground",
                      )}
                    />
                    <div className="flex items-center gap-2">
                      <span className="num font-mono text-t3 text-muted-foreground">{formatClock(ev.wall_time_ms)}</span>
                      <span
                        className={cn(
                          "num border px-1.5 py-0.5 font-mono text-t2 font-semibold uppercase",
                          ALERT_TONE[ev.level],
                        )}
                      >
                        {ev.level}
                      </span>
                      <span className="font-mono text-t2 text-muted-foreground">{ev.kind}</span>
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-foreground/85">
                      {eventTitle(ev, instById.get(ev.bot_id) ?? "合約")}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </Panel>
      </div>
    </AppShell>
  );
}
