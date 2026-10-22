import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState, useRef, useCallback } from "react";
import { Play, CheckCircle2, ArrowUpRight, ArrowDownLeft, AlertCircle, RefreshCw, Layers, Clock, XCircle, Loader2 } from "lucide-react";
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
import { BacktestUnderwaterChart } from "@/components/catos/backtest-underwater-chart";
import {
  researchApi,
  ResearchApiError,
  type ResearchVersion,
  type ResearchCatalog,
  type ResearchRunStatus,
  type BacktestResultPayload,
  type BacktestRequest,
} from "@/adapters/research-api-adapter";

export const Route = createFileRoute("/backtest")({
  head: () => ({
    meta: [
      { title: "歷史回測 (Backtest) — catOS Quant Terminal" },
      { name: "description", content: "catOS 歷史回測工作區：單合約、單週期、Closed Bar 策略回測與績效評估。" },
    ],
  }),
  component: BacktestPage,
});

function formatUtcTime(ms: number | string | null | undefined): string {
  if (!ms) return "--";
  const num = typeof ms === "string" ? Date.parse(ms) : ms;
  const d = new Date(num);
  if (isNaN(d.getTime())) return String(ms);
  const month = String(d.getUTCMonth() + 1).padStart(2, "0");
  const day = String(d.getUTCDate()).padStart(2, "0");
  const hours = String(d.getUTCHours()).padStart(2, "0");
  const mins = String(d.getUTCMinutes()).padStart(2, "0");
  const secs = String(d.getUTCSeconds()).padStart(2, "0");
  return `${month}/${day} ${hours}:${mins}:${secs} UTC`;
}

function BacktestPage() {
  const isMountedRef = useRef(true);
  const requestGenerationRef = useRef<number>(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const pollTimerRef = useRef<number | null>(null);
  const busyPollTimerRef = useRef<number | null>(null);

  const [version, setVersion] = useState<ResearchVersion | null>(null);
  const [catalog, setCatalog] = useState<ResearchCatalog | null>(null);
  const [runs, setRuns] = useState<ResearchRunStatus[]>([]);
  const [selectedRun, setSelectedRun] = useState<ResearchRunStatus | null>(null);
  const [result, setResult] = useState<BacktestResultPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [resultLoading, setResultLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Modal State
  const [openSubmitDialog, setOpenSubmitDialog] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [pollingRunId, setPollingRunId] = useState<string | null>(null);

  // Form Fields
  const [period, setPeriod] = useState<number>(2);
  const [quantity, setQuantity] = useState<string>("2");
  const [initialBalance, setInitialBalance] = useState<string>("1000");
  const [feeRate, setFeeRate] = useState<string>("0.0005");
  const [slippageBps, setSlippageBps] = useState<string>("2");
  const [warmupBars, setWarmupBars] = useState<number>(2);

  const selectedRunRef = useRef<ResearchRunStatus | null>(null);
  selectedRunRef.current = selectedRun;

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (pollTimerRef.current !== null) {
        window.clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      if (busyPollTimerRef.current !== null) {
        window.clearTimeout(busyPollTimerRef.current);
        busyPollTimerRef.current = null;
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
    };
  }, []);

  // Fetch a specific run's result safely with request generation and abort
  const selectRun = useCallback(async (run: ResearchRunStatus) => {
    const generation = ++requestGenerationRef.current;

    // Abort in-flight result fetch
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    setSelectedRun(run);
    selectedRunRef.current = run;
    setResult(null); // Clear previous result immediately
    setErrorMsg(null);

    if (run.status !== "complete") {
      // Incomplete runs must reset resultLoading to false immediately!
      setResultLoading(false);
      return;
    }

    setResultLoading(true);
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const res = await researchApi.getRunResult(run.run_id, controller.signal);
      if (!isMountedRef.current || requestGenerationRef.current !== generation) {
        return; // Stale response discarded
      }
      setResult(res);
    } catch (err: any) {
      if (!isMountedRef.current || requestGenerationRef.current !== generation) return;
      if (err.name === "AbortError") return;
      if (err instanceof ResearchApiError) {
        setErrorMsg(`讀取回測結果失敗 [${err.status}]: ${err.detail}`);
      } else {
        setErrorMsg("讀取回測結果時遭遇異常");
      }
    } finally {
      if (isMountedRef.current && requestGenerationRef.current === generation) {
        setResultLoading(false);
      }
    }
  }, []);

  // Non-overlapping poll execution with version refresh & background non-overwrite
  const startPolling = useCallback((targetRunId: string) => {
    if (pollTimerRef.current !== null) {
      window.clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    setPollingRunId(targetRunId);

    const pollStep = async () => {
      if (!isMountedRef.current) return;
      try {
        const status = await researchApi.getRunStatus(targetRunId);
        if (!isMountedRef.current) return;

        if (status.status === "complete" || status.status === "failed") {
          setPollingRunId(null);

          // Update both runs and version from backend; do NOT force active_run_id to null.
          // Task completion and busy slot release are decoupled; version continues to reflect backend state.
          const [updatedRuns, updatedVersion] = await Promise.all([
            researchApi.getRuns(),
            researchApi.getVersion(),
          ]);
          if (!isMountedRef.current) return;
          setRuns(updatedRuns);
          setVersion(updatedVersion);

          const found = updatedRuns.find((r) => r.run_id === targetRunId) || status;

          if (status.status === "complete") {
            // Background task complete: DO NOT overwrite if user selected another historical run!
            const currentSelected = selectedRunRef.current;
            if (!currentSelected || currentSelected.run_id === targetRunId) {
              selectRun(found);
            }
          } else {
            const currentSelected = selectedRunRef.current;
            if (!currentSelected || currentSelected.run_id === targetRunId) {
              setSelectedRun(found);
              setResult(null);
              setResultLoading(false);
            }
            setErrorMsg(`回測任務執行失敗: ${status.error || "未知錯誤"}`);
          }

          // If another task is queued or running, continue polling
          const nextActive = updatedRuns.find(
            (r) => r.kind === "backtest" && (r.run_id === updatedVersion.active_run_id || r.status === "running" || r.status === "queued")
          );
          if (nextActive && nextActive.run_id !== targetRunId) {
            startPolling(nextActive.run_id);
          }
        } else {
          // Still queued or running; schedule next non-overlapping poll in 500ms
          pollTimerRef.current = window.setTimeout(pollStep, 500);
        }
      } catch (pollErr: any) {
        if (!isMountedRef.current) return;
        setPollingRunId(null);
        if (pollErr instanceof ResearchApiError) {
          setErrorMsg(`輪詢狀態中斷 [${pollErr.status}]: ${pollErr.detail}`);
        } else {
          setErrorMsg("輪詢任務狀態連線異常");
        }
      }
    };

    pollStep();
  }, [selectRun]);

  // Load initial version, catalog, and runs; auto-resume existing queued/running tasks
  const loadInitialData = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [ver, cat, rList] = await Promise.all([
        researchApi.getVersion(),
        researchApi.getCatalog(),
        researchApi.getRuns(),
      ]);
      if (!isMountedRef.current) return;
      setVersion(ver);
      setCatalog(cat);
      setRuns(rList);

      if (cat.defaults) {
        setPeriod(cat.defaults.parameters.period);
        setQuantity(cat.defaults.parameters.quantity);
        setInitialBalance(cat.defaults.initial_balance);
        setFeeRate(cat.defaults.fee_rate);
        setSlippageBps(cat.defaults.slippage_bps);
        setWarmupBars(cat.defaults.warmup_bars);
      }

      const backtestRuns = rList.filter((r) => r.kind === "backtest");

      // Check if there is an active running backtest task to auto-resume polling
      const activeBacktest = backtestRuns.find(
        (r) => r.run_id === ver.active_run_id || r.status === "running" || r.status === "queued"
      );

      if (activeBacktest) {
        // Auto-resume polling for existing active task on page load
        setSelectedRun(activeBacktest);
        startPolling(activeBacktest.run_id);
      } else if (backtestRuns.length > 0) {
        selectRun(backtestRuns[0]);
      } else {
        setSelectedRun(null);
        setResult(null);
      }
    } catch (err) {
      if (!isMountedRef.current) return;
      if (err instanceof ResearchApiError) {
        setErrorMsg(`API 連線異常 [${err.status}]: ${err.detail}`);
      } else {
        setErrorMsg("無法連線至研究 API 服務，請確認 127.0.0.1 服務狀態");
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [selectRun, startPolling]);

  // Periodically refresh version and runs when backend is busy
  useEffect(() => {
    if (version?.active_run_id && pollingRunId === null) {
      let isCancelled = false;
      const pollBusyStatus = async () => {
        try {
          const [ver, rList] = await Promise.all([
            researchApi.getVersion(),
            researchApi.getRuns(),
          ]);
          if (!isMountedRef.current || isCancelled) return;
          setVersion(ver);
          setRuns(rList);

          // If the active task is a backtest, start polling it!
          const activeBacktest = rList.find(
            (r) => r.kind === "backtest" && (r.run_id === ver.active_run_id || r.status === "running" || r.status === "queued")
          );
          if (activeBacktest) {
            startPolling(activeBacktest.run_id);
            return;
          }

          if (ver.active_run_id) {
            busyPollTimerRef.current = window.setTimeout(pollBusyStatus, 300);
          }
        } catch {
          if (!isMountedRef.current || isCancelled) return;
          busyPollTimerRef.current = window.setTimeout(pollBusyStatus, 1000);
        }
      };
      busyPollTimerRef.current = window.setTimeout(pollBusyStatus, 300);
      return () => {
        isCancelled = true;
        if (busyPollTimerRef.current !== null) {
          window.clearTimeout(busyPollTimerRef.current);
          busyPollTimerRef.current = null;
        }
      };
    }
  }, [version?.active_run_id, pollingRunId, startPolling]);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Submit backtest
  const handleSubmitBacktest = async () => {
    if (!version || !catalog) return;

    if (version.restart_required) {
      setErrorMsg("原始碼已更新，服務需重新啟動後方可發起新回測");
      return;
    }
    if (version.active_run_id !== null || pollingRunId !== null) {
      setErrorMsg("後端目前有其他任務執行中（忙碌槽佔用），請稍後再試");
      return;
    }

    setSubmitting(true);
    setErrorMsg(null);

    // Strict validation
    if (period < 2 || period > 32) {
      setErrorMsg("period 必須為整數且介於 [2, 32]");
      setSubmitting(false);
      return;
    }
    if (warmupBars < period || warmupBars >= 64) {
      setErrorMsg("warmup_bars 必須 >= period 且小於 64");
      setSubmitting(false);
      return;
    }

    const payload: BacktestRequest = {
      strategy_id: catalog.strategies[0]?.id || "sma-trend",
      dataset_id: catalog.datasets[0]?.id || "synthetic-btc-15m-v1",
      parameters: {
        period: Number(period),
        quantity: String(quantity).trim(),
      },
      initial_balance: String(initialBalance).trim(),
      fee_rate: String(feeRate).trim(),
      slippage_bps: String(slippageBps).trim(),
      warmup_bars: Number(warmupBars),
    };

    try {
      const initialStatus = await researchApi.submitBacktest(payload, version.build_id);
      if (!isMountedRef.current) return;
      setOpenSubmitDialog(false);
      // Immediately start non-overlapping poll
      startPolling(initialStatus.run_id);
    } catch (err) {
      if (!isMountedRef.current) return;
      if (err instanceof ResearchApiError) {
        if (err.status === 409) {
          setErrorMsg(`後端拒絕提交 [409]: ${err.detail}（服務忙碌或版本不符）`);
        } else if (err.status === 422) {
          setErrorMsg(`請求欄位不合契約 [422]: ${err.detail}`);
        } else {
          setErrorMsg(`提交失敗 [${err.status}]: ${err.detail}`);
        }
      } else {
        setErrorMsg("網路傳輸異常，未確認提交結果。請檢查歷史清單確認任務狀態，勿盲目重複點擊。");
      }
    } finally {
      if (isMountedRef.current) {
        setSubmitting(false);
      }
    }
  };

  const isRestartRequired = version?.restart_required === true;
  const isBusy = (version?.active_run_id !== null && version?.active_run_id !== undefined) || pollingRunId !== null;
  const backtestRuns = runs.filter((r) => r.kind === "backtest");

  // Derive parameters from actual selected run / result
  const activeRequest = result?.request || selectedRun?.request;
  const perf = result?.result?.performance;
  const isRunning = selectedRun?.status === "running" || selectedRun?.status === "queued";
  const isFailed = selectedRun?.status === "failed";

  return (
    <AppShell>
      <PageHead
        code="RESEARCH // BACKTEST"
        title="歷史回測中心"
        desc="單合約單週期 Closed Bar 策略回測 · Decimal 精準結算 · 零盤中偷窺"
        right={
          <div className="flex items-center gap-2">
            {pollingRunId && (
              <span className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono bg-primary/10 border border-primary/30 text-primary rounded animate-pulse">
                <RefreshCw className="size-3 animate-spin" />
                <span>輪詢任務: {pollingRunId.slice(0, 8)}...</span>
              </span>
            )}
            <Button
              id="btn-refresh-backtest"
              onClick={() => loadInitialData()}
              variant="outline"
              size="sm"
              className="h-7 text-xs border-border bg-surface hover:bg-surface-raised cursor-pointer"
            >
              <RefreshCw className={cn("size-3.5 mr-1", loading && "animate-spin")} /> 重新整理
            </Button>
            <Button
              id="btn-open-backtest-modal"
              onClick={() => setOpenSubmitDialog(true)}
              size="sm"
              disabled={submitting || isBusy || isRestartRequired}
              className={cn(
                "h-7 text-xs font-medium cursor-pointer",
                isBusy || isRestartRequired
                  ? "bg-muted text-muted-foreground cursor-not-allowed opacity-60"
                  : "bg-primary text-primary-foreground hover:bg-primary/90"
              )}
              title={
                isRestartRequired
                  ? "原始碼已變更，後端需重啟後才可提交"
                  : isBusy
                  ? "後端目前執行任務中 (單槽忙碌)"
                  : "發起新回測"
              }
            >
              <Play className="size-3.5 mr-1 fill-current" />
              {isBusy ? "服務忙碌中" : "發起新回測"}
            </Button>
          </div>
        }
      />

      <div className="space-y-3">
        {/* ==================== 狀態指示與版本橫幅 ==================== */}
        <div className="flex flex-wrap items-center justify-between gap-2.5 rounded-lg border border-border/80 bg-surface/90 px-3.5 py-2 text-xs font-mono shadow-xs backdrop-blur-md">
          <div className="flex items-center gap-2.5">
            <span className={cn(
              "px-1.5 py-0.5 rounded text-[10px] font-bold",
              version ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30" : "bg-rose-500/15 text-rose-400 border border-rose-500/30"
            )}>
              {version ? "127.0.0.1:8770 ONLINE" : "OFFLINE / DISCONNECTED"}
            </span>
            <span className="text-muted-foreground">
              策略: <strong className="text-foreground">{catalog?.strategies[0]?.name || "SMA 趨勢 (Long / Flat)"}</strong>
            </span>
            <span className="text-border">|</span>
            <span className="text-muted-foreground">
              資料集: <strong className="text-foreground">{catalog?.datasets[0]?.name || "合成 BTC 15m (96 根)"}</strong>
            </span>
          </div>

          <div className="flex items-center gap-2 text-[11px] font-mono text-muted-foreground">
            <span>Build: <strong className="text-primary">{version?.build_id ? version.build_id.slice(0, 8) : "--"}</strong></span>
            {isRestartRequired && (
              <span className="text-amber-400 font-bold bg-amber-400/10 px-1 rounded">
                [RESTART REQUIRED]
              </span>
            )}
            <span className="text-border">|</span>
            <span>合約: <strong className="text-foreground">BTC-USDT-SWAP</strong></span>
          </div>
        </div>

        {errorMsg && (
          <div className="flex items-center gap-2 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3.5 py-2 text-xs font-mono text-rose-400">
            <AlertCircle className="size-4 shrink-0 text-rose-400" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* ==================== 頂部核心指標 (定案方案 B 嚴格 Decimal 核心) ==================== */}
        <div
          id="backtest-summary-kpis"
          data-selected-run-id={selectedRun?.run_id || ""}
          data-result-run-id={result?.run_id || ""}
          data-result-period={activeRequest?.parameters?.period ?? ""}
          data-result-net-pnl={perf?.net_pnl ?? ""}
          data-result-trade-count={perf?.trade_count ?? ""}
          className="flex flex-wrap items-center justify-between gap-2.5 rounded-lg border border-border/80 bg-surface/90 px-3.5 py-2 text-xs font-mono shadow-xs backdrop-blur-md"
        >
          <div className="flex items-center gap-3">
            <span className="text-muted-foreground">
              總回報: <strong className={cn("font-bold text-sm", perf && parseFloat(perf.return_pct) >= 0 ? "text-up" : "text-down")}>
                {perf ? `${parseFloat(perf.return_pct) >= 0 ? '+' : ''}${perf.return_pct}%` : "--"}
              </strong>
            </span>
            <span className="text-border">|</span>
            <span className="text-muted-foreground">
              淨損益: <strong className={cn("font-bold", perf && parseFloat(perf.net_pnl) >= 0 ? "text-up" : "text-down")}>
                {perf ? `${parseFloat(perf.net_pnl) >= 0 ? '+' : ''}${perf.net_pnl} USDT` : "--"}
              </strong>
            </span>
            <span className="text-border">|</span>
            <span className="text-muted-foreground">
              最大回撤: <strong className="text-down font-bold">{perf ? `-${perf.max_drawdown_pct}%` : "--"}</strong>
            </span>
            <span className="text-border">|</span>
            <span className="text-muted-foreground">
              成交筆數: <strong className="text-foreground">{perf ? `${perf.trade_count} 筆` : "--"}</strong>
              <span className="text-[10px] text-muted-foreground/80 ml-1">(單邊撮合)</span>
            </span>
            <span className="text-border">|</span>
            <span className="text-muted-foreground">
              夏普 (Sharpe): <span className="text-muted-foreground/60 italic text-[11px]" title="Decimal 核心不包含 Sharpe 或往返勝率">後端尚未提供 (Decimal 核心無此指標)</span>
            </span>
            <span className="text-border">|</span>
            <span className="text-muted-foreground">
              勝率: <span className="text-muted-foreground/60 italic text-[11px]">後端尚未提供 (無往返勝率)</span>
            </span>
          </div>
          <div className="flex items-center gap-2.5 text-[11px] text-muted-foreground">
            <span>初始本金: <strong className="text-foreground">{perf ? `${perf.initial_equity} USDT` : "--"}</strong></span>
            <span className="text-border">|</span>
            <span>期末權益: <strong className="text-primary font-semibold">{perf ? `${perf.final_equity} USDT` : "--"}</strong></span>
            <span className="text-border">|</span>
            <span className="text-amber-400/90 text-[10px]">期末估值，未強制平倉</span>
          </div>
        </div>

        {/* ==================== 定案：水下載回撤圖與月度收益熱力矩陣 ==================== */}
        <BacktestUnderwaterChart
          equityCurve={result?.result?.equity_curve}
          drawdownCurve={result?.drawdown_curve}
          currentEquity={perf ? `${perf.final_equity} USDT` : undefined}
          returnPct={perf?.return_pct}
          maxDrawdownPct={perf?.max_drawdown_pct}
          dataNotice={result?.data_notice}
          loading={resultLoading}
        />

        {/* ==================== 主體分割：左欄回測歷史與約束，右欄模擬成交流 ==================== */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          {/* 左欄：回測任務列表 (5 欄) */}
          <div className="lg:col-span-5 space-y-4">
            <Panel
              title="歷史回測清單 (Backtest Runs)"
              meta={<span className="text-[10px] text-muted-foreground font-mono">{backtestRuns.length} 項紀錄</span>}
            >
              <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
                {backtestRuns.length === 0 ? (
                  <p className="text-xs text-muted-foreground py-4 text-center">尚無回測任務紀錄</p>
                ) : (
                  backtestRuns.map((run) => {
                    const isSelected = selectedRun?.run_id === run.run_id;
                    const periodVal = run.request?.parameters?.period;
                    const qtyVal = run.request?.parameters?.quantity;
                    return (
                      <div
                        key={run.run_id}
                        data-run-id={run.run_id}
                        data-selected={isSelected ? "true" : "false"}
                        onClick={() => selectRun(run)}
                        className={cn(
                          "group cursor-pointer rounded-lg border p-3 transition-all",
                          isSelected
                            ? "border-primary bg-primary/5 shadow-xs"
                            : "border-border/60 bg-surface/40 hover:border-border hover:bg-surface/70"
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            {run.status === "complete" ? (
                              <CheckCircle2 className={cn("size-3.5", isSelected ? "text-primary" : "text-muted-foreground")} />
                            ) : run.status === "failed" ? (
                              <XCircle className="size-3.5 text-rose-400" />
                            ) : (
                              <Clock className="size-3.5 text-amber-400 animate-spin" />
                            )}
                            <span className="font-medium text-xs text-foreground">
                              SMA 回測 · period={periodVal || "?"}
                            </span>
                          </div>
                          <span className={cn(
                            "font-mono text-[10px] px-1.5 py-0.2 rounded font-semibold",
                            run.status === "complete" ? "text-emerald-400 bg-emerald-500/10 border border-emerald-500/30" :
                            run.status === "failed" ? "text-rose-400 bg-rose-500/10 border border-rose-500/30" :
                            "text-amber-400 bg-amber-400/10 border border-amber-400/30"
                          )}>
                            {run.status.toUpperCase()}
                          </span>
                        </div>
                        <div className="mt-2 flex items-center justify-between text-[10px] font-mono text-muted-foreground">
                          <span>{run.request?.dataset_id || "synthetic-btc"} · qty={qtyVal || "?"}</span>
                          <span>{formatUtcTime(run.created_at)}</span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </Panel>

            <Panel title="本筆任務約束與參數 (Constraints)">
              <div className="space-y-2.5 text-xs">
                <div className="flex items-center justify-between border-b border-border/50 pb-2">
                  <span className="text-muted-foreground">K 線週期取樣</span>
                  <span className="font-mono text-foreground font-medium">Closed Bar（次根開盤市價撮合）</span>
                </div>
                <div className="flex items-center justify-between border-b border-border/50 pb-2">
                  <span className="text-muted-foreground">週期參數 (period)</span>
                  <span className="font-mono text-foreground font-medium">{activeRequest?.parameters?.period ?? "--"}</span>
                </div>
                <div className="flex items-center justify-between border-b border-border/50 pb-2">
                  <span className="text-muted-foreground">下單數量 (quantity)</span>
                  <span className="font-mono text-foreground font-medium">{activeRequest?.parameters?.quantity ?? "--"} 張</span>
                </div>
                <div className="flex items-center justify-between border-b border-border/50 pb-2">
                  <span className="text-muted-foreground">預熱根數 (warmup_bars)</span>
                  <span className="font-mono text-foreground font-medium">{activeRequest?.warmup_bars ?? "--"} 根（不計入交易績效）</span>
                </div>
                <div className="flex items-center justify-between border-b border-border/50 pb-2">
                  <span className="text-muted-foreground">手續費費率 (fee_rate)</span>
                  <span className="font-mono text-foreground font-medium">{activeRequest?.fee_rate ?? "--"}</span>
                </div>
                <div className="flex items-center justify-between border-b border-border/50 pb-2">
                  <span className="text-muted-foreground">滑點模型 (slippage_bps)</span>
                  <span className="font-mono text-foreground font-medium">{activeRequest?.slippage_bps ?? "--"} bps</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">資金費與平倉</span>
                  <span className="font-mono text-foreground font-medium">明示零資金費 · 期末估值平倉</span>
                </div>
              </div>
            </Panel>
          </div>

          {/* 右欄：回測成交明細 (7 欄) */}
          <div className="lg:col-span-7 space-y-4">
            <Panel
              title={`模擬逐筆成交流 (${activeRequest?.strategy_id || "sma-trend"})`}
              meta={
                <span className="text-[10px] font-mono text-muted-foreground">
                  {result?.result?.trades?.length || 0} 筆成交 · Decimal 精準結算
                </span>
              }
            >
              <div className="overflow-x-auto max-h-[380px]">
                <table className="w-full text-left border-collapse text-xs">
                  <thead className="border-b border-border text-[10px] font-mono text-muted-foreground bg-background/30 sticky top-0">
                    <tr>
                      <th className="py-2 px-3 font-normal">時間 (UTC)</th>
                      <th className="py-2 px-3 font-normal">方向</th>
                      <th className="py-2 px-3 text-right font-normal">成交價</th>
                      <th className="py-2 px-3 text-right font-normal">數量</th>
                      <th className="py-2 px-3 text-right font-normal">手續費</th>
                      <th className="py-2 px-3 text-right font-normal">已實現損益</th>
                      <th className="py-2 px-3 text-right font-normal">持倉後</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40 font-mono">
                    {resultLoading ? (
                      <tr>
                        <td colSpan={7} className="py-8 text-center text-muted-foreground">
                          <Loader2 className="size-4 animate-spin inline mr-1 text-primary" />
                          載入成交流水中...
                        </td>
                      </tr>
                    ) : isRunning ? (
                      <tr>
                        <td colSpan={7} className="py-8 text-center text-amber-400">
                          <Clock className="size-4 animate-spin inline mr-1" />
                          任務仍在執行中 ({selectedRun?.status})，尚未產生最終結果
                        </td>
                      </tr>
                    ) : isFailed ? (
                      <tr>
                        <td colSpan={7} className="py-8 text-center text-rose-400">
                          <XCircle className="size-4 inline mr-1" />
                          任務執行失敗: {selectedRun?.error || "未知錯誤"}
                        </td>
                      </tr>
                    ) : !result?.result?.trades || result.result.trades.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="py-8 text-center text-muted-foreground">
                          此回測期間無產生任何成交撮合
                        </td>
                      </tr>
                    ) : (
                      result.result.trades.map((t, idx) => {
                        const isBuy = !t.quantity.startsWith("-");
                        return (
                          <tr key={idx} className="hover:bg-secondary/30 transition-colors">
                            <td className="py-2.5 px-3 text-[11px] text-muted-foreground">
                              {formatUtcTime(t.time_ms)}
                            </td>
                            <td className="py-2.5 px-3">
                              <span className={cn(
                                "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-semibold",
                                isBuy ? "bg-up/10 text-up" : "bg-down/10 text-down"
                              )}>
                                {isBuy ? <ArrowDownLeft className="size-2.5" /> : <ArrowUpRight className="size-2.5" />}
                                {isBuy ? "BUY" : "SELL"}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 text-right font-medium text-foreground">{t.price}</td>
                            <td className="py-2.5 px-3 text-right text-muted-foreground">{t.quantity}</td>
                            <td className="py-2.5 px-3 text-right text-muted-foreground">{t.fee} USDT</td>
                            <td className={cn(
                              "py-2.5 px-3 text-right font-medium",
                              parseFloat(t.realized_pnl) >= 0 ? "text-up" : "text-down"
                            )}>
                              {parseFloat(t.realized_pnl) >= 0 ? `+${t.realized_pnl}` : t.realized_pnl} USDT
                            </td>
                            <td className="py-2.5 px-3 text-right text-muted-foreground font-semibold">
                              {t.position_after}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </Panel>

            {/* 回測底層假設說明 */}
            {result?.result?.assumptions && (
              <div className="rounded-lg border border-border/60 bg-surface/40 p-3 text-[11px] text-muted-foreground space-y-1">
                <div className="flex items-center gap-1.5 font-medium text-foreground text-xs mb-1">
                  <Layers className="size-3.5 text-primary" />
                  <span>底層架構假設 (P7 Decimal Research Core)</span>
                </div>
                <ul className="list-disc list-inside space-y-0.5 font-mono text-[10.5px]">
                  {result.result.assumptions.slice(0, 4).map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ==================== 發起新回測 Dialog ==================== */}
      <Dialog open={openSubmitDialog} onOpenChange={setOpenSubmitDialog}>
        <DialogContent className="border-border bg-surface max-w-md">
          <DialogHeader>
            <DialogTitle className="font-mono text-primary text-sm flex items-center gap-2">
              <Play className="size-4 text-primary fill-current" />
              發起 Closed Bar 策略回測
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              嚴格遵循 Decimal 計算契約 · 單合約、單週期合成 K 線
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-1">
            <div className="space-y-1">
              <Label className="text-[11px] font-mono text-muted-foreground">選擇登錄策略</Label>
              <div className="px-2.5 py-1.5 rounded border border-border bg-background text-xs font-mono text-foreground">
                {catalog?.strategies[0]?.name || "SMA 趨勢（Long / Flat）"} ({catalog?.strategies[0]?.id || "sma-trend"})
              </div>
            </div>

            <div className="space-y-1">
              <Label className="text-[11px] font-mono text-muted-foreground">標的與資料集</Label>
              <div className="px-2.5 py-1.5 rounded border border-border bg-background text-xs font-mono text-foreground flex items-center justify-between">
                <span>{catalog?.datasets[0]?.name || "合成 BTC 15m · 96 根 K 線"}</span>
                <span className="text-[10px] text-primary">BTC-USDT-SWAP</span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-[11px] font-mono text-muted-foreground">SMA 週期 (period: 2~32)</Label>
                <Input
                  type="number"
                  min={2}
                  max={32}
                  value={period}
                  onChange={(e) => setPeriod(parseInt(e.target.value) || 2)}
                  className="font-mono text-xs bg-background h-8"
                />
              </div>

              <div className="space-y-1">
                <Label className="text-[11px] font-mono text-muted-foreground">下單張數 (quantity: 1~1000)</Label>
                <Input
                  type="text"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="font-mono text-xs bg-background h-8"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-[11px] font-mono text-muted-foreground">初始本金 (USDT)</Label>
                <Input
                  type="text"
                  value={initialBalance}
                  onChange={(e) => setInitialBalance(e.target.value)}
                  className="font-mono text-xs bg-background h-8"
                />
              </div>

              <div className="space-y-1">
                <Label className="text-[11px] font-mono text-muted-foreground">預熱根數 (warmup: &gt;= period)</Label>
                <Input
                  type="number"
                  min={period}
                  max={63}
                  value={warmupBars}
                  onChange={(e) => setWarmupBars(parseInt(e.target.value) || period)}
                  className="font-mono text-xs bg-background h-8"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-[11px] font-mono text-muted-foreground">手續費率 (fee_rate)</Label>
                <Input
                  type="text"
                  value={feeRate}
                  onChange={(e) => setFeeRate(e.target.value)}
                  className="font-mono text-xs bg-background h-8"
                />
              </div>

              <div className="space-y-1">
                <Label className="text-[11px] font-mono text-muted-foreground">滑價 (slippage_bps)</Label>
                <Input
                  type="text"
                  value={slippageBps}
                  onChange={(e) => setSlippageBps(e.target.value)}
                  className="font-mono text-xs bg-background h-8"
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setOpenSubmitDialog(false)}
              className="text-xs h-8 cursor-pointer"
            >
              取消
            </Button>
            <Button
              id="btn-confirm-submit-backtest"
              type="button"
              size="sm"
              disabled={submitting}
              onClick={handleSubmitBacktest}
              className="text-xs h-8 bg-primary text-primary-foreground hover:bg-primary/90 font-medium cursor-pointer"
            >
              {submitting ? "提交中..." : "確認發起回測"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
