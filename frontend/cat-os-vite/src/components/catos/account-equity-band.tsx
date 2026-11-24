import React, { useState, useRef, useEffect, useMemo } from "react";
import { cn } from "@/lib/utils";
import { CardHeaderTitle } from "./card-header-title";
import { useCatStore } from "@/state/catStore";
import { StateAdapter } from "@/state/stateAdapter";
import { formatClock, formatDateTime, formatDecimal, formatRatioPct, toPlotNumber, toneOf, shortId } from "@/lib/format";

interface AccountEquityBandProps {
  className?: string;
  showHeader?: boolean;
}

const STATE_LABEL: Record<string, string> = {
  starting: "啟動中", running: "運行中", stopping: "停止中", completed: "已完成",
  stopped: "已停止", failed: "失敗", recovery_required: "待恢復",
};

function formatShortAxisDate(ms: number | null | undefined, multiDay: boolean): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms)) return "不適用";
  if (!multiDay) return formatClock(ms, false);
  const full = formatDateTime(ms); // "MM/DD HH:mm"
  return full.split(" ")[0] || full;
}

/**
 * 帳戶權益與損益 (AccountEquityBand)
 * 依卡片寬高比自動切換三種形態：
 * - 直式/窄卡 (width < 480 && height >= 260)：上下堆疊（上 KPI 摘要、下滿寬曲線）
 * - 超扁橫卡 (height < 210)：緊湊單欄主 KPI＋全高走勢圖
 * - 標準／寬卡：左側自適應寬度 KPI 欄＋右側走勢圖
 */
export function AccountEquityBand({ className, showHeader = true }: AccountEquityBandProps) {
  const summary = useCatStore((s) => s.summary);
  const risk = useCatStore((s) => s.risk);
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
  const isStacked = (cardW < 480 && cardH >= 260) || (cardH > 340 && cardH / Math.max(1, cardW) >= 0.78);
  const isShort = !isStacked && cardH < 210;
  const isNarrow = cardW < 520;
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
  const axisW = chartWidth < 260 ? 38 : isNarrow ? 44 : 52;
  const xAxisH = height < 100 ? 15 : 20;
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
  const getY = (v: number) => 8 + ((yBounds.hi - v) / (yBounds.hi - yBounds.lo)) * Math.max(10, plotH - 18);

  const line = useMemo(() => {
    let d = "";
    let pen = false;
    points.forEach((v, k) => {
      if (Number.isNaN(v)) { pen = false; return; }
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
    if (px > plotW || px < 0) { setHoverIdx(null); return; }
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
  const fmtPctNumber = (v: number) => (Number.isNaN(v) ? "不適用" : `${v > 0 ? "+" : ""}${v.toFixed(2)}%`);

  const emptyReason =
    connection.status === "mode_not_open" ? "此模式未開放（demo/live 不在 v1 範圍）"
    : connection.status === "unavailable" ? `模擬服務不可用：${connection.detail ?? "unknown"}`
    : connection.status === "error" ? `無法連線：${connection.detail ?? "network_error"}`
    : !bot ? "等待模擬服務…"
    : !runId ? "尚未啟動模擬 run"
    : curve.length === 0 ? "本次 run 尚無已收盤 K 線觀測"
    : null;

  const Kpi = ({ label, value, sub, tone, hideSub }: { label: string; value: string; sub?: string; tone?: string; hideSub?: boolean }) => (
    <div className="flex flex-col gap-0.5 min-w-0">
      <span className="text-t2 text-muted-foreground font-sans truncate">{label}</span>
      <span className={cn("font-semibold leading-tight tabular-nums truncate", isWide ? "text-sm" : "text-xs", tone ?? "text-foreground")}>{value}</span>
      {!hideSub && sub && <span className="text-t1 text-muted-foreground/75 truncate leading-tight" title={sub}>{sub}</span>}
    </div>
  );

  return (
    <div ref={bandRef} className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40", className)}>
      {showHeader && (
        <div className="flex items-center justify-between px-3 h-9 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
          <CardHeaderTitle
            cardId="equity"
            title="帳戶權益與損益"
            subtext={
              cardW >= 380 ? (
                <span className={cn(
                  "px-1.5 py-0.5 rounded border text-t1 font-mono font-semibold leading-none shrink-0 whitespace-nowrap inline-flex items-center gap-1",
                  connection.status === "ok"
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                    : "bg-amber-500/10 border-amber-500/30 text-amber-400"
                )}>
                  <span className={cn("size-1.5 rounded-full", connection.status === "ok" ? "bg-emerald-400" : "bg-amber-400")} />
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
                  {runId ? `${shortId(runId)} · ${STATE_LABEL[bot?.state ?? ""] ?? bot?.state}` : "無 run"}
                </span>
              </>
            )}
          </div>
        </div>
      )}

      {/* 依寬高比自動切換：直式上下堆疊 vs 橫式左右並排 */}
      <div className={cn("flex flex-1 min-h-0 overflow-hidden relative", isStacked ? "flex-col" : "flex-row")}>
        {/* KPI 區塊 */}
        <div className={cn(
          "shrink-0 bg-background/20 overflow-y-auto custom-scrollbar",
          isStacked
            ? "w-full border-b border-border/70 px-3 py-2.5 flex flex-col gap-2"
            : isShort
            ? "w-[178px] border-r border-border/70 px-2.5 py-2 flex flex-col justify-center gap-1.5"
            : isWide
            ? "w-[252px] border-r border-border/70 px-3.5 py-3 flex flex-col justify-between gap-2.5"
            : isNarrow
            ? "w-[168px] border-r border-border/70 px-2.5 py-2.5 flex flex-col justify-between gap-2"
            : "w-[216px] border-r border-border/70 px-3 py-3 flex flex-col justify-between gap-2.5"
        )}>
          <div className={cn("flex", isStacked ? "items-baseline justify-between gap-2 flex-wrap" : "flex-col gap-0.5")}>
            <div className="flex flex-col gap-0.5 min-w-0">
              {!isShort && <span className="text-t2 text-muted-foreground font-sans">帳戶總權益</span>}
              <div className={cn(
                "font-mono font-bold text-foreground tracking-tight tabular-nums leading-tight",
                isShort ? "text-lg" : isWide ? "text-3xl" : isNarrow ? "text-xl" : "text-2xl"
              )}>
                {summary ? formatDecimal(summary.equity, { prefix: "$" }) : <span className="text-muted-foreground text-sm">未啟動</span>}
              </div>
            </div>
            <div className={cn("font-mono font-semibold tabular-nums", isShort ? "text-t2" : "text-t3", toneOf(summary?.period_pnl))}>
              {summary?.period_pnl != null
                ? `${formatDecimal(summary.period_pnl, { sign: true, prefix: "$" })} (${formatRatioPct(summary.period_pnl_ratio)})`
                : "風控期間損益 不適用"}
            </div>
          </div>

          <div className={cn(
            "grid font-mono border-t border-border/60",
            isStacked
              ? (cardW >= 360 ? "grid-cols-4 gap-2 pt-2" : "grid-cols-2 gap-2 pt-2")
              : isShort
              ? "grid-cols-2 gap-x-2 gap-y-1 pt-1.5"
              : "grid-cols-2 gap-x-2.5 gap-y-2.5 pt-2.5"
          )}>
            <Kpi
              label="已實現損益"
              value={formatDecimal(summary?.realized_pnl, { sign: true, prefix: "$" }, "未啟動")}
              tone={summary ? toneOf(summary.realized_pnl) : undefined}
              sub="OKX 模擬子帳戶"
              hideSub={isShort || isStacked}
            />
            <Kpi
              label="未實現損益"
              value={formatDecimal(summary?.unrealized_pnl, { sign: true, prefix: "$" }, "未啟動")}
              tone={summary ? toneOf(summary.unrealized_pnl) : undefined}
              sub={risk?.snapshot ? `標記 $${formatDecimal(risk.snapshot.mark)}` : "尚無標記價"}
              hideSub={isShort || isStacked}
            />
            {!isShort && (
              <>
                <Kpi
                  label="風控期間基準"
                  value={summary?.basis_equity ? formatDecimal(summary.basis_equity, { prefix: "$" }) : "不適用"}
                  sub={summary?.period_start_ms ? `${formatDateTime(summary.period_start_ms)} 起算` : "尚無基準"}
                  hideSub={isStacked}
                />
                <Kpi
                  label="手續費累計"
                  value={formatDecimal(summary?.fees, { prefix: "$", digits: 4 }, "未啟動")}
                  tone={summary ? "text-rose-400" : undefined}
                  sub={summary ? `槓桿上限 ${formatDecimal(summary.leverage_limit, { digits: 1 })}x` : undefined}
                  hideSub={isStacked}
                />
              </>
            )}
          </div>
        </div>

        {/* SVG 走勢圖（移除硬性 min-h 死鎖，完美貼合任何高度比例） */}
        <div className={cn("flex-1 flex flex-col min-w-0 min-h-0", isShort ? "px-2.5 py-1.5" : "px-3 py-2.5")}>
          <div className="flex items-center justify-between gap-2 text-t2 font-mono text-muted-foreground h-4 shrink-0 min-w-0">
            <div className="flex items-center gap-1.5 shrink-0 whitespace-nowrap">
              <span className="w-2.5 h-[2px] bg-primary inline-block rounded-full" />
              <span>{chartWidth < 300 ? `權益 · ${curve.length} 點` : `本次 run 權益曲線 · ${curve.length} 點`}</span>
            </div>
            <div className="min-w-0 truncate text-right">
              {hover ? (
                <span className="text-foreground font-mono text-t2 whitespace-nowrap tabular-nums">
                  {formatDateTime(hover.time_ms)} · {formatDecimal(hover.equity, { prefix: "$" })} ·{" "}
                  <span className="text-primary font-bold">{fmtPctNumber(hoverPct)}</span>
                </span>
              ) : (
                chartWidth >= 360 && (
                  <span className="text-muted-foreground/55 text-t1 whitespace-nowrap">
                    懸停檢視各 K 線權益
                  </span>
                )
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
            ) : chartWidth > 0 && chartHeight > 0 && (
              <svg width={chartWidth} height={height} className="w-full h-full overflow-visible">
                <defs>
                  <linearGradient id="v0EqGradReact2" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.20} />
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
                      stroke="currentColor"
                      className={t === 0 ? "text-border/75" : "text-border/35"}
                      strokeDasharray={t === 0 ? undefined : "3 3"}
                      strokeWidth={t === 0 ? 1 : 0.75}
                    />
                    <text
                      x={plotW + 5}
                      y={getY(t) + 3}
                      fill="currentColor"
                      className={cn("text-t1 font-mono", t === 0 ? "text-primary font-semibold" : "text-muted-foreground/65")}
                    >
                      {t > 0 ? `+${t.toFixed(1)}%` : `${t.toFixed(1)}%`}
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
                    className="text-t1 font-mono text-muted-foreground/65"
                  >
                    {formatShortAxisDate(curve[idx]?.time_ms, isMultiDay)}
                  </text>
                ))}

                {areaPath && <path d={areaPath} fill="url(#v0EqGradReact2)" />}
                {line && <path d={line} fill="none" stroke="var(--primary)" strokeWidth={1.75} strokeLinejoin="round" />}
                {lastValidIdx >= 0 && hoverIdx === null && (
                  <circle
                    cx={getX(lastValidIdx)}
                    cy={getY(points[lastValidIdx])}
                    r={3}
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
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
