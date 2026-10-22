import { useState, useMemo, useEffect, useRef } from "react";
import { CardHeaderTitle } from "./card-header-title";
import { cn } from "@/lib/utils";
import { useLiveMarketStore } from "@/state/liveMarketStore";
import { NumberTicker } from "./motion/number-ticker";

// 定案配色：低彩度、高質感的幣種資料系列色
const cryptoColors = {
  btc: "#e8b45e",       // BTC 蜂蜜金
  in_flight: "#7faee2", // ETH / 在途凍結 雅緻瓦藍
  available: "#10b981", // 可用額度 翡翠綠 (安全緩衝)
  alt: "#8b8df8",       // SOL 沉穩淡靛
  mm: "#f59e0b",        // 維持保證金 琥珀橘
  im: "#38bdf8",        // 初始保證金 晴空藍
  free: "#34d399",      // 自由保證金 薄荷青
};

export interface DonutConfig {
  donutRatio: number;      // 左側圓環寬度佔比 (51%)
  radius: number;          // 圓環外半徑 (66px)
  strokeWidth: number;     // 環身厚度 (10px)
  sliceGap: number;        // 切片物理縫隙 (2px)
  hudFontSize: number;     // 中央 HUD 主字大小 (28px)
  hudYOffset: number;      // 中央 HUD 垂直偏移 (-13px)
  barHeight: number;       // 右側進度條高度 (3px)
  limitMarkLength: number; // 50% 刻度線長度 (0px)
}

// ==================== 定案 C 參數 (Solidified TradingView 極簡微隙甜甜圈配置) ====================
export const DONUT_CONFIG: DonutConfig = {
  donutRatio: 51,
  radius: 66,
  strokeWidth: 10,
  sliceGap: 2,
  hudFontSize: 28,
  hudYOffset: -13,
  barHeight: 3,
  limitMarkLength: 0,
};

interface DonutItem {
  symbol: string;
  label: string;
  shortLabel?: string;
  sub: string;
  nominal_usdt: number;
  pct_share: number;
  color: string;
  leverage?: string;
}

export function AllocationDonutCard({ className }: { className?: string }) {
  // Hover 切片索引
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  // 容器寬高響應式動態捕捉 (Fluid ResizeObserver)
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState<{ width: number; height: number }>({ width: 380, height: 240 });

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
  }, []);

  const {
    totalEquity,
    effectiveLeverage,
    btcNotional,
    ethNotional,
    solNotional,
    inFlightNotional: inFlightNominal,
  } = useLiveMarketStore();

  // ==================== 全域唯一真實持倉名義計算 (單一真理，杜絕數值打架) ====================
  const totalHoldingsNominal = btcNotional + ethNotional + solNotional;

  // 總曝險額度容量（100% = 總權益 × 3.0x 槓桿上限）
  const budgetItems: DonutItem[] = useMemo(() => {
    const maxBudget = totalEquity * 3.0; // 3.0x 槓桿上限
    const usedNom = totalHoldingsNominal + inFlightNominal;
    const availNom = Math.max(0, maxBudget - usedNom);

    return [
      {
        symbol: "BTC",
        label: "BTC 持倉名義額",
        shortLabel: "BTC",
        sub: `已開倉 (${(btcNotional / totalEquity).toFixed(2)}x)`,
        nominal_usdt: btcNotional,
        pct_share: (btcNotional / maxBudget) * 100,
        color: cryptoColors.btc,
        leverage: "單幣上限 50%",
      },
      {
        symbol: "ETH",
        label: "ETH 持倉名義額",
        shortLabel: "ETH",
        sub: `已開倉 (${(ethNotional / totalEquity).toFixed(2)}x)`,
        nominal_usdt: ethNotional,
        pct_share: (ethNotional / maxBudget) * 100,
        color: cryptoColors.in_flight,
        leverage: "單幣上限 50%",
      },
      {
        symbol: "SOL",
        label: "SOL 持倉名義額",
        shortLabel: "SOL",
        sub: `已開倉 (${(solNotional / totalEquity).toFixed(2)}x)`,
        nominal_usdt: solNotional,
        pct_share: (solNotional / maxBudget) * 100,
        color: cryptoColors.alt,
        leverage: "單幣上限 50%",
      },
      {
        symbol: "在途",
        label: "在途委託凍結額",
        shortLabel: "在途",
        sub: `掛單中 (${(inFlightNominal / totalEquity).toFixed(2)}x)`,
        nominal_usdt: inFlightNominal,
        pct_share: (inFlightNominal / maxBudget) * 100,
        color: "#a1a1aa",
        leverage: "限價掛單",
      },
      {
        symbol: "可用",
        label: "剩餘可用曝險額度",
        shortLabel: "可用",
        sub: `安全緩衝 (${(availNom / totalEquity).toFixed(2)}x)`,
        nominal_usdt: availNom,
        pct_share: (availNom / maxBudget) * 100,
        color: cryptoColors.available,
        leverage: "安全緩衝",
      },
    ];
  }, [btcNotional, ethNotional, solNotional, totalHoldingsNominal, inFlightNominal, totalEquity]);

  const getBarGradient = (color: string) => {
    if (color === cryptoColors.btc || color === "#e8b45e") return "linear-gradient(90deg, #d97706, #fbbf24)";
    if (color === cryptoColors.in_flight || color === "#7faee2") return "linear-gradient(90deg, #2563eb, #60a5fa)";
    if (color === cryptoColors.alt || color === "#8b8df8") return "linear-gradient(90deg, #6366f1, #a78bfa)";
    if (color === cryptoColors.available || color === "#10b981") return "linear-gradient(90deg, #059669, #34d399)";
    return `linear-gradient(90deg, ${color}cc, ${color})`;
  };

  const W = dimensions.width || 380;
  const H = dimensions.height || 220;
  const activeHoverItem = hoveredIndex !== null ? budgetItems[hoveredIndex] : null;

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40 relative", className)}>
      {/* 1. 卡片頂部一體化 Header (定案固化，零多餘調試按鈕) */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
        <div className="flex items-center gap-2">
          <CardHeaderTitle
            cardId="allocation"
            title="槓桿倍數與資產曝險"
          />
        </div>
      </div>

      {/* 2. 核心繪圖與內容展示區：定案方案 C (TradingView 甜甜圈 + 5 條高密度進度資訊棧 + 4 格風控矩陣) */}
      <div ref={containerRef} className="flex-1 min-h-0 w-full h-full relative overflow-hidden p-2.5">
        <div className="w-full h-full flex flex-col justify-between overflow-hidden font-mono">
          {/* 上半部核心：左側 Donut 圓環 (帶同心 HUD) + 右側雙層風控條列 */}
          <div className="flex-1 min-h-0 flex items-center justify-between gap-2 overflow-hidden pt-0.5">
            {/* 左側 Donut 圓環 (51% 寬度佔比) */}
            <div
              style={{ width: `${DONUT_CONFIG.donutRatio}%` }}
              className="h-full flex items-center justify-center relative shrink-0"
            >
              {(() => {
                const donutColW = Math.max(80, Math.floor(W * (DONUT_CONFIG.donutRatio / 100)));
                const cx = Math.floor(donutColW / 2);
                const contentH = Math.max(100, H - 55);
                const cy = Math.floor(contentH / 2) + DONUT_CONFIG.hudYOffset;

                const strokeWidth = DONUT_CONFIG.strokeWidth;
                // 根據定案 radius 繪製，同時確保不溢出 SVG 容器
                const r = Math.min(
                  cx - Math.ceil(strokeWidth / 2) - 3,
                  cy - Math.ceil(strokeWidth / 2) - 3,
                  DONUT_CONFIG.radius
                );
                const circumference = 2 * Math.PI * r;
                const sliceGap = DONUT_CONFIG.sliceGap;

                let accumulatedArc = 0;

                return (
                  <svg
                    width={donutColW}
                    height={contentH}
                    viewBox={`0 0 ${donutColW} ${contentH}`}
                    className="w-full h-full block select-none overflow-visible"
                  >
                    {/* 底部導軌 */}
                    <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1c2027" strokeWidth={strokeWidth} />

                    {/* 各幣種切片（帶物理微隙 sliceGap 與微光懸浮） */}
                    {budgetItems.map((item, idx) => {
                      const fullArc = (item.pct_share / 100) * circumference;
                      const arcLen = Math.max(0, fullArc - sliceGap);
                      const dasharray = `${arcLen} ${circumference - arcLen}`;
                      const dashoffset = -accumulatedArc - sliceGap / 2;
                      accumulatedArc += fullArc;

                      return (
                        <circle
                          key={item.symbol}
                          cx={cx}
                          cy={cy}
                          r={r}
                          fill="none"
                          stroke={item.color}
                          strokeWidth={hoveredIndex === idx ? strokeWidth + 3.5 : strokeWidth}
                          strokeDasharray={dasharray}
                          strokeDashoffset={dashoffset}
                          className="cursor-pointer transition-all duration-150"
                          style={{
                            transform: "rotate(-90deg)",
                            transformOrigin: `${cx}px ${cy}px`,
                            filter: hoveredIndex === idx ? `drop-shadow(0 0 10px ${item.color}95)` : undefined,
                          }}
                          onMouseEnter={() => setHoveredIndex(idx)}
                          onMouseLeave={() => setHoveredIndex(null)}
                        />
                      );
                    })}

                    {/* 50% 單幣上限安全刻度線 */}
                    {DONUT_CONFIG.limitMarkLength > 0 && (
                      <>
                        <circle cx={cx} cy={cy + r} r="2.5" fill="#f43f5e" />
                        <line
                          x1={cx}
                          y1={cy + r - strokeWidth / 2 - DONUT_CONFIG.limitMarkLength / 2}
                          x2={cx}
                          y2={cy + r + strokeWidth / 2 + DONUT_CONFIG.limitMarkLength / 2}
                          stroke="#f43f5e"
                          strokeWidth="1.5"
                        />
                        <text
                          x={cx}
                          y={cy + r + strokeWidth / 2 + DONUT_CONFIG.limitMarkLength / 2 + 9}
                          textAnchor="middle"
                          fill="#f43f5e"
                          fontSize="7.5"
                          fontWeight="bold"
                        >
                          50% 上限
                        </text>
                      </>
                    )}

                    {/* 中央純淨同心 HUD */}
                    {activeHoverItem ? (
                      <g className="pointer-events-none select-none">
                        <text
                          x={cx}
                          y={cy - Math.floor(DONUT_CONFIG.hudFontSize * 0.7)}
                          textAnchor="middle"
                          fill="#94a3b8"
                          fontSize="8.5"
                          fontFamily="monospace"
                        >
                          {activeHoverItem.shortLabel || activeHoverItem.symbol}
                        </text>
                        <text
                          x={cx}
                          y={cy + Math.floor(DONUT_CONFIG.hudFontSize * 0.25)}
                          textAnchor="middle"
                          fill={activeHoverItem.color}
                          fontSize={DONUT_CONFIG.hudFontSize}
                          fontWeight="bold"
                          fontFamily="monospace"
                        >
                          {activeHoverItem.pct_share.toFixed(1)}%
                        </text>
                        <text
                          x={cx}
                          y={cy + Math.floor(DONUT_CONFIG.hudFontSize * 0.95)}
                          textAnchor="middle"
                          fill="#cbd5e1"
                          fontSize="8"
                          fontFamily="monospace"
                        >
                          ${Math.round(activeHoverItem.nominal_usdt).toLocaleString()}
                        </text>
                      </g>
                    ) : (
                      <g className="pointer-events-none select-none">
                        <text
                          x={cx}
                          y={cy - Math.floor(DONUT_CONFIG.hudFontSize * 0.7)}
                          textAnchor="middle"
                          fill="#94a3b8"
                          fontSize="8"
                          fontFamily="monospace"
                          letterSpacing="0.05em"
                        >
                          有效槓桿
                        </text>
                        <text
                          x={cx}
                          y={cy + Math.floor(DONUT_CONFIG.hudFontSize * 0.25)}
                          textAnchor="middle"
                          fill="#e8b45e"
                          fontSize={DONUT_CONFIG.hudFontSize}
                          fontWeight="bold"
                          fontFamily="monospace"
                          style={{ filter: "drop-shadow(0 0 8px rgba(232, 180, 94, 0.35))" }}
                        >
                          {effectiveLeverage.toFixed(2)}x
                        </text>
                        <text
                          x={cx}
                          y={cy + Math.floor(DONUT_CONFIG.hudFontSize * 0.95)}
                          textAnchor="middle"
                          fill="#10b981"
                          fontSize="8"
                          fontFamily="monospace"
                        >
                          上限 3.0x · {((effectiveLeverage / 3.0) * 100).toFixed(0)}%
                        </text>
                      </g>
                    )}
                  </svg>
                );
              })()}
            </div>

            {/* 右側 5 條高密度進度資訊棧 (49% 寬度佔比) */}
            <div
              style={{ width: `${100 - DONUT_CONFIG.donutRatio}%` }}
              className="h-full flex flex-col justify-around py-0.5 overflow-hidden pl-1"
            >
              {budgetItems.map((item, idx) => {
                const isHovered = hoveredIndex === idx;
                const isAvailable = item.symbol === "可用";
                const isSafe = item.pct_share <= 50;

                return (
                  <div
                    key={item.symbol}
                    onMouseEnter={() => setHoveredIndex(idx)}
                    onMouseLeave={() => setHoveredIndex(null)}
                    className={cn(
                      "group flex flex-col gap-0.5 px-2 py-0.5 rounded transition-colors cursor-pointer",
                      isHovered ? "bg-secondary/70 ring-1 ring-primary/40 shadow-xs" : "hover:bg-white/[0.03]"
                    )}
                  >
                    <div className="flex justify-between items-center text-[9.5px]">
                      <span className="font-semibold text-foreground flex items-center gap-1.5 truncate">
                        <span className="size-1.5 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                        <span className="truncate">{item.shortLabel || item.symbol}</span>
                        <span className="text-[8px] text-muted-foreground/80 font-normal shrink-0">({item.sub})</span>
                      </span>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <span className="text-zinc-400 text-[9px] flex items-center gap-1">
                          <NumberTicker value={item.nominal_usdt} decimals={0} prefix="$" />
                          <span className="font-bold text-foreground">
                            (<NumberTicker value={item.pct_share} decimals={1} suffix="%" />)
                          </span>
                        </span>
                        <span className={cn(
                          "px-1 py-0.2 rounded text-[7.5px] font-bold border shrink-0",
                          isAvailable
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                            : isSafe
                            ? "bg-emerald-400/10 text-emerald-300 border-emerald-400/25"
                            : "bg-rose-400/10 text-rose-300 border-rose-400/30"
                        )}>
                          {isAvailable ? "BUFFER" : isSafe ? "SAFE" : "ALERT"}
                        </span>
                      </div>
                    </div>

                    {/* 雙層進度軌道 (帶 50% 單幣上限安全輔助刻度，3px 高度) */}
                    <div
                      style={{ height: `${DONUT_CONFIG.barHeight}px` }}
                      className="w-full bg-zinc-800/80 rounded-full overflow-hidden relative"
                    >
                      {/* 50% 刻度垂直標記 */}
                      <div className="absolute left-1/2 top-0 bottom-0 w-[1px] bg-rose-400/70 z-10 pointer-events-none" />
                      <div
                        className="h-full rounded-full transition-all duration-300"
                        style={{
                          width: `${Math.min(100, item.pct_share)}%`,
                          background: getBarGradient(item.color),
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 下半部：4 格緊湊風控數據底線矩陣 (零浪費 Zero-Waste) */}
          <div className="pt-1.5 border-t border-border/50 shrink-0">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 text-[8.5px]">
              <div className="flex flex-col p-1.5 rounded bg-secondary/40 border border-border/50">
                <span className="text-muted-foreground text-[8px]">單幣最大曝險</span>
                <span className="text-foreground font-bold text-[10px] mt-0.5">
                  BTC {(btcNotional / (totalEquity * 3.0) * 100).toFixed(1)}%
                </span>
                <span className="text-emerald-400 text-[7.5px]">安全 (≤ 50% 上限)</span>
              </div>

              <div className="flex flex-col p-1.5 rounded bg-secondary/40 border border-border/50">
                <span className="text-muted-foreground text-[8px]">可用曝險額度</span>
                <span className="text-emerald-400 font-bold text-[10px] mt-0.5">
                  ${Math.round(Math.max(0, totalEquity * 3.0 - totalHoldingsNominal - inFlightNominal)).toLocaleString()}
                </span>
                <span className="text-muted-foreground text-[7.5px]">
                  緩衝 {(Math.max(0, (totalEquity * 3.0 - totalHoldingsNominal - inFlightNominal) / (totalEquity * 3.0)) * 100).toFixed(1)}%
                </span>
              </div>

              <div className="flex flex-col p-1.5 rounded bg-secondary/40 border border-border/50">
                <span className="text-muted-foreground text-[8px]">多空淨敞口</span>
                <span className="text-foreground font-bold text-[10px] mt-0.5">
                  +${Math.round(totalHoldingsNominal).toLocaleString()}
                </span>
                <span className="text-emerald-400 text-[7.5px]">100% 多頭偏置</span>
              </div>

              <div className="flex flex-col p-1.5 rounded bg-secondary/40 border border-border/50">
                <span className="text-muted-foreground text-[8px]">風控日損鎖存</span>
                <span className="text-emerald-400 font-bold text-[10px] mt-0.5">
                  NORMAL
                </span>
                <span className="text-muted-foreground text-[7.5px]">未觸發 Latch</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
