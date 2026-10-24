import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import {
  Award,
  Sparkles,
  Download,
  Loader2,
  RefreshCw,
  AlertCircle,
  HelpCircle,
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
import { ParetoScatterChart, type TrialPoint } from "@/components/catos/pareto-scatter-chart";
import type { OptimizationRequest } from "@/adapters/research-api-adapter";
import { useOptimizationResearch } from "@/hooks/use-optimization-research";

export const Route = createFileRoute("/optimization")({
  head: () => ({
    meta: [
      { title: "參數優化 (Optimization) — catOS Quant Terminal" },
      { name: "description", content: "catOS 策略參數優化：Optuna 貝氏搜尋、帕累托前沿超參數尋優。" },
    ],
  }),
  component: OptimizationPage,
});

interface OptTrial {
  trialNumber: number;
  fastPeriod: number;
  slowPeriod: number;
  atrMultiplier: number;
  sharpe: string;
  totalReturn: string;
  maxDrawdown: string;
  isBest: boolean;
}

const DEMO_TRIALS: OptTrial[] = [
  { trialNumber: 42, fastPeriod: 12, slowPeriod: 34, atrMultiplier: 2.5, sharpe: "2.45", totalReturn: "+26.8%", maxDrawdown: "-3.8%", isBest: true },
  { trialNumber: 28, fastPeriod: 10, slowPeriod: 30, atrMultiplier: 2.0, sharpe: "2.21", totalReturn: "+22.4%", maxDrawdown: "-4.2%", isBest: false },
  { trialNumber: 65, fastPeriod: 14, slowPeriod: 38, atrMultiplier: 3.0, sharpe: "2.08", totalReturn: "+19.6%", maxDrawdown: "-3.5%", isBest: false },
  { trialNumber: 15, fastPeriod: 8, slowPeriod: 25, atrMultiplier: 1.8, sharpe: "1.92", totalReturn: "+17.3%", maxDrawdown: "-5.1%", isBest: false },
  { trialNumber: 84, fastPeriod: 16, slowPeriod: 45, atrMultiplier: 2.8, sharpe: "1.75", totalReturn: "+14.1%", maxDrawdown: "-4.6%", isBest: false },
  { trialNumber: 91, fastPeriod: 11, slowPeriod: 32, atrMultiplier: 2.2, sharpe: "1.68", totalReturn: "+13.5%", maxDrawdown: "-4.9%", isBest: false },
];

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
  const [viewMode, setViewMode] = useState<"real" | "demo">("real");

  // Demo view states
  const [selectedDemoTrial, setSelectedDemoTrial] = useState<OptTrial>(DEMO_TRIALS[0]);
  const [exported, setExported] = useState(false);

  const {
    version, catalog, optRuns, selectedRun, realResult, loading, resultLoading,
    submitting, errorMsg, fetchRealData, selectRun, submit, isBusy,
  } = useOptimizationResearch();

  const [openDialog, setOpenDialog] = useState(false);
  const [periodLow, setPeriodLow] = useState(2);
  const [periodHigh, setPeriodHigh] = useState(8);
  const [periodStep, setPeriodStep] = useState(1);
  const [nTrials, setNTrials] = useState(8);
  const [seed, setSeed] = useState(42);

  const handleSubmitRealOpt = async () => {
    const req: OptimizationRequest = {
      backtest: {
        strategy_id: "sma-trend", dataset_id: "synthetic-btc-15m-v1",
        parameters: { period: 2, quantity: "2" }, initial_balance: "1000",
        fee_rate: "0.0005", slippage_bps: "2", warmup_bars: Math.max(8, periodHigh),
      },
      search_space: { period: { low: periodLow, high: periodHigh, step: periodStep } },
      n_trials: nTrials, seed,
    };
    if (await submit(req)) setOpenDialog(false);
  };

  const handleSelectParetoTrial = (point: TrialPoint) => {
    const found = DEMO_TRIALS.find((t) => t.trialNumber === point.trialNumber);
    if (found) {
      setSelectedDemoTrial(found);
    } else {
      setSelectedDemoTrial({
        trialNumber: point.trialNumber,
        fastPeriod: point.fastPeriod,
        slowPeriod: point.slowPeriod,
        atrMultiplier: point.atrMultiplier,
        sharpe: point.sharpe.toFixed(2),
        totalReturn: `+${point.totalReturn}%`,
        maxDrawdown: `-${point.maxDrawdown}%`,
        isBest: point.isBest || false,
      });
    }
  };

  return (
    <AppShell>
      <PageHead
        code="RESEARCH // OPTIMIZATION"
        title="參數優化中心"
        desc="Optuna 貝氏最佳化引擎 · 樣本內搜尋 · 嚴格 Decimal 績效核心"
        right={
          <div className="flex items-center gap-2">
            {/* 視圖切換器：真實研究契約 vs 概念展示 */}
            <div className="flex items-center rounded-lg bg-secondary/80 p-0.5 border border-border/60">
              <button
                onClick={() => setViewMode("real")}
                className={cn(
                  "px-2.5 py-1 text-xs font-mono rounded transition-colors",
                  viewMode === "real"
                    ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                真實研究契約 (SMA Optuna)
              </button>
              <button
                onClick={() => setViewMode("demo")}
                className={cn(
                  "px-2.5 py-1 text-xs font-mono rounded transition-colors",
                  viewMode === "demo"
                    ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                展示資料 (多目標概念)
              </button>
            </div>

            {viewMode === "real" && (
              <Button
                size="sm"
                disabled={!version || loading || isBusy || version.restart_required}
                onClick={() => setOpenDialog(true)}
                className="h-7 text-xs bg-primary text-primary-foreground hover:bg-primary/90 font-medium"
              >
                {isBusy ? <Loader2 className="size-3.5 mr-1 animate-spin" /> : <Sparkles className="size-3.5 mr-1" />}
                {isBusy ? "後端計算中..." : "發起 SMA 優化任務"}
              </Button>
            )}
          </div>
        }
      />

      <div className="space-y-3">
        {/* ==================== 頂部契約約束橫幅 (Scheme B 滿版純淨視野) ==================== */}
        <div className="flex flex-wrap items-center justify-between gap-2.5 rounded-lg border border-border/80 bg-surface/90 px-3.5 py-2 text-xs font-mono shadow-xs backdrop-blur-md">
          <div className="flex items-center gap-3">
            <span className="text-muted-foreground">
              目前模式: <strong className={cn(viewMode === "real" ? "text-primary" : "text-amber-400")}>
                {viewMode === "real" ? "真實研究後端 (POST /api/research/optimizations)" : "展示資料模式 (EMA-ATR 多維探索)"}
              </strong>
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
              <span className="text-amber-400 font-medium text-[11px] bg-amber-500/10 border border-amber-500/25 px-2 py-0.5 rounded">
                服務源檔案已異動 (restart_required)
              </span>
            )}
            {isBusy && (
              <span className="text-primary font-medium text-[11px] flex items-center gap-1 bg-primary/10 border border-primary/25 px-2 py-0.5 rounded">
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
        {viewMode === "real" && (
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
                    className="h-6 px-2 text-[10px] font-mono text-muted-foreground hover:text-foreground"
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
                                "text-[9.5px] px-1.5 py-0.2 rounded font-semibold uppercase",
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
                          <p className="text-[10px] text-muted-foreground mt-1">
                            建立時間: {formatUtc(r.created_at)}
                          </p>
                          <p className="text-[10px] text-muted-foreground">
                            搜尋範圍: SMA period {r.request?.search_space?.period?.low ?? 2}~{r.request?.search_space?.period?.high ?? 8} · {r.request?.n_trials ?? 8} 試驗
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
                    <strong className="text-foreground">能力限制:</strong> 後端僅實作 SMA period 單參數樣本內搜尋，目標 return_pct 最大化；未提供 Sharpe 自訂目標、多 Worker 平行、多目標 Pareto 或未審計之策略檔匯出。
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
                      <span className="text-[10px] text-muted-foreground block">最佳試驗</span>
                      <span className="text-base font-bold text-primary mt-0.5 block">
                        Trial #{realResult.best_trial_number ?? "--"}
                      </span>
                      <span className="text-[9.5px] text-muted-foreground">
                        最佳週期: {realResult.trials.find((t) => t.number === realResult.best_trial_number)?.params.period ?? "--"}
                      </span>
                    </div>

                    <div className="rounded-lg border border-border/80 bg-surface/90 p-3 shadow-xs">
                      <span className="text-[10px] text-muted-foreground block">尋優目標</span>
                      <span className="text-base font-bold text-foreground mt-0.5 block">
                        {realResult.objective.name}
                      </span>
                      <span className="text-[9.5px] text-muted-foreground capitalize">
                        方向: {realResult.objective.direction}
                      </span>
                    </div>

                    <div className="rounded-lg border border-border/80 bg-surface/90 p-3 shadow-xs">
                      <span className="text-[10px] text-muted-foreground block">Optuna 引擎版本</span>
                      <span className="text-base font-bold text-foreground mt-0.5 block">
                        v{realResult.optuna_version}
                      </span>
                      <span className="text-[9.5px] text-muted-foreground">隨機種子: {realResult.seed}</span>
                    </div>

                    <div className="rounded-lg border border-border/80 bg-surface/90 p-3 shadow-xs">
                      <span className="text-[10px] text-muted-foreground block">完成試驗數</span>
                      <span className="text-base font-bold text-foreground mt-0.5 block">
                        {realResult.trials.length} 筆
                      </span>
                      <span className="text-[9.5px] text-muted-foreground">
                        有效: {realResult.trials.filter((t) => t.state === "COMPLETE").length} 筆
                      </span>
                    </div>
                  </div>

                  {/* 試驗詳細列表 */}
                  <Panel
                    title={
                      <div className="flex items-center gap-2">
                        <Award className="size-3.5 text-primary" />
                        <span>Optuna 試驗明細矩陣 (Trials Matrix · Decimal)</span>
                      </div>
                    }
                    meta={
                      <span className="text-[10px] font-mono text-muted-foreground">
                        Run: {realResult.run_id?.slice(0, 12)}
                      </span>
                    }
                  >
                    <div className="overflow-x-auto">
                      <table className="w-full text-left border-collapse text-xs">
                        <thead className="border-b border-border text-[10px] font-mono text-muted-foreground bg-background/30">
                          <tr>
                            <th className="py-2 px-3 font-normal">Trial #</th>
                            <th className="py-2 px-3 font-normal">狀態</th>
                            <th className="py-2 px-3 text-right font-normal">SMA Period</th>
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
                                      <span className="bg-primary text-primary-foreground text-[8.5px] px-1 rounded">
                                        BEST
                                      </span>
                                    )}
                                  </span>
                                </td>
                                <td className="py-2.5 px-3">
                                  <span className="text-[10px] text-muted-foreground">{t.state}</span>
                                </td>
                                <td className="py-2.5 px-3 text-right font-semibold text-foreground">
                                  {t.params.period}
                                </td>
                                <td className="py-2.5 px-3 text-right font-bold text-primary">
                                  {t.score_decimal}
                                </td>
                                <td className="py-2.5 px-3 text-right font-semibold text-foreground">
                                  {t.performance ? `${t.performance.net_pnl} USDT` : "--"}
                                </td>
                                <td className="py-2.5 px-3 text-right text-muted-foreground">
                                  {t.performance ? t.performance.fees : "--"}
                                </td>
                                <td className="py-2.5 px-3 text-right text-muted-foreground">
                                  {t.performance ? `${t.performance.max_drawdown_pct}%` : "--"}
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
                      <div className="mt-3 pt-2.5 border-t border-border/40 text-[10.5px] font-mono text-muted-foreground flex items-center justify-between">
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
        )}

        {/* ==================== 視圖 B：展示資料模式 (EMA-ATR 多目標概念) ==================== */}
        {viewMode === "demo" && (
          <div className="space-y-3">
            {/* 概念橫幅 */}
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-3.5 py-2 text-xs text-amber-400 font-mono flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <HelpCircle className="size-3.5" />
                <span>此面板為多參數概念展示（EMA+ATR 帕累托尋優），非目前後端正式執行的單參數 SMA 搜尋。</span>
              </span>
              <span>展示資料 · 示範概念</span>
            </div>

            {/* 帕累托散佈圖 */}
            <ParetoScatterChart
              selectedTrialNumber={selectedDemoTrial.trialNumber}
              onSelectTrial={handleSelectParetoTrial}
            />

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
              {/* 左欄：搜尋空間 (5 欄) */}
              <div className="lg:col-span-5 space-y-3">
                <Panel
                  title="搜尋空間定義 (Search Space · 示範)"
                  meta={<span className="text-[10px] font-mono text-muted-foreground">3 個超參數維度</span>}
                >
                  <div className="space-y-2.5">
                    <div className="rounded-lg border border-border/60 bg-background/40 p-2.5">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-semibold text-foreground">fast_ema_period</span>
                        <span className="font-mono text-[10px] text-primary bg-primary/10 px-1.5 py-0.5 rounded">最佳值: 12</span>
                      </div>
                      <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                        IntRange(min=5, max=25, step=1)
                      </p>
                    </div>

                    <div className="rounded-lg border border-border/60 bg-background/40 p-2.5">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-semibold text-foreground">slow_ema_period</span>
                        <span className="font-mono text-[10px] text-primary bg-primary/10 px-1.5 py-0.5 rounded">最佳值: 34</span>
                      </div>
                      <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                        IntRange(min=20, max=60, step=2)
                      </p>
                    </div>

                    <div className="rounded-lg border border-border/60 bg-background/40 p-2.5">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-semibold text-foreground">atr_stop_multiplier</span>
                        <span className="font-mono text-[10px] text-primary bg-primary/10 px-1.5 py-0.5 rounded">最佳值: 2.5</span>
                      </div>
                      <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                        FloatRange(min=1.5, max=4.0, step=0.5)
                      </p>
                    </div>

                    <div className="pt-2">
                      <Button
                        onClick={() => {
                          setExported(true);
                          setTimeout(() => setExported(false), 2500);
                        }}
                        className="w-full text-xs font-semibold bg-primary text-primary-foreground hover:bg-primary/90 h-8"
                      >
                        <Download className="size-3.5 mr-1.5" />
                        {exported ? "已導出策略製品" : "導出 Trial #42 參數製品"}
                      </Button>
                    </div>
                  </div>
                </Panel>
              </div>

              {/* 右欄：排行榜表格 (7 欄) */}
              <div className="lg:col-span-7">
                <Panel
                  title="試驗排行榜 (Top Trials · 帕累托前沿示範)"
                  meta={<span className="text-[10px] font-mono text-primary font-medium flex items-center gap-1"><Award className="size-3" />帕累托前沿</span>}
                >
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead className="border-b border-border text-[10px] font-mono text-muted-foreground bg-background/30">
                        <tr>
                          <th className="py-2 px-3 font-normal">Trial #</th>
                          <th className="py-2 px-3 font-normal">Fast / Slow</th>
                          <th className="py-2 px-3 font-normal">ATR Multi</th>
                          <th className="py-2 px-3 text-right font-normal">夏普評分</th>
                          <th className="py-2 px-3 text-right font-normal">總收益</th>
                          <th className="py-2 px-3 text-right font-normal">最大回撤</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/40 font-mono">
                        {DEMO_TRIALS.map((t) => {
                          const isSelected = selectedDemoTrial.trialNumber === t.trialNumber;
                          return (
                            <tr
                              key={t.trialNumber}
                              onClick={() => setSelectedDemoTrial(t)}
                              className={cn(
                                "cursor-pointer transition-colors",
                                isSelected ? "bg-primary/10" : "hover:bg-secondary/30"
                              )}
                            >
                              <td className="py-2.5 px-3">
                                <span className={cn("inline-flex items-center gap-1 font-semibold", t.isBest ? "text-primary" : "text-foreground")}>
                                  #{t.trialNumber} {t.isBest && <span className="text-[9px] bg-primary text-primary-foreground px-1 rounded">BEST</span>}
                                </span>
                              </td>
                              <td className="py-2.5 px-3 text-muted-foreground">{t.fastPeriod} / {t.slowPeriod}</td>
                              <td className="py-2.5 px-3 text-muted-foreground">{t.atrMultiplier.toFixed(1)}x</td>
                              <td className="py-2.5 px-3 text-right font-bold text-foreground">{t.sharpe}</td>
                              <td className="py-2.5 px-3 text-right text-up font-medium">{t.totalReturn}</td>
                              <td className="py-2.5 px-3 text-right text-down font-medium">{t.maxDrawdown}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </Panel>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ==================== 發起新優化任務彈窗 (符合後端研究契約) ==================== */}
      <Dialog open={openDialog} onOpenChange={setOpenDialog}>
        <DialogContent className="border-border bg-surface max-w-md">
          <DialogHeader>
            <DialogTitle className="text-sm font-bold text-foreground flex items-center gap-2">
              <Sparkles className="size-4 text-primary" /> 發起 SMA 參數優化任務
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              符合後端 POST /api/research/optimizations 契約（合成 BTC 15m 資料 · 96 根）
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2 text-xs font-mono">
            <div className="rounded border border-primary/25 bg-primary/5 p-2.5 space-y-1 text-[11px]">
              <span className="text-primary font-semibold">固定登錄模型</span>
              <p className="text-muted-foreground text-[10px]">
                策略: RegisteredSMA (sma-trend) · 資料: synthetic-btc-15m-v1
              </p>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">Period 最小值</Label>
                <Input
                  type="number"
                  min={2}
                  max={32}
                  value={periodLow}
                  onChange={(e) => setPeriodLow(parseInt(e.target.value) || 2)}
                  className="h-8 font-mono text-xs bg-background"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">Period 最大值</Label>
                <Input
                  type="number"
                  min={2}
                  max={32}
                  value={periodHigh}
                  onChange={(e) => setPeriodHigh(parseInt(e.target.value) || 8)}
                  className="h-8 font-mono text-xs bg-background"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">搜尋步進 (Step)</Label>
                <Input
                  type="number"
                  min={1}
                  max={8}
                  value={periodStep}
                  onChange={(e) => setPeriodStep(parseInt(e.target.value) || 1)}
                  className="h-8 font-mono text-xs bg-background"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">Optuna 試驗數 (1~{catalog?.optimization?.max_trials || 20})</Label>
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
                <Label className="text-[10px] text-muted-foreground">隨機種子 (Seed)</Label>
                <Input
                  type="number"
                  value={seed}
                  onChange={(e) => setSeed(parseInt(e.target.value) || 42)}
                  className="h-8 font-mono text-xs bg-background"
                />
              </div>
            </div>

            <p className="text-[10px] text-muted-foreground leading-relaxed">
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
              disabled={submitting}
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
