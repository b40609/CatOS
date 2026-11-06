import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import {
  Award,
  Sparkles,
Loader2,
  RefreshCw,
  AlertCircle,
} from "lucide-react";
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
import type { OptimizationRequest } from "@/adapters/research-api-adapter";
import { useOptimizationResearch } from "@/hooks/use-optimization-research";
import { DatasetPicker, pickDataset } from "@/components/catos/dataset-picker";
import { StrategyPicker } from "@/components/catos/strategy-picker";
import { CostBreakdownPanel, costViewFromBreakdown } from "@/components/catos/cost-breakdown-panel";
import { formatDecimal } from "@/lib/format";
import {
  type Axis, DONCHIAN_ID, donchianAxes, formatParams, formatRanges, formatTrialParams, gridBase,
  gridProblems, gridWarmup, paramLabel, paramSpecs, pickStrategy, shortName, warmupBarsProblems,
} from "@/lib/research-strategies";

// SMA keeps its original 2~8 step 1 search and warm-up of at least 8 bars.
const SMA_AXES: Record<string, Axis> = { period: { low: 2, high: 8, step: 1 } };

export const Route = createFileRoute("/optimization")({
  head: () => ({
    meta: [
      { title: "參數優化 (Optimization) — catOS Quant Terminal" },
      { name: "description", content: "catOS 策略參數優化：Optuna 貝氏搜尋、帕累托前沿超參數尋優。" },
    ],
  }),
  component: OptimizationPage,
});


function formatUtc(msOrIso: string | number | null | undefined): string {
  if (!msOrIso) return "--";
  const d = new Date(msOrIso);
  if (isNaN(d.getTime())) return String(msOrIso);
  const m = String(d.getUTCMonth() + 1).padStart(2, "0");
  const day = String(d.getUTCDate()).padStart(2, "0");
  const h = String(d.getUTCHours()).padStart(2, "0");
  const min = String(d.getUTCMinutes()).padStart(2, "0");
  const s = String(d.getUTCSeconds()).padStart(2, "0");
  return `${m}/${day} ${h}:${min}:${s} UTC`;
}

function OptimizationPage() {

  const {
    version, catalog, optRuns, selectedRun, realResult, loading, resultLoading,
    submitting, errorMsg, fetchRealData, selectRun, submit, isBusy,
  } = useOptimizationResearch();

  const [openDialog, setOpenDialog] = useState(false);
  const [strategyId, setStrategyId] = useState<string | null>(null);
  const [axes, setAxes] = useState<Record<string, Axis>>(SMA_AXES);
  const [nTrials, setNTrials] = useState(8);
  const [seed, setSeed] = useState(42);
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const dataset = pickDataset(catalog?.datasets, datasetId);
  const strategy = pickStrategy(catalog?.strategies, strategyId);
  // SMA keeps a warm-up of at least 8 bars; Donchian covers its highest entry channel.
  const warmup = !strategy ? 0
    : strategy.id === DONCHIAN_ID ? gridWarmup(strategy, axes) : Math.max(8, gridWarmup(strategy, axes));
  const problems = strategy ? [...gridProblems(strategy, axes), ...warmupBarsProblems(warmup, dataset)] : [];

  const changeStrategy = (sid: string) => {
    setStrategyId(sid);
    setAxes(sid === DONCHIAN_ID ? donchianAxes(dataset) : SMA_AXES);
  };
  const changeDataset = (id: string) => {
    setDatasetId(id);
    if (strategy?.id === DONCHIAN_ID) setAxes(donchianAxes(pickDataset(catalog?.datasets, id)));
  };
  const setAxis = (name: string, key: keyof Axis, value: number) =>
    setAxes((current) => ({ ...current, [name]: { ...current[name], [key]: value } }));

  const handleSubmitRealOpt = async () => {
    if (!strategy || problems.length) return;
    // SMA keeps its fixed period 2 base; Donchian starts from the lowest grid point.
    const base = strategy.id === DONCHIAN_ID ? gridBase(strategy, axes) : { period: 2 };
    const req: OptimizationRequest = {
      backtest: {
        strategy_id: strategy.id, dataset_id: dataset?.id || "synthetic-btc-15m-v1",
        parameters: { ...base, quantity: "2" }, initial_balance: "1000",
        fee_rate: "0.0005", slippage_bps: "2", warmup_bars: warmup,
      },
      search_space: Object.fromEntries(paramSpecs(strategy).map((spec) => [spec.name, { ...axes[spec.name] }])),
      n_trials: nTrials, seed,
    };
    if (await submit(req)) setOpenDialog(false);
  };

  return (
    <AppShell>
      <PageHead
        code="RESEARCH // OPTIMIZATION"
        title="參數優化中心"
        desc="Optuna 貝氏最佳化引擎 · 樣本內搜尋 · 嚴格 Decimal 績效核心"
        right={
          <div className="flex items-center gap-2">
            {/* 頂部操作按鈕 */}
            

            <Button
              size="sm"
              disabled={!version || loading || isBusy || version.restart_required}
              onClick={() => setOpenDialog(true)}
              className="h-7 text-xs bg-primary text-primary-foreground hover:bg-primary/90 font-medium cursor-pointer"
            >
              {isBusy ? <Loader2 className="size-3.5 mr-1 animate-spin" /> : <Sparkles className="size-3.5 mr-1" />}
              {isBusy ? "後端計算中..." : "發起優化任務"}
            </Button>
          </div>
        }
      />

      <div className="space-y-3">
        {/* ==================== 頂部契約約束橫幅 (Scheme B 滿版純淨視野) ==================== */}
        <div className="flex flex-wrap items-center justify-between gap-2.5 rounded-lg border border-border/80 bg-surface/90 px-3.5 py-2 text-xs font-mono shadow-xs backdrop-blur-md">
          <div className="flex items-center gap-3">
            <span className="text-muted-foreground">
              引擎核心: <strong className="text-primary font-semibold">Optuna TPE · 樣本內回測評估</strong>
            </span>
            <span className="text-border">|</span>
            <span className="text-muted-foreground">
              演算法: <strong className="text-foreground">Optuna TPE</strong>
            </span>
            <span className="text-border">|</span>
            <span className="text-muted-foreground">
              目標函式: <strong className="text-foreground">return_pct (Maximize)</strong>
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

        {/* 錯誤提示 */}
        {errorMsg && (
          <div className="flex items-center gap-2 rounded-lg border border-down/40 bg-down/10 px-3.5 py-2 text-xs text-down font-mono">
            <AlertCircle className="size-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* ==================== 視圖 A：真實研究契約 (SMA Optuna) ==================== */}
        <>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-12 items-start">
            {/* 左欄：歷史優化任務列表 (4 欄) */}
            <div className="lg:col-span-4 space-y-3">
              <Panel
                title="歷史優化任務 (Optimization Runs)"
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
                {optRuns.length === 0 ? (
                  <p className="text-xs text-muted-foreground py-6 text-center">
                    目前尚無優化任務紀錄，點擊右上角發起新任務。
                  </p>
                ) : (
                  <div className="space-y-1.5 max-h-[480px] overflow-y-auto pr-1">
                    {optRuns.map((r) => {
                      const isSelected = selectedRun?.run_id === r.run_id;
                      return (
                        <div
                          key={r.run_id}
                          onClick={() => selectRun(r)}
                          className={cn(
                            "rounded-lg border p-2.5 cursor-pointer transition-colors text-xs font-mono",
                            isSelected
                              ? "border-primary bg-primary/10"
                              : "border-border/60 bg-background/40 hover:bg-secondary/40"
                          )}
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-foreground truncate max-w-[140px]">
                              #{r.run_id.slice(0, 8)}
                            </span>
                            <span
                              className={cn(
                                "text-t1 px-1.5 py-0.2 rounded font-semibold uppercase",
                                r.status === "complete"
                                  ? "bg-up/15 text-up border border-up/30"
                                  : r.status === "running"
                                  ? "bg-primary/15 text-primary border border-primary/30"
                                  : "bg-down/15 text-down border border-down/30"
                              )}
                            >
                              {r.status}
                            </span>
                          </div>
                          <p className="text-t2 text-muted-foreground mt-1">
                            建立時間: {formatUtc(r.created_at)}
                          </p>
                          <p className="text-t2 text-muted-foreground">
                            搜尋範圍: {shortName(r.request?.backtest?.strategy_id)} {formatRanges(r.request?.search_space) || "--"} · {r.request?.n_trials ?? 8} 試驗
                          </p>
                        </div>
                      );
                    })}
                  </div>
                )}
              </Panel>

              {/* 架構與邊界約束 */}
              <Panel title="P7 核心與後端能力邊界">
                <div className="space-y-2 text-xs text-muted-foreground leading-relaxed">
                  <p>
                    <strong className="text-foreground">數值精確度:</strong> 原始帳務、淨損益、費用與報酬率一律強制使用 Decimal 字串儲存；僅交給 Optuna 進行尋優排序之數值轉為 Float，不得回流為帳務依據。
                  </p>
                  <p>
                    <strong className="text-foreground">能力限制:</strong> 後端只搜尋固定白名單策略（SMA 週期、Donchian 進出場通道）的樣本內參數，目標 return_pct 最大化；未提供 Sharpe 自訂目標、多 Worker 平行、多目標 Pareto 或未審計之策略檔匯出。
                  </p>
                </div>
              </Panel>
            </div>

            {/* 右欄：選中任務之 Optuna 試驗結果 (8 欄) */}
            <div className="lg:col-span-8 space-y-3">
              {resultLoading ? (
                <Panel title="優化結果載入中">
                  <div className="py-16 text-center text-xs text-muted-foreground flex flex-col items-center justify-center gap-2">
                    <Loader2 className="size-6 animate-spin text-primary" />
                    <span>讀取封存試驗數據中...</span>
                  </div>
                </Panel>
              ) : realResult ? (
                <>
                  {/* 結果 HUD 條 */}
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 font-mono">
                    <div className="rounded-lg border border-border/80 bg-surface/90 p-3 shadow-xs">
                      <span className="text-t2 text-muted-foreground block">最佳試驗</span>
                      <span className="text-base font-bold text-primary mt-0.5 block">
                        Trial #{realResult.best_trial_number ?? "--"}
                      </span>
                      <span className="text-t1 text-muted-foreground">
                        最佳參數: {formatParams(realResult.trials.find((t) => t.number === realResult.best_trial_number)?.params) || "--"}
                      </span>
                    </div>

                    <div className="rounded-lg border border-border/80 bg-surface/90 p-3 shadow-xs">
                      <span className="text-t2 text-muted-foreground block">尋優目標</span>
                      <span className="text-base font-bold text-foreground mt-0.5 block">
                        {realResult.objective.name}
                      </span>
                      <span className="text-t1 text-muted-foreground capitalize">
                        方向: {realResult.objective.direction}
                      </span>
                    </div>

                    <div className="rounded-lg border border-border/80 bg-surface/90 p-3 shadow-xs">
                      <span className="text-t2 text-muted-foreground block">Optuna 引擎版本</span>
                      <span className="text-base font-bold text-foreground mt-0.5 block">
                        v{realResult.optuna_version}
                      </span>
                      <span className="text-t1 text-muted-foreground">隨機種子: {realResult.seed}</span>
                    </div>

                    <div className="rounded-lg border border-border/80 bg-surface/90 p-3 shadow-xs">
                      <span className="text-t2 text-muted-foreground block">完成試驗數</span>
                      <span className="text-base font-bold text-foreground mt-0.5 block">
                        {realResult.trials.length} 筆
                      </span>
                      <span className="text-t1 text-muted-foreground">
                        有效: {realResult.trials.filter((t) => t.state === "COMPLETE").length} 筆
                      </span>
                    </div>
                  </div>

                  <CostBreakdownPanel
                    title={`最佳試驗成本拆解（Trial #${realResult.best_trial_number ?? "--"}）`}
                    meta="同參數重跑一次的精算；樣本內"
                    testId="optimization-best-costs"
                    view={realResult.best_costs ? costViewFromBreakdown(realResult.best_costs) : null}
                  />

                  {/* 試驗詳細列表 */}
                  <Panel
                    title={
                      <div className="flex items-center gap-2">
                        <Award className="size-3.5 text-primary" />
                        <span>Optuna 試驗明細矩陣 (Trials Matrix · Decimal)</span>
                      </div>
                    }
                    meta={
                      <span className="text-t2 font-mono text-muted-foreground">
                        Run: {realResult.run_id?.slice(0, 12)}
                      </span>
                    }
                  >
                    <div className="overflow-x-auto">
                      <table className="w-full text-left border-collapse text-xs">
                        <thead className="border-b border-border text-t2 font-mono text-muted-foreground bg-background/30">
                          <tr>
                            <th className="py-2 px-3 font-normal">Trial #</th>
                            <th className="py-2 px-3 font-normal">狀態</th>
                            <th className="py-2 px-3 text-right font-normal">參數</th>
                            <th className="py-2 px-3 text-right font-normal">Decimal 評分</th>
                            <th className="py-2 px-3 text-right font-normal">淨損益 (USDT)</th>
                            <th className="py-2 px-3 text-right font-normal">手續費</th>
                            <th className="py-2 px-3 text-right font-normal">回撤幅度</th>
                            <th className="py-2 px-3 text-right font-normal">成交次數</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/40 font-mono">
                          {realResult.trials.map((t) => {
                            const isBest = t.number === realResult.best_trial_number;
                            return (
                              <tr
                                key={t.number}
                                className={cn(
                                  "transition-colors",
                                  isBest ? "bg-primary/10" : "hover:bg-secondary/30"
                                )}
                              >
                                <td className="py-2.5 px-3">
                                  <span className={cn("font-bold flex items-center gap-1", isBest ? "text-primary" : "text-foreground")}>
                                    #{t.number}
                                    {isBest && (
                                      <span className="bg-primary text-primary-foreground text-t1 px-1 rounded">
                                        BEST
                                      </span>
                                    )}
                                  </span>
                                </td>
                                <td className="py-2.5 px-3">
                                  <span className="text-t2 text-muted-foreground">{t.state}</span>
                                </td>
                                <td className="py-2.5 px-3 text-right font-semibold text-foreground">
                                  {formatTrialParams(t.params)}
                                </td>
                                {/* 顯示取兩位小數；title 保留完整 Decimal 字串供核對 */}
                                <td className="py-2.5 px-3 text-right font-bold text-primary" title={t.score_decimal ?? undefined}>
                                  {formatDecimal(t.score_decimal, { digits: 2, sign: true, suffix: "%" }, "--")}
                                </td>
                                <td className="py-2.5 px-3 text-right font-semibold text-foreground" title={t.performance?.net_pnl}>
                                  {t.performance ? formatDecimal(t.performance.net_pnl, { digits: 2, sign: true, suffix: " USDT" }) : "--"}
                                </td>
                                <td className="py-2.5 px-3 text-right text-muted-foreground" title={t.performance?.fees}>
                                  {t.performance ? formatDecimal(t.performance.fees, { digits: 2 }) : "--"}
                                </td>
                                <td className="py-2.5 px-3 text-right text-muted-foreground" title={t.performance?.max_drawdown_pct}>
                                  {t.performance ? formatDecimal(t.performance.max_drawdown_pct, { digits: 2, suffix: "%" }) : "--"}
                                </td>
                                <td className="py-2.5 px-3 text-right text-muted-foreground">
                                  {t.performance ? t.performance.trade_count : "--"}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>

                    {realResult.data_notice && (
                      <div className="mt-3 pt-2.5 border-t border-border/40 text-t2 font-mono text-muted-foreground flex items-center justify-between">
                        <span>聲明: {realResult.data_notice}</span>
                        <span>成交次數為 simulated fills，非往返交易</span>
                      </div>
                    )}
                  </Panel>
                </>
              ) : (
                <Panel title="未選取任務">
                  <p className="text-xs text-muted-foreground py-16 text-center">
                    請由左側清單點選一筆優化任務查看結果，或點選右上角發起新任務。
                  </p>
                </Panel>
              )}
            </div>
          </div>
        </>
      </div>

      {/* ==================== 發起新優化任務彈窗 (符合後端研究契約) ==================== */}
      <Dialog open={openDialog} onOpenChange={setOpenDialog}>
        <DialogContent className="border-border bg-surface max-w-md">
          <DialogHeader>
            <DialogTitle className="text-sm font-bold text-foreground flex items-center gap-2">
              <Sparkles className="size-4 text-primary" /> 發起策略參數優化任務
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              符合後端 POST /api/research/optimizations 契約 · 樣本內搜尋
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2 text-xs font-mono">
            <div className="space-y-1">
              <Label className="text-t2 text-muted-foreground">策略</Label>
              <StrategyPicker strategies={catalog?.strategies ?? []} value={strategy?.id ?? null} onChange={changeStrategy} />
            </div>

            <div className="space-y-1">
              <Label className="text-t2 text-muted-foreground">資料集</Label>
              <DatasetPicker datasets={catalog?.datasets ?? []} value={dataset?.id ?? null} onChange={changeDataset} />
            </div>

            <div className="space-y-1">
              <Label className="text-t2 text-muted-foreground">搜尋範圍（最小值 · 最大值 · 步進）</Label>
              {(strategy ? paramSpecs(strategy) : []).map((spec) => (
                <div key={spec.name} className="grid grid-cols-[5.5rem_1fr_1fr_1fr] items-center gap-2">
                  <span className="text-t2 text-muted-foreground truncate" title={spec.name}>{paramLabel(spec.name)}</span>
                  {(["low", "high", "step"] as const).map((key) => (
                    <Input
                      key={key}
                      type="number"
                      min={key === "step" ? 1 : spec.min}
                      max={key === "step" ? spec.max - spec.min : spec.max}
                      aria-label={`${paramLabel(spec.name)} ${key}`}
                      value={axes[spec.name]?.[key] ?? 0}
                      onChange={(e) => setAxis(spec.name, key, parseInt(e.target.value) || 0)}
                      className="h-8 font-mono text-xs bg-background"
                    />
                  ))}
                </div>
              ))}
              {strategy && (
                <p className="text-t2 text-muted-foreground">
                  預熱 {warmup} 根（涵蓋最大{paramLabel(strategy.warmup.covers)}）
                </p>
              )}
              {problems.length > 0 && (
                <ul className="space-y-0.5 text-t2 text-down">
                  {problems.map((problem) => <li key={problem}>· {problem}</li>)}
                </ul>
              )}
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-t2 text-muted-foreground">Optuna 試驗數 (1~{catalog?.optimization?.max_trials || 20})</Label>
                <Input
                  type="number"
                  min={1}
                  max={catalog?.optimization?.max_trials || 20}
                  value={nTrials}
                  onChange={(e) => setNTrials(parseInt(e.target.value) || 8)}
                  className="h-8 font-mono text-xs bg-background"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-t2 text-muted-foreground">隨機種子 (Seed)</Label>
                <Input
                  type="number"
                  value={seed}
                  onChange={(e) => setSeed(parseInt(e.target.value) || 42)}
                  className="h-8 font-mono text-xs bg-background"
                />
              </div>
            </div>

            <p className="text-t2 text-muted-foreground leading-relaxed">
              ※ 提交後後端將以獨立 Worker 執行 Optuna TPE 尋優，期間後端鎖定忙碌槽，直到 complete/failed 並釋放。
            </p>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setOpenDialog(false)}
              className="text-xs font-mono h-8"
            >
              取消
            </Button>
            <Button
              size="sm"
              disabled={submitting || !strategy || problems.length > 0}
              onClick={handleSubmitRealOpt}
              className="text-xs font-mono h-8 bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {submitting ? <Loader2 className="size-3.5 mr-1 animate-spin" /> : null}
              {submitting ? "提交中..." : "確認發起優化"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
