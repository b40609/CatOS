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
  INITIAL_BOTS,
  type Period,
} from "@/lib/v0-engine";
import { cn } from "@/lib/utils";
import { CardHeaderTitle } from "./card-header-title";
import { NumberTicker } from "./motion/number-ticker";
import { BorderBeam } from "./motion/border-beam";
import { useLiveMarketStore } from "@/state/liveMarketStore";

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
  const bandRef = useRef<HTMLDivElement>(null);
  const [bandDimensions, setBandDimensions] = useState({ width: 600, height: 240 });

  // 1. 取得即時市場撮合與帳戶波動 Store
  const {
    equity,
    todayPnl,
    todayPct,
    totalUpnl,
    realized,
  } = useLiveMarketStore();

  // 取得帳戶整體 Series 與當前週期摘要
  const totalSeries = useMemo(() => accountSeries(INITIAL_BOTS), []);
  const periodSum = useMemo(() => summarize(totalSeries, period), [totalSeries, period]);

  // 2. 自適應容器寬高 ResizeObserver (雙向響應式，監聽整體卡片與圖表區)
  useEffect(() => {
    const el = bandRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setBandDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

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

  const isNarrow = bandDimensions.width < 460;
  const isSuperNarrow = bandDimensions.width < 340;
  const isShort = bandDimensions.height < 170;
  const isCompact = isNarrow || isShort;

  // 3. 幾何座標與軸長運算 (動態自適應容器高度與寬度)
  const height = Math.max(120, chartHeight);
  const axisW = isNarrow ? 40 : 54;
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
    <div ref={bandRef} className={cn("flex flex-col h-full w-full select-none overflow-hidden", className)}>
      {/* 1. Header 列：一體化標題 + 排版切換 + 週期快捷鍵 (窄版自動過濾為核心 3 週期) */}
      {showHeader && (
        <div className="flex items-center justify-between px-3 h-9 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
          <CardHeaderTitle
            cardId="equity"
            title="帳戶權益與損益"
          />

          {/* 週期切換按鈕 (窄版自動切換為核心週期，防止標題截字) */}
          <div className="flex items-center gap-0.5 bg-background/60 border border-border/60 rounded p-0.5 shrink-0">
            {(isSuperNarrow ? (["24H", "7D"] as Period[]) : isNarrow ? (["24H", "7D", "30D"] as Period[]) : PERIODS).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setPeriod(p)}
                className={cn(
                  "px-1.5 sm:px-2 py-0.5 text-[10px] sm:text-[10.5px] font-mono rounded transition-colors cursor-pointer",
                  period === p
                    ? "bg-secondary text-foreground font-semibold shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 2. 定案方案 B：Bloomberg AIM / TradingView (左側緊湊對齊側欄 + 右側 100% 自適應走勢圖) */}
      <div className="flex flex-1 min-h-0 overflow-hidden relative">
          {/* 邊界微光流動 (Magic UI Border Beam) */}
          <BorderBeam size={180} duration={8} borderWidth={1.5} colorFrom="var(--color-primary, #e8b45e)" />

          {/* 左側緊湊 KPI 欄位 (自適應寬度與緊湊態，窄版縮至 130px 讓出圖表空間) */}
          <div className={cn(
            "shrink-0 border-r border-border/80 flex flex-col overflow-y-auto bg-surface/30",
            isNarrow ? "w-[130px] p-2 gap-1.5" : "w-[195px] p-2.5 gap-2"
          )}>
            <div className="flex flex-col gap-0.5">
              <span className="text-[10px] text-muted-foreground uppercase font-mono tracking-wider flex items-center justify-between">
                <span>帳戶權益</span>
                {!isNarrow && (
                  <span className="text-[9px] text-emerald-400 font-mono flex items-center gap-1">
                    <span className="size-1.5 rounded-full bg-emerald-400 animate-ping" />
                    即時
                  </span>
                )}
              </span>
              <div className={cn(
                "font-mono font-bold text-foreground tracking-tight",
                isNarrow ? "text-lg" : "text-2xl"
              )}>
                <NumberTicker value={equity} prefix="$" decimals={2} />
              </div>
              <div className={cn("font-mono font-semibold", isNarrow ? "text-[10px]" : "text-[11px]", toneOf(todayPnl))}>
                <NumberTicker value={Math.abs(todayPnl)} prefix={todayPnl >= 0 ? "+$" : "-$"} decimals={2} /> ({todayPct >= 0 ? `+${todayPct}%` : `${todayPct}%`})
              </div>
            </div>

            {/* 次要 KPI 指標 */}
            {isNarrow ? (
              // 窄版精緻單欄速覽
              <div className="flex flex-col gap-1.5 pt-1.5 border-t border-border/60 text-[10px] font-mono">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">今日</span>
                  <span className={cn("font-semibold", toneOf(todayPnl))}>
                    {todayPnl >= 0 ? "+" : ""}{formatUsd(todayPnl, false)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">{period}</span>
                  <span className={cn("font-semibold", toneOf(periodSum.pnl))}>
                    {periodSum.pnl >= 0 ? "+" : ""}{formatUsd(periodSum.pnl, false)}
                  </span>
                </div>
                {!isShort && (
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">未結</span>
                    <span className={cn("font-semibold", toneOf(totalUpnl))}>
                      {totalUpnl >= 0 ? "+" : ""}{formatUsd(totalUpnl, false)}
                    </span>
                  </div>
                )}
              </div>
            ) : (
              // 寬版 2x2 矩陣
              <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border/60">
                <div className="flex flex-col gap-0.5">
                  <span className="text-[10px] text-muted-foreground">今日損益</span>
                  <span className={cn("font-mono text-xs font-semibold leading-tight", toneOf(todayPnl))}>
                    <NumberTicker value={Math.abs(todayPnl)} prefix={todayPnl >= 0 ? "+$" : "-$"} decimals={2} />
                  </span>
                  <span className="text-[9.5px] text-muted-foreground font-mono">{todayPct >= 0 ? `+${todayPct}%` : `${todayPct}%`}</span>
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
                  <span className={cn("font-mono text-xs font-semibold leading-tight", toneOf(totalUpnl))}>
                    <NumberTicker value={Math.abs(totalUpnl)} prefix={totalUpnl >= 0 ? "+$" : "-$"} decimals={2} />
                  </span>
                  <span className="text-[9.5px] text-muted-foreground font-mono">3 筆持倉聯動</span>
                </div>

                <div className="flex flex-col gap-0.5">
                  <span className="text-[10px] text-muted-foreground">已實現</span>
                  <span className={cn("font-mono text-xs font-semibold leading-tight", toneOf(realized))}>
                    {formatUsd(realized, true)}
                  </span>
                  <span className="text-[9.5px] text-muted-foreground font-mono">OKX-SWAP</span>
                </div>
              </div>
            )}
          </div>

          {/* 右側 SVG 走勢圖 (100% 響應垂直拉伸) */}
          <div className={cn("flex-1 flex flex-col min-w-0", isCompact ? "p-1.5" : "p-2.5")}>
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
