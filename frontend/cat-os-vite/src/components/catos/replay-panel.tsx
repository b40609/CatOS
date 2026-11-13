import { useEffect, useState } from "react";
import { Panel } from "@/components/catos/shell";
import { fetchReplayOverview } from "@/adapters/replay-api-adapter";
import type { ReplayOverviewDTO, ReplayRunDTO } from "@/contracts/replay";
import { formatDateTimeWithYear, formatDecimal, formatTimeframe, shortId } from "@/lib/format";
import { cn } from "@/lib/utils";

const POLL_MS = 2000;

const RUN_STATE: Record<ReplayRunDTO["state"], string> = {
  running: "重播中",
  completed: "完成",
  stopped: "已停止",
  failed: "失敗",
  unknown: "未知",
};

function params(value: Record<string, number>) {
  return Object.entries(value).map(([k, v]) => `${k} ${v}`).join(" · ");
}

function progress(run: ReplayRunDTO) {
  if (!run.bars) return "不適用";
  const pct = Math.floor((run.bars_done * 1000) / run.bars) / 10;
  return `${run.bars_done} / ${run.bars}（${pct}%）`;
}

/** Read-only: approval records and Bot replays. Approve, revoke and replay stay CLI-only. */
export function ReplayPanel() {
  const [data, setData] = useState<ReplayOverviewDTO | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = async () => {
      const result = await fetchReplayOverview(controller.signal);
      if (controller.signal.aborted) return;
      if (result.ok) {
        setData(result.data);
        setError(null);
      } else {
        setError(result.error);
      }
      timer = setTimeout(load, POLL_MS);
    };
    void load();
    return () => {
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, []);

  return (
    <Panel
      title="deployment · 研究策略上 Bot（核准與歷史重播）"
      meta={<span className="label-xs">唯讀 · 核准與重播只用 CLI</span>}
    >
      {!data ? (
        <p className="py-4 text-center font-mono text-xs text-muted-foreground">
          {error ? `無法讀取：${error}` : "讀取中…"}
        </p>
      ) : (
        <div className="space-y-3" data-testid="replay-panel">
          <div>
            <p className="label-xs mb-1">核准紀錄 · {data.approvals_state === "available" ? `${data.approvals.length} 筆` : "不可用"}</p>
            {data.approvals.length === 0 ? (
              <p className="text-t2 text-muted-foreground">
                尚無核准。可上 Bot 的研究策略：
                {data.eligible.map((e) => ` ${e.strategy_id}/${e.version}`).join("、")}
              </p>
            ) : (
              <dl className="space-y-px">
                {data.approvals.map((a) => (
                  <div key={a.approval_id} className="border-b border-border/60 py-1.5 text-xs last:border-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className="num truncate font-semibold text-foreground" title={a.approval_id}>
                        {a.strategy_id} · {params(a.parameters)} · {a.quantity} 張
                      </span>
                      <span
                        className={cn(
                          "num shrink-0",
                          a.state === "active" && a.source === "current" ? "text-up" : "text-down",
                        )}
                      >
                        {a.state === "revoked" ? "已撤銷" : a.source === "current" ? "有效" : "來源已變更"}
                      </span>
                    </div>
                    <div className="num mt-0.5 flex flex-wrap gap-x-3 text-t2 text-muted-foreground">
                      <span>{a.inst_id} · {formatTimeframe(a.timeframe_ms)} · 預熱 {a.warmup_bars}</span>
                      <span>本金 {formatDecimal(a.initial_balance, { prefix: "$", digits: 0 })}</span>
                      <span title={a.source_sha256}>sha256 {shortId(a.source_sha256, 12)}</span>
                      <span>id {shortId(a.approval_id, 12)}</span>
                    </div>
                  </div>
                ))}
              </dl>
            )}
          </div>

          <div>
            <p className="label-xs mb-1">重播紀錄 · {data.runs.length} 筆</p>
            {data.runs.length === 0 ? (
              <p className="text-t2 text-muted-foreground">尚無重播</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="label-xs text-left">
                      <th className="py-1 pr-3 font-normal">run</th>
                      <th className="py-1 pr-3 font-normal">狀態</th>
                      <th className="py-1 pr-3 font-normal">進度</th>
                      <th className="py-1 pr-3 font-normal">成交</th>
                      <th className="py-1 pr-3 font-normal">期末權益</th>
                      <th className="py-1 pr-3 font-normal">一致性</th>
                      <th className="py-1 font-normal">資料到</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.runs.map((r) => (
                      <tr key={r.run_id} className="num border-t border-border/60">
                        <td className="py-1 pr-3" title={`${r.strategy_id} ${params(r.parameters)} · ${r.dataset_id ?? ""}`}>
                          {shortId(r.run_id)}
                        </td>
                        <td className="py-1 pr-3" title={r.stop_reason ?? undefined}>
                          {RUN_STATE[r.state] ?? r.state}
                          {r.stop_reason ? ` · ${r.stop_reason}` : ""}
                        </td>
                        <td className="py-1 pr-3">{progress(r)}</td>
                        <td className="py-1 pr-3">{r.fills ?? "不適用"}</td>
                        <td className="py-1 pr-3">{formatDecimal(r.final_equity, { prefix: "$" })}</td>
                        <td
                          className={cn(
                            "py-1 pr-3",
                            r.consistency?.passed === true ? "text-up" : r.consistency ? "text-down" : "text-muted-foreground",
                          )}
                        >
                          {r.consistency ? (r.consistency.passed ? "PASS（誤差 0）" : "FAIL") : "未比對"}
                        </td>
                        <td className="py-1">{formatDateTimeWithYear(r.last_time_ms)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          <p className="text-t2 text-muted-foreground" title={`核准檔：${data.approvals_path}`}>{data.notice}</p>
          {data.issues.length > 0 && <p className="text-t2 text-down">{data.issues.join("、")}</p>}
        </div>
      )}
    </Panel>
  );
}
