import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState, type ChangeEvent } from "react";
import { Loader2, RefreshCw, AlertCircle, Route as RouteIcon, Layers } from "lucide-react";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from "recharts";
import { AppShell, PageHead, Panel } from "@/components/catos/shell";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { researchApi } from "@/adapters/research-api-adapter";
import type {
  ResearchRunStatus,
  ValidationRequest,
  ValidationResultPayload,
  ValidationWindow,
} from "@/adapters/research-api-adapter";
import { useResearchRuns } from "@/hooks/use-research-runs";
import { DatasetPicker, pickDataset } from "@/components/catos/dataset-picker";
import { StrategyPicker } from "@/components/catos/strategy-picker";
import { compareDecimal, formatDecimal, formatDrawdownPct, signOf, toPlotNumber, toneOf } from "@/lib/format";
import {
  type Axis, formatRanges, formatTrialParams, paramLabel, paramSpecs, pickStrategy, shortName,
} from "@/lib/research-strategies";
import {
  VALIDATION_BACKTEST,
  barEvaluations,
  barsUsed,
  buildValidationRequest,
  candidateCount,
  defaultValidationForm,
  requiredRuns,
  validationProblems,
  warmupBars,
  type ValidationForm,
} from "@/lib/validation-plan";

export const Route = createFileRoute("/validation")({
  head: () => ({
    meta: [
      { title: "滾動驗證 (Walk-Forward) — catOS Quant Terminal" },
      { name: "description", content: "catOS 滾動驗證：訓練窗穩定區選參、獨立樣本外視窗檢驗與分環境歸屬。" },
    ],
  }),
  component: ValidationPage,
});

const NA = "不適用";

type IntegerField = { [K in keyof ValidationForm]: ValidationForm[K] extends number ? K : never }[keyof ValidationForm];

const REGIME_NAMES: Record<string, string> = {
  UNKNOWN: "未知（歷史不足）",
  UP_LOW: "上漲 · 低波動",
  UP_HIGH: "上漲 · 高波動",
  DOWN_LOW: "下跌 · 低波動",
  DOWN_HIGH: "下跌 · 高波動",
  RANGE_LOW: "震盪 · 低波動",
  RANGE_HIGH: "震盪 · 高波動",
};

const pad = (n: number) => String(n).padStart(2, "0");

/** `MM/DD HH:mm` in UTC, matching the archived report. */
function formatUtcMinute(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return NA;
  const d = new Date(ms);
  if (isNaN(d.getTime())) return NA;
  return `${pad(d.getUTCMonth() + 1)}/${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}

function formatUtcRange(start: number, end: number): string {
  return `${formatUtcMinute(start)} → ${formatUtcMinute(end)}`;
}

function formatCreated(iso: string | null | undefined): string {
  if (!iso) return NA;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return `${formatUtcMinute(d.getTime())}:${pad(d.getUTCSeconds())} UTC`;
}

function selectedTrial(window: ValidationWindow) {
  const number = window.training.selected_trial_number;
  return number === null ? null : window.training.trials[number] ?? null;
}

function paramsOf(params: [string, number | string][] | undefined): string {
  return formatTrialParams(params) || NA;
}

const pct = (value: string | null | undefined) => formatDecimal(value, { digits: 2, sign: true, suffix: "%" }, NA);
const usdt = (value: string | null | undefined) => formatDecimal(value, { digits: 2, sign: true }, NA);
const plain = (value: string | null | undefined) => formatDecimal(value, { digits: 2 }, NA);

function statusTone(status: string) {
  return status === "COMPLETE" || status === "complete"
    ? "bg-up/15 text-up border border-up/30"
    : status === "running" || status === "queued"
    ? "bg-primary/15 text-primary border border-primary/30"
    : "bg-down/15 text-down border border-down/30";
}

function runSummary(run: ResearchRunStatus) {
  const request = run.request as ValidationRequest | undefined;
  const plan = request?.plan;
  if (!request?.search_space || !plan) return NA;
  return `${shortName(request.backtest?.strategy_id)} ${formatRanges(request.search_space)} · ${plan.windows} 窗 · 訓練 ${plan.train_bars} / 測試 ${plan.test_bars} 根`;
}

function OosEquityChart({ window, initialBalance }: { window: ValidationWindow; initialBalance: string }) {
  const curve = window.out_of_sample?.equity_curve ?? [];
  const multiDay = curve.length > 1 && curve[curve.length - 1].time_ms - curve[0].time_ms > 86_400_000;
  // Plot numbers are geometry only; the tooltip shows the original Decimal string.
  const data = curve.map((point) => {
    const d = new Date(point.time_ms);
    return {
      label: multiDay ? `${pad(d.getUTCMonth() + 1)}/${pad(d.getUTCDate())}` : `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`,
      equity: toPlotNumber(point.equity),
      equityText: point.equity,
      time: formatUtcMinute(point.time_ms),
    };
  });
  const tone = signOf(window.out_of_sample?.performance.net_pnl) === "negative" ? "var(--color-down)" : "var(--color-up)";
  return (
    <div className="h-[150px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 5, right: 10, left: -12, bottom: 0 }}>
          <defs>
            <linearGradient id="oosEquityGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={tone} stopOpacity={0.3} />
              <stop offset="95%" stopColor={tone} stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" opacity={0.3} />
          <XAxis dataKey="label" tick={{ fontSize: 9, fill: "var(--color-muted-foreground)" }} minTickGap={24} />
          <YAxis domain={["dataMin", "dataMax"]} tick={{ fontSize: 9, fill: "var(--color-muted-foreground)" }}
                 tickFormatter={(v: number) => v.toFixed(0)} width={52} />
          <ReferenceLine y={toPlotNumber(initialBalance)} stroke="var(--color-muted-foreground)" strokeDasharray="4 4" />
          <Tooltip
            contentStyle={{ backgroundColor: "var(--color-surface)", borderColor: "var(--color-border)", fontSize: "11px", fontFamily: "var(--font-mono)" }}
            labelFormatter={(_label: string, items: { payload?: { time?: string } }[]) => `${items?.[0]?.payload?.time ?? ""} UTC`}
            formatter={(_v: number, _name: string, item: { payload?: { equityText?: string } }) =>
              [formatDecimal(item.payload?.equityText, { prefix: "$", suffix: " USDT" }, NA), "OOS 權益"]}
          />
          <Area type="monotone" dataKey="equity" stroke={tone} strokeWidth={1.6} fill="url(#oosEquityGrad)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function WindowDetail({ result, window }: { result: ValidationResultPayload; window: ValidationWindow }) {
  const diagnostic = result.result.windows.find((row) => row.number === window.number);
  const evaluation = diagnostic?.evaluation ?? null;
  const neighborhoods = new Map(window.training.neighborhoods.map((row) => [row.trial_number, row]));
  const oos = window.out_of_sample;
  return (
    <Panel
      title={
        <div className="flex items-center gap-2">
          <Layers className="size-3.5 text-primary" />
          <span>視窗 #{window.number} · OOS {formatUtcRange(window.test_start_ms, window.test_end_ms)} UTC</span>
        </div>
      }
      meta={
        window.curve_sampling ? (
          <span className="text-t2 font-mono text-muted-foreground" title="每段保留回撤最深的一點並保留起點；績效數字以全部 K 線計算">
            圖表取樣 {window.curve_sampling.returned_points.toLocaleString()} / {window.curve_sampling.total_points.toLocaleString()} 點
          </span>
        ) : undefined
      }
    >
      {oos ? (
        <div className="space-y-1">
          <div className="flex flex-wrap items-center justify-between gap-2 text-t2 font-mono text-muted-foreground">
            <span>樣本外權益（USDT，每窗從本金 {formatDecimal(result.request.backtest.initial_balance, { digits: 0 })} 獨立起算；虛線為本金）</span>
            <span className={toneOf(oos.performance.net_pnl)}>
              {pct(oos.performance.return_pct)} · 最大回撤 {formatDrawdownPct(oos.performance.max_drawdown_pct, NA)}
            </span>
          </div>
          <OosEquityChart window={window} initialBalance={result.request.backtest.initial_balance} />
        </div>
      ) : (
        <div className="rounded border border-down/30 bg-down/5 px-3 py-2 text-xs font-mono text-down">
          此視窗沒有樣本外結果（{window.status}）：{window.error ?? "訓練格點沒有可選的穩定區"}。不以 0 計入。
        </div>
      )}

      <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-2">
        <div className="min-w-0">
          <p className="text-t2 font-mono text-muted-foreground mb-1">
            訓練格點（{formatUtcRange(window.train_start_ms, window.train_end_ms)} UTC · 規則 {window.training.selection_rule}）
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead className="border-b border-border text-t2 font-mono text-muted-foreground bg-background/30">
                <tr>
                  <th className="py-1.5 px-2 font-normal">參數</th>
                  <th className="py-1.5 px-2 text-right font-normal">訓練評分</th>
                  <th className="py-1.5 px-2 text-right font-normal">鄰域最差</th>
                  <th className="py-1.5 px-2 text-right font-normal">鄰域平均</th>
                  <th className="py-1.5 px-2 text-right font-normal">成交</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40 font-mono">
                {window.training.trials.map((trial) => {
                  const chosen = trial.number === window.training.selected_trial_number;
                  const neighborhood = neighborhoods.get(trial.number);
                  return (
                    <tr key={trial.number} className={cn(chosen && "bg-primary/10")}>
                      <td className="py-1.5 px-2">
                        <span className={cn("font-semibold", chosen ? "text-primary" : "text-foreground")}>
                          {paramsOf(trial.params)}
                        </span>
                        {chosen && <span className="ml-1 bg-primary text-primary-foreground text-t1 px-1 rounded">選定</span>}
                        {trial.error && <span className="ml-1 text-t1 text-down" title={trial.error}>錯誤</span>}
                      </td>
                      <td className="py-1.5 px-2 text-right" title={trial.score ?? undefined}>{pct(trial.score)}</td>
                      <td className="py-1.5 px-2 text-right text-muted-foreground" title={neighborhood?.worst_score ?? undefined}>
                        {pct(neighborhood?.worst_score)}
                      </td>
                      <td className="py-1.5 px-2 text-right text-muted-foreground" title={neighborhood?.mean_score ?? undefined}>
                        {pct(neighborhood?.mean_score)}
                      </td>
                      <td className="py-1.5 px-2 text-right text-muted-foreground">{trial.performance?.trade_count ?? NA}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div className="min-w-0">
          <p className="text-t2 font-mono text-muted-foreground mb-1">
            樣本外分環境歸屬（規則 {result.result.rule_version}；環境標籤只用前一根已收盤 K 線）
          </p>
          {evaluation ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead className="border-b border-border text-t2 font-mono text-muted-foreground bg-background/30">
                  <tr>
                    <th className="py-1.5 px-2 font-normal">環境</th>
                    <th className="py-1.5 px-2 text-right font-normal">K 線</th>
                    <th className="py-1.5 px-2 text-right font-normal">正／負／零</th>
                    <th className="py-1.5 px-2 text-right font-normal">成交</th>
                    <th className="py-1.5 px-2 text-right font-normal">淨損益</th>
                    <th className="py-1.5 px-2 text-right font-normal">手續費</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40 font-mono">
                  {[...evaluation.summaries, evaluation.total].map((row) => {
                    const total = row === evaluation.total;
                    return (
                      <tr key={total ? "ALL" : row.regime}
                          className={cn(total && "border-t border-border font-semibold", !total && row.bar_count === 0 && "text-muted-foreground/60")}>
                        <td className="py-1.5 px-2" title={row.regime}>{total ? "合計" : REGIME_NAMES[row.regime] ?? row.regime}</td>
                        <td className="py-1.5 px-2 text-right">{row.bar_count.toLocaleString()}</td>
                        <td className="py-1.5 px-2 text-right text-muted-foreground">
                          {row.positive_bars}／{row.negative_bars}／{row.zero_bars}
                        </td>
                        <td className="py-1.5 px-2 text-right text-muted-foreground">{row.fill_count}</td>
                        <td className={cn("py-1.5 px-2 text-right", row.bar_count ? toneOf(row.net_pnl) : "")} title={row.net_pnl}>
                          {usdt(row.net_pnl)}
                        </td>
                        <td className="py-1.5 px-2 text-right text-muted-foreground" title={row.fees}>{plain(row.fees)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p className="mt-1.5 text-t2 font-mono text-muted-foreground">
                {evaluation.reconciled ? "與樣本外帳務核對一致" : "未核對"} · 淨損益已含手續費與資金費；K 線數不是獨立樣本或勝率
              </p>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground py-4">此視窗沒有樣本外結果，無分環境歸屬。</p>
          )}
        </div>
      </div>
    </Panel>
  );
}

function ValidationPage() {
  const {
    version, catalog, runs, selectedRun, realResult, loading, resultLoading,
    submitting, errorMsg, fetchRealData, selectRun, submit, isBusy,
  } = useResearchRuns<ValidationRequest, ValidationResultPayload>("validation", "驗證", researchApi.submitValidation);

  const [openDialog, setOpenDialog] = useState(false);
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const [strategyId, setStrategyId] = useState<string | null>(null);
  const [form, setForm] = useState<ValidationForm | null>(null);
  const [windowNumber, setWindowNumber] = useState(0);
  const dataset = pickDataset(catalog?.datasets, datasetId);
  const strategy = pickStrategy(catalog?.strategies, strategyId);
  const limits = catalog?.validation;

  useEffect(() => { setWindowNumber(0); }, [realResult?.run_id]);

  const resetForm = (id: string | null, sid: string | null) => {
    const target = pickDataset(catalog?.datasets, id);
    const meta = pickStrategy(catalog?.strategies, sid);
    if (target && meta && limits) setForm(defaultValidationForm(target, limits.example_request, meta));
  };
  const openSubmit = () => {
    if (!form || form.datasetId !== dataset?.id || form.strategyId !== strategy?.id) {
      resetForm(dataset?.id ?? null, strategy?.id ?? null);
    }
    setOpenDialog(true);
  };
  const changeDataset = (id: string) => {
    setDatasetId(id);
    resetForm(id, strategy?.id ?? null);
  };
  const changeStrategy = (sid: string) => {
    setStrategyId(sid);
    resetForm(dataset?.id ?? null, sid);
  };
  const setField = <K extends keyof ValidationForm>(key: K, value: ValidationForm[K]) =>
    setForm((current) => current && { ...current, [key]: value });
  const intField = (key: IntegerField) => (event: ChangeEvent<HTMLInputElement>) =>
    setField(key, parseInt(event.target.value, 10) || 0);
  const axisField = (name: string, key: keyof Axis) => (event: ChangeEvent<HTMLInputElement>) =>
    setForm((current) => current && {
      ...current, axes: { ...current.axes, [name]: { ...current.axes[name], [key]: parseInt(event.target.value, 10) || 0 } },
    });

  const problems = form && strategy ? validationProblems(form, dataset, limits, strategy) : [];
  const count = form && strategy ? candidateCount(form, strategy) : null;
  const handleSubmit = async () => {
    if (!form || !strategy || problems.length) return;
    if (await submit(buildValidationRequest(form, strategy))) setOpenDialog(false);
  };

  const windows = realResult?.result.validation.windows ?? [];
  const activeWindow = windows.find((w) => w.number === windowNumber) ?? windows[0] ?? null;
  const completeCount = windows.filter((w) => w.status === "COMPLETE").length;
  const oosReturns = windows.flatMap((w) => (w.out_of_sample ? [w.out_of_sample.performance.return_pct] : []));
  const positiveCount = oosReturns.filter((value) => signOf(value) === "positive").length;
  const best = oosReturns.reduce<string | null>((acc, v) => (acc === null || compareDecimal(v, acc) === 1 ? v : acc), null);
  const worst = oosReturns.reduce<string | null>((acc, v) => (acc === null || compareDecimal(v, acc) === -1 ? v : acc), null);
  const chosenParams = windows.reduce<Record<string, number>>((acc, w) => {
    const trial = selectedTrial(w);
    if (trial) acc[paramsOf(trial.params)] = (acc[paramsOf(trial.params)] ?? 0) + 1;
    return acc;
  }, {});
  const resultDataset = catalog?.datasets.find((d) => d.id === realResult?.request.backtest.dataset_id);

  return (
    <AppShell>
      <PageHead
        code="RESEARCH // WALK-FORWARD"
        title="滾動驗證"
        desc="訓練窗穩定區選參 · 獨立樣本外視窗 · 分環境歸屬 · 嚴格 Decimal 核心"
        right={
          <Button
            size="sm"
            disabled={!version || !catalog || loading || isBusy || version.restart_required}
            onClick={openSubmit}
            className="h-7 text-xs bg-primary text-primary-foreground hover:bg-primary/90 font-medium cursor-pointer"
          >
            {isBusy ? <Loader2 className="size-3.5 mr-1 animate-spin" /> : <RouteIcon className="size-3.5 mr-1" />}
            {isBusy ? "後端計算中..." : "發起滾動驗證"}
          </Button>
        }
      />

      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2.5 rounded-lg border border-border/80 bg-surface/90 px-3.5 py-2 text-xs font-mono shadow-xs backdrop-blur-md">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-muted-foreground">
              選參規則: <strong className="text-primary font-semibold">maximin_axis_neighbors_v1 · 完整格點</strong>
            </span>
            <span className="text-border">|</span>
            <span className="text-muted-foreground">
              目標函式: <strong className="text-foreground">return_pct (Maximize)</strong>
            </span>
            <span className="text-border">|</span>
            <span className="text-muted-foreground">
              上限: <strong className="text-foreground">
                {limits ? `${limits.max_windows} 窗 · ${limits.max_runs} 次回測 · 計算量 ${limits.max_bar_evaluations.toLocaleString()}` : NA}
              </strong>
            </span>
          </div>
          <div className="flex items-center gap-2">
            {version?.restart_required && (
              <span className="text-amber-400 font-medium text-t3 bg-amber-500/10 border border-amber-500/25 px-2 py-0.5 rounded">
                服務源檔案已異動 (restart_required)
              </span>
            )}
            {isBusy && (
              <span className="text-primary font-medium text-t3 flex items-center gap-1 bg-primary/10 border border-primary/25 px-2 py-0.5 rounded">
                <Loader2 className="size-3 animate-spin" /> 後端忙碌中
              </span>
            )}
          </div>
        </div>

        {errorMsg && (
          <div className="flex items-center gap-2 rounded-lg border border-down/40 bg-down/10 px-3.5 py-2 text-xs text-down font-mono">
            <AlertCircle className="size-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-12 items-start">
          <div className="lg:col-span-4 space-y-3">
            <Panel
              title="歷史驗證任務 (Validation Runs)"
              meta={
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={fetchRealData}
                  className="h-6 px-2 text-t2 font-mono text-muted-foreground hover:text-foreground"
                >
                  <RefreshCw className={cn("size-3 mr-1", loading && "animate-spin")} /> 刷新
                </Button>
              }
            >
              {runs.length === 0 ? (
                <p className="text-xs text-muted-foreground py-6 text-center">
                  目前尚無驗證任務紀錄，點擊右上角發起新任務。
                </p>
              ) : (
                <div className="space-y-1.5 max-h-[480px] overflow-y-auto pr-1">
                  {runs.map((r) => {
                    const isSelected = selectedRun?.run_id === r.run_id;
                    const runDataset = catalog?.datasets.find((d) => d.id === (r.request as ValidationRequest | undefined)?.backtest?.dataset_id);
                    return (
                      <div
                        key={r.run_id}
                        onClick={() => selectRun(r)}
                        className={cn(
                          "rounded-lg border p-2.5 cursor-pointer transition-colors text-xs font-mono",
                          isSelected ? "border-primary bg-primary/10" : "border-border/60 bg-background/40 hover:bg-secondary/40"
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-foreground truncate max-w-[140px]">#{r.run_id.slice(0, 8)}</span>
                          <span className={cn("text-t1 px-1.5 py-0.2 rounded font-semibold uppercase", statusTone(r.status))}>
                            {r.status}
                          </span>
                        </div>
                        <p className="text-t2 text-muted-foreground mt-1">建立時間: {formatCreated(r.created_at)}</p>
                        <p className="text-t2 text-muted-foreground truncate" title={runDataset?.name}>
                          資料集: {runDataset?.name ?? (r.request as ValidationRequest | undefined)?.backtest?.dataset_id ?? NA}
                        </p>
                        <p className="text-t2 text-muted-foreground">{runSummary(r)}</p>
                      </div>
                    );
                  })}
                </div>
              )}
            </Panel>

            <Panel title="驗證邊界與輸出">
              <div className="space-y-2 text-xs text-muted-foreground leading-relaxed">
                <p>
                  <strong className="text-foreground">獨立視窗:</strong> 每個樣本外視窗都從本金重新起算、空倉開始，不是連續投資組合；不串接權益曲線，也不是部署通過門檻。較早的樣本外資料會進入之後視窗的訓練。
                </p>
                <p>
                  <strong className="text-foreground">選參:</strong> 每窗先跑完整格點，依鄰域最差分數（maximin）選穩定區；選定後才建立樣本外策略，分環境標籤不回饋選參。
                </p>
                <p>
                  <strong className="text-foreground">輸出 v2:</strong> 不保存逐根環境標籤與逐根歸屬（可由綁定的資料與規則重算）；每窗樣本外權益曲線超過上限時取樣，績效與分環境合計以全部 K 線計算。
                </p>
              </div>
            </Panel>
          </div>

          <div className="lg:col-span-8 space-y-3">
            {resultLoading ? (
              <Panel title="驗證結果載入中">
                <div className="py-16 text-center text-xs text-muted-foreground flex flex-col items-center justify-center gap-2">
                  <Loader2 className="size-6 animate-spin text-primary" />
                  <span>讀取封存驗證結果中...</span>
                </div>
              </Panel>
            ) : realResult && activeWindow ? (
              <>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 font-mono">
                  <div className="rounded-lg border border-border/80 bg-surface/90 p-3 shadow-xs">
                    <span className="text-t2 text-muted-foreground block">視窗狀態</span>
                    <span className={cn("text-base font-bold mt-0.5 block", realResult.evaluation_complete ? "text-up" : "text-down")}>
                      {completeCount} / {windows.length} COMPLETE
                    </span>
                    <span className="text-t1 text-muted-foreground">
                      {realResult.evaluation_complete ? "每窗皆有樣本外結果" : "部分視窗無樣本外結果"}
                    </span>
                  </div>
                  <div className="rounded-lg border border-border/80 bg-surface/90 p-3 shadow-xs">
                    <span className="text-t2 text-muted-foreground block">選定參數（各窗）</span>
                    <span className="text-base font-bold text-primary mt-0.5 block truncate"
                          title={Object.entries(chosenParams).map(([params, n]) => `${params} ×${n}`).join("\n")}>
                      {Object.keys(chosenParams).length
                        ? Object.entries(chosenParams).map(([params, n]) => `${params}×${n}`).join(" · ")
                        : NA}
                    </span>
                    <span className="text-t1 text-muted-foreground block truncate">
                      {shortName(realResult.request.backtest.strategy_id)} · {formatRanges(realResult.request.search_space)}
                    </span>
                  </div>
                  <div className="rounded-lg border border-border/80 bg-surface/90 p-3 shadow-xs">
                    <span className="text-t2 text-muted-foreground block">樣本外報酬（各窗獨立）</span>
                    <span className="text-base font-bold text-foreground mt-0.5 block">
                      {positiveCount} / {oosReturns.length} 窗為正
                    </span>
                    <span className="text-t1 text-muted-foreground">最佳 {pct(best)} · 最差 {pct(worst)}</span>
                  </div>
                  <div className="rounded-lg border border-border/80 bg-surface/90 p-3 shadow-xs">
                    <span className="text-t2 text-muted-foreground block">計算預算</span>
                    <span className="text-base font-bold text-foreground mt-0.5 block">
                      {realResult.result.validation.attempted_runs} / {realResult.result.validation.max_runs} 次回測
                    </span>
                    <span className="text-t1 text-muted-foreground">
                      未使用 K 線 {realResult.result.validation.unused_bars.toLocaleString()} 根
                    </span>
                  </div>
                </div>

                <Panel
                  title={
                    <div className="flex items-center gap-2">
                      <RouteIcon className="size-3.5 text-primary" />
                      <span>各視窗樣本外結果 (Walk-Forward Windows · Decimal)</span>
                    </div>
                  }
                  meta={
                    <span className="text-t2 font-mono text-muted-foreground truncate max-w-[320px]" title={resultDataset?.name}>
                      {resultDataset?.name ?? realResult.request.backtest.dataset_id} · Run {realResult.run_id?.slice(0, 8)}
                    </span>
                  }
                >
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead className="border-b border-border text-t2 font-mono text-muted-foreground bg-background/30">
                        <tr>
                          <th className="py-2 px-2 font-normal">視窗</th>
                          <th className="py-2 px-2 font-normal">狀態</th>
                          <th className="py-2 px-2 font-normal">樣本外區間 (UTC)</th>
                          <th className="py-2 px-2 text-right font-normal">選定參數</th>
                          <th className="py-2 px-2 text-right font-normal">訓練評分</th>
                          <th className="py-2 px-2 text-right font-normal">OOS 報酬</th>
                          <th className="py-2 px-2 text-right font-normal">淨損益 (USDT)</th>
                          <th className="py-2 px-2 text-right font-normal">最大回撤</th>
                          <th className="py-2 px-2 text-right font-normal">手續費</th>
                          <th className="py-2 px-2 text-right font-normal">資金費</th>
                          <th className="py-2 px-2 text-right font-normal">成交</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/40 font-mono">
                        {windows.map((w) => {
                          const trial = selectedTrial(w);
                          const perf = w.out_of_sample?.performance;
                          const active = w.number === activeWindow.number;
                          return (
                            <tr
                              key={w.number}
                              onClick={() => setWindowNumber(w.number)}
                              className={cn("cursor-pointer transition-colors", active ? "bg-primary/10" : "hover:bg-secondary/30")}
                            >
                              <td className="py-2 px-2 font-bold text-foreground">#{w.number}</td>
                              <td className="py-2 px-2">
                                <span className={cn("text-t1 px-1.5 py-0.2 rounded font-semibold", statusTone(w.status))} title={w.error ?? undefined}>
                                  {w.status}
                                </span>
                              </td>
                              <td className="py-2 px-2 text-muted-foreground whitespace-nowrap">{formatUtcRange(w.test_start_ms, w.test_end_ms)}</td>
                              <td className="py-2 px-2 text-right font-semibold text-primary">{trial ? paramsOf(trial.params) : NA}</td>
                              <td className="py-2 px-2 text-right text-muted-foreground" title={trial?.score ?? undefined}>{pct(trial?.score)}</td>
                              <td className={cn("py-2 px-2 text-right", toneOf(perf?.return_pct))} title={perf?.return_pct}>{pct(perf?.return_pct)}</td>
                              <td className="py-2 px-2 text-right text-foreground" title={perf?.net_pnl}>{usdt(perf?.net_pnl)}</td>
                              <td className="py-2 px-2 text-right text-muted-foreground" title={perf?.max_drawdown_pct}>
                                {perf ? formatDrawdownPct(perf.max_drawdown_pct, NA) : NA}
                              </td>
                              <td className="py-2 px-2 text-right text-muted-foreground" title={perf?.fees}>{plain(perf?.fees)}</td>
                              <td className="py-2 px-2 text-right text-muted-foreground" title={perf?.funding_paid}>{plain(perf?.funding_paid)}</td>
                              <td className="py-2 px-2 text-right text-muted-foreground">{perf ? perf.trade_count : NA}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <div className="mt-3 pt-2.5 border-t border-border/40 text-t2 font-mono text-muted-foreground space-y-0.5">
                    <p>聲明: {realResult.data_notice}</p>
                    <p>點選列查看該窗曲線、訓練格點與分環境歸屬 · 成交為 simulated fills，非往返交易 · 資金費正值為支出</p>
                  </div>
                </Panel>

                <WindowDetail result={realResult} window={activeWindow} />
              </>
            ) : (
              <Panel title="未選取任務">
                <p className="text-xs text-muted-foreground py-16 text-center">
                  請由左側清單點選一筆驗證任務查看結果，或點選右上角發起新任務。
                </p>
              </Panel>
            )}
          </div>
        </div>
      </div>

      <Dialog open={openDialog} onOpenChange={setOpenDialog}>
        <DialogContent className="border-border bg-surface max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-sm font-bold text-foreground flex items-center gap-2">
              <RouteIcon className="size-4 text-primary" /> 發起滾動驗證
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              符合後端 POST /api/research/validations 契約 · 完整格點、無隨機種子
            </DialogDescription>
          </DialogHeader>

          {form && strategy && (
            <div className="space-y-3 py-1 text-xs font-mono max-h-[65vh] overflow-y-auto pr-1">
              <div className="space-y-1">
                <Label className="text-t2 text-muted-foreground">策略</Label>
                <StrategyPicker strategies={catalog?.strategies ?? []} value={strategy.id} onChange={changeStrategy} />
                <p className="text-muted-foreground text-t2">
                  固定帳戶：{VALIDATION_BACKTEST.quantity} 張 · 本金 {VALIDATION_BACKTEST.initial_balance} USDT · 手續費率 {VALIDATION_BACKTEST.fee_rate} · 滑價 {VALIDATION_BACKTEST.slippage_bps} bps
                </p>
              </div>

              <div className="space-y-1">
                <Label className="text-t2 text-muted-foreground">資料集</Label>
                <DatasetPicker datasets={catalog?.datasets ?? []} value={dataset?.id ?? null} onChange={changeDataset} />
              </div>

              <div className="space-y-1">
                <Label className="text-t2 text-muted-foreground">
                  候選參數（完整格點，{count === null ? "格點無效，原因見下方" : `${count} 個候選`}）
                </Label>
                {paramSpecs(strategy).map((spec) => (
                  <div key={spec.name} className="grid grid-cols-[5.5rem_1fr_1fr_1fr] items-center gap-2">
                    <span className="text-t2 text-muted-foreground truncate" title={spec.name}>{paramLabel(spec.name)}</span>
                    <Input type="number" min={spec.min} max={spec.max} aria-label={`${paramLabel(spec.name)}最小值`}
                           value={form.axes[spec.name]?.low ?? 0} onChange={axisField(spec.name, "low")}
                           className="h-8 font-mono text-xs bg-background" />
                    <Input type="number" min={spec.min} max={spec.max} aria-label={`${paramLabel(spec.name)}最大值`}
                           value={form.axes[spec.name]?.high ?? 0} onChange={axisField(spec.name, "high")}
                           className="h-8 font-mono text-xs bg-background" />
                    <Input type="number" min={1} max={spec.max - spec.min} aria-label={`${paramLabel(spec.name)}步進`}
                           value={form.axes[spec.name]?.step ?? 0} onChange={axisField(spec.name, "step")}
                           className="h-8 font-mono text-xs bg-background" />
                  </div>
                ))}
                <p className="text-t2 text-muted-foreground">
                  最小值 · 最大值 · 步進；預熱 {warmupBars(form, strategy)} 根（涵蓋最大{paramLabel(strategy.warmup.covers)}）
                </p>
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <Label className="text-t2 text-muted-foreground">滾動計畫（K 線根數）</Label>
                  <button type="button" onClick={() => resetForm(dataset?.id ?? null, strategy.id)}
                          className="text-t2 text-primary hover:underline cursor-pointer">
                    依資料長度重設
                  </button>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <Input type="number" min={1} aria-label="訓練根數" value={form.trainBars}
                         onChange={intField("trainBars")} className="h-8 font-mono text-xs bg-background" />
                  <Input type="number" min={1} aria-label="測試根數" value={form.testBars}
                         onChange={intField("testBars")} className="h-8 font-mono text-xs bg-background" />
                  <Input type="number" min={1} max={limits?.max_windows ?? 8} aria-label="視窗數" value={form.windows}
                         onChange={intField("windows")} className="h-8 font-mono text-xs bg-background" />
                </div>
                <p className="text-t2 text-muted-foreground">
                  訓練 · 測試 · 視窗數；使用 {barsUsed(form, strategy).toLocaleString()} / {dataset?.bars.toLocaleString() ?? NA} 根 ·{" "}
                  {count === null
                    ? "格點無效，無法估算回測次數與計算量"
                    : `需 ${requiredRuns(form, strategy)} 次回測 · 計算量 ${barEvaluations(form, strategy)?.toLocaleString()} / ${limits?.max_bar_evaluations.toLocaleString() ?? NA}`}
                </p>
              </div>

              <div className="space-y-1">
                <Label className="text-t2 text-muted-foreground">環境分類規則（事前明示的示範門檻，不回饋選參）</Label>
                <div className="grid grid-cols-3 gap-2">
                  <Input type="number" min={1} max={limits?.max_lookback_bars ?? 512} aria-label="回看根數" value={form.lookbackBars}
                         onChange={intField("lookbackBars")} className="h-8 font-mono text-xs bg-background" />
                  <Input type="text" inputMode="decimal" aria-label="趨勢效率門檻" value={form.trendEfficiency}
                         onChange={(e) => setField("trendEfficiency", e.target.value)} className="h-8 font-mono text-xs bg-background" />
                  <Input type="text" inputMode="decimal" aria-label="高波動門檻 bps" value={form.highVolatilityBps}
                         onChange={(e) => setField("highVolatilityBps", e.target.value)} className="h-8 font-mono text-xs bg-background" />
                </div>
                <p className="text-t2 text-muted-foreground">
                  回看根數（1~{limits?.max_lookback_bars ?? 512}）· 趨勢效率門檻 (0~1] · 高波動門檻（每根平均真實波幅，bps）
                </p>
              </div>

              {problems.length > 0 && (
                <ul className="rounded border border-amber-500/30 bg-amber-500/10 px-2.5 py-2 text-t2 text-amber-400 space-y-0.5">
                  {problems.map((problem) => <li key={problem}>· {problem}</li>)}
                </ul>
              )}

              <p className="text-t2 text-muted-foreground leading-relaxed">
                ※ 提交後後端以獨立 Worker 執行，期間鎖定共用忙碌槽；單次上限 {catalog?.limits.timeout_seconds ?? 30} 秒、輸出 {((catalog?.limits.max_output_bytes ?? 2_000_000) / 1_000_000).toFixed(0)} MB。
              </p>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setOpenDialog(false)} className="text-xs font-mono h-8">
              取消
            </Button>
            <Button
              size="sm"
              disabled={submitting || !form || problems.length > 0}
              onClick={handleSubmit}
              className="text-xs font-mono h-8 bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {submitting ? <Loader2 className="size-3.5 mr-1 animate-spin" /> : null}
              {submitting ? "提交中..." : "確認發起驗證"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
