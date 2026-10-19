import React, { useState, useRef, useEffect, useMemo } from "react";
import {
  PERIODS,
  PERIOD_LABEL,
  timeAt,
  formatPct,
  formatTime,
  formatUsd,
  toneOf,
  accountSeries,
  summarize,
  accountSnapshot,
  INITIAL_BOTS,
  type Period,
} from "@/lib/v0-engine";
import { cn } from "@/lib/utils";
import { CardHeaderTitle } from "./card-header-title";

interface AccountEquityBandProps {
  className?: string;
  defaultPeriod?: Period;
  showHeader?: boolean;
}

export function AccountEquityBand({
  className,
  defaultPeriod = "7D",
  showHeader = true,
}: AccountEquityBandProps) {
  const [period, setPeriod] = useState<Period>(defaultPeriod);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const [chartWidth, setChartWidth] = useState(600);
  const [chartHeight, setChartHeight] = useState(240);
  const chartContainerRef = useRef<HTMLDivElement>(null);

  // 1. 取得帳戶整體 Series 與當前週期摘要
  const totalSeries = useMemo(() => accountSeries(INITIAL_BOTS), []);
  const snap = useMemo(() => accountSnapshot(INITIAL_BOTS), []);
  const periodSum = useMemo(() => summarize(totalSeries, period), [totalSeries, period]);

  // 2. 自適應容器寬高 ResizeObserver (雙向響應式，根除高度硬編碼)
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
  }, []);

  // 3. 幾何座標與軸長運算 (動態自適應容器高度)
  const height = Math.max(120, chartHeight);
  const axisW = 54;
  const xAxisH = 20;
  const plotW = Math.max(1, chartWidth - axisW);
  const plotH = Math.max(1, height - xAxisH);

  const n = periodSum.indices.length;

  const niceStep = (span: number) => {
    const raw = span / 3;
    const mag = 10 ** Math.floor(Math.log10(raw || 1));
    const stepN = raw / mag;
    return (stepN < 1.5 ? 1 : stepN < 3 ? 2 : stepN < 7 ? 5 : 10) * mag;
  };

  const yBounds = useMemo(() => {
    const pts = periodSum.points.filter((v) => !Number.isNaN(v));
    let lo = Math.min(0, ...pts);
    let hi = Math.max(0, ...pts);
    const span = hi - lo || 1;
    hi += span * 0.14;
    lo -= span * 0.14;
    const step = niceStep(hi - lo);
    const ticks: number[] = [];
    for (let t = Math.ceil(lo / step) * step; t <= hi; t += step) {
      ticks.push(Number(t.toFixed(4)));
    }
    return { lo, hi, ticks, step };
  }, [periodSum.points]);

  const getX = (k: number) => (n > 1 ? (k / (n - 1)) * plotW : 0);
  const getY = (v: number) => {
    const { lo, hi } = yBounds;
    return 10 + ((hi - v) / (hi - lo)) * (plotH - 24);
  };

  const generateLine = (vals: number[]) => {
    let d = "";
    let pen = false;
    vals.forEach((v, k) => {
      if (Number.isNaN(v)) {
        pen = false;
        return;
      }
      d += `${pen ? "L" : "M"}${getX(k).toFixed(1)},${getY(v).toFixed(1)}`;
      pen = true;
    });
    return d;
  };

  const eqLinePath = useMemo(() => generateLine(periodSum.points), [periodSum.points, plotW, yBounds]);

  const eqAreaPath = useMemo(() => {
    const firstK = periodSum.points.findIndex((v) => !Number.isNaN(v));
    if (firstK < 0 || !eqLinePath) return "";
    const zeroY = Math.min(plotH - 8, Math.max(8, getY(0)));
    return `${eqLinePath}L${getX(n - 1).toFixed(1)},${zeroY.toFixed(1)}L${getX(firstK).toFixed(1)},${zeroY.toFixed(1)}Z`;
  }, [eqLinePath, n, plotW, plotH, yBounds]);

  const xTicks = useMemo(() => {
    const fractions = plotW < 320 ? [0, 1] : plotW < 480 ? [0, 0.5, 1] : [0, 0.25, 0.5, 0.75, 1];
    return fractions.map((f) => Math.round(f * (n - 1)));
  }, [n, plotW]);

  const lastPoint = periodSum.points[n - 1] ?? 0;

  // 滑鼠懸停互動
  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!chartContainerRef.current) return;
    const rect = chartContainerRef.current.getBoundingClientRect();
    const px = e.clientX - rect.left;
    if (px > plotW || px < 0) {
      setHoverIdx(null);
      return;
    }
    setHoverIdx(Math.max(0, Math.min(n - 1, Math.round((px / plotW) * (n - 1)))));
  };

  const hoverData = useMemo(() => {
    if (hoverIdx === null) return null;
    const rawIdx = periodSum.indices[hoverIdx];
    const timeStr = formatTime(timeAt(rawIdx), true);
    const val = periodSum.points[hoverIdx];
    return { timeStr, val };
  }, [hoverIdx, periodSum]);

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden", className)}>
      {/* 1. Header 列：一體化標題 + 排版切換 + 週期快捷鍵 (單層結構，杜絕雙重標題) */}
      {showHeader && (
        <div className="flex items-center justify-between px-3 py-2 bg-secondary/50 border-b border-border/80 shrink-0">
          <CardHeaderTitle
            cardId="equity"
            title="帳戶權益 (Equity & Drawdown)"
          />

          <div className="flex items-center gap-2">
            {/* 週期切換按鈕 */}
            <div className="flex bg-background/60 border border-border/60 rounded p-0.5 gap-0.5">
              {PERIODS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPeriod(p)}
                  className={cn(
                    "px-2 py-0.5 text-[11px] font-mono font-semibold rounded transition-colors cursor-pointer",
                    period === p
                      ? "bg-secondary text-primary border border-border"
                      : "text-muted-foreground hover:text-foreground border border-transparent"
                  )}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 2. 定案方案 B：Bloomberg AIM / TradingView (左側緊湊對齊側欄 + 右側 100% 自適應走勢圖) */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
          {/* 左側緊湊 KPI 欄位 (移除 justify-between 撕裂，改為頂部自然緊湊對齊) */}
          <div className="w-[195px] shrink-0 p-2.5 border-r border-border/80 flex flex-col gap-2 overflow-y-auto bg-surface/30">
            <div className="flex flex-col gap-0.5">
              <span className="text-[10px] text-muted-foreground uppercase font-mono tracking-wider">帳戶權益</span>
              <div className="font-mono text-2xl font-bold text-foreground tracking-tight">
                {formatUsd(snap.equity)}
              </div>
              <div className={cn("font-mono text-[11px] font-semibold", toneOf(snap.totalPnl))}>
                {formatUsd(snap.totalPnl, true)} ({formatPct((snap.totalPnl / snap.capital) * 100)})
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border/60">
              <div className="flex flex-col gap-0.5">
                <span className="text-[10px] text-muted-foreground">今日損益</span>
                <span className={cn("font-mono text-xs font-semibold leading-tight", toneOf(snap.todayPnl))}>
                  {formatUsd(snap.todayPnl, true)}
                </span>
                <span className="text-[9.5px] text-muted-foreground font-mono">{formatPct(snap.todayPct)}</span>
              </div>

              <div className="flex flex-col gap-0.5">
                <span className="text-[10px] text-muted-foreground">{period} 損益</span>
                <span className={cn("font-mono text-xs font-semibold leading-tight", toneOf(periodSum.pnl))}>
                  {formatUsd(periodSum.pnl, true)}
                </span>
                <span className="text-[9.5px] text-muted-foreground font-mono">{formatPct(periodSum.ret)}</span>
              </div>

              <div className="flex flex-col gap-0.5">
                <span className="text-[10px] text-muted-foreground">未實現</span>
                <span className={cn("font-mono text-xs font-semibold leading-tight", toneOf(snap.upnl))}>
                  {formatUsd(snap.upnl, true)}
                </span>
                <span className="text-[9.5px] text-muted-foreground font-mono">{snap.positionsCount} 筆部位</span>
              </div>

              <div className="flex flex-col gap-0.5">
                <span className="text-[10px] text-muted-foreground">已實現</span>
                <span className={cn("font-mono text-xs font-semibold leading-tight", toneOf(snap.realized))}>
                  {formatUsd(snap.realized, true)}
                </span>
                <span className="text-[9.5px] text-muted-foreground font-mono">OKX-SWAP</span>
              </div>
            </div>


          </div>

          {/* 右側 SVG 走勢圖 (100% 響應垂直拉伸) */}
          <div className="flex-1 flex flex-col min-w-0 p-2.5">
            <div className="flex items-center gap-3 text-[11px] font-mono text-muted-foreground h-5 shrink-0 px-1">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-[2px] bg-primary inline-block" />
                <span>帳戶淨值走勢 · {PERIOD_LABEL[period]}</span>
              </div>
              {hoverData ? (
                <span className="text-primary font-mono">
                  [{hoverData.timeStr}] 累計報酬: {formatPct(hoverData.val)}
                </span>
              ) : (
                <span className="text-muted-foreground/60 text-[10px]">
                  移動游標可檢視時間節點損益
                </span>
              )}
            </div>

            <div
              ref={chartContainerRef}
              className="flex-1 w-full relative min-h-[140px] cursor-crosshair mt-1"
              onPointerMove={handlePointerMove}
              onPointerLeave={() => setHoverIdx(null)}
            >
              {chartWidth > 0 && chartHeight > 0 && (
                <svg width={chartWidth} height={height} className="w-full h-full overflow-visible">
                  <defs>
                    <linearGradient id="v0EqGradReact2" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.16} />
                      <stop offset="100%" stopColor="var(--primary)" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>

                  {/* Y 軸水平輔助線與刻度 */}
                  {yBounds.ticks.map((t) => (
                    <g key={t}>
                      <line
                        x1={0}
                        x2={plotW}
                        y1={getY(t)}
                        y2={getY(t)}
                        stroke={t === 0 ? "rgba(255,255,255,0.2)" : "rgba(255,255,255,0.06)"}
                        strokeDasharray={t === 0 ? "3 3" : undefined}
                        strokeWidth={1}
                      />
                      <text
                        x={plotW + 6}
                        y={getY(t) + 3.5}
                        fill="rgba(255,255,255,0.4)"
                        fontFamily="monospace"
                        fontSize={9}
                      >
                        {formatPct(t, yBounds.step < 1 ? 1 : 0)}
                      </text>
                    </g>
                  ))}

                  {/* 面積微光與淨值折線 */}
                  <path d={eqAreaPath} fill="url(#v0EqGradReact2)" />
                  <path d={eqLinePath} fill="none" stroke="var(--primary)" strokeWidth={1.8} strokeLinejoin="round" />

                  {/* X 軸時間戳記 */}
                  {xTicks.map((k, idx) => (
                    <text
                      key={k}
                      x={getX(k)}
                      y={height - 3}
                      textAnchor={idx === 0 ? "start" : idx === xTicks.length - 1 ? "end" : "middle"}
                      fill="rgba(255,255,255,0.4)"
                      fontFamily="monospace"
                      fontSize={9}
                    >
                      {formatTime(timeAt(periodSum.indices[k]), period !== "24H")}
                    </text>
                  ))}

                  {/* 滑鼠 Hover 十字線與節點圈 */}
                  {hoverIdx !== null ? (
                    <g style={{ pointerEvents: "none" }}>
                      <line
                        x1={getX(hoverIdx)}
                        x2={getX(hoverIdx)}
                        y1={0}
                        y2={height - xAxisH}
                        stroke="rgba(255,255,255,0.4)"
                        strokeDasharray="2 2"
                        strokeWidth={1}
                      />
                      <circle
                        cx={getX(hoverIdx)}
                        cy={getY(periodSum.points[hoverIdx])}
                        r={4}
                        fill="var(--primary)"
                        stroke="#13161a"
                        strokeWidth={2}
                      />
                    </g>
                  ) : !Number.isNaN(lastPoint) ? (
                    <g style={{ pointerEvents: "none" }}>
                      <circle
                        cx={getX(n - 1)}
                        cy={getY(lastPoint)}
                        r={3.5}
                        fill={lastPoint >= 0 ? "var(--up)" : "var(--down)"}
                      />
                      <rect
                        x={plotW + 2}
                        y={getY(lastPoint) - 8}
                        width={46}
                        height={16}
                        rx={2}
                        fill={lastPoint >= 0 ? "var(--up)" : "var(--down)"}
                      />
                      <text
                        x={plotW + 25}
                        y={getY(lastPoint) + 3.5}
                        fill="#0c0f12"
                        fontFamily="monospace"
                        fontSize={9.5}
                        fontWeight={800}
                        textAnchor="middle"
                      >
                        {formatPct(lastPoint)}
                      </text>
                    </g>
                  ) : null}
                </svg>
              )}
            </div>
          </div>
        </div>
      </div>
  );
}
