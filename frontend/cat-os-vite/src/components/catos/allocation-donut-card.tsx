import { useState, useMemo, useEffect, useRef } from "react";
import { CardHeaderTitle } from "./card-header-title";
import { PulseBeacon } from "./pulse-beacon";
import { cn } from "@/lib/utils";

// 定案配色：低彩度、高質感的幣種資料系列色 (收斂刺眼霓虹感，依循 8899 原版)
const cryptoColors = {
  btc: "#e8b45e",       // BTC 蜂蜜金
  in_flight: "#7faee2", // ETH / 在途凍結 雅緻瓦藍
  available: "#65cba7", // 可用額度 薄荷青
  alt: "#8b8df8",       // SOL 沉穩淡靛
  neutral: "#90969d",   // 中性灰
};

export type ViewMode = "ranked_assets" | "leveraged" | "raw_margin" | "compare_all";

interface DonutItem {
  symbol: string;
  label: string;
  shortLabel?: string;
  sub: string;
  nominal_usdt: number;
  pct_share: number;
  color: string;
}

const DATA_MODES: Record<
  ViewMode,
  {
    name: string;
    subtitle: string;
    items: DonutItem[];
    summary: { shortLabel: string; nominal_usdt: number; color: string };
    centerValue: string;
    centerLabel: string;
  }
> = {
  ranked_assets: {
    name: "幣種排行",
    subtitle: "外置微折短鉤視圖",
    items: [
      { symbol: "BTC", label: "BTC-USDT", shortLabel: "BTC", sub: "持有中", nominal_usdt: 596.6, pct_share: 73.7, color: cryptoColors.btc },
      { symbol: "ETH", label: "ETH-USDT", shortLabel: "ETH", sub: "掛單中", nominal_usdt: 213.08, pct_share: 26.3, color: cryptoColors.in_flight },
      { symbol: "SOL", label: "SOL-USDT", shortLabel: "SOL", sub: "空倉", nominal_usdt: 0.0, pct_share: 0.0, color: cryptoColors.alt },
    ],
    summary: { shortLabel: "總額度", nominal_usdt: 1420.5, color: "#94a3b8" },
    centerValue: "1,420",
    centerLabel: "總額度",
  },
  leveraged: {
    name: "名義曝險",
    subtitle: "名義曝險視圖",
    items: [
      { symbol: "BTC", label: "BTC 永續持倉", shortLabel: "BTC 持倉", sub: "持倉", nominal_usdt: 596.6, pct_share: 42.0, color: cryptoColors.btc },
      { symbol: "在途", label: "在途委託凍結", shortLabel: "在途凍結", sub: "凍結", nominal_usdt: 213.08, pct_share: 15.0, color: cryptoColors.in_flight },
      { symbol: "可用", label: "可用曝險額度", shortLabel: "可用額度", sub: "剩餘", nominal_usdt: 610.82, pct_share: 43.0, color: cryptoColors.available },
    ],
    summary: { shortLabel: "總額度", nominal_usdt: 1420.5, color: "#94a3b8" },
    centerValue: "1,420",
    centerLabel: "總額度",
  },
  raw_margin: {
    name: "真實本金",
    subtitle: "真實保證金視圖",
    items: [
      { symbol: "佔用", label: "佔用本金", shortLabel: "佔用本金", sub: "保證金", nominal_usdt: 80.97, pct_share: 0.07, color: cryptoColors.btc },
      { symbol: "可用", label: "自由未佔用", shortLabel: "自由現金", sub: "本金", nominal_usdt: 125400, pct_share: 99.93, color: cryptoColors.available },
    ],
    summary: { shortLabel: "總權益", nominal_usdt: 125480.97, color: "#94a3b8" },
    centerValue: "125.4k",
    centerLabel: "總權益",
  },
  compare_all: {
    name: "雙軸對照",
    subtitle: "雙軸對照視圖",
    items: [
      { symbol: "BTC", label: "BTC 持倉", shortLabel: "BTC", sub: "槓桿", nominal_usdt: 596.6, pct_share: 42.0, color: cryptoColors.btc },
      { symbol: "在途", label: "在途委託", shortLabel: "在途", sub: "委託", nominal_usdt: 213.08, pct_share: 15.0, color: cryptoColors.in_flight },
      { symbol: "可用", label: "可用額度", shortLabel: "可用", sub: "預算", nominal_usdt: 610.82, pct_share: 43.0, color: cryptoColors.available },
    ],
    summary: { shortLabel: "總額度", nominal_usdt: 1420.5, color: "#94a3b8" },
    centerValue: "1,420",
    centerLabel: "總額度",
  },
};

function formatUsdt(val: number | string): string {
  if (typeof val === "string" && val.includes("k")) return val;
  const num = typeof val === "string" ? parseFloat(val.replace(/,/g, "")) : val;
  if (isNaN(num)) return String(val);
  if (num >= 100000) {
    return Math.round(num).toLocaleString("en-US");
  }
  return num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function AllocationDonutCard({ className }: { className?: string }) {
  const [activeMode, setActiveMode] = useState<ViewMode>("ranked_assets");
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [pinnedIndex, setPinnedIndex] = useState<number | null>(null);

  // 1. 自適應容器寬高 ResizeObserver (雙向響應式，隨卡片拖曳縮放即時聯動重繪)
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState<{ width: number; height: number }>({ width: 460, height: 230 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let rafId: number | null = null;
    const updateSize = () => {
      const rect = el.getBoundingClientRect();
      const w = Math.floor(rect.width);
      const h = Math.floor(rect.height);
      if (w > 0 && h > 0) {
        setDims((prev) => (prev.width === w && prev.height === h ? prev : { width: w, height: h }));
      }
    };
    updateSize();
    const ro = new ResizeObserver(() => {
      if (rafId) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(updateSize);
    });
    ro.observe(el);
    return () => {
      if (rafId) cancelAnimationFrame(rafId);
      ro.disconnect();
    };
  }, []);

  const effectiveIndex = pinnedIndex !== null ? pinnedIndex : hoveredIndex;
  const currentConfig = DATA_MODES[activeMode];
  const items = currentConfig.items;

  // 2. 流體幾何運算 (徹底修正「太大了」與「頂底文字跑版溢出」)
  const W = dims.width;
  const H = dims.height;

  // 中心坐標永遠精確坐落卡片核心中點
  const cx = W / 2;
  const cy = H / 2;

  // 動態預估文字寬度：窄卡精簡至 56px，標準/寬卡 76px
  const estTextW = W < 340 ? 56 : 76;

  // 垂直空間預留：上下各預留約 42px (合計 84px) 給折線與上下兩行文字
  // 嚴格確保圓環外徑不超過容器高度的 58%，杜絕頂天立地膨脹感
  const maxRadiusByH = Math.max(26, (H - 84) / 2.32);

  // 水平空間預留：兩側預留文字與折線
  const maxRadiusByW = Math.max(26, (W / 2 - 20 - estTextW) / 1.35);

  // 自適應半徑：上限收斂至 75px (外徑 ~174px)，克制大方，徹底解決「太大了」的視覺壓迫
  const radius = Math.round(Math.min(75, Math.max(26, Math.min(maxRadiusByW, maxRadiusByH))));

  // 環身厚度：收斂在 12~24px 之間，維持定案的扎實質感但絕不臃腫
  const strokeWidth = Math.max(12, Math.min(24, Math.round(radius * 0.32)));
  const r_out = radius + strokeWidth / 2;
  const circumference = 2 * Math.PI * radius;

  // 外置微折短鉤幾何尺寸 (隨半徑等比微調)
  const elbowDist = Math.max(9, Math.min(18, Math.round(radius * 0.18)));
  const hookLen = Math.max(8, Math.min(14, Math.round(radius * 0.14)));

  // 字級隨圖表縮放動態匹配
  const isCompact = radius < 55;
  const isLarge = radius >= 72;
  const fontSizes = {
    pct: isCompact ? "10.5px" : isLarge ? "13px" : "11.5px",
    amt: isCompact ? "9px" : isLarge ? "10.5px" : "9.5px",
    sub: isCompact ? "8px" : isLarge ? "9.5px" : "8.5px",
    lineGap: isCompact ? 11 : isLarge ? 14 : 12,
  };

  // 定案方案 A（微折短鉤）幾何計算
  const slicesWithCallouts = useMemo(() => {
    let accumulated = 0;
    const gapPx = 2.0;

    return items.map((item, idx) => {
      let effectivePct = item.pct_share;
      if (activeMode === "raw_margin" && item.pct_share < 1 && item.pct_share > 0) {
        effectivePct = 6.0;
      }
      const fullArc = (effectivePct / 100) * circumference;
      const arcLength = Math.max(0, fullArc - gapPx);
      const strokeDasharray = `${arcLength} ${circumference - arcLength}`;
      const strokeDashoffset = -accumulated;

      // 弧度中間角（從頂部 -90° 開始順時針）
      const startAngle = (accumulated / circumference) * 2 * Math.PI - Math.PI / 2;
      const arcAngle = (fullArc / circumference) * 2 * Math.PI;
      const midAngle = startAngle + arcAngle / 2;
      accumulated += fullArc;

      const cos = Math.cos(midAngle);
      const sin = Math.sin(midAngle);
      const isRight = cos >= 0;

      // 1. 起點：圓環外沿定位點
      const x1 = cx + r_out * cos;
      const y1 = cy + r_out * sin;

      // 2. 拐點：斜向 45° 放射肘點 (若接近正上/正下方 12點或6點鐘，加強側向延伸避免垂直撞邊)
      const isNearlyVertical = Math.abs(cos) < 0.32;
      const effectiveElbowDist = isNearlyVertical ? elbowDist + 5 : elbowDist;
      let x2 = cx + (r_out + effectiveElbowDist) * cos;
      if (isNearlyVertical) {
        x2 = isRight ? Math.max(cx + 16, x2) : Math.min(cx - 16, x2);
      }

      let y2 = cy + (r_out + effectiveElbowDist) * sin;
      // 垂直上下防溢出安全夾持 (Clamp)：確保文字與短鉤絕對落在畫布 [18, H - 24] 安全區內
      const minY2 = 18;
      const maxY2 = H - fontSizes.lineGap - 10;
      y2 = Math.max(minY2, Math.min(maxY2, y2));

      // 3. 方案 A 微折短鉤：僅 8~14px 微型轉折，徹底廢除長底線，絕不穿透切割文字
      const x3 = isRight ? x2 + hookLen : x2 - hookLen;

      // 4. 文字錨點：坐落在短鉤外側 5px，嚴格夾持在安全邊界內，徹底防裁切
      let textX = isRight ? x3 + 5 : x3 - 5;
      if (isRight) {
        textX = Math.min(W - estTextW - 4, Math.max(x3 + 4, textX));
      } else {
        textX = Math.max(estTextW + 4, Math.min(x3 - 4, textX));
      }
      const textAnchor: "start" | "end" = isRight ? "start" : "end";

      return {
        ...item,
        strokeDasharray,
        strokeDashoffset,
        isHovered: effectiveIndex === idx,
        hasCallout: item.pct_share > 0, // 僅大於 0% 伸出牽引線
        callout: {
          x1, y1,
          x2, y2,
          x3,
          textX,
          textAnchor,
          isRight,
        },
      };
    });
  }, [items, activeMode, circumference, effectiveIndex, cx, cy, r_out, elbowDist, hookLen, W]);

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40", className)}>
      {/* 1. 卡片頂部工具列 (收斂固化，純淨專業排版) */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-secondary/50 border-b border-border/80 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <CardHeaderTitle
            cardId="allocation"
            title="資產曝險配置"
            subtext={<span className="text-[10px] text-muted-foreground font-mono ml-1">{currentConfig.subtitle}</span>}
          />
        </div>

        {/* 即時同步動態指示 (符合制度規範) */}
        <div className="flex items-center gap-1.5 shrink-0 text-[10px] font-mono text-muted-foreground">
          <PulseBeacon size={4.5} />
          <span>即時同步</span>
        </div>
      </div>

      {/* 2. 業務視圖切換列 (4 等分 Micro-tabs) */}
      <div className="flex bg-black/30 border-b border-white/[0.06] p-0.5 shrink-0">
        {(["ranked_assets", "leveraged", "raw_margin", "compare_all"] as const).map((mode) => (
          <button
            key={mode}
            type="button"
            onClick={() => {
              setActiveMode(mode);
              setHoveredIndex(null);
              setPinnedIndex(null);
            }}
            className={cn(
              "flex-1 text-center py-1 text-[10.5px] font-semibold rounded-xs transition-colors whitespace-nowrap",
              activeMode === mode
                ? "bg-white/[0.1] text-white font-bold shadow-2xs"
                : "text-slate-400 hover:text-white hover:bg-white/[0.04]"
            )}
          >
            {DATA_MODES[mode].name}
          </button>
        ))}
      </div>

      {/* 3. 核心內容區 (自適應全尺寸縮放 · 隨卡片縮放無縫動態重繪) */}
      <div className="flex-1 min-h-0 flex flex-col justify-between overflow-hidden p-2">
        {/* SVG 畫布容器：由 ResizeObserver 監聽即時像素寬高 */}
        <div ref={containerRef} className="flex-1 min-h-0 w-full h-full flex items-center justify-center relative overflow-hidden">
          <svg
            width={W}
            height={H}
            viewBox={`0 0 ${W} ${H}`}
            className="w-full h-full block select-none"
          >
            {/* 1. 底環背景軌道 */}
            <circle cx={cx} cy={cy} r={radius} fill="none" stroke="#1c2027" strokeWidth={strokeWidth} />

            {/* 2. 多幣種切片環 */}
            <g className="-rotate-90 origin-center" style={{ transformOrigin: `${cx}px ${cy}px` }}>
              {slicesWithCallouts.map((s, idx) => (
                <circle
                  key={s.label}
                  cx={cx}
                  cy={cy}
                  r={radius}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={s.isHovered ? strokeWidth + 4 : strokeWidth}
                  strokeDasharray={s.strokeDasharray}
                  strokeDashoffset={s.strokeDashoffset}
                  className="cursor-pointer"
                  style={{
                    transition: "stroke-width 0.18s ease, opacity 0.18s ease",
                    opacity: effectiveIndex !== null && effectiveIndex !== idx ? 0.35 : 1,
                  }}
                  onMouseEnter={() => {
                    if (pinnedIndex === null) setHoveredIndex(idx);
                  }}
                  onMouseLeave={() => {
                    if (pinnedIndex === null) setHoveredIndex(null);
                  }}
                  onClick={() => setPinnedIndex((prev) => (prev === idx ? null : idx))}
                />
              ))}
            </g>

            {/* 3. 外置微折短鉤標註 */}
            {slicesWithCallouts.map((s, idx) => {
              if (!s.hasCallout) return null;
              const c = s.callout;
              const isHovered = effectiveIndex === idx;
              const isDimmed = effectiveIndex !== null && !isHovered;

              return (
                <g
                  key={`callout-${s.label}`}
                  className="cursor-pointer transition-all duration-200"
                  style={{ opacity: isDimmed ? 0.3 : 1 }}
                  onMouseEnter={() => {
                    if (pinnedIndex === null) setHoveredIndex(idx);
                  }}
                  onMouseLeave={() => {
                    if (pinnedIndex === null) setHoveredIndex(null);
                  }}
                  onClick={() => setPinnedIndex((prev) => (prev === idx ? null : idx))}
                >
                  {/* 起點圓環定位點 */}
                  <circle
                    cx={c.x1}
                    cy={c.y1}
                    r={isHovered ? 4 : 2.8}
                    fill={s.color}
                    style={{ filter: isHovered ? `drop-shadow(0 0 5px ${s.color})` : "none" }}
                  />

                  {/* 方案 A 微折短鉤 (乾淨俐落收尾) */}
                  <polyline
                    points={`${c.x1},${c.y1} ${c.x2},${c.y2} ${c.x3},${c.y2}`}
                    fill="none"
                    stroke={s.color}
                    strokeWidth={isHovered ? 2 : 1.3}
                    strokeOpacity={isHovered ? 1 : 0.8}
                  />

                  {/* 上行文字：幣種名稱與佔比 */}
                  <text
                    x={c.textX}
                    y={c.y2 - 2}
                    textAnchor={c.textAnchor}
                    className="select-none"
                    style={{ fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' }}
                  >
                    <tspan fill="#f8fafc" fontWeight="700" fontSize={fontSizes.pct} letterSpacing="0.02em">
                      {s.symbol || s.shortLabel}
                    </tspan>
                    <tspan
                      dx="5"
                      fill={s.color}
                      fontWeight="800"
                      fontSize={fontSizes.pct}
                      style={{ fontFamily: '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace' }}
                    >
                      {s.pct_share.toFixed(1)}%
                    </tspan>
                  </text>

                  {/* 下行文字：名目金額與狀態 */}
                  <text
                    x={c.textX}
                    y={c.y2 + fontSizes.lineGap}
                    textAnchor={c.textAnchor}
                    className="select-none"
                    style={{ fontFamily: '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace' }}
                  >
                    <tspan fill="#cbd5e1" fontSize={fontSizes.amt} fontWeight="600">
                      ${formatUsdt(s.nominal_usdt)}
                    </tspan>
                    {W >= 340 && (
                      <tspan
                        dx="4"
                        fill="#64748b"
                        fontSize={fontSizes.sub}
                        fontWeight="500"
                        style={{ fontFamily: 'system-ui, -apple-system, sans-serif' }}
                      >
                        ({s.sub})
                      </tspan>
                    )}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        {/* 4. 底部整合式量化資訊面板 (徹底防破版 · 支援各尺寸卡片) */}
        <div className="shrink-0 mt-0.5 border-t border-white/[0.06] bg-black/25 px-2.5 py-1.5 rounded-b flex flex-col gap-1 select-none">
          {/* 上列：資產幣種配置與總名目額度 (嚴格防止文字斷行疊字) */}
          <div className="flex items-center justify-between text-[10px] gap-2 overflow-hidden whitespace-nowrap">
            <div className="flex items-center gap-2.5 min-w-0 overflow-hidden">
              {items.map((it, idx) => (
                <div
                  key={it.label}
                  className="inline-flex items-center gap-1 cursor-pointer shrink-0"
                  onMouseEnter={() => setHoveredIndex(idx)}
                  onMouseLeave={() => setHoveredIndex(null)}
                >
                  <span className="size-1.5 rounded-full shrink-0" style={{ backgroundColor: it.color }} />
                  <span className={cn("font-medium", effectiveIndex === idx ? "text-white font-bold" : "text-slate-400")}>
                    {it.symbol}
                  </span>
                  <span className="font-mono text-slate-300 font-semibold">{it.pct_share.toFixed(1)}%</span>
                  {it.pct_share === 0 && <span className="text-[9px] text-slate-500 font-mono hidden sm:inline">(空)</span>}
                </div>
              ))}
            </div>

            {/* 總額 */}
            <div className="inline-flex items-center gap-1 font-mono shrink-0">
              <span className="text-slate-400 text-[9px]">總配置額</span>
              <span className="text-white font-bold text-[10.5px]">${formatUsdt(currentConfig.summary.nominal_usdt)} U</span>
            </div>
          </div>

          {/* 下列：風控核心三指標 (簡明精準，杜絕斷行) */}
          <div className="flex items-center justify-between pt-1 border-t border-white/[0.04] text-[9.5px] font-mono whitespace-nowrap gap-1 overflow-hidden">
            <span className="text-slate-400 shrink-0">
              槓桿 <b className="text-[#65cba7] font-bold">0.01x</b> <span className="text-slate-500 text-[8.5px]">/3x</span>
            </span>
            <span className="text-slate-400 shrink-0">
              在途 <b className="text-[#e8b45e] font-bold">213 U</b> <span className="text-slate-500 text-[8.5px]">(15%)</span>
            </span>
            <span className="text-slate-400 shrink-0">
              可用 <b className="text-[#e5e8ec] font-bold">375k U</b> <span className="text-[#65cba7] text-[8.5px]">SAFE</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
