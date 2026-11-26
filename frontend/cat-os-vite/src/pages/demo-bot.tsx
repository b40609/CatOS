import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AppShell, PageHead, Panel } from "@/components/catos/shell";
import { fetchDemoBotOverview, fetchDemoBotRun } from "@/adapters/demo-bot-api-adapter";
import type { DemoBotEventDTO, DemoBotOverviewDTO, DemoBotRunDetailDTO, DemoBotRunSummaryDTO } from "@/contracts/demo-bot";
import { formatDateTime, formatDecimal, formatRatioPct, formatTimeframe, shortId } from "@/lib/format";
import { isOperatorStop } from "@/lib/status-truth";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/demo-bot")({
  head: () => ({ meta: [{ title: "模擬盤 Bot — catOS" }] }),
  component: DemoBotPage,
});

const POLL_MS = 15_000;

type Health = { label: string; tone: string };

function health(run: DemoBotRunSummaryDTO): Health {
  if (run.state === "running" && run.stale) return { label: "無回應", tone: "text-down" };
  if (run.state === "running") return { label: "運行中", tone: "text-up" };
  if (run.state === "failed") return { label: "錯誤停止", tone: "text-down" };
  if (run.state === "stopped" && !isOperatorStop(run.stop_reason)) return { label: "異常停止", tone: "text-warn" };
  if (run.state === "stopped") return { label: "已停止", tone: "text-muted-foreground" };
  return { label: run.state, tone: "text-muted-foreground" };
}

function position(value: string | null | undefined): string {
  if (value === null || value === undefined) return "不適用";
  if (/^-?0+(\.0*)?$/.test(value)) return "空倉";
  return `${value.startsWith("-") ? "空" : "多"} ${formatDecimal(value.replace(/^-/, ""), { digits: 0 })} 張`;
}

const EVENT_LABEL: Record<string, string> = {
  started: "啟動", stopped: "停止", fill: "成交", order: "委託", protection: "保底停損",
  protection_alert: "停損告警", protection_altered: "停損被改", protection_config: "停損比例",
  protection_left: "停損殘留", protection_wait: "停損等待", kill_switch: "Kill-Switch",
  hard_kill_switch: "Hard 寫入 Kill", flatten: "清倉", flatten_done: "清倉完成", flatten_failed: "清倉失敗",
  soft_latched: "Soft 鎖住", soft_rearmed: "Soft 解除", soft_rearm_refused: "Soft 仍鎖",
  risk: "風控", day_basis: "當日基準", read_retry: "讀取重試", resume_input: "接續補 K 線",
  resume_intent: "接續作廢意圖", previous_run_unsettled: "舊 run 未結清",
};
const EVENT_ALERT = new Set(["protection_alert", "protection_altered", "flatten_failed", "kill_switch",
  "hard_kill_switch", "soft_latched", "protection_left", "previous_run_unsettled"]);

function eventDetail(e: DemoBotEventDTO): string {
  switch (e.kind) {
    case "protection":
      return e.price ? `${e.side === "sell" ? "賣" : "買"} @ ${String(e.price)}` : "撤銷";
    case "protection_config":
      return formatRatioPct(String(e.ratio ?? ""), { sign: false });
    case "fill":
      return String(e.leg ?? "");
    case "read_retry":
      return `${String(e.code ?? "")} #${String(e.attempt ?? "")}`;
    case "started":
      return e.resumed ? `接續，補 ${String(e.missed ?? 0)} 根` : "新 run";
    default: {
      const rest = Object.entries(e).filter(([k]) => k !== "kind" && k !== "time_ms");
      return rest.map(([, v]) => (Array.isArray(v) ? v.join(",") : String(v))).join(" ");
    }
  }
}

function Cell({ label, value, tone, sub }: { label: string; value: string; tone?: string; sub?: string }) {
  return (
    <div className="rounded border border-border/60 bg-secondary/20 px-3 py-2 min-w-0">
      <div className="text-t1 text-muted-foreground">{label}</div>
      <div className={cn("font-mono text-t4 font-bold truncate", tone ?? "text-foreground")}>{value}</div>
      {sub && <div className="text-t1 font-mono text-muted-foreground truncate">{sub}</div>}
    </div>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-muted-foreground shrink-0">{label}</span>
      <span className={cn("font-mono truncate", tone ?? "text-foreground")}>{value}</span>
    </div>
  );
}

function DemoBotPage() {
  const [overview, setOverview] = useState<DemoBotOverviewDTO | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<DemoBotRunDetailDTO | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      const result = await fetchDemoBotOverview(controller.signal);
      if (result.ok) { setOverview(result.data); setError(null); }
      else if (result.error !== "aborted") setError(result.error);
    };
    void load();
    const timer = window.setInterval(load, POLL_MS);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, []);

  const currentId = overview?.current?.run_id ?? null;
  const viewing = selected ?? currentId;

  useEffect(() => {
    if (!viewing || viewing === currentId) { setDetail(null); return; }
    const controller = new AbortController();
    void fetchDemoBotRun(viewing, controller.signal).then((r) => { if (r.ok) setDetail(r.data); });
    return () => controller.abort();
  }, [viewing, currentId, overview?.observed_at_ms]);

  const run = viewing && viewing !== currentId ? detail : overview?.current ?? null;
  const h = run ? health(run) : null;

  return (
    <AppShell>
      <PageHead code="OKX DEMO" title="模擬盤 Bot" desc=""
                right={h && <span className={cn("font-mono text-t2 font-bold", h.tone)}>{h.label}</span>} />

      {error && <div className="mb-2 rounded border border-down/40 px-3 py-1.5 text-t2 font-mono text-down">讀取失敗：{error}</div>}
      {!run && !error && <div className="px-3 py-8 text-center text-t2 text-muted-foreground font-mono">
        {overview ? "還沒有模擬盤 Bot 的 run" : "讀取中…"}</div>}

      {run && h && (
        <>
          {run.stale && (
            <div className="mb-2 rounded border border-down/40 bg-down/5 px-3 py-1.5 text-t2 font-mono text-down">
              {formatDateTime(run.updated_at_ms)} 之後沒有更新，程序可能已結束
            </div>
          )}
          {run.stop_reason && (
            <div className="mb-2 rounded border border-border/60 bg-secondary/20 px-3 py-1.5 text-t2 font-mono">
              <span className="text-muted-foreground">停止原因 </span><span className="text-foreground">{run.stop_reason}</span>
              {run.stop_hint && <div className="text-muted-foreground">{run.stop_hint}</div>}
            </div>
          )}

          <div className="mb-3 grid grid-cols-2 lg:grid-cols-5 gap-2">
            <Cell label="狀態" value={h.label} tone={h.tone} sub={`更新 ${formatDateTime(run.updated_at_ms)}`} />
            <Cell label="部位" value={position(run.position)} sub={run.inst_id ?? undefined} />
            <Cell label="權益 USDT" value={formatDecimal(run.last_bar?.equity, { digits: 2 })}
                  sub={`起始 ${formatDecimal(run.starting_equity, { digits: 2 })}`} />
            <Cell label="保底停損" value={run.protection ? `${run.protection.side === "sell" ? "賣" : "買"} @ ${formatDecimal(run.protection.price)}` : "未掛"}
                  sub={`比例 ${formatRatioPct(run.disaster_stop, { sign: false })}`} />
            <Cell label="K 線 / 成交" value={`${run.bars} / ${run.fills}`}
                  sub={run.last_bar ? `收 ${formatDecimal(run.last_bar.close)} · ${run.last_bar.disposition ?? ""}` : undefined} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 items-start">
            <div className="lg:col-span-8 space-y-3 min-w-0">
              <Panel title="成交" meta={<span className="text-t1 font-mono text-muted-foreground">{run.fill_rows.length} 筆</span>}>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead><tr className="border-b border-border/70 text-t1 text-muted-foreground">
                      {["時間", "腿", "方向", "張數", "價格", "手續費", "狀態"].map((c) => <th key={c} className="px-2 py-1.5 font-medium whitespace-nowrap">{c}</th>)}
                    </tr></thead>
                    <tbody className="divide-y divide-border/40">
                      {run.fill_rows.length === 0 && <tr><td colSpan={7} className="px-2 py-4 text-center text-muted-foreground">無</td></tr>}
                      {run.fill_rows.map((f, i) => (
                        <tr key={`${f.cl_ord_id}-${i}`}>
                          <td className="px-2 py-1.5 whitespace-nowrap text-muted-foreground">{formatDateTime(f.time_ms)}</td>
                          <td className="px-2 py-1.5 whitespace-nowrap">{f.leg}</td>
                          <td className={cn("px-2 py-1.5", f.side === "buy" ? "text-up" : "text-down")}>{f.side === "buy" ? "買" : "賣"}</td>
                          <td className="px-2 py-1.5">{f.quantity}</td>
                          <td className="px-2 py-1.5 whitespace-nowrap">{f.prices.join(" / ")}</td>
                          <td className="px-2 py-1.5 whitespace-nowrap text-muted-foreground">{f.fees.map((x) => formatDecimal(x, { digits: 4 })).join(" / ")}</td>
                          <td className={cn("px-2 py-1.5", f.state === "FILLED" ? "text-muted-foreground" : "text-amber-400")}>{f.state}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>

              <Panel title="事件" meta={<span className="text-t1 font-mono text-muted-foreground">最近 {run.events.length} 筆</span>}>
                <div className="max-h-80 overflow-y-auto divide-y divide-border/40 text-xs font-mono">
                  {run.events.length === 0 && <div className="py-3 text-center text-muted-foreground">無</div>}
                  {run.events.map((e, i) => (
                    <div key={i} className="flex gap-3 py-1">
                      <span className="w-24 shrink-0 text-muted-foreground">{formatDateTime(e.time_ms)}</span>
                      <span className={cn("w-24 shrink-0", EVENT_ALERT.has(e.kind) ? "text-amber-400" : "text-foreground")}>
                        {EVENT_LABEL[e.kind] ?? e.kind}</span>
                      <span className="truncate text-muted-foreground">{eventDetail(e)}</span>
                    </div>
                  ))}
                </div>
              </Panel>
            </div>

            <div className="lg:col-span-4 space-y-3 min-w-0">
              <Panel title="設定">
                <div className="space-y-1 text-t2">
                  <Row label="run" value={shortId(run.run_id)} />
                  <Row label="策略" value={`${run.strategy_id ?? ""} ${run.version ?? ""}`} />
                  <Row label="參數" value={run.parameters ? Object.values(run.parameters).join(" / ") : "不適用"} />
                  <Row label="週期 · 張數" value={`${formatTimeframe(run.timeframe_ms)} · ${run.quantity ?? ""}`} />
                  <Row label="核准" value={shortId(run.approval_id)} />
                  <Row label="開始" value={formatDateTime(run.created_at_ms)} />
                  <Row label="接續" value={`${run.resumes} 次`} />
                  {run.protection?.algo_id && <Row label="停損 algoId" value={run.protection.algo_id} />}
                </div>
              </Panel>

              <Panel title="歷史 run" meta={<span className="text-t1 font-mono text-muted-foreground">{overview?.runs.length ?? 0}</span>}>
                <div className="divide-y divide-border/40 text-xs font-mono">
                  {(overview?.runs ?? []).map((r) => {
                    const rh = health(r);
                    return (
                      <button key={r.run_id} onClick={() => setSelected(r.run_id === currentId ? null : r.run_id)}
                              className={cn("w-full flex items-center gap-2 py-1.5 px-1 text-left hover:bg-secondary/40 cursor-pointer",
                                r.run_id === run.run_id && "bg-secondary/60")}>
                        <span className="text-muted-foreground w-24 shrink-0">{formatDateTime(r.created_at_ms)}</span>
                        <span className="w-16 shrink-0">{shortId(r.run_id)}</span>
                        <span className={cn("w-14 shrink-0", rh.tone)}>{rh.label}</span>
                        <span className="text-muted-foreground truncate">{r.fills} 筆 · {formatTimeframe(r.timeframe_ms)}</span>
                      </button>
                    );
                  })}
                </div>
              </Panel>
            </div>
          </div>
        </>
      )}
    </AppShell>
  );
}
