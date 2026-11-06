import { Panel } from "@/components/catos/shell";
import type { OverfittingReport, SelectionEdges } from "@/adapters/research-api-adapter";
import { cn } from "@/lib/utils";
import { compareDecimal } from "@/lib/format";

function paramsText(params: [string, number | string][]) {
  return params.map(([name, value]) => `${name}=${value}`).join(", ");
}

/** Threshold tone on a probability string, compared as exact decimals. */
function dsrTone(value: string | null) {
  if (value === null) return "text-muted-foreground";
  if ((compareDecimal(value, "0.95") ?? -1) >= 0) return "text-emerald-400 font-semibold";
  if ((compareDecimal(value, "0.5") ?? -1) >= 0) return "text-amber-400 font-semibold";
  return "text-rose-400 font-semibold";
}

function pboTone(value: string | undefined) {
  if (value === undefined) return "text-muted-foreground";
  if ((compareDecimal(value, "0.2") ?? 1) <= 0) return "text-emerald-400 font-semibold";
  if ((compareDecimal(value, "0.5") ?? 1) <= 0) return "text-amber-400 font-semibold";
  return "text-rose-400 font-semibold";
}

function Row({ label, value, tone, hint }: { label: string; value: string; tone?: string; hint?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border/50 py-1.5 last:border-b-0">
      <span className="text-muted-foreground" title={hint}>{label}</span>
      <span className={cn("font-mono text-foreground", tone)}>{value}</span>
    </div>
  );
}

export function OverfittingPanel({ report, earlierSearches }: { report: OverfittingReport | null | undefined; earlierSearches: number }) {
  return (
    <Panel title="過擬合檢查（DSR／PBO）" meta={<span className="text-t2 font-mono text-muted-foreground">Bailey & López de Prado</span>}>
      {!report ? (
        <p className="py-3 text-center text-xs text-muted-foreground">這筆結果沒有過擬合檢查（功能上線前的舊紀錄，或沒有完成的試驗）。</p>
      ) : (
        <div data-testid="optimization-overfitting" data-dsr={report.dsr ?? ""} data-pbo={report.pbo?.pbo ?? ""} className="text-xs">
          <p className="mb-2 rounded border border-border/60 bg-surface/40 px-2.5 py-1.5 text-muted-foreground">{report.verdict}</p>
          <div className="grid grid-cols-1 gap-x-6 md:grid-cols-2">
            <div>
              <Row label="不同參數組數 N（只計本次）" value={`${report.distinct_trials} 組`}
                hint="TPE 可能重複抽到同一組；N 只計實際評估過的不同組合" />
              <Row label="最佳參數" value={paramsText(report.best.params)} />
              <Row label="最佳 Sharpe（年化）" value={report.best.sharpe_annualized}
                hint={`每根 ${report.best.sharpe_per_bar} · 偏態 ${report.best.skew} · 峰態 ${report.best.kurtosis}`} />
              <Row label="純運氣可期待的最大 Sharpe（年化）" value={report.expected_max_sharpe_annualized}
                hint="N 組都沒有優勢時，最好那組的 Sharpe 期望值" />
            </div>
            <div>
              <Row label="PSR（真實 Sharpe > 0）" value={report.psr_vs_zero ?? "不適用"} tone={dsrTone(report.psr_vs_zero)} />
              <Row label="DSR（扣多重試驗後）" value={report.dsr ?? "不適用"} tone={dsrTone(report.dsr)}
                hint="≥ 0.95 才算顯著" />
              <Row label="PBO（CSCV）" value={report.pbo ? `${report.pbo.pbo}（${report.pbo.splits} 種切法）` : "樣本不足"}
                tone={pboTone(report.pbo?.pbo)} hint="樣本內冠軍在樣本外落到中位數以下的比例" />
              <Row label="樣本外虧損比例" value={report.pbo?.prob_oos_loss ?? "不適用"} />
            </div>
          </div>
          <p className="mt-2 text-t2 text-muted-foreground">
            {report.notice}
            {earlierSearches > 0 && ` 本清單中同資料集、同策略還有 ${earlierSearches} 筆其他優化任務，實際試驗數比 N 多。`}
          </p>
        </div>
      )}
    </Panel>
  );
}

export function SelectionEdgesNote({ edges }: { edges: SelectionEdges | undefined }) {
  if (!edges || edges.windows_at_edge === 0) return null;
  const detail = Object.entries(edges.params)
    .filter(([, counts]) => counts.at_low || counts.at_high)
    .map(([name, counts]) => `${name}：下限 ${counts.at_low} 窗、上限 ${counts.at_high} 窗`)
    .join("；");
  return (
    <div data-testid="validation-selection-edges"
         className="rounded border border-amber-400/30 bg-amber-400/5 px-3 py-2 text-xs text-muted-foreground">
      <span className="font-semibold text-amber-400/90">
        {edges.windows_at_edge} / {edges.windows_with_selection} 窗的選定參數落在搜尋範圍邊界
      </span>
      <span className="ml-2 font-mono">{detail}</span>
      <p className="mt-1 text-t2">{edges.notice}</p>
    </div>
  );
}
