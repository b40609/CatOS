import React, { useState, useRef, useEffect, useMemo } from "react";
import { cn } from "@/lib/utils";
import { CardHeaderTitle } from "./card-header-title";
import { useCatStore } from "@/state/catStore";
import { StateAdapter } from "@/state/stateAdapter";
import {
  formatClock,
  formatDateTime,
  formatDecimal,
  formatRatioPct,
  toPlotNumber,
  toneOf,
  shortId,
} from "@/lib/format";
import { deriveCushionStatus } from "@/lib/status-truth";

interface AccountEquityBandProps {
  className?: string;
  showHeader?: boolean;
}

const STATE_LABEL: Record<string, string> = {
  starting: "啟動中",
  running: "運行中",
  stopping: "停止中",
  completed: "已完成",
  stopped: "已停止",
  failed: "失敗",
  recovery_required: "待恢復",
};

function formatShortAxisDate(ms: number | null | undefined, multiDay: boolean): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms)) return "不適用";
  if (!multiDay) return formatClock(ms, false);
  const full = formatDateTime(ms); // "MM/DD HH:mm"
  return full.split(" ")[0] || full;
}

function formatLimitPctLabel(pct: number): string {
  const rounded = Math.round(pct * 10) / 10;
  return Number.isInteger(rounded) ? `${rounded}%` : `${rounded.toFixed(1)}%`;
}

function fmtSignedPct(v: number, digits = 2): string {
  if (!Number.isFinite(v)) return "不適用";
  const rounded = Number(v.toFixed(digits));
  if (rounded === 0) return `${(0).toFixed(digits)}%`;
  return `${rounded > 0 ? "+" : ""}${rounded.toFixed(digits)}%`;
}

function fmtDrawdownNum(v: number, digits = 1): string {
  if (!Number.isFinite(v)) return "不適用";
  const rounded = Number(v.toFixed(digits));
  if (rounded === 0) return `${(0).toFixed(digits)}%`;
  return `${rounded.toFixed(digits)}%`;
}

/**
 * 帳戶權益與損益 (AccountEquityBand)
 * 採用定案「方案 1：雙欄髮絲帳本」：
 * - 左欄無嵌套小方盒、無光暈動畫，純 1px 髮絲線排版：
 *   頂部總權益＋右對齊日切損益 → 中段裸尺日損風控安全墊 → 底部 4 行純線帳本
 * - 右欄走勢圖：調亮水平格線與 0% 基準線，頂部顯示真實區間統計（累計／最高／回撤），懸停切回該點明細
 * - 依卡片寬高比自動切換直式堆疊／矮卡緊湊／標準與寬卡雙欄
 */
export function AccountEquityBand({ className, showHeader = true }: AccountEquityBandProps) {
  const summary = useCatStore((s) => s.summary);
  const risk = useCatStore((s) => s.risk);
  const killSwitch = useCatStore((s) => s.killSwitch);
  const bots = useCatStore((s) => s.bots);
  const events = useCatStore((s) => s.events);
  const connection = useCatStore((s) => s.connection);

  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const [chartWidth, setChartWidth] = useState(500);
  const [chartHeight, setChartHeight] = useState(200);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const bandRef = useRef<HTMLDivElement>(null);
  const [bandDimensions, setBandDimensions] = useState({ width: 640, height: 260 });

  const bot = bots[0] ?? null;
  const runId = bot?.current_run_id ?? null;
  const curve = useMemo(() => StateAdapter.equityCurve(events, runId), [events, runId]);

  useEffect(() => {
    const el = bandRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setBandDimensions({ width: entry.contentRect.width, height: entry.contentRect.height });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const { width: cardW, height: cardH } = bandDimensions;
  const isStacked =
    (cardW < 480 && cardH >= 260) || (cardH > 340 && cardH / Math.max(1, cardW) >= 0.78);
  const isShort = !isStacked && cardH < 248;
  const isNarrow = !isStacked && cardW < 560;
  const isWide = !isStacked && cardW >= 780;

  useEffect(() => {
    const el = chartContainerRef.current;
    if (!el) return;
    const updateSize = () => {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0) setChartWidth(Math.floor(rect.width));
      if (rect.height > 0) setChartHeight(Math.floor(rect.height));
    };
    updateSize();
    const ro = new ResizeObserver(updateSize);
    ro.observe(el);
    return () => ro.disconnect();
  }, [isStacked, isShort]);

  const height = Math.max(68, chartHeight);
  const axisW = chartWidth < 260 ? 42 : isNarrow ? 50 : 58;
  const xAxisH = height < 100 ? 16 : 22;
  const plotW = Math.max(1, chartWidth - axisW);
  const plotH = Math.max(1, height - xAxisH);

  const points = useMemo(() => {
    const values = curve.map((p) => toPlotNumber(p.equity));
    const base = values.find((v) => !Number.isNaN(v));
    if (base === undefined || base === 0) return values.map(() => Number.NaN);
    return values.map((v) => (Number.isNaN(v) ? Number.NaN : (v / base - 1) * 100));
  }, [curve]);
  const n = points.length;

  const isMultiDay = useMemo(() => {
    if (curve.length < 2) return false;
    const span = (curve[curve.length - 1]?.time_ms ?? 0) - (curve[0]?.time_ms ?? 0);
    return span > 36 * 3600 * 1000;
  }, [curve]);

  const niceStep = (span: number) => {
    const raw = span / (plotH < 100 ? 2 : 3);
    const mag = 10 ** Math.floor(Math.log10(raw || 1));
    const stepN = raw / mag;
    return (stepN < 1.5 ? 1 : stepN < 3 ? 2 : stepN < 7 ? 5 : 10) * mag;
  };

  const yBounds = useMemo(() => {
    const pts = points.filter((v) => !Number.isNaN(v));
    let lo = Math.min(0, ...pts);
    let hi = Math.max(0, ...pts);
    const span = hi - lo || 0.01;
    hi += span * 0.16;
    lo -= span * 0.16;
    const step = niceStep(hi - lo);
    const ticks: number[] = [];
    for (let t = Math.ceil(lo / step) * step; t <= hi; t += step) ticks.push(Number(t.toFixed(6)));
    return { lo, hi, ticks };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [points, plotH]);

  const getX = (k: number) => (n > 1 ? (k / (n - 1)) * plotW : plotW / 2);
  const getY = (v: number) =>
    8 + ((yBounds.hi - v) / (yBounds.hi - yBounds.lo)) * Math.max(10, plotH - 18);

  const line = useMemo(() => {
    let d = "";
    let pen = false;
    points.forEach((v, k) => {
      if (Number.isNaN(v)) {
        pen = false;
        return;
      }
      d += `${pen ? "L" : "M"}${getX(k).toFixed(1)},${getY(v).toFixed(1)}`;
      pen = true;
    });
    return d;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [points, plotW, plotH, yBounds]);

  const areaPath = useMemo(() => {
    const firstK = points.findIndex((v) => !Number.isNaN(v));
    if (firstK < 0 || !line) return "";
    const zeroY = Math.min(plotH - 6, Math.max(6, getY(0)));
    return `${line}L${getX(n - 1).toFixed(1)},${zeroY.toFixed(1)}L${getX(firstK).toFixed(1)},${zeroY.toFixed(1)}Z`;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [line, n, plotW, plotH, yBounds]);

  const xTicks = useMemo(() => {
    if (n === 0) return [] as number[];
    const fractions = plotW < 240 ? [0, 1] : plotW < 420 ? [0, 0.5, 1] : [0, 0.25, 0.5, 0.75, 1];
    return [...new Set(fractions.map((f) => Math.round(f * (n - 1))))];
  }, [n, plotW]);

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!chartContainerRef.current || n === 0) return;
    const rect = chartContainerRef.current.getBoundingClientRect();
    const px = e.clientX - rect.left;
    if (px > plotW || px < 0) {
      setHoverIdx(null);
      return;
    }
    setHoverIdx(Math.max(0, Math.min(n - 1, Math.round((px / plotW) * (n - 1)))));
  };

  const hover = hoverIdx !== null && curve[hoverIdx] ? curve[hoverIdx] : null;
  const hoverPct = hoverIdx !== null ? points[hoverIdx] : Number.NaN;

  const lastValidIdx = useMemo(() => {
    for (let i = points.length - 1; i >= 0; i--) {
      if (!Number.isNaN(points[i])) return i;
    }
    return -1;
  }, [points]);

  // 由真實 curve / points 計算的區間統計（累計 / 最高 / 最大回撤）
  const curveStats = useMemo(() => {
    if (lastValidIdx < 0) return null;
    let peakPct = -Infinity;
    let runningPeakEq = -Infinity;
    let maxDrawdownPct = 0;
    for (let i = 0; i < curve.length; i++) {
      const pct = points[i];
      const eq = toPlotNumber(curve[i]?.equity);
      if (Number.isNaN(pct) || Number.isNaN(eq)) continue;
      if (pct > peakPct) peakPct = pct;
      if (eq > runningPeakEq) runningPeakEq = eq;
      if (runningPeakEq > 0) {
        const dd = ((eq - runningPeakEq) / runningPeakEq) * 100;
        if (dd < maxDrawdownPct) maxDrawdownPct = dd;
      }
    }
    const totalPct = points[lastValidIdx];
    if (!Number.isFinite(totalPct) || !Number.isFinite(peakPct)) return null;
    return { totalPct, peakPct, maxDrawdownPct };
  }, [curve, points, lastValidIdx]);

  // 日損風控安全墊：讀真實 summary.period_pnl_ratio 與 risk.limits / killSwitch.default_limits
  const cushion = useMemo(() => {
    const limits = risk?.limits ?? killSwitch?.default_limits ?? null;
    const softRaw = toPlotNumber(limits?.soft_loss);
    const hardRaw = toPlotNumber(limits?.hard_loss);
    const softPct = Number.isFinite(softRaw) && softRaw > 0 ? softRaw * 100 : null;
    const hardPct = Number.isFinite(hardRaw) && hardRaw > 0 ? hardRaw * 100 : null;

    const ratioStr = summary?.period_pnl_ratio ?? risk?.derived.period_pnl_ratio ?? null;
    const ratioRaw = toPlotNumber(ratioStr);
    const currentPct = Number.isFinite(ratioRaw) ? ratioRaw * 100 : null;

    const maxAbs = hardPct ?? (softPct ? softPct * 2 : 10);
    const toPos = (v: number) => Math.max(0, Math.min(100, ((v + maxAbs) / (2 * maxAbs)) * 100));

    const softTickPos = softPct !== null ? toPos(-softPct) : 25;
    const zeroPos = 50;
    const pinPos = currentPct !== null ? toPos(currentPct) : null;

    const { statusText, statusTone, pinTone, fillTone } = deriveCushionStatus({
      currentPct,
      softPct,
      hardPct,
      riskStatus: risk?.derived.status ?? null,
      riskMode: risk?.mode ?? null,
      killEngaged: Boolean(killSwitch?.engaged),
    });

    const hardLabel = hardPct !== null ? formatLimitPctLabel(hardPct) : null;
    const softLabel = softPct !== null ? formatLimitPctLabel(softPct) : null;
    const currentLabel = ratioStr !== null ? formatRatioPct(ratioStr) : "不適用";

    const tooltip =
      currentPct !== null && softLabel && hardLabel
        ? `目前日切 ${currentLabel} · Soft -${softLabel} / Hard -${hardLabel}`
        : "尚無日損風控安全墊資料";

    return {
      currentPct,
      softTickPos,
      zeroPos,
      pinPos,
      statusText,
      statusTone,
      pinTone,
      fillTone,
      hardLabel,
      softLabel,
      tooltip,
    };
  }, [risk, killSwitch, summary]);

  const emptyReason =
    connection.status === "mode_not_open"
      ? "此模式未開放（demo/live 不在 v1 範圍）"
      : connection.status === "unavailable"
      ? `模擬服務不可用：${connection.detail ?? "unknown"}`
      : connection.status === "error"
      ? `無法連線：${connection.detail ?? "network_error"}`
      : !bot
      ? "等待模擬服務…"
      : !runId
      ? "尚未啟動模擬 run"
      : curve.length === 0
      ? "本次 run 尚無已收盤 K 線觀測"
      : null;

  const periodRatioStr = summary?.period_pnl_ratio ?? null;
  const ledgerRows = [
    {
      label: "已實現損益",
      value: formatDecimal(summary?.realized_pnl, { sign: true, prefix: "$" }, "未啟動"),
      tone: summary ? toneOf(summary.realized_pnl) : "text-muted-foreground",
      title: "OKX 模擬子帳戶已實現損益",
    },
    {
      label: "未實現損益",
      value: formatDecimal(summary?.unrealized_pnl, { sign: true, prefix: "$" }, "未啟動"),
      tone: summary ? toneOf(summary.unrealized_pnl) : "text-muted-foreground",
      title: risk?.snapshot ? `標記價 $${formatDecimal(risk.snapshot.mark)}` : "尚無標記價",
    },
    {
      label: "風控基準",
      value: summary?.basis_equity ? formatDecimal(summary.basis_equity, { prefix: "$" }) : "不適用",
      tone: summary?.basis_equity ? "text-foreground font-semibold" : "text-muted-foreground",
      title: summary?.period_start_ms
        ? `${formatDateTime(summary.period_start_ms)} 起算`
        : "尚無風控期間基準",
    },
    {
      label: "手續費累計",
      value: formatDecimal(summary?.fees, { prefix: "$", digits: 4 }, "未啟動"),
      tone: summary ? "text-rose-400 font-semibold" : "text-muted-foreground",
      title: summary
        ? `有效槓桿上限 ${formatDecimal(summary.leverage_limit, { digits: 1 })}x`
        : "尚未啟動",
    },
  ];

  return (
    <div
      ref={bandRef}
      className={cn(
        "flex flex-col h-full w-full select-none overflow-hidden bg-surface/40",
        className
      )}
    >
      {showHeader && (
        <div className="flex items-center justify-between px-3 h-9 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
          <CardHeaderTitle
            cardId="equity"
            title="帳戶權益與損益"
            subtext={
              cardW >= 380 ? (
                <span
                  className={cn(
                    "px-1.5 py-0.5 rounded border text-t1 font-mono font-semibold leading-none shrink-0 whitespace-nowrap inline-flex items-center gap-1",
                    connection.status === "ok"
                      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                      : "bg-amber-500/10 border-amber-500/30 text-amber-400"
                  )}
                >
                  <span
                    className={cn(
                      "size-1.5 rounded-full",
                      connection.status === "ok" ? "bg-emerald-400" : "bg-amber-400"
                    )}
                  />
                  {connection.status === "ok" ? "local-sim" : connection.status}
                </span>
              ) : undefined
            }
          />
          <div className="flex items-center gap-1 bg-background/60 border border-border/60 rounded px-2 py-0.5 text-t2 font-mono shrink-0">
            <span className="text-foreground font-semibold">{bot ? bot.bot_id : "sim"}</span>
            {cardW >= 340 && (
              <>
                <span className="text-border">·</span>
                <span className="text-muted-foreground whitespace-nowrap">
                  {runId
                    ? `${shortId(runId)} · ${STATE_LABEL[bot?.state ?? ""] ?? bot?.state}`
                    : "無 run"}
                </span>
              </>
            )}
          </div>
        </div>
      )}

      {/* 方案 1：雙欄髮絲帳本（直式窄卡自動切換上下堆疊） */}
      <div
        className={cn(
          "flex flex-1 min-h-0 overflow-hidden relative",
          isStacked ? "flex-col" : "flex-row"
        )}
      >
        {/* 左欄：純 1px 髮絲線排版（零嵌套小方盒、無光暈動畫） */}
        <div
          className={cn(
            "shrink-0 bg-background/20 overflow-y-auto custom-scrollbar flex flex-col justify-between",
            isStacked
              ? "w-full border-b border-border/75 px-3 py-2 gap-1.5"
              : isShort
              ? "w-[236px] border-r border-border/75 px-3 py-1.5 gap-1"
              : isWide
              ? "w-[264px] border-r border-border/75 px-3.5 py-2 gap-1.5"
              : isNarrow
              ? "w-[200px] border-r border-border/75 px-2.5 py-1.5 gap-1"
              : "w-[248px] border-r border-border/75 px-3 py-2 gap-1.5"
          )}
        >
          {/* 頂部：帳戶總權益大字 ＋ 右對齊日切損益與百分比 */}
          <div className="flex items-baseline justify-between gap-2 min-w-0">
            <div className="min-w-0">
              {!isShort && (
                <div className="text-t1 text-muted-foreground font-sans leading-tight">
                  帳戶總權益
                </div>
              )}
              <div
                className={cn(
                  "font-mono font-bold text-foreground tracking-tight tabular-nums leading-tight truncate",
                  isShort
                    ? "text-lg"
                    : isWide
                    ? "text-2xl"
                    : isNarrow
                    ? "text-lg"
                    : "text-xl"
                )}
              >
                {summary ? (
                  formatDecimal(summary.equity, { prefix: "$" })
                ) : (
                  <span className="text-muted-foreground text-t3 font-medium">未啟動</span>
                )}
              </div>
            </div>
            <div className="text-right shrink-0">
              <div
                className={cn(
                  "font-mono text-t3 font-bold tabular-nums leading-tight",
                  summary?.period_pnl != null
                    ? toneOf(summary.period_pnl)
                    : "text-muted-foreground font-normal"
                )}
              >
                {summary?.period_pnl != null
                  ? formatDecimal(summary.period_pnl, { sign: true, prefix: "$" })
                  : "不適用"}
              </div>
              <div
                className={cn(
                  "font-mono text-t1 tabular-nums leading-tight",
                  periodRatioStr != null ? toneOf(periodRatioStr) : "text-muted-foreground"
                )}
              >
                {periodRatioStr != null ? `日切 ${formatRatioPct(periodRatioStr)}` : "日切 不適用"}
              </div>
            </div>
          </div>

          {/* 中段：裸尺「日損風控安全墊」 */}
          <div className="flex flex-col gap-1" title={cushion.tooltip}>
            <div className="flex items-baseline justify-between gap-1.5 text-t1 leading-tight">
              <span className="text-muted-foreground font-sans truncate">日損風控安全墊</span>
              <span
                className={cn(
                  "font-mono font-semibold tabular-nums whitespace-nowrap shrink-0",
                  cushion.statusTone
                )}
              >
                {cushion.statusText}
              </span>
            </div>
            <div className="relative h-1.5 rounded-xs bg-foreground/10 overflow-visible">
              {/* Hard 區間（左端至 Soft 刻度） */}
              <span
                className="absolute left-0 top-0 bottom-0 bg-rose-500/35 rounded-l-xs"
                style={{ width: `${cushion.softTickPos}%` }}
              />
              {/* Soft 區間（Soft 刻度至 0% 軸） */}
              <span
                className="absolute top-0 bottom-0 bg-amber-500/30"
                style={{
                  left: `${cushion.softTickPos}%`,
                  width: `${Math.max(0, cushion.zeroPos - cushion.softTickPos)}%`,
                }}
              />
              {/* 目前日切損益區段填色 */}
              {cushion.pinPos !== null && cushion.currentPct !== null && (
                <span
                  className={cn("absolute top-0 bottom-0", cushion.fillTone)}
                  style={
                    cushion.currentPct >= 0
                      ? {
                          left: `${cushion.zeroPos}%`,
                          width: `${Math.max(0, cushion.pinPos - cushion.zeroPos)}%`,
                        }
                      : {
                          left: `${cushion.pinPos}%`,
                          width: `${Math.max(0, cushion.zeroPos - cushion.pinPos)}%`,
                        }
                  }
                />
              )}
              {/* Soft 刻度線 */}
              <span
                className="absolute -top-0.5 -bottom-0.5 w-px bg-foreground/25"
                style={{ left: `${cushion.softTickPos}%` }}
              />
              {/* 0% 中線 */}
              <span
                className="absolute -top-0.5 -bottom-0.5 w-px bg-foreground/55"
                style={{ left: `${cushion.zeroPos}%` }}
              />
              {/* 目前位置指針 */}
              {cushion.pinPos !== null && (
                <span
                  className={cn(
                    "absolute -top-0.5 -bottom-0.5 w-[3px] rounded-xs -translate-x-1/2",
                    cushion.pinTone
                  )}
                  style={{ left: `${cushion.pinPos}%` }}
                />
              )}
            </div>
            <div className="flex items-center justify-between font-mono text-t1 leading-none text-muted-foreground tabular-nums">
              <span className="text-rose-400">
                {cushion.hardLabel ? (isNarrow ? `-${cushion.hardLabel}` : `Hard -${cushion.hardLabel}`) : "Hard 不適用"}
              </span>
              {cushion.softLabel && (
                <span className="text-amber-400">
                  {isNarrow ? `-${cushion.softLabel}` : `Soft -${cushion.softLabel}`}
                </span>
              )}
              <span>0%</span>
              <span className="text-emerald-400">
                {cushion.hardLabel ? `+${cushion.hardLabel}` : "不適用"}
              </span>
            </div>
          </div>

          {/* 底部：4 行純 1px 細線對齊帳本 */}
          <div
            className={cn(
              "border-t border-border/60",
              isStacked && cardW >= 400
                ? "grid grid-cols-2 gap-x-4"
                : "flex flex-col"
            )}
          >
            {ledgerRows.map((row, idx) => (
              <div
                key={row.label}
                title={row.title}
                className={cn(
                  "flex items-baseline justify-between gap-2 min-w-0 leading-tight",
                  isShort ? "py-[2.5px]" : "py-[3.5px]",
                  isStacked && cardW >= 400
                    ? idx < 2
                      ? "border-b border-border/45"
                      : ""
                    : idx < ledgerRows.length - 1
                    ? "border-b border-border/45"
                    : "pb-0"
                )}
              >
                <span className="text-t2 text-muted-foreground font-sans whitespace-nowrap truncate leading-tight">
                  {row.label}
                </span>
                <span
                  className={cn(
                    "font-mono text-t3 tabular-nums whitespace-nowrap shrink-0 leading-tight",
                    row.tone
                  )}
                >
                  {row.value}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* 右欄：走勢圖（調亮格線與 0% 基準線，頂部真實區間統計） */}
        <div
          className={cn(
            "flex-1 flex flex-col min-w-0 min-h-0",
            isShort ? "px-2.5 py-1.5" : "px-3 py-2"
          )}
        >
          <div className="flex items-center justify-between gap-2 text-t2 font-mono text-muted-foreground h-4 shrink-0 min-w-0">
            <div className="flex items-center gap-1.5 shrink-0 whitespace-nowrap">
              <span className="w-2.5 h-[2px] bg-primary inline-block rounded-full" />
              <span>
                {chartWidth < 360 ? `權益 · ${curve.length} 點` : `run 權益曲線 · ${curve.length} 點`}
              </span>
            </div>
            <div className="min-w-0 truncate text-right">
              {hover ? (
                <span className="text-foreground font-mono text-t2 whitespace-nowrap tabular-nums">
                  {formatDateTime(hover.time_ms)} · {formatDecimal(hover.equity, { prefix: "$" })} ·{" "}
                  <span className="text-primary font-bold">{fmtSignedPct(hoverPct)}</span>
                </span>
              ) : curveStats ? (
                <span className="inline-flex items-center gap-2 text-t1 font-mono whitespace-nowrap tabular-nums">
                  <span>
                    累計{" "}
                    <strong
                      className={cn(
                        "font-semibold",
                        Number(curveStats.totalPct.toFixed(2)) > 0
                          ? "text-emerald-400"
                          : Number(curveStats.totalPct.toFixed(2)) < 0
                          ? "text-rose-400"
                          : "text-foreground"
                      )}
                    >
                      {fmtSignedPct(curveStats.totalPct)}
                    </strong>
                  </span>
                  {chartWidth >= 285 && (
                    <span>
                      最高{" "}
                      <strong className="font-semibold text-foreground">
                        {fmtSignedPct(curveStats.peakPct, 1)}
                      </strong>
                    </span>
                  )}
                  {chartWidth >= 230 && (
                    <span>
                      回撤{" "}
                      <strong
                        className={cn(
                          "font-semibold",
                          Number(curveStats.maxDrawdownPct.toFixed(1)) < 0
                            ? "text-rose-400"
                            : "text-muted-foreground"
                        )}
                      >
                        {fmtDrawdownNum(curveStats.maxDrawdownPct, 1)}
                      </strong>
                    </span>
                  )}
                </span>
              ) : (
                <span className="text-muted-foreground text-t1 whitespace-nowrap">不適用</span>
              )}
            </div>
          </div>

          <div
            ref={chartContainerRef}
            className="flex-1 w-full relative min-h-0 cursor-crosshair mt-1"
            onPointerMove={handlePointerMove}
            onPointerLeave={() => setHoverIdx(null)}
          >
            {emptyReason ? (
              <div className="absolute inset-0 flex items-center justify-center text-t3 font-mono text-muted-foreground">
                {emptyReason}
              </div>
            ) : (
              chartWidth > 0 &&
              chartHeight > 0 && (
                <svg width={chartWidth} height={height} className="w-full h-full overflow-visible">
                  <defs>
                    <linearGradient id="v0EqGradReact2" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.22} />
                      <stop offset="100%" stopColor="var(--primary)" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>

                  {yBounds.ticks.map((t) => (
                    <g key={t}>
                      <line
                        x1={0}
                        x2={plotW}
                        y1={getY(t)}
                        y2={getY(t)}
                        stroke={t === 0 ? "var(--primary)" : "currentColor"}
                        strokeOpacity={t === 0 ? 0.42 : undefined}
                        className={t === 0 ? undefined : "text-foreground/15"}
                        strokeDasharray={t === 0 ? undefined : "3 3"}
                        strokeWidth={t === 0 ? 1 : 0.85}
                      />
                      <text
                        x={plotW + 5}
                        y={getY(t) + 3}
                        fill="currentColor"
                        className={cn(
                          "text-t1 font-mono",
                          t === 0 ? "text-primary font-semibold" : "text-muted-foreground/90"
                        )}
                      >
                        {Math.abs(t) < 0.05
                          ? "0.0%"
                          : t > 0
                          ? `+${t.toFixed(1)}%`
                          : `${t.toFixed(1)}%`}
                      </text>
                    </g>
                  ))}

                  {xTicks.map((idx) => (
                    <text
                      key={idx}
                      x={getX(idx)}
                      y={plotH + (xAxisH - 5)}
                      textAnchor={idx === 0 ? "start" : idx === n - 1 ? "end" : "middle"}
                      fill="currentColor"
                      className="text-t1 font-mono text-muted-foreground/85"
                    >
                      {formatShortAxisDate(curve[idx]?.time_ms, isMultiDay)}
                    </text>
                  ))}

                  {areaPath && <path d={areaPath} fill="url(#v0EqGradReact2)" />}
                  {line && (
                    <path
                      d={line}
                      fill="none"
                      stroke="var(--primary)"
                      strokeWidth={1.85}
                      strokeLinejoin="round"
                    />
                  )}
                  {lastValidIdx >= 0 && hoverIdx === null && (
                    <circle
                      cx={getX(lastValidIdx)}
                      cy={getY(points[lastValidIdx])}
                      r={3.2}
                      fill="var(--primary)"
                      stroke="var(--background)"
                      strokeWidth={1.5}
                    />
                  )}

                  {hoverIdx !== null && (
                    <g>
                      <line
                        x1={getX(hoverIdx)}
                        x2={getX(hoverIdx)}
                        y1={6}
                        y2={plotH}
                        stroke="var(--primary)"
                        strokeWidth={1}
                        strokeDasharray="2 2"
                        opacity={0.75}
                      />
                      <circle
                        cx={getX(hoverIdx)}
                        cy={getY(points[hoverIdx] ?? 0)}
                        r={3.5}
                        fill="var(--primary)"
                        stroke="var(--background)"
                        strokeWidth={1.5}
                      />
                    </g>
                  )}
                </svg>
              )
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
