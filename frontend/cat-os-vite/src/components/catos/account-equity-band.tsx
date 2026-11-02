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
  equitySeries,
  summarize,
  INITIAL_BOTS,
  type Period,
} from "@/lib/v0-engine";
import { cn } from "@/lib/utils";
import { CardHeaderTitle } from "./card-header-title";
import { NumberTicker } from "./motion/number-ticker";
import { BorderBeam } from "./motion/border-beam";
import { useLiveMarketStore } from "@/state/liveMarketStore";
import { useBotLensStore } from "@/state/botLensStore";
import { RotateCcw } from "lucide-react";

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
  const { activeLens, setActiveLens, resetLens } = useBotLensStore();
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const [chartWidth, setChartWidth] = useState(600);
  const [chartHeight, setChartHeight] = useState(240);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const bandRef = useRef<HTMLDivElement>(null);
  const [bandDimensions, setBandDimensions] = useState({ width: 600, height: 240 });

  // 1. 即時市場行情與總資產 Store
  const { equity, todayPnl, todayPct, realized } = useLiveMarketStore();

  // 2. 帳戶整體 Series 與各 Bot Series 歸一化摘要
  const totalSeries = useMemo(() => accountSeries(INITIAL_BOTS), []);
  const periodSum = useMemo(() => summarize(totalSeries, period), [totalSeries, period]);

  const botBTC = useMemo(() => INITIAL_BOTS.find((b) => b.id === "tabby")!, []);
  const botETH = useMemo(() => INITIAL_BOTS.find((b) => b.id === "calico")!, []);
  const botSOL = useMemo(() => INITIAL_BOTS.find((b) => b.id === "mochi")!, []);

  const sumBTC = useMemo(() => summarize(equitySeries(botBTC), period), [botBTC, period]);
  const sumETH = useMemo(() => summarize(equitySeries(botETH), period), [botETH, period]);
  const sumSOL = useMemo(() => summarize(equitySeries(botSOL), period), [botSOL, period]);

  // 自適應容器尺寸監聽
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

  const isNarrow = bandDimensions.width < 500;
  const isSuperNarrow = bandDimensions.width < 380;
  const isShort = bandDimensions.height < 170;
  const isCompact = isNarrow || isShort;

  // 幾何座標與 Y 軸縮放運算 (根據當前選定的策略曲線動態計算)
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
    let pool: number[] = periodSum.points;
    if (activeLens === "tabby") pool = [...pool, ...sumBTC.points];
    else if (activeLens === "calico") pool = [...pool, ...sumETH.points];
    else if (activeLens === "mochi") pool = [...pool, ...sumSOL.points];
    else if (activeLens === "COMPARE_ALL") pool = [...pool, ...sumBTC.points, ...sumETH.points, ...sumSOL.points];

    const pts = pool.filter((v) => !Number.isNaN(v));
    let lo = Math.min(0, ...pts);
    let hi = Math.max(0, ...pts);
    const span = hi - lo || 1;
    hi += span * 0.16;
    lo -= span * 0.16;
    const step = niceStep(hi - lo);
    const ticks: number[] = [];
    for (let t = Math.ceil(lo / step) * step; t <= hi; t += step) {
      ticks.push(Number(t.toFixed(4)));
    }
    return { lo, hi, ticks, step };
  }, [activeLens, periodSum.points, sumBTC.points, sumETH.points, sumSOL.points]);

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

  // 生成各曲線路徑 (Base 0% 歸一化)
  const lineAccount = useMemo(() => generateLine(periodSum.points), [periodSum.points, plotW, yBounds]);
  const lineBTC = useMemo(() => generateLine(sumBTC.points), [sumBTC.points, plotW, yBounds]);
  const lineETH = useMemo(() => generateLine(sumETH.points), [sumETH.points, plotW, yBounds]);
  const lineSOL = useMemo(() => generateLine(sumSOL.points), [sumSOL.points, plotW, yBounds]);

  const eqAreaPath = useMemo(() => {
    const firstK = periodSum.points.findIndex((v) => !Number.isNaN(v));
    if (firstK < 0 || !lineAccount) return "";
    const zeroY = Math.min(plotH - 8, Math.max(8, getY(0)));
    return `${lineAccount}L${getX(n - 1).toFixed(1)},${zeroY.toFixed(1)}L${getX(firstK).toFixed(1)},${zeroY.toFixed(1)}Z`;
  }, [lineAccount, n, plotW, plotH, yBounds]);

  const xTicks = useMemo(() => {
    const fractions = plotW < 320 ? [0, 1] : plotW < 480 ? [0, 0.5, 1] : [0, 0.25, 0.5, 0.75, 1];
    return fractions.map((f) => Math.round(f * (n - 1)));
  }, [n, plotW]);

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

  // 懸停時各維度即時數據解析
  const hoverData = useMemo(() => {
    if (hoverIdx === null) return null;
    const rawIdx = periodSum.indices[hoverIdx];
    const timeStr = formatTime(timeAt(rawIdx), true);
    const accVal = periodSum.points[hoverIdx] ?? 0;
    const btcVal = sumBTC.points[hoverIdx] ?? 0;
    const ethVal = sumETH.points[hoverIdx] ?? 0;
    const solVal = sumSOL.points[hoverIdx] ?? 0;

    return {
      timeStr,
      accVal,
      btcVal,
      ethVal,
      solVal,
      alphaBTC: btcVal - accVal,
      alphaETH: ethVal - accVal,
      alphaSOL: solVal - accVal,
    };
  }, [hoverIdx, periodSum, sumBTC, sumETH, sumSOL]);

  // 當前 Bot 專屬數據快捷映射
  const selectedBotMeta = useMemo(() => {
    if (activeLens === "tabby") {
      return {
        name: "BOT-BTC-15M",
        strat: "突破唐奇安",
        color: "#e8b45e",
        todayPnl: 1364.34,
        periodRet: sumBTC.ret,
        alpha: sumBTC.ret - periodSum.ret,
        budgetPct: "35.6% / 50.0%",
        notional: "$74,535",
        stopPrice: "$59,500.00 (-4.21%)",
      };
    }
    if (activeLens === "calico") {
      return {
        name: "BOT-ETH-1H",
        strat: "趨勢追蹤",
        color: "#7faee2",
        todayPnl: 1175.55,
        periodRet: sumETH.ret,
        alpha: sumETH.ret - periodSum.ret,
        budgetPct: "21.7% / 50.0%",
        notional: "$45,515",
        stopPrice: "$3,210.00 (-4.79%)",
      };
    }
    if (activeLens === "mochi") {
      return {
        name: "BOT-SOL-5M",
        strat: "自適應網格",
        color: "#8b8df8",
        todayPnl: 980.0,
        periodRet: sumSOL.ret,
        alpha: sumSOL.ret - periodSum.ret,
        budgetPct: "9.8% / 50.0%",
        notional: "$20,574",
        stopPrice: "$142.00 (-6.82%)",
      };
    }
    return null;
  }, [activeLens, sumBTC.ret, sumETH.ret, sumSOL.ret, periodSum.ret]);

  return (
    <div ref={bandRef} className={cn("flex flex-col h-full w-full select-none overflow-hidden", className)}>
      {/* 1. Header 列：一體化標題 + 策略視角切換列 + 週期快捷鍵 */}
      {showHeader && (
        <div className="flex items-center justify-between px-3 h-9 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
          <CardHeaderTitle cardId="equity" title="帳戶權益與損益" />

          {/* 策略焦點工具列 (Strategy Focus Toolbar) */}
          <div className="flex items-center gap-0.5 bg-background/70 border border-border/70 rounded p-0.5 text-t1 font-mono shrink-0">
            <button
              type="button"
              onClick={() => setActiveLens("ALL")}
              className={cn(
                "px-2 py-0.5 rounded cursor-pointer transition-colors",
                activeLens === "ALL"
                  ? "bg-secondary text-foreground font-bold shadow-xs"
                  : "text-muted-foreground hover:text-foreground"
              )}
              title="總覽視角：帳戶整體淨值走勢與宏觀風控"
            >
              總覽
            </button>
            <button
              type="button"
              onClick={() => setActiveLens("tabby")}
              className={cn(
                "px-1.5 py-0.5 rounded cursor-pointer transition-colors flex items-center gap-1",
                activeLens === "tabby"
                  ? "bg-[#e8b45e]/20 text-[#e8b45e] font-bold border border-[#e8b45e]/40 shadow-xs"
                  : "text-muted-foreground hover:text-[#e8b45e]"
              )}
              title="策略焦點：聚焦 BOT-BTC 突破唐奇安策略，對比帳戶 Alpha"
            >
              <span className="size-1.5 rounded-full bg-[#e8b45e]" />
              <span>BTC</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveLens("calico")}
              className={cn(
                "px-1.5 py-0.5 rounded cursor-pointer transition-colors flex items-center gap-1",
                activeLens === "calico"
                  ? "bg-[#7faee2]/20 text-[#7faee2] font-bold border border-[#7faee2]/40 shadow-xs"
                  : "text-muted-foreground hover:text-[#7faee2]"
              )}
              title="策略焦點：聚焦 BOT-ETH 趨勢追蹤策略，對比帳戶 Alpha"
            >
              <span className="size-1.5 rounded-full bg-[#7faee2]" />
              <span>ETH</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveLens("mochi")}
              className={cn(
                "px-1.5 py-0.5 rounded cursor-pointer transition-colors flex items-center gap-1",
                activeLens === "mochi"
                  ? "bg-[#8b8df8]/20 text-[#8b8df8] font-bold border border-[#8b8df8]/40 shadow-xs"
                  : "text-muted-foreground hover:text-[#8b8df8]"
              )}
              title="策略焦點：聚焦 BOT-SOL 自適應網格策略，對比帳戶 Alpha"
            >
              <span className="size-1.5 rounded-full bg-[#8b8df8]" />
              <span>SOL</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveLens("COMPARE_ALL")}
              className={cn(
                "px-2 py-0.5 rounded cursor-pointer transition-colors flex items-center gap-1",
                activeLens === "COMPARE_ALL"
                  ? "bg-primary text-primary-foreground font-bold shadow-xs"
                  : "text-muted-foreground hover:text-foreground"
              )}
              title="多策略對比：同軸基準歸一化收益對比與 Alpha 歸因"
            >
              <span>多策略對比</span>
            </button>
          </div>

          {/* 週期切換按鈕 */}
          <div className="flex items-center gap-0.5 bg-background/60 border border-border/60 rounded p-0.5 shrink-0">
            {(isSuperNarrow ? (["24H", "7D"] as Period[]) : isNarrow ? (["24H", "7D", "30D"] as Period[]) : PERIODS).map(
              (p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPeriod(p)}
                  className={cn(
                    "px-1.5 sm:px-2 py-0.5 text-t2 sm:text-t2 font-mono rounded transition-colors cursor-pointer",
                    period === p
                      ? "bg-secondary text-foreground font-semibold shadow-xs"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {p}
                </button>
              )
            )}
          </div>
        </div>
      )}

      {/* 2. 主視圖：左側動態響應 KPI 側欄 + 右側自適應走勢圖 */}
      <div className="flex flex-1 min-h-0 overflow-hidden relative">
        <BorderBeam size={180} duration={8} borderWidth={1.5} colorFrom="var(--color-primary, #e8b45e)" />

        {/* 左側動態響應 KPI 欄位 */}
        <div
          className={cn(
            "shrink-0 border-r border-border/80 flex flex-col justify-between overflow-y-auto bg-surface/30",
            isNarrow ? "w-[130px] p-2 gap-1.5" : "w-[205px] p-2.5 gap-2"
          )}
        >
          {/* ================= 視角 A：總覽模式 (Macro) ================= */}
          {activeLens === "ALL" && (
            <div className="flex flex-col gap-2">
              <div className="flex flex-col gap-0.5">
                <span className="text-t2 text-muted-foreground uppercase font-mono tracking-wider flex items-center justify-between">
                  <span>帳戶總權益</span>
                  {!isNarrow && (
                    <span className="text-t1 text-emerald-400 font-mono flex items-center gap-1">
                      <span className="size-1.5 rounded-full bg-emerald-400 animate-ping" />
                      即時
                    </span>
                  )}
                </span>
                <div className={cn("font-mono font-bold text-foreground tracking-tight", isNarrow ? "text-lg" : "text-2xl")}>
                  <NumberTicker value={equity} prefix="$" decimals={2} />
                </div>
                <div className={cn("font-mono font-semibold", isNarrow ? "text-t2" : "text-t3", toneOf(todayPnl))}>
                  <NumberTicker value={Math.abs(todayPnl)} prefix={todayPnl >= 0 ? "+$" : "-$"} decimals={2} /> ({todayPct >= 0 ? `+${todayPct}%` : `${todayPct}%`})
                </div>
              </div>

              {/* 寬版 2x2 矩陣 */}
              <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border/60 font-mono">
                <div className="flex flex-col gap-0.5">
                  <span className="text-t2 text-muted-foreground">今日損益</span>
                  <span className={cn("text-xs font-semibold leading-tight", toneOf(todayPnl))}>
                    <NumberTicker value={Math.abs(todayPnl)} prefix={todayPnl >= 0 ? "+$" : "-$"} decimals={2} />
                  </span>
                  <span className="text-t1 text-muted-foreground">{todayPct >= 0 ? `+${todayPct}%` : `${todayPct}%`}</span>
                </div>

                <div className="flex flex-col gap-0.5">
                  <span className="text-t2 text-muted-foreground">{period} 損益</span>
                  <span className={cn("text-xs font-semibold leading-tight", toneOf(periodSum.pnl))}>
                    {formatUsd(periodSum.pnl, true)}
                  </span>
                  <span className="text-t1 text-muted-foreground">{formatPct(periodSum.ret)}</span>
                </div>

                <div className="flex flex-col gap-0.5">
                  <span className="text-t2 text-muted-foreground">台北日切 (R1)</span>
                  <span className="text-xs font-semibold leading-tight text-emerald-400">+$3,092.64</span>
                  <span className="text-t1 text-muted-foreground">00:00:15 起算</span>
                </div>

                <div className="flex flex-col gap-0.5">
                  <span className="text-t2 text-muted-foreground">已實現損益</span>
                  <span className={cn("text-xs font-semibold leading-tight", toneOf(realized))}>
                    {formatUsd(realized, true)}
                  </span>
                  <span className="text-t1 text-muted-foreground">OKX 專用子帳戶</span>
                </div>
              </div>
            </div>
          )}

          {/* ================= 視角 B：單策略焦點模式 (Single Strategy Focus) ================= */}
          {selectedBotMeta && (
            <div className="flex flex-col gap-2">
              <div className="flex flex-col gap-0.5">
                <div className="flex items-center justify-between">
                  <span
                    className="text-t1 font-mono font-bold px-1.5 py-0.2 rounded"
                    style={{ backgroundColor: `${selectedBotMeta.color}20`, color: selectedBotMeta.color }}
                  >
                    {selectedBotMeta.name}
                  </span>
                  <span className="text-t1 text-muted-foreground font-mono">{selectedBotMeta.strat}</span>
                </div>
                <div className="font-mono font-bold text-foreground tracking-tight text-xl mt-1">
                  {formatUsd(selectedBotMeta.todayPnl, true)}
                </div>
                <div className="font-mono text-t2 text-emerald-400 font-semibold flex items-center gap-1">
                  <span>Alpha 超額:</span>
                  <span>{formatPct(selectedBotMeta.alpha)}</span>
                </div>
              </div>

              {/* 專屬 Bot 2x2 矩陣 */}
              <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border/60 font-mono">
                <div className="flex flex-col gap-0.5">
                  <span className="text-t2 text-muted-foreground">單幣預算佔用</span>
                  <span className="text-xs font-semibold text-foreground leading-tight">{selectedBotMeta.budgetPct}</span>
                  <span className="text-t1 text-muted-foreground">上限 50.0%</span>
                </div>

                <div className="flex flex-col gap-0.5">
                  <span className="text-t2 text-muted-foreground">{period} 報酬率</span>
                  <span className={cn("text-xs font-bold leading-tight", toneOf(selectedBotMeta.periodRet))}>
                    {formatPct(selectedBotMeta.periodRet)}
                  </span>
                  <span className="text-t1 text-muted-foreground">歸一化回報</span>
                </div>

                <div className="flex flex-col gap-0.5">
                  <span className="text-t2 text-muted-foreground">名目持倉</span>
                  <span className="text-xs font-semibold text-foreground leading-tight">{selectedBotMeta.notional}</span>
                  <span className="text-t1 text-muted-foreground">1 Bot : 1 SWAP</span>
                </div>

                <div className="flex flex-col gap-0.5">
                  <span className="text-t2 text-muted-foreground">交易所強制停損</span>
                  <span className="text-t2 font-bold text-primary leading-tight">{selectedBotMeta.stopPrice}</span>
                  <span className="text-t1 text-emerald-400">生效防護中</span>
                </div>
              </div>

              <button
                type="button"
                onClick={resetLens}
                className="mt-1 flex items-center justify-center gap-1 px-2 py-1 rounded bg-secondary/70 hover:bg-secondary text-t2 font-mono text-muted-foreground hover:text-foreground border border-border/60 transition-colors cursor-pointer"
              >
                <RotateCcw className="size-2.5" />
                <span>返回帳戶總覽</span>
              </button>
            </div>
          )}

          {/* ================= 視角 C：多策略對比模式 (Multi-Strategy Overlay) ================= */}
          {activeLens === "COMPARE_ALL" && (
            <div className="flex flex-col gap-2">
              <div className="flex flex-col gap-0.5">
                <span className="text-t2 text-primary uppercase font-mono tracking-wider font-bold">
                  多策略疊加 · 基準歸一化
                </span>
                <div className="font-mono font-bold text-foreground tracking-tight text-lg">3 策略同軸對比</div>
                <div className="font-mono text-t2 text-muted-foreground">起算點強制歸零 (0.00%)</div>
              </div>

              <div className="flex flex-col gap-1.5 pt-1.5 border-t border-border/60 font-mono text-xs">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1 text-t3">
                    <span className="size-1.5 rounded-full bg-[#7faee2]" />
                    <span className="font-bold text-foreground">BOT-ETH</span>
                  </span>
                  <span className="text-emerald-400 font-bold text-t3">{formatPct(sumETH.ret)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1 text-t3">
                    <span className="size-1.5 rounded-full bg-[#e8b45e]" />
                    <span className="font-bold text-foreground">BOT-BTC</span>
                  </span>
                  <span className="text-emerald-400 font-bold text-t3">{formatPct(sumBTC.ret)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1 text-t3">
                    <span className="size-1.5 rounded-full bg-[#8b8df8]" />
                    <span className="font-bold text-foreground">BOT-SOL</span>
                  </span>
                  <span className="text-emerald-400 font-bold text-t3">{formatPct(sumSOL.ret)}</span>
                </div>
                <div className="flex items-center justify-between pt-1 border-t border-border/40 text-muted-foreground text-t2">
                  <span>帳戶基準線</span>
                  <span>{formatPct(periodSum.ret)}</span>
                </div>
              </div>

              <button
                type="button"
                onClick={resetLens}
                className="mt-1 flex items-center justify-center gap-1 px-2 py-1 rounded bg-secondary/70 hover:bg-secondary text-t2 font-mono text-muted-foreground hover:text-foreground border border-border/60 transition-colors cursor-pointer"
              >
                <RotateCcw className="size-2.5" />
                <span>返回帳戶總覽</span>
              </button>
            </div>
          )}
        </div>

        {/* 右側 SVG 走勢圖 */}
        <div className={cn("flex-1 flex flex-col min-w-0", isCompact ? "p-1.5" : "p-2.5")}>
          {/* 圖表微型 Header / 狀態與圖例 */}
          <div className="flex items-center justify-between text-t3 font-mono text-muted-foreground h-5 shrink-0 px-1">
            <div className="flex items-center gap-3">
              {activeLens === "ALL" && (
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-[2px] bg-primary inline-block" />
                  <span>帳戶淨值走勢 · {PERIOD_LABEL[period]}</span>
                </div>
              )}
              {activeLens === "tabby" && (
                <div className="flex items-center gap-2">
                  <span className="flex items-center gap-1 text-[#e8b45e] font-semibold">
                    <span className="w-2.5 h-[2.5px] bg-[#e8b45e] inline-block" />
                    <span>BOT-BTC-15M 突破唐奇安</span>
                  </span>
                  <span className="flex items-center gap-1 text-zinc-400">
                    <span className="w-2 h-[1.5px] border-b border-dashed border-zinc-400 inline-block" />
                    <span>帳戶基準</span>
                  </span>
                </div>
              )}
              {activeLens === "calico" && (
                <div className="flex items-center gap-2">
                  <span className="flex items-center gap-1 text-[#7faee2] font-semibold">
                    <span className="w-2.5 h-[2.5px] bg-[#7faee2] inline-block" />
                    <span>BOT-ETH-1H 趨勢追蹤</span>
                  </span>
                  <span className="flex items-center gap-1 text-zinc-400">
                    <span className="w-2 h-[1.5px] border-b border-dashed border-zinc-400 inline-block" />
                    <span>帳戶基準</span>
                  </span>
                </div>
              )}
              {activeLens === "mochi" && (
                <div className="flex items-center gap-2">
                  <span className="flex items-center gap-1 text-[#8b8df8] font-semibold">
                    <span className="w-2.5 h-[2.5px] bg-[#8b8df8] inline-block" />
                    <span>BOT-SOL-5M 自適應網格</span>
                  </span>
                  <span className="flex items-center gap-1 text-zinc-400">
                    <span className="w-2 h-[1.5px] border-b border-dashed border-zinc-400 inline-block" />
                    <span>帳戶基準</span>
                  </span>
                </div>
              )}
              {activeLens === "COMPARE_ALL" && (
                <div className="flex items-center gap-2.5 text-t2">
                  <span className="text-[#e8b45e] font-semibold flex items-center gap-1">
                    <span className="size-1.5 rounded-full bg-[#e8b45e]" /> BTC
                  </span>
                  <span className="text-[#7faee2] font-semibold flex items-center gap-1">
                    <span className="size-1.5 rounded-full bg-[#7faee2]" /> ETH
                  </span>
                  <span className="text-[#8b8df8] font-semibold flex items-center gap-1">
                    <span className="size-1.5 rounded-full bg-[#8b8df8]" /> SOL
                  </span>
                  <span className="text-zinc-400 flex items-center gap-1">
                    <span className="w-2 border-b border-dashed border-zinc-400" /> 基準
                  </span>
                </div>
              )}
            </div>

            {/* 右側懸停動態反饋 */}
            <div>
              {hoverData ? (
                <span className="text-foreground font-mono text-t2">
                  [{hoverData.timeStr}]{" "}
                  {activeLens === "ALL" && (
                    <span className="text-primary font-bold">累計報酬: {formatPct(hoverData.accVal)}</span>
                  )}
                  {activeLens === "tabby" && (
                    <span>
                      <strong className="text-[#e8b45e]">{formatPct(hoverData.btcVal)}</strong> (vs 基準 {formatPct(hoverData.accVal)} ·{" "}
                      <span className="text-emerald-400 font-bold">Alpha {formatPct(hoverData.alphaBTC)}</span>)
                    </span>
                  )}
                  {activeLens === "calico" && (
                    <span>
                      <strong className="text-[#7faee2]">{formatPct(hoverData.ethVal)}</strong> (vs 基準 {formatPct(hoverData.accVal)} ·{" "}
                      <span className="text-emerald-400 font-bold">Alpha {formatPct(hoverData.alphaETH)}</span>)
                    </span>
                  )}
                  {activeLens === "mochi" && (
                    <span>
                      <strong className="text-[#8b8df8]">{formatPct(hoverData.solVal)}</strong> (vs 基準 {formatPct(hoverData.accVal)} ·{" "}
                      <span className="text-emerald-400 font-bold">Alpha {formatPct(hoverData.alphaSOL)}</span>)
                    </span>
                  )}
                  {activeLens === "COMPARE_ALL" && (
                    <span>
                      <strong className="text-[#7faee2]">ETH {formatPct(hoverData.ethVal)}</strong> ·{" "}
                      <strong className="text-[#e8b45e]">BTC {formatPct(hoverData.btcVal)}</strong> ·{" "}
                      <strong className="text-[#8b8df8]">SOL {formatPct(hoverData.solVal)}</strong>
                    </span>
                  )}
                </span>
              ) : (
                <span className="text-muted-foreground/60 text-t2">游標懸停檢視各時間節點即時收益與 Alpha</span>
              )}
            </div>
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
                      stroke="currentColor"
                      className="text-border/40"
                      strokeDasharray={t === 0 ? undefined : "3 3"}
                      strokeWidth={t === 0 ? 1 : 0.75}
                    />
                    <text
                      x={plotW + 6}
                      y={getY(t) + 3}
                      fill="currentColor"
                      className={cn("text-t1 font-mono", t === 0 ? "text-primary font-bold" : "text-muted-foreground/60")}
                    >
                      {t > 0 ? `+${t.toFixed(1)}%` : `${t.toFixed(1)}%`}
                    </text>
                  </g>
                ))}

                {/* X 軸時間標籤 */}
                {xTicks.map((idx) => {
                  const raw = periodSum.indices[idx];
                  if (raw === undefined) return null;
                  const label = formatTime(timeAt(raw), false);
                  return (
                    <text
                      key={idx}
                      x={getX(idx)}
                      y={plotH + 13}
                      textAnchor={idx === 0 ? "start" : idx === n - 1 ? "end" : "middle"}
                      fill="currentColor"
                      className="text-t1 font-mono text-muted-foreground/60"
                    >
                      {label}
                    </text>
                  );
                })}

                {/* ================= 模式 1：總覽視角 (ALL) ================= */}
                {activeLens === "ALL" && (
                  <>
                    {eqAreaPath && <path d={eqAreaPath} fill="url(#v0EqGradReact2)" />}
                    {lineAccount && <path d={lineAccount} fill="none" stroke="var(--primary)" strokeWidth={2} />}
                  </>
                )}

                {/* ================= 模式 2：單策略焦點視角 (BTC) ================= */}
                {activeLens === "tabby" && (
                  <>
                    {/* 背景：帳戶基準虛線 */}
                    {lineAccount && (
                      <path d={lineAccount} fill="none" stroke="#a1a1aa" strokeWidth={1.5} strokeDasharray="3 3" opacity={0.5} />
                    )}
                    {/* 前景：BOT-BTC 實線 */}
                    {lineBTC && (
                      <path
                        d={lineBTC}
                        fill="none"
                        stroke="#e8b45e"
                        strokeWidth={2.5}
                        style={{ filter: "drop-shadow(0 0 6px rgba(232, 180, 94, 0.4))" }}
                      />
                    )}
                  </>
                )}

                {/* ================= 模式 2：單策略焦點視角 (ETH) ================= */}
                {activeLens === "calico" && (
                  <>
                    {lineAccount && (
                      <path d={lineAccount} fill="none" stroke="#a1a1aa" strokeWidth={1.5} strokeDasharray="3 3" opacity={0.5} />
                    )}
                    {lineETH && (
                      <path
                        d={lineETH}
                        fill="none"
                        stroke="#7faee2"
                        strokeWidth={2.5}
                        style={{ filter: "drop-shadow(0 0 6px rgba(127, 174, 226, 0.4))" }}
                      />
                    )}
                  </>
                )}

                {/* ================= 模式 2：單策略焦點視角 (SOL) ================= */}
                {activeLens === "mochi" && (
                  <>
                    {lineAccount && (
                      <path d={lineAccount} fill="none" stroke="#a1a1aa" strokeWidth={1.5} strokeDasharray="3 3" opacity={0.5} />
                    )}
                    {lineSOL && (
                      <path
                        d={lineSOL}
                        fill="none"
                        stroke="#8b8df8"
                        strokeWidth={2.5}
                        style={{ filter: "drop-shadow(0 0 6px rgba(139, 141, 248, 0.4))" }}
                      />
                    )}
                  </>
                )}

                {/* ================= 模式 3：多策略對比 (COMPARE_ALL) ================= */}
                {activeLens === "COMPARE_ALL" && (
                  <>
                    {lineAccount && (
                      <path d={lineAccount} fill="none" stroke="#ffffff" strokeWidth={1.2} strokeDasharray="3 3" opacity={0.4} />
                    )}
                    {lineETH && <path d={lineETH} fill="none" stroke="#7faee2" strokeWidth={2} />}
                    {lineBTC && <path d={lineBTC} fill="none" stroke="#e8b45e" strokeWidth={2} />}
                    {lineSOL && <path d={lineSOL} fill="none" stroke="#8b8df8" strokeWidth={2} />}
                  </>
                )}

                {/* 游標垂直十字參考線與端點標記 */}
                {hoverIdx !== null && (
                  <g>
                    <line
                      x1={getX(hoverIdx)}
                      x2={getX(hoverIdx)}
                      y1={8}
                      y2={plotH}
                      stroke="var(--primary)"
                      strokeWidth={1}
                      strokeDasharray="2 2"
                      opacity={0.8}
                    />
                    {activeLens === "ALL" && (
                      <circle
                        cx={getX(hoverIdx)}
                        cy={getY(periodSum.points[hoverIdx] ?? 0)}
                        r={3.5}
                        fill="var(--primary)"
                        stroke="var(--background)"
                        strokeWidth={1.5}
                      />
                    )}
                    {activeLens === "tabby" && (
                      <circle
                        cx={getX(hoverIdx)}
                        cy={getY(sumBTC.points[hoverIdx] ?? 0)}
                        r={4}
                        fill="#e8b45e"
                        stroke="var(--background)"
                        strokeWidth={1.5}
                      />
                    )}
                    {activeLens === "calico" && (
                      <circle
                        cx={getX(hoverIdx)}
                        cy={getY(sumETH.points[hoverIdx] ?? 0)}
                        r={4}
                        fill="#7faee2"
                        stroke="var(--background)"
                        strokeWidth={1.5}
                      />
                    )}
                    {activeLens === "mochi" && (
                      <circle
                        cx={getX(hoverIdx)}
                        cy={getY(sumSOL.points[hoverIdx] ?? 0)}
                        r={4}
                        fill="#8b8df8"
                        stroke="var(--background)"
                        strokeWidth={1.5}
                      />
                    )}
                    {activeLens === "COMPARE_ALL" && (
                      <>
                        <circle cx={getX(hoverIdx)} cy={getY(sumBTC.points[hoverIdx] ?? 0)} r={3} fill="#e8b45e" />
                        <circle cx={getX(hoverIdx)} cy={getY(sumETH.points[hoverIdx] ?? 0)} r={3} fill="#7faee2" />
                        <circle cx={getX(hoverIdx)} cy={getY(sumSOL.points[hoverIdx] ?? 0)} r={3} fill="#8b8df8" />
                      </>
                    )}
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
