import { useState, useMemo, useEffect, useRef } from "react";
import { CardHeaderTitle } from "./card-header-title";
import { PulseBeacon } from "./pulse-beacon";
import { cn } from "@/lib/utils";
import { ShieldCheck, Layers, Sliders, LayoutList } from "lucide-react";

// 定案配色：低彩度、高質感的幣種資料系列色
const cryptoColors = {
  btc: "#e8b45e",       // BTC 蜂蜜金
  in_flight: "#7faee2", // ETH / 在途凍結 雅緻瓦藍
  available: "#65cba7", // 可用額度 薄荷青
  alt: "#8b8df8",       // SOL 沉穩淡靛
  mm: "#f59e0b",        // 維持保證金 琥珀橘
  im: "#38bdf8",        // 初始保證金 晴空藍
  free: "#34d399",      // 自由保證金 翡翠綠
};

export type CandidateScheme = "scheme_a_bloomberg" | "scheme_b_okx" | "scheme_c_matrix";

interface DonutItem {
  symbol: string;
  label: string;
  shortLabel?: string;
  sub: string;
  nominal_usdt: number;
  pct_share: number;
  color: string;
  leverage?: string;
  pnl?: string;
  pnlUp?: boolean;
}

export function AllocationDonutCard({ className }: { className?: string }) {
  // 3 大業界候選方案切換狀態
  const [candidateScheme, setCandidateScheme] = useState<CandidateScheme>("scheme_a_bloomberg");

  // 方案 B 專用：OKX 雙維度切換 (notional: 標的曝險分佈 | margin: 保證金風控水位)
  const [okxDimension, setOkxDimension] = useState<"notional" | "margin">("notional");

  // Hover / Active 切片索引 (方案 A & 方案 B 核心 HUD 動態聯動)
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  // 容器寬高響應式動態捕捉 (Fluid ResizeObserver)
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState<{ width: number; height: number }>({ width: 380, height: 260 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    let rAF = 0;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      cancelAnimationFrame(rAF);
      rAF = requestAnimationFrame(() => {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          setDimensions({
            width: Math.floor(width),
            height: Math.floor(height),
          });
        }
      });
    });

    observer.observe(el);
    return () => {
      cancelAnimationFrame(rAF);
      observer.disconnect();
    };
  }, [candidateScheme]);

  // ==================== 方案數據來源定義 ====================

  // 方案 A 數據：合約名義曝險（聚焦 BTC & ETH 持倉與待機）
  const schemeAItems: DonutItem[] = useMemo(() => [
    { symbol: "BTC", label: "BTC-USDT-SWAP", shortLabel: "BTC", sub: "持有中", nominal_usdt: 596.60, pct_share: 73.7, color: cryptoColors.btc, leverage: "3x Cross", pnl: "+$79.26", pnlUp: true },
    { symbol: "ETH", label: "ETH-USDT-SWAP", shortLabel: "ETH", sub: "掛單在途", nominal_usdt: 213.08, pct_share: 26.3, color: cryptoColors.in_flight, leverage: "3x Cross", pnl: "+$132.48", pnlUp: true },
    { symbol: "SOL", label: "SOL-USDT-SWAP", shortLabel: "SOL", sub: "空倉待機", nominal_usdt: 0.00, pct_share: 0.0, color: cryptoColors.alt, leverage: "未持有", pnl: "$0.00", pnlUp: true },
  ], []);

  // 方案 B 數據 1：標的曝險分佈
  const okxNotionalItems: DonutItem[] = useMemo(() => [
    { symbol: "BTC", label: "BTC 永續持倉", shortLabel: "BTC", sub: "持倉", nominal_usdt: 596.60, pct_share: 42.0, color: cryptoColors.btc, leverage: "3x", pnl: "+$79.2" },
    { symbol: "在途", label: "在途委託凍結", shortLabel: "在途", sub: "凍結", nominal_usdt: 213.08, pct_share: 15.0, color: cryptoColors.in_flight, leverage: "委託中" },
    { symbol: "可用", label: "可用曝險預算", shortLabel: "可用", sub: "剩餘額度", nominal_usdt: 610.82, pct_share: 43.0, color: cryptoColors.available, leverage: "額度充裕" },
  ], []);

  // 方案 B 數據 2：保證金風控水位 (四段式健康刻度，徹底消除 99.9% 失真！)
  const okxMarginItems: DonutItem[] = useMemo(() => [
    { symbol: "MM", label: "維持保證金 (MM)", shortLabel: "維持保證金", sub: "強制平倉線", nominal_usdt: 80.97, pct_share: 8.5, color: cryptoColors.mm, leverage: "強平防線" },
    { symbol: "IM", label: "初始保證金 (IM)", shortLabel: "初始保證金", sub: "已開倉佔用", nominal_usdt: 135.40, pct_share: 14.2, color: cryptoColors.im, leverage: "常規佔用" },
    { symbol: "掛單", label: "在途凍結保證金", shortLabel: "在途凍結", sub: "限價掛單", nominal_usdt: 143.00, pct_share: 15.0, color: cryptoColors.alt, leverage: "在途預留" },
    { symbol: "可用", label: "自由保證金緩衝", shortLabel: "自由保證金", sub: "爆倉緩衝區", nominal_usdt: 593.63, pct_share: 62.3, color: cryptoColors.free, leverage: "安全緩衝" },
  ], []);

  // 方案 C 數據：高密度左環右表
  const schemeCItems = schemeAItems;

  // 根據當前方案挑選生效的 Donut 資料列
  const currentItems: DonutItem[] = useMemo(() => {
    if (candidateScheme === "scheme_a_bloomberg") return schemeAItems;
    if (candidateScheme === "scheme_b_okx") return okxDimension === "notional" ? okxNotionalItems : okxMarginItems;
    return schemeCItems;
  }, [candidateScheme, okxDimension, schemeAItems, okxNotionalItems, okxMarginItems, schemeCItems]);

  // ==================== 圓環幾何參數自適應計算 ====================
  const W = dimensions.width || 380;
  const H = dimensions.height || 260;
  const cx = candidateScheme === "scheme_c_matrix" ? Math.floor(W * 0.24) : Math.floor(W / 2);
  const cy = Math.floor(H / 2);

  // 依方案縮放圓環尺寸 (方案 C 為精緻迷你環，方案 A/B 為大氣 HUD 環)
  const isCompact = candidateScheme === "scheme_c_matrix";
  const r_out = isCompact
    ? Math.min(56, Math.max(42, Math.floor(H * 0.30)))
    : Math.min(76, Math.max(50, Math.floor(Math.min(W, H) * 0.28)));
  const strokeWidth = isCompact ? 12 : Math.min(22, Math.max(14, Math.floor(r_out * 0.24)));
  const radius = r_out - strokeWidth / 2;
  const circumference = 2 * Math.PI * radius;

  // 方案 A/B 引線參數
  const elbowDist = Math.min(18, Math.max(10, Math.floor(r_out * 0.20)));
  const hookLen = Math.min(14, Math.max(8, Math.floor(r_out * 0.16)));
  const estTextW = Math.min(78, Math.max(52, Math.floor(W * 0.22)));

  // 計算圓弧段與短鉤引線
  const donutSlices = useMemo(() => {
    let accumulated = 0;
    const gapPx = currentItems.filter((i) => i.pct_share > 0).length > 1 ? 2.5 : 0;

    return currentItems.map((item, idx) => {
      const fullArc = (item.pct_share / 100) * circumference;
      const arcLength = Math.max(0, fullArc - gapPx);
      const strokeDasharray = `${arcLength} ${circumference - arcLength}`;
      const strokeDashoffset = -accumulated;

      const startAngle = (accumulated / circumference) * 2 * Math.PI - Math.PI / 2;
      const arcAngle = (fullArc / circumference) * 2 * Math.PI;
      const midAngle = startAngle + arcAngle / 2;
      accumulated += fullArc;

      const cos = Math.cos(midAngle);
      const sin = Math.sin(midAngle);
      const isRight = cos >= 0;

      const x1 = cx + r_out * cos;
      const y1 = cy + r_out * sin;

      const isNearlyVertical = Math.abs(cos) < 0.32;
      const effectiveElbowDist = isNearlyVertical ? elbowDist + 5 : elbowDist;
      let x2 = cx + (r_out + effectiveElbowDist) * cos;
      if (isNearlyVertical) {
        x2 = isRight ? Math.max(cx + 16, x2) : Math.min(cx - 16, x2);
      }

      let y2 = cy + (r_out + effectiveElbowDist) * sin;
      y2 = Math.max(18, Math.min(H - 22, y2));

      const x3 = isRight ? x2 + hookLen : x2 - hookLen;
      let textX = isRight ? x3 + 5 : x3 - 5;
      if (isRight) {
        textX = Math.min(W - estTextW - 4, Math.max(x3 + 4, textX));
      } else {
        textX = Math.max(estTextW + 4, Math.min(x3 - 4, textX));
      }

      return {
        ...item,
        strokeDasharray,
        strokeDashoffset,
        isHovered: hoveredIndex === idx,
        hasCallout: item.pct_share > 0 && candidateScheme !== "scheme_c_matrix",
        callout: { x1, y1, x2, y2, x3, textX, isRight },
      };
    });
  }, [currentItems, circumference, cx, cy, r_out, elbowDist, hookLen, estTextW, W, H, hoveredIndex, candidateScheme]);

  // 目前 Hover 的單項
  const activeHoverItem = hoveredIndex !== null ? currentItems[hoveredIndex] : null;

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40", className)}>
      {/* 1. 卡片頂部標題列 (純淨標題抓手) */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-secondary/50 border-b border-border/80 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <CardHeaderTitle
            cardId="allocation"
            title="資產曝險配置"
            subtext={
              <span className="text-[10px] text-muted-foreground font-mono ml-1">
                {candidateScheme === "scheme_a_bloomberg" && "Bloomberg AIM · 智慧 HUD"}
                {candidateScheme === "scheme_b_okx" && "OKX Pro · 雙維度風控"}
                {candidateScheme === "scheme_c_matrix" && "CoinGlass · 左環右表複合矩陣"}
              </span>
            }
          />
        </div>

        <div className="flex items-center gap-1.5 shrink-0 text-[10px] font-mono text-muted-foreground">
          <PulseBeacon size={4.5} />
          <span>即時計算</span>
        </div>
      </div>

      {/* 2. 方案候選切換列 (3 大業界方案一鍵切換對比) */}
      <div className="flex items-center justify-between bg-black/40 border-b border-white/[0.08] px-2 py-1 shrink-0 gap-1.5">
        <div className="flex items-center gap-1 flex-1">
          <button
            type="button"
            onClick={() => { setCandidateScheme("scheme_a_bloomberg"); setHoveredIndex(null); }}
            className={cn(
              "flex-1 flex items-center justify-center gap-1 py-1 px-1.5 rounded text-[10.5px] font-mono transition-all cursor-pointer",
              candidateScheme === "scheme_a_bloomberg"
                ? "bg-primary/20 text-primary border border-primary/50 font-bold shadow-xs"
                : "text-muted-foreground hover:text-foreground hover:bg-secondary/60 border border-transparent"
            )}
          >
            <Sliders className="size-3" />
            <span>方案 A: 彭博智慧 HUD</span>
          </button>

          <button
            type="button"
            onClick={() => { setCandidateScheme("scheme_b_okx"); setHoveredIndex(null); }}
            className={cn(
              "flex-1 flex items-center justify-center gap-1 py-1 px-1.5 rounded text-[10.5px] font-mono transition-all cursor-pointer",
              candidateScheme === "scheme_b_okx"
                ? "bg-primary/20 text-primary border border-primary/50 font-bold shadow-xs"
                : "text-muted-foreground hover:text-foreground hover:bg-secondary/60 border border-transparent"
            )}
          >
            <Layers className="size-3" />
            <span>方案 B: OKX 專業雙維度</span>
          </button>

          <button
            type="button"
            onClick={() => { setCandidateScheme("scheme_c_matrix"); setHoveredIndex(null); }}
            className={cn(
              "flex-1 flex items-center justify-center gap-1 py-1 px-1.5 rounded text-[10.5px] font-mono transition-all cursor-pointer",
              candidateScheme === "scheme_c_matrix"
                ? "bg-primary/20 text-primary border border-primary/50 font-bold shadow-xs"
                : "text-muted-foreground hover:text-foreground hover:bg-secondary/60 border border-transparent"
            )}
          >
            <LayoutList className="size-3" />
            <span>方案 C: 左環右表矩陣</span>
          </button>
        </div>
      </div>

      {/* 方案 B 次級切換列 (標的曝險 vs 保證金水位) */}
      {candidateScheme === "scheme_b_okx" && (
        <div className="flex bg-secondary/30 border-b border-border/60 px-3 py-1 items-center justify-between shrink-0 text-[10px] font-mono">
          <span className="text-muted-foreground">金融視圖維度：</span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => { setOkxDimension("notional"); setHoveredIndex(null); }}
              className={cn(
                "px-2 py-0.5 rounded transition-all cursor-pointer",
                okxDimension === "notional"
                  ? "bg-primary text-primary-foreground font-semibold"
                  : "bg-surface hover:bg-secondary text-muted-foreground"
              )}
            >
              1. 標的合約曝險 (Notional)
            </button>
            <button
              type="button"
              onClick={() => { setOkxDimension("margin"); setHoveredIndex(null); }}
              className={cn(
                "px-2 py-0.5 rounded transition-all cursor-pointer",
                okxDimension === "margin"
                  ? "bg-primary text-primary-foreground font-semibold"
                  : "bg-surface hover:bg-secondary text-muted-foreground"
              )}
            >
              2. 保證金風控水位 (Margin)
            </button>
          </div>
        </div>
      )}

      {/* 3. 核心繪圖與內容展示區 */}
      <div className="flex-1 min-h-0 flex flex-col justify-between overflow-hidden p-2">
        <div ref={containerRef} className="flex-1 min-h-0 w-full h-full relative overflow-hidden flex items-center">
          
          {/* ==================== 方案 A & 方案 B：完整環圖 + 智慧中央 HUD ==================== */}
          {(candidateScheme === "scheme_a_bloomberg" || candidateScheme === "scheme_b_okx") && (
            <div className="w-full h-full relative">
              <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="w-full h-full block select-none">
                {/* 底環軌道 */}
                <circle cx={cx} cy={cy} r={radius} fill="none" stroke="#1c2027" strokeWidth={strokeWidth} />

                {/* 數據圓弧切片 */}
                {donutSlices.map((slice, idx) => {
                  if (slice.pct_share <= 0) return null;
                  return (
                    <circle
                      key={slice.symbol}
                      cx={cx}
                      cy={cy}
                      r={radius}
                      fill="none"
                      stroke={slice.color}
                      strokeWidth={slice.isHovered ? strokeWidth + 4 : strokeWidth}
                      strokeDasharray={slice.strokeDasharray}
                      strokeDashoffset={slice.strokeDashoffset}
                      className="cursor-pointer transition-all duration-150"
                      style={{
                        transform: "rotate(-90deg)",
                        transformOrigin: `${cx}px ${cy}px`,
                        filter: slice.isHovered ? `drop-shadow(0 0 8px ${slice.color}90)` : undefined,
                      }}
                      onMouseEnter={() => setHoveredIndex(idx)}
                      onMouseLeave={() => setHoveredIndex(null)}
                    />
                  );
                })}

                {/* 方案 A/B 微折短鉤引線與外部標籤 */}
                {donutSlices.map((slice) => {
                  if (!slice.hasCallout) return null;
                  const c = slice.callout;
                  return (
                    <g key={`callout-${slice.symbol}`} className="pointer-events-none transition-opacity duration-150">
                      <polyline
                        points={`${c.x1},${c.y1} ${c.x2},${c.y2} ${c.x3},${c.y2}`}
                        fill="none"
                        stroke={slice.color}
                        strokeWidth="1.25"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className={slice.isHovered ? "opacity-100" : "opacity-85"}
                      />
                      <circle cx={c.x3} cy={c.y2} r="1.5" fill={slice.color} />
                      <text
                        x={c.textX}
                        y={c.y2 - 3}
                        textAnchor={c.isRight ? "start" : "end"}
                        className="font-mono font-bold select-none"
                        fill="#ffffff"
                        fontSize={Math.max(10.5, Math.min(12.5, W * 0.032))}
                      >
                        {slice.shortLabel || slice.symbol} {slice.pct_share.toFixed(1)}%
                      </text>
                      <text
                        x={c.textX}
                        y={c.y2 + 9}
                        textAnchor={c.isRight ? "start" : "end"}
                        className="font-mono select-none"
                        fill="#94a3b8"
                        fontSize={Math.max(9, Math.min(10.5, W * 0.026))}
                      >
                        ${slice.nominal_usdt.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
                      </text>
                    </g>
                  );
                })}
              </svg>

              {/* 中央智慧 HUD (Hero 數據核心 · 徹底消滅黑洞！) */}
              <div
                className="absolute flex flex-col items-center justify-center text-center pointer-events-none transition-all duration-200"
                style={{
                  left: `${cx - radius + strokeWidth}px`,
                  top: `${cy - radius + strokeWidth}px`,
                  width: `${(radius - strokeWidth) * 2}px`,
                  height: `${(radius - strokeWidth) * 2}px`,
                }}
              >
                {activeHoverItem ? (
                  // Hover 聚焦展示單項詳情
                  <div className="flex flex-col items-center justify-center animate-in fade-in zoom-in-95 duration-100">
                    <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-tight">
                      {activeHoverItem.shortLabel || activeHoverItem.symbol}
                    </span>
                    <span
                      className="num font-bold text-base leading-tight tracking-tight my-0.5"
                      style={{ color: activeHoverItem.color }}
                    >
                      {activeHoverItem.pct_share.toFixed(1)}%
                    </span>
                    <span className="text-[9.5px] font-mono text-muted-foreground/90">
                      ${activeHoverItem.nominal_usdt.toFixed(1)}
                    </span>
                    {activeHoverItem.leverage && (
                      <span className="mt-0.5 px-1 py-0.2 rounded bg-white/10 text-[8.5px] font-mono text-white/90">
                        {activeHoverItem.leverage}
                      </span>
                    )}
                  </div>
                ) : (
                  // 常態總覽 HUD
                  <div className="flex flex-col items-center justify-center">
                    <span className="text-[9.5px] font-mono text-muted-foreground uppercase tracking-wider">
                      {candidateScheme === "scheme_b_okx" && okxDimension === "margin" ? "保證金率" : "總名義額"}
                    </span>
                    <span className="num font-bold text-[15px] sm:text-[17px] text-foreground leading-tight tracking-tight my-0.5 text-primary">
                      {candidateScheme === "scheme_b_okx" && okxDimension === "margin" ? "14.2%" : "$1,420"}
                    </span>
                    <span className="text-[9px] font-mono text-muted-foreground flex items-center gap-1">
                      {candidateScheme === "scheme_b_okx" && okxDimension === "margin" ? (
                        <span className="text-up font-semibold">緩衝 +85.8%</span>
                      ) : (
                        <span>0.01x / 3x</span>
                      )}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ==================== 方案 C：CoinGlass 左環右表量化矩陣 ==================== */}
          {candidateScheme === "scheme_c_matrix" && (
            <div className="w-full h-full flex items-center justify-between gap-3 overflow-hidden">
              {/* 左側精巧迷你 Donut */}
              <div className="relative shrink-0 flex items-center justify-center" style={{ width: `${cx * 2}px`, height: `${H}px` }}>
                <svg width={cx * 2} height={H} viewBox={`0 0 ${cx * 2} ${H}`} className="block select-none">
                  <circle cx={cx} cy={cy} r={radius} fill="none" stroke="#1c2027" strokeWidth={strokeWidth} />
                  {donutSlices.map((slice, idx) => {
                    if (slice.pct_share <= 0) return null;
                    return (
                      <circle
                        key={slice.symbol}
                        cx={cx}
                        cy={cy}
                        r={radius}
                        fill="none"
                        stroke={slice.color}
                        strokeWidth={strokeWidth}
                        strokeDasharray={slice.strokeDasharray}
                        strokeDashoffset={slice.strokeDashoffset}
                        style={{
                          transform: "rotate(-90deg)",
                          transformOrigin: `${cx}px ${cy}px`,
                        }}
                        onMouseEnter={() => setHoveredIndex(idx)}
                        onMouseLeave={() => setHoveredIndex(null)}
                      />
                    );
                  })}
                </svg>

                {/* 迷你環中央數值 */}
                <div
                  className="absolute flex flex-col items-center justify-center text-center pointer-events-none"
                  style={{
                    left: `${cx - radius + strokeWidth}px`,
                    top: `${cy - radius + strokeWidth}px`,
                    width: `${(radius - strokeWidth) * 2}px`,
                    height: `${(radius - strokeWidth) * 2}px`,
                  }}
                >
                  <span className="text-[8.5px] font-mono text-muted-foreground uppercase">總曝險</span>
                  <span className="num font-bold text-[13px] text-primary leading-tight">$1,420</span>
                  <span className="text-[8px] font-mono text-muted-foreground">3x cross</span>
                </div>
              </div>

              {/* 右側高密度量化數據矩陣表 */}
              <div className="flex-1 min-w-0 h-full flex flex-col justify-center gap-1.5 pr-2 overflow-y-auto">
                <div className="text-[9.5px] font-mono text-muted-foreground/70 uppercase tracking-wider flex items-center justify-between border-b border-border/50 pb-1">
                  <span>標的 / 策略</span>
                  <span>佔比 · 名義額</span>
                  <span>未平盈虧</span>
                </div>

                {schemeCItems.map((item, idx) => (
                  <div
                    key={item.symbol}
                    onMouseEnter={() => setHoveredIndex(idx)}
                    onMouseLeave={() => setHoveredIndex(null)}
                    className={cn(
                      "flex items-center justify-between p-1.5 rounded-md border transition-all cursor-pointer font-mono text-[11px]",
                      hoveredIndex === idx
                        ? "bg-secondary/70 border-primary/40 shadow-xs"
                        : "bg-surface/50 border-border/60 hover:bg-secondary/40"
                    )}
                  >
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className="size-2 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                      <div className="flex flex-col min-w-0">
                        <span className="font-semibold text-foreground text-[11.5px] truncate">{item.label}</span>
                        <span className="text-[9px] text-muted-foreground">{item.leverage}</span>
                      </div>
                    </div>

                    <div className="flex flex-col text-right">
                      <span className="font-bold text-foreground text-[11.5px]">{item.pct_share.toFixed(1)}%</span>
                      <span className="text-[9.5px] text-muted-foreground">${item.nominal_usdt.toFixed(1)}</span>
                    </div>

                    <div className="flex flex-col text-right">
                      <span className={cn("text-[11px] font-semibold", item.pnlUp ? "text-up" : "text-down")}>
                        {item.pnl}
                      </span>
                      <span className="text-[8.5px] text-muted-foreground">7D 損益</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 4. 底部量化風控與狀態列 (依方案收斂，零浪費排版) */}
        <div className="mt-1 pt-1.5 border-t border-border/70 flex items-center justify-between text-[10px] font-mono shrink-0 whitespace-nowrap overflow-x-hidden">
          {candidateScheme === "scheme_a_bloomberg" && (
            <>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">單幣預算防線:</span>
                <span className="text-primary font-bold">BTC 42.0% / 50%</span>
                <span className="text-up bg-up/10 px-1 py-0.2 rounded border border-up/20 text-[9px]">SAFE</span>
              </div>
              <div className="flex items-center gap-2 text-muted-foreground">
                <span>多空淨敞口: <span className="text-foreground font-semibold">+$810 (多74%)</span></span>
                <span>·</span>
                <span>在途凍結: <span className="text-foreground font-semibold">$213.08</span></span>
              </div>
            </>
          )}

          {candidateScheme === "scheme_b_okx" && (
            <>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">
                  {okxDimension === "margin" ? "維持保證金 MM:" : "總曝險預算:"}
                </span>
                <span className="text-foreground font-bold">
                  {okxDimension === "margin" ? "$80.97 (8.5%)" : "$37,500.00"}
                </span>
              </div>
              <div className="flex items-center gap-2 text-muted-foreground">
                <span>Asia/Taipei 00:00: <span className="text-up font-semibold">日損 0.0%/10% (SAFE)</span></span>
                <span>·</span>
                <span>強平安全距離: <span className="text-foreground font-semibold">+85.8%</span></span>
              </div>
            </>
          )}

          {candidateScheme === "scheme_c_matrix" && (
            <>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">總資產淨值:</span>
                <span className="text-primary font-bold">$47,855.08</span>
                <span>·</span>
                <span>有效槓桿: <span className="text-foreground font-semibold">0.43x / 3x</span></span>
              </div>
              <div className="flex items-center gap-1.5 text-muted-foreground">
                <ShieldCheck className="size-3 text-up" />
                <span className="text-up font-semibold">風控 Latch 監控中</span>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
