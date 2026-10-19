import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import { CardHeaderTitle } from "./card-header-title";
import { cn } from "@/lib/utils";

// 定案配色：低彩度、高質感的幣種資料系列色
const cryptoColors = {
  btc: "#e8b45e",       // BTC 蜂蜜金
  in_flight: "#7faee2", // ETH / 在途凍結 雅緻瓦藍
  available: "#65cba7", // 可用額度 薄荷青
  alt: "#8b8df8",       // SOL 沉穩淡靛
  mm: "#f59e0b",        // 維持保證金 琥珀橘
  im: "#38bdf8",        // 初始保證金 晴空藍
  free: "#34d399",      // 自由保證金 翡翠綠
  long_btc: "#10b981",  // 多頭 BTC 翡翠綠
  long_eth: "#34d399",  // 多頭 ETH 薄荷青
  short_sol: "#f43f5e", // 空頭 SOL 玫瑰紅
};

/**
 * 4 大專業金融視圖維度（順序 1 定案：Top-Down 頂層風控與槓桿容量優先）：
 * 1. budget: 總額度容量（當前持倉占總權益乘以 3.0x 槓桿上限的佔比，回答「我離 3 倍上限還剩多少空間？」）
 * 2. exposure: 多空標尺（0 基準雙向尺規 + Bot 積木塊 + 金色淨指針，回答「多空對沖是否平衡？」）
 * 3. holdings: 幣種持倉（BTC / ETH / SOL 相對持倉佔比與單幣防線）
 * 4. bots: Bot 策略（Tabby / Calico / Shiro 掌管之資產規模與多空角色）
 */
export type AllocationViewMode = "budget" | "exposure" | "holdings" | "bots";

export interface AllocationTuningParams {
  layout: "horizontal" | "vertical"; // 佈局模式：橫向雙欄 vs 縱向上下
  donutRatio: number;                // 圓餅佔比：橫向寬度 %(35~75)，縱向高度 %(35~75)
  radius: number;                    // 圓環外半徑 r_out (38~80px)
  strokeWidth: number;               // 環身厚度 (8~20px)
  showCallout: boolean;              // 是否顯示引線標籤
  lineExt: number;                   // 引線延伸長度 (6~45px)
  labelGap: number;                  // 標籤智慧垂直避讓間距 (14~34px)
  sliceGap: number;                  // 切片物理間隙 (0~8px)
}

export const STORAGE_KEY = "catos_allocation_tuning_v1";

export const DEFAULT_TUNING: AllocationTuningParams = {
  layout: "horizontal",
  donutRatio: 58,    // 58% 圓餅明顯大於長條圖 (42%)
  radius: 54,        // 54px 大氣外半徑
  strokeWidth: 12,   // 12px 環身厚度
  showCallout: true, // 預設顯示標記線
  lineExt: 22,       // 22px 延伸長度 (顯著加長)
  labelGap: 22,      // 22px 智慧避讓排開 (徹底排開鄰近的 ETH、SOL、在途標籤)
  sliceGap: 3.5,     // 3.5px 切片物理間隙 (不同分類清晰隔開)
};

export interface SmartSlice extends DonutItem {
  strokeDasharray: string;
  strokeDashoffset: number;
  hasCallout: boolean;
  callout: {
    x1: number;
    y1: number;
    x2: number;
    y2: number;
    x3: number;
    textX: number;
    isRight: boolean;
  };
}

/**
 * 智慧避讓圓環切片與引線計算演算法：
 * 1. 支援切片間隙 (sliceGap) 物理排開
 * 2. 支援線段延伸長度 (lineExt) 大幅舒展
 * 3. 雙向垂直放鬆避讓 (labelGap)：自動將相鄰密集切片（如 ETH、SOL、在途）的 Y 軸排開至少 labelGap，徹底根絕疊字踩踏
 */
export function computeSmartDonutSlices({
  items,
  cx,
  cy,
  radius,
  strokeWidth,
  lineExt,
  labelGap,
  sliceGap,
  svgH,
  showCallout,
}: {
  items: DonutItem[];
  cx: number;
  cy: number;
  radius: number;
  strokeWidth: number;
  lineExt: number;
  labelGap: number;
  sliceGap: number;
  svgH: number;
  showCallout: boolean;
}): SmartSlice[] {
  const r_mid = Math.max(10, radius - strokeWidth / 2);
  const circumference = 2 * Math.PI * r_mid;
  const hookLen = 7;

  // 1. 基礎圓弧幾何計算（含物理切片間隙 sliceGap）
  let accumulatedArc = 0;
  const baseSlices = items.map((item) => {
    const fullArc = (item.pct_share / 100) * circumference;
    const arcLength = Math.max(0, fullArc - (item.pct_share > 0 ? sliceGap : 0));
    const strokeDasharray = `${arcLength} ${circumference - arcLength}`;
    const strokeDashoffset = -accumulatedArc - sliceGap / 2;

    const startAngle = (accumulatedArc / circumference) * 2 * Math.PI - Math.PI / 2;
    const arcAngle = (fullArc / circumference) * 2 * Math.PI;
    const midAngle = startAngle + arcAngle / 2;
    accumulatedArc += fullArc;

    const cos = Math.cos(midAngle);
    const sin = Math.sin(midAngle);
    const isRight = cos >= 0;

    const x1 = cx + radius * cos;
    const y1 = cy + radius * sin;

    return {
      ...item,
      strokeDasharray,
      strokeDashoffset,
      midAngle,
      cos,
      sin,
      isRight,
      x1,
      y1,
    };
  });

  if (!showCallout) {
    return baseSlices.map((s) => ({
      ...s,
      hasCallout: false,
      callout: { x1: s.x1, y1: s.y1, x2: s.x1, y2: s.y1, x3: s.x1, textX: s.x1, isRight: s.isRight },
    }));
  }

  // 2. 左右兩側分別進行垂直放鬆避讓（智慧排開，消除重疊文字）
  const rightSlices = baseSlices.filter((s) => s.pct_share > 0 && s.isRight);
  const leftSlices = baseSlices.filter((s) => s.pct_share > 0 && !s.isRight);

  const relaxY = (slices: typeof rightSlices) => {
    if (slices.length === 0) return new Map<string, number>();
    const sorted = [...slices].sort((a, b) => a.y1 - b.y1);
    const targetY = sorted.map((s) => s.y1);

    const minY = 14;
    const maxY = Math.max(minY + 20, svgH - 14);

    // 正向推擠：若後者小於前者 + labelGap，向後推開
    for (let i = 1; i < targetY.length; i++) {
      if (targetY[i] < targetY[i - 1] + labelGap) {
        targetY[i] = targetY[i - 1] + labelGap;
      }
    }
    // 逆向回拉：若底部溢出 maxY，整組向上拉回
    if (targetY[targetY.length - 1] > maxY) {
      targetY[targetY.length - 1] = maxY;
      for (let i = targetY.length - 2; i >= 0; i--) {
        if (targetY[i] > targetY[i + 1] - labelGap) {
          targetY[i] = targetY[i + 1] - labelGap;
        }
      }
    }
    // 頂部鉗位：若頂部被推太高低於 minY，向下拉平
    if (targetY[0] < minY) {
      targetY[0] = minY;
      for (let i = 1; i < targetY.length; i++) {
        if (targetY[i] < targetY[i - 1] + labelGap) {
          targetY[i] = targetY[i - 1] + labelGap;
        }
      }
    }

    const resultMap = new Map<string, number>();
    sorted.forEach((s, idx) => {
      resultMap.set(s.symbol, targetY[idx]);
    });
    return resultMap;
  };

  const rightYMap = relaxY(rightSlices);
  const leftYMap = relaxY(leftSlices);

  // 3. 建構三段式微折引線坐標
  return baseSlices.map((s) => {
    if (s.pct_share <= 0) {
      return {
        ...s,
        hasCallout: false,
        callout: { x1: s.x1, y1: s.y1, x2: s.x1, y2: s.y1, x3: s.x1, textX: s.x1, isRight: s.isRight },
      };
    }

    const relaxedY = s.isRight ? (rightYMap.get(s.symbol) ?? s.y1) : (leftYMap.get(s.symbol) ?? s.y1);
    
    // 水平外展：兼顧垂直切片的平滑側展
    const horizExt = Math.max(0.45, Math.abs(s.cos)) * lineExt + 6;
    const x2 = s.isRight ? s.x1 + horizExt : s.x1 - horizExt;
    const y2 = relaxedY;
    const x3 = s.isRight ? x2 + hookLen : x2 - hookLen;
    const textX = s.isRight ? x3 + 3 : x3 - 3;

    return {
      ...s,
      hasCallout: true,
      callout: {
        x1: s.x1,
        y1: s.y1,
        x2,
        y2,
        x3,
        textX,
        isRight: s.isRight,
      },
    };
  });
}

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

// 雙向多空標尺資料結構
interface PositionLeg {
  id: string;
  botId: string;
  botName: string;
  side: "long" | "short";
  notional: number;
}

interface SymbolExposure {
  symbol: string;
  base: string;
  chg: number;
  mark: number;
  legs: PositionLeg[];
  long: number;
  short: number;
  net: number;
}

const DEFAULT_SYMBOLS: SymbolExposure[] = [
  {
    symbol: "BTC-USDT-SWAP",
    base: "BTC",
    chg: 1.42,
    mark: 62140.5,
    legs: [
      { id: "l1", botId: "tabby", botName: "Tabby", side: "long", notional: 7456.86 },
      { id: "l2", botId: "shiro", botName: "Shiro", side: "long", notional: 3107.03 },
    ],
    long: 10563.89,
    short: 0,
    net: 10563.89,
  },
  {
    symbol: "ETH-USDT-SWAP",
    base: "ETH",
    chg: -0.85,
    mark: 2450.2,
    legs: [
      { id: "l3", botId: "calico", botName: "Calico", side: "long", notional: 5880.48 },
      { id: "l4", botId: "shiro", botName: "Shiro", side: "short", notional: 3185.26 },
    ],
    long: 5880.48,
    short: 3185.26,
    net: 2695.22,
  },
  {
    symbol: "SOL-USDT-SWAP",
    base: "SOL",
    chg: 3.1,
    mark: 152.8,
    legs: [
      { id: "l5", botId: "mochi", botName: "Mochi", side: "long", notional: 2750.4 },
    ],
    long: 2750.4,
    short: 0,
    net: 2750.4,
  },
];

const SCALE_PCT = 50;
const TOTAL_EQUITY = 40272.5;

export function AllocationDonutCard({ className }: { className?: string }) {
  // 順序 1：預設為「額度（總曝險容量與槓桿佔比）」
  const [viewMode, setViewMode] = useState<AllocationViewMode>("budget");

  // Hover / Active 切片索引
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  // UI/UX 參數調校狀態（支援 localStorage 持久化記憶）
  const [showTuner, setShowTuner] = useState(false);
  const [tuning, setTuning] = useState<AllocationTuningParams>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) return { ...DEFAULT_TUNING, ...JSON.parse(saved) };
    } catch {
      // ignore
    }
    return DEFAULT_TUNING;
  });

  const updateTuning = useCallback((patch: Partial<AllocationTuningParams>) => {
    setTuning((prev) => {
      const next = { ...prev, ...patch };
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
  }, []);

  const resetTuning = useCallback(() => {
    setTuning(DEFAULT_TUNING);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(DEFAULT_TUNING));
    } catch {
      // ignore
    }
  }, []);

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
  }, [viewMode]);

  // ==================== 4 大核心金融視圖數據（嚴謹數學加總 100%） ====================

  // 視圖 1（預設核心）：總曝險額度容量（100% = 總權益 × 3.0x 槓桿上限 = $37,500）
  const budgetItems: DonutItem[] = useMemo(() => [
    { symbol: "BTC", label: "BTC 持倉名義額", shortLabel: "BTC", sub: "已開倉 (0.84x)", nominal_usdt: 10564.00, pct_share: 28.2, color: cryptoColors.btc, leverage: "單幣上限 50%" },
    { symbol: "ETH", label: "ETH 持倉名義額", shortLabel: "ETH", sub: "已開倉 (0.22x)", nominal_usdt: 2695.00, pct_share: 7.2, color: cryptoColors.in_flight, leverage: "單幣上限 50%" },
    { symbol: "SOL", label: "SOL 持倉名義額", shortLabel: "SOL", sub: "已開倉 (0.22x)", nominal_usdt: 2750.00, pct_share: 7.3, color: cryptoColors.alt, leverage: "單幣上限 50%" },
    { symbol: "在途", label: "在途委託凍結額", shortLabel: "在途", sub: "掛單中 (0.11x)", nominal_usdt: 1430.00, pct_share: 3.8, color: "#a1a1aa", leverage: "限價掛單" },
    { symbol: "可用", label: "剩餘可用曝險額度", shortLabel: "可用", sub: "可開額度 (1.61x)", nominal_usdt: 20061.00, pct_share: 53.5, color: cryptoColors.available, leverage: "安全緩衝" },
  ], []);

  // 視圖 2：標的持倉分佈（手上的部位押在哪些幣上？）
  const holdingsItems: DonutItem[] = useMemo(() => [
    { symbol: "BTC", label: "BTC-USDT", shortLabel: "BTC", sub: "持有中", nominal_usdt: 596.60, pct_share: 73.7, color: cryptoColors.btc, leverage: "3x Cross", pnl: "+$79.26", pnlUp: true },
    { symbol: "ETH", label: "ETH-USDT", shortLabel: "ETH", sub: "持有中", nominal_usdt: 213.08, pct_share: 26.3, color: cryptoColors.in_flight, leverage: "3x Cross", pnl: "+$132.48", pnlUp: true },
    { symbol: "SOL", label: "SOL-USDT", shortLabel: "SOL", sub: "空倉待機", nominal_usdt: 0.00, pct_share: 0.0, color: cryptoColors.alt, leverage: "未持有", pnl: "$0.00", pnlUp: true },
  ], []);

  // 視圖 3：機器人配置視角（Bot 策略分佈）
  const botItems: DonutItem[] = useMemo(() => [
    { symbol: "Tabby", label: "Tabby · BTC 多頭", shortLabel: "Tabby", sub: "突破策略", nominal_usdt: 596.60, pct_share: 56.8, color: "#10b981", leverage: "3x 多頭", pnl: "+$79.26", pnlUp: true },
    { symbol: "Calico", label: "Calico · ETH 多頭", shortLabel: "Calico", sub: "趨勢跟隨", nominal_usdt: 213.08, pct_share: 20.3, color: "#34d399", leverage: "3x 多頭", pnl: "+$132.48", pnlUp: true },
    { symbol: "Shiro", label: "Shiro · SOL 空頭", shortLabel: "Shiro", sub: "費率對沖", nominal_usdt: 240.00, pct_share: 22.9, color: "#f43f5e", leverage: "2x 空頭", pnl: "-$14.20", pnlUp: false },
  ], []);

  const currentItems: DonutItem[] = useMemo(() => {
    switch (viewMode) {
      case "budget": return budgetItems;
      case "holdings": return holdingsItems;
      case "bots": return botItems;
      default: return budgetItems;
    }
  }, [viewMode, budgetItems, holdingsItems, botItems]);

  // 漸變色彩對照輔助函式（賦予長條圖極致現代金融終端光澤）
  const getBarGradient = (color: string) => {
    if (color === cryptoColors.btc || color === "#e8b45e") return "linear-gradient(90deg, #d97706, #fbbf24)";
    if (color === cryptoColors.in_flight || color === "#7faee2") return "linear-gradient(90deg, #2563eb, #60a5fa)";
    if (color === cryptoColors.alt || color === "#8b8df8") return "linear-gradient(90deg, #6366f1, #a78bfa)";
    if (color === cryptoColors.available || color === "#65cba7" || color === cryptoColors.free || color === "#34d399" || color === cryptoColors.long_btc || color === "#10b981") {
      return "linear-gradient(90deg, #059669, #34d399)";
    }
    if (color === cryptoColors.short_sol || color === "#f43f5e") return "linear-gradient(90deg, #e11d48, #fb7185)";
    if (color === cryptoColors.mm || color === "#f59e0b") return "linear-gradient(90deg, #d97706, #f59e0b)";
    if (color === cryptoColors.im || color === "#38bdf8") return "linear-gradient(90deg, #0284c7, #38bdf8)";
    return `linear-gradient(90deg, ${color}dd, ${color})`;
  };

  // ==================== 圓環幾何參數自適應計算 ====================
  const W = dimensions.width || 380;
  const H = dimensions.height || 220;

  // 1. 預算視圖專屬智慧避讓切片計算（支援橫向/縱向切換與即時參數調校）
  const smartBudgetSlices = useMemo(() => {
    const isHoriz = tuning.layout === "horizontal";
    const contentH = Math.max(160, H - 36);
    const svgW = isHoriz ? Math.floor(W * (tuning.donutRatio / 100)) : W;
    const svgH = isHoriz ? contentH : Math.floor(contentH * (tuning.donutRatio / 100));
    const cx = Math.floor(svgW / 2);
    const cy = Math.floor(svgH / 2);

    return computeSmartDonutSlices({
      items: budgetItems,
      cx,
      cy,
      radius: tuning.radius,
      strokeWidth: tuning.strokeWidth,
      lineExt: tuning.lineExt,
      labelGap: tuning.labelGap,
      sliceGap: tuning.sliceGap,
      svgH,
      showCallout: tuning.showCallout,
    });
  }, [tuning, W, H, budgetItems]);

  // 2. 標的與 Bot 視圖之智慧避讓切片計算
  const svgH_std = Math.max(130, Math.floor(H * 0.52));
  const cx_std = Math.floor(W / 2);
  const cy_std = Math.floor(svgH_std / 2);

  const donutSlices = useMemo(() => {
    return computeSmartDonutSlices({
      items: currentItems,
      cx: cx_std,
      cy: cy_std,
      radius: tuning.radius,
      strokeWidth: tuning.strokeWidth,
      lineExt: tuning.lineExt,
      labelGap: tuning.labelGap,
      sliceGap: tuning.sliceGap,
      svgH: svgH_std,
      showCallout: tuning.showCallout,
    });
  }, [currentItems, cx_std, cy_std, tuning, svgH_std]);

  const activeHoverItem = hoveredIndex !== null ? currentItems[hoveredIndex] : null;

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40 relative", className)}>
      {/* 1. 卡片頂部一體化 Header（左側標題 + 右上角 4 大金融視圖切換器 + ⚙️ 即時調校鈕） */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
        <div className="flex items-center gap-2">
          <CardHeaderTitle
            cardId="allocation"
            title="資產曝險配置"
          />
          {/* UI/UX 即時調校橫桿開關 */}
          <button
            type="button"
            onClick={() => setShowTuner((prev) => !prev)}
            title="開啟 UI/UX 即時參數調校橫桿"
            className={cn(
              "px-1.5 py-0.5 text-[9px] font-mono rounded flex items-center gap-1 transition-colors cursor-pointer border",
              showTuner
                ? "bg-amber-500/20 text-amber-300 border-amber-500/50 shadow-xs font-semibold"
                : "bg-secondary/40 text-muted-foreground hover:text-foreground border-border/40"
            )}
          >
            <span>🎛️</span>
            <span>微調參數</span>
          </button>
        </div>

        {/* 右上角切換按鈕（順序 1：額度 ➜ 標尺 ➜ 幣種 ➜ Bot） */}
        <div className="flex items-center bg-background/60 border border-border/60 rounded p-0.5 gap-0.5 shrink-0">
          {[
            { id: "budget" as const, label: "額度", title: "總額度容量：當前持倉占總權益乘以 3.0x 槓桿上限的佔比與可用額度" },
            { id: "exposure" as const, label: "標尺", title: "多空標尺：中央 0 基準尺規、Bot 積木塊與淨曝險金色指針" },
            { id: "holdings" as const, label: "幣種", title: "幣種持倉：各合約標的之相對名義額度配比" },
            { id: "bots" as const, label: "Bot", title: "Bot 策略：各機器人掌管之資產規模與多空角色" },
          ].map((btn) => (
            <button
              key={btn.id}
              type="button"
              onClick={() => { setViewMode(btn.id); setHoveredIndex(null); }}
              title={btn.title}
              className={cn(
                "px-2 py-0.5 text-[10px] font-mono font-medium rounded transition-colors cursor-pointer",
                viewMode === btn.id
                  ? "bg-secondary text-primary border border-border font-semibold shadow-xs"
                  : "text-muted-foreground hover:text-foreground border border-transparent"
              )}
            >
              {btn.label}
            </button>
          ))}
        </div>
      </div>

      {/* 2. UI/UX 即時參數調校抽屜面板（流暢覆蓋，拖曳即時渲染） */}
      {showTuner && (
        <div className="absolute top-[37px] left-2 right-2 z-40 bg-card/95 backdrop-blur-md border border-amber-500/40 rounded-lg p-2.5 shadow-2xl font-mono text-[10px] flex flex-col gap-2">
          <div className="flex items-center justify-between border-b border-border/60 pb-1">
            <span className="font-bold text-amber-300 flex items-center gap-1.5">
              <span>🎛️</span>
              <span>UI / UX 即時參數調校面板</span>
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={resetTuning}
                className="px-2 py-0.5 rounded text-[8.5px] bg-secondary text-muted-foreground hover:text-foreground border border-border cursor-pointer"
              >
                重設預設值
              </button>
              <button
                type="button"
                onClick={() => setShowTuner(false)}
                className="px-1.5 py-0.5 rounded text-[9px] text-muted-foreground hover:text-foreground hover:bg-white/10 cursor-pointer"
              >
                ✕
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
            {/* 佈局模式切換 */}
            <div className="flex flex-col gap-0.5">
              <span className="text-muted-foreground text-[8.5px]">佈局模式</span>
              <div className="grid grid-cols-2 gap-1 bg-background/80 p-0.5 rounded border border-border">
                <button
                  type="button"
                  onClick={() => updateTuning({ layout: "horizontal" })}
                  className={cn(
                    "py-0.5 text-[8.5px] rounded text-center transition-colors cursor-pointer",
                    tuning.layout === "horizontal"
                      ? "bg-amber-500/20 text-amber-300 font-bold border border-amber-500/40"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  橫向 (左大環右條)
                </button>
                <button
                  type="button"
                  onClick={() => updateTuning({ layout: "vertical" })}
                  className={cn(
                    "py-0.5 text-[8.5px] rounded text-center transition-colors cursor-pointer",
                    tuning.layout === "vertical"
                      ? "bg-amber-500/20 text-amber-300 font-bold border border-amber-500/40"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  縱向 (上大環下條)
                </button>
              </div>
            </div>

            {/* 標記線開關 */}
            <div className="flex flex-col gap-0.5">
              <span className="text-muted-foreground text-[8.5px]">標記引線開關</span>
              <div className="grid grid-cols-2 gap-1 bg-background/80 p-0.5 rounded border border-border">
                <button
                  type="button"
                  onClick={() => updateTuning({ showCallout: true })}
                  className={cn(
                    "py-0.5 text-[8.5px] rounded text-center transition-colors cursor-pointer",
                    tuning.showCallout
                      ? "bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/40"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  顯示標記線
                </button>
                <button
                  type="button"
                  onClick={() => updateTuning({ showCallout: false })}
                  className={cn(
                    "py-0.5 text-[8.5px] rounded text-center transition-colors cursor-pointer",
                    !tuning.showCallout
                      ? "bg-zinc-700/50 text-foreground font-bold border border-border"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  純淨無引線
                </button>
              </div>
            </div>

            {/* 圓餅佔比比例 */}
            <div className="flex flex-col gap-0.5">
              <div className="flex justify-between text-[8.5px]">
                <span className="text-muted-foreground">圓餅主體佔比 (比長條圖大)</span>
                <span className="text-amber-300 font-bold">{tuning.donutRatio}%</span>
              </div>
              <input
                type="range"
                min={35}
                max={75}
                step={1}
                value={tuning.donutRatio}
                onChange={(e) => updateTuning({ donutRatio: Number(e.target.value) })}
                className="w-full accent-amber-400 cursor-pointer h-1.5 bg-zinc-800 rounded-lg appearance-none"
              />
            </div>

            {/* 圓環外半徑 */}
            <div className="flex flex-col gap-0.5">
              <div className="flex justify-between text-[8.5px]">
                <span className="text-muted-foreground">圓環外半徑 (半徑尺寸)</span>
                <span className="text-amber-300 font-bold">{tuning.radius}px</span>
              </div>
              <input
                type="range"
                min={38}
                max={75}
                step={1}
                value={tuning.radius}
                onChange={(e) => updateTuning({ radius: Number(e.target.value) })}
                className="w-full accent-amber-400 cursor-pointer h-1.5 bg-zinc-800 rounded-lg appearance-none"
              />
            </div>

            {/* 引線延伸長度 */}
            <div className="flex flex-col gap-0.5">
              <div className="flex justify-between text-[8.5px]">
                <span className="text-muted-foreground">線段延伸長度 (向外舒展)</span>
                <span className="text-amber-300 font-bold">{tuning.lineExt}px</span>
              </div>
              <input
                type="range"
                min={6}
                max={42}
                step={1}
                value={tuning.lineExt}
                onChange={(e) => updateTuning({ lineExt: Number(e.target.value) })}
                className="w-full accent-amber-400 cursor-pointer h-1.5 bg-zinc-800 rounded-lg appearance-none"
              />
            </div>

            {/* 標籤防擠間距 */}
            <div className="flex flex-col gap-0.5">
              <div className="flex justify-between text-[8.5px]">
                <span className="text-muted-foreground">標籤防擠排開間距 (避讓排開)</span>
                <span className="text-amber-300 font-bold">{tuning.labelGap}px</span>
              </div>
              <input
                type="range"
                min={14}
                max={32}
                step={1}
                value={tuning.labelGap}
                onChange={(e) => updateTuning({ labelGap: Number(e.target.value) })}
                className="w-full accent-amber-400 cursor-pointer h-1.5 bg-zinc-800 rounded-lg appearance-none"
              />
            </div>

            {/* 切片物理間隔 */}
            <div className="flex flex-col gap-0.5 col-span-2">
              <div className="flex justify-between text-[8.5px]">
                <span className="text-muted-foreground">不同分類切片間隔 (排開分類縫隙)</span>
                <span className="text-amber-300 font-bold">{tuning.sliceGap}px</span>
              </div>
              <input
                type="range"
                min={0}
                max={8}
                step={0.5}
                value={tuning.sliceGap}
                onChange={(e) => updateTuning({ sliceGap: Number(e.target.value) })}
                className="w-full accent-amber-400 cursor-pointer h-1.5 bg-zinc-800 rounded-lg appearance-none"
              />
            </div>
          </div>

          {/* 複製與定案提示 */}
          <div className="pt-1 border-t border-border/60 flex items-center justify-between text-[8px] text-muted-foreground">
            <span className="truncate pr-2">
              當前參數：<code>{`{ layout: "${tuning.layout}", donut: ${tuning.donutRatio}%, r: ${tuning.radius}px, line: ${tuning.lineExt}px, labelGap: ${tuning.labelGap}px, sliceGap: ${tuning.sliceGap}px }`}</code>
            </span>
            <button
              type="button"
              onClick={() => {
                navigator.clipboard?.writeText(JSON.stringify(tuning));
                alert("已複製當前調校參數！");
              }}
              className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 font-semibold shrink-0 cursor-pointer"
            >
              複製參數
            </button>
          </div>
        </div>
      )}

      {/* 3. 核心繪圖與內容展示區 */}
      <div ref={containerRef} className="flex-1 min-h-0 w-full h-full relative overflow-hidden p-2">
        {/* ==================== 視圖 1：額度容量（支援橫向大餅/縱向與即時參數調校） ==================== */}
        {viewMode === "budget" && (
          <div className="w-full h-full flex flex-col justify-between overflow-hidden">
            {tuning.layout === "horizontal" ? (
              // 橫向模式：左大環 (佔比可調，預設 58% 大於長條圖)，右長條列表 (42%)
              <div className="flex-1 min-h-0 flex items-center justify-between gap-2 overflow-hidden">
                {/* 左側 Donut 圓環與智慧引線 */}
                <div
                  style={{ width: `${tuning.donutRatio}%` }}
                  className="h-full flex items-center justify-center relative shrink-0 overflow-visible"
                >
                  {(() => {
                    const contentH = Math.max(160, H - 36);
                    const leftW = Math.floor(W * (tuning.donutRatio / 100));
                    const cx = Math.floor(leftW / 2);
                    const cy = Math.floor(contentH / 2);
                    const r_mid = Math.max(10, tuning.radius - tuning.strokeWidth / 2);

                    return (
                      <svg
                        width={leftW}
                        height={contentH}
                        viewBox={`0 0 ${leftW} ${contentH}`}
                        className="w-full h-full block select-none overflow-visible"
                      >
                        {/* 底部導軌 */}
                        <circle cx={cx} cy={cy} r={r_mid} fill="none" stroke="#1c2027" strokeWidth={tuning.strokeWidth} />

                        {/* 各幣種切片（支援切片物理間距 sliceGap 排開） */}
                        {smartBudgetSlices.map((slice, idx) => (
                          <circle
                            key={slice.symbol}
                            cx={cx}
                            cy={cy}
                            r={r_mid}
                            fill="none"
                            stroke={slice.color}
                            strokeWidth={hoveredIndex === idx ? tuning.strokeWidth + 3 : tuning.strokeWidth}
                            strokeDasharray={slice.strokeDasharray}
                            strokeDashoffset={slice.strokeDashoffset}
                            className="cursor-pointer transition-all duration-150"
                            style={{
                              transform: "rotate(-90deg)",
                              transformOrigin: `${cx}px ${cy}px`,
                              filter: hoveredIndex === idx ? `drop-shadow(0 0 8px ${slice.color}90)` : undefined,
                            }}
                            onMouseEnter={() => setHoveredIndex(idx)}
                            onMouseLeave={() => setHoveredIndex(null)}
                          />
                        ))}

                        {/* 智慧避讓標記引線與數值標籤（線段延伸長度 lineExt 可調、標籤垂直防疊字排開 labelGap 可調） */}
                        {tuning.showCallout &&
                          smartBudgetSlices.map((slice) => {
                            if (!slice.hasCallout) return null;
                            const c = slice.callout;
                            const isHov = hoveredIndex !== null && smartBudgetSlices[hoveredIndex]?.symbol === slice.symbol;
                            return (
                              <g
                                key={`callout-${slice.symbol}`}
                                className="pointer-events-none transition-opacity duration-150"
                              >
                                <polyline
                                  points={`${c.x1},${c.y1} ${c.x2},${c.y2} ${c.x3},${c.y2}`}
                                  fill="none"
                                  stroke={slice.color}
                                  strokeWidth="1.25"
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  className={isHov ? "opacity-100 stroke-[1.6]" : "opacity-85"}
                                />
                                <circle cx={c.x3} cy={c.y2} r="1.5" fill={slice.color} />
                                <text
                                  x={c.textX}
                                  y={c.y2 - 2}
                                  textAnchor={c.isRight ? "start" : "end"}
                                  className="font-mono font-bold select-none"
                                  fill="#ffffff"
                                  fontSize="9"
                                >
                                  {slice.shortLabel || slice.symbol} {slice.pct_share.toFixed(1)}%
                                </text>
                                <text
                                  x={c.textX}
                                  y={c.y2 + 9}
                                  textAnchor={c.isRight ? "start" : "end"}
                                  className="font-mono select-none"
                                  fill="#94a3b8"
                                  fontSize="8"
                                >
                                  ${slice.nominal_usdt.toLocaleString()}
                                </text>
                              </g>
                            );
                          })}

                        {/* 中央同心 HUD */}
                        {activeHoverItem ? (
                          <g className="pointer-events-none select-none">
                            <text x={cx} y={cy - 12} textAnchor="middle" fill="#94a3b8" fontSize="8.5" fontFamily="monospace">
                              {activeHoverItem.shortLabel || activeHoverItem.symbol}
                            </text>
                            <text x={cx} y={cy + 4} textAnchor="middle" fill={activeHoverItem.color} fontSize="14.5" fontWeight="bold" fontFamily="monospace">
                              {activeHoverItem.pct_share.toFixed(1)}%
                            </text>
                            <text x={cx} y={cy + 17} textAnchor="middle" fill="#cbd5e1" fontSize="8.5" fontFamily="monospace">
                              ${activeHoverItem.nominal_usdt.toLocaleString()}
                            </text>
                          </g>
                        ) : (
                          <g className="pointer-events-none select-none">
                            <text x={cx} y={cy - 13} textAnchor="middle" fill="#94a3b8" fontSize="8" fontFamily="monospace">
                              有效槓桿 / 上限
                            </text>
                            <text x={cx} y={cy + 3} textAnchor="middle" fill="#e8b45e" fontSize="13.5" fontWeight="bold" fontFamily="monospace">
                              0.43x / 3.0x
                            </text>
                            <text x={cx} y={cy + 16} textAnchor="middle" fill="#94a3b8" fontSize="8" fontFamily="monospace">
                              已用 14.3%
                            </text>
                          </g>
                        )}
                      </svg>
                    );
                  })()}
                </div>

                {/* 右側 5 條水平進度長條 */}
                <div
                  style={{ width: `${100 - tuning.donutRatio}%` }}
                  className="min-w-0 h-full flex flex-col justify-around py-0.5 overflow-hidden pl-1"
                >
                  {budgetItems.map((item, idx) => (
                    <div
                      key={item.symbol}
                      onMouseEnter={() => setHoveredIndex(idx)}
                      onMouseLeave={() => setHoveredIndex(null)}
                      className={cn(
                        "group flex flex-col gap-0.5 px-2 py-0.5 rounded transition-colors cursor-pointer font-mono",
                        hoveredIndex === idx ? "bg-secondary/70 ring-1 ring-primary/40 shadow-xs" : "hover:bg-white/[0.03]"
                      )}
                    >
                      <div className="flex justify-between items-center text-[9px]">
                        <span className="font-semibold text-foreground flex items-center gap-1.5 truncate">
                          <span className="size-1.5 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                          <span className="truncate">{item.shortLabel || item.symbol}</span>
                          <span className="text-[7.5px] text-muted-foreground/80 font-normal shrink-0">({item.sub})</span>
                        </span>
                        <span className="text-zinc-400 text-[8.5px] shrink-0">
                          ${item.nominal_usdt.toLocaleString()}{" "}
                          <span className="font-bold text-foreground">({item.pct_share.toFixed(1)}%)</span>
                        </span>
                      </div>
                      <div className="w-full bg-zinc-800/70 h-1.5 rounded-full overflow-hidden relative">
                        <div
                          className="h-full rounded-full transition-all duration-300"
                          style={{
                            width: `${Math.min(100, item.pct_share)}%`,
                            background: getBarGradient(item.color),
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              // 縱向模式：上大環 (佔比可調，預設 58%)，下長條列表 (42%)
              <div className="flex-1 min-h-0 flex flex-col justify-between overflow-hidden">
                <div
                  style={{ height: `${tuning.donutRatio}%` }}
                  className="w-full flex items-center justify-center relative shrink-0 overflow-visible"
                >
                  {(() => {
                    const contentH = Math.max(160, H - 36);
                    const topH = Math.floor(contentH * (tuning.donutRatio / 100));
                    const cx = Math.floor(W / 2);
                    const cy = Math.floor(topH / 2);
                    const r_mid = Math.max(10, tuning.radius - tuning.strokeWidth / 2);

                    return (
                      <svg
                        width={W}
                        height={topH}
                        viewBox={`0 0 ${W} ${topH}`}
                        className="w-full h-full block select-none overflow-visible"
                      >
                        <circle cx={cx} cy={cy} r={r_mid} fill="none" stroke="#1c2027" strokeWidth={tuning.strokeWidth} />
                        {smartBudgetSlices.map((slice, idx) => (
                          <circle
                            key={slice.symbol}
                            cx={cx}
                            cy={cy}
                            r={r_mid}
                            fill="none"
                            stroke={slice.color}
                            strokeWidth={hoveredIndex === idx ? tuning.strokeWidth + 3 : tuning.strokeWidth}
                            strokeDasharray={slice.strokeDasharray}
                            strokeDashoffset={slice.strokeDashoffset}
                            className="cursor-pointer transition-all duration-150"
                            style={{
                              transform: "rotate(-90deg)",
                              transformOrigin: `${cx}px ${cy}px`,
                              filter: hoveredIndex === idx ? `drop-shadow(0 0 8px ${slice.color}90)` : undefined,
                            }}
                            onMouseEnter={() => setHoveredIndex(idx)}
                            onMouseLeave={() => setHoveredIndex(null)}
                          />
                        ))}

                        {tuning.showCallout &&
                          smartBudgetSlices.map((slice) => {
                            if (!slice.hasCallout) return null;
                            const c = slice.callout;
                            const isHov = hoveredIndex !== null && smartBudgetSlices[hoveredIndex]?.symbol === slice.symbol;
                            return (
                              <g
                                key={`callout-${slice.symbol}`}
                                className="pointer-events-none transition-opacity duration-150"
                              >
                                <polyline
                                  points={`${c.x1},${c.y1} ${c.x2},${c.y2} ${c.x3},${c.y2}`}
                                  fill="none"
                                  stroke={slice.color}
                                  strokeWidth="1.25"
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  className={isHov ? "opacity-100 stroke-[1.6]" : "opacity-85"}
                                />
                                <circle cx={c.x3} cy={c.y2} r="1.5" fill={slice.color} />
                                <text
                                  x={c.textX}
                                  y={c.y2 - 2}
                                  textAnchor={c.isRight ? "start" : "end"}
                                  className="font-mono font-bold select-none"
                                  fill="#ffffff"
                                  fontSize="9.5"
                                >
                                  {slice.shortLabel || slice.symbol} {slice.pct_share.toFixed(1)}%
                                </text>
                                <text
                                  x={c.textX}
                                  y={c.y2 + 9}
                                  textAnchor={c.isRight ? "start" : "end"}
                                  className="font-mono select-none"
                                  fill="#94a3b8"
                                  fontSize="8.5"
                                >
                                  ${slice.nominal_usdt.toLocaleString()}
                                </text>
                              </g>
                            );
                          })}

                        {activeHoverItem ? (
                          <g className="pointer-events-none select-none">
                            <text x={cx} y={cy - 12} textAnchor="middle" fill="#94a3b8" fontSize="8.5" fontFamily="monospace">
                              {activeHoverItem.shortLabel || activeHoverItem.symbol}
                            </text>
                            <text x={cx} y={cy + 4} textAnchor="middle" fill={activeHoverItem.color} fontSize="15" fontWeight="bold" fontFamily="monospace">
                              {activeHoverItem.pct_share.toFixed(1)}%
                            </text>
                            <text x={cx} y={cy + 17} textAnchor="middle" fill="#cbd5e1" fontSize="8.5" fontFamily="monospace">
                              ${activeHoverItem.nominal_usdt.toLocaleString()}
                            </text>
                          </g>
                        ) : (
                          <g className="pointer-events-none select-none">
                            <text x={cx} y={cy - 13} textAnchor="middle" fill="#94a3b8" fontSize="8" fontFamily="monospace">
                              有效槓桿 / 上限
                            </text>
                            <text x={cx} y={cy + 3} textAnchor="middle" fill="#e8b45e" fontSize="13.5" fontWeight="bold" fontFamily="monospace">
                              0.43x / 3.0x
                            </text>
                            <text x={cx} y={cy + 16} textAnchor="middle" fill="#94a3b8" fontSize="8" fontFamily="monospace">
                              已用 14.3%
                            </text>
                          </g>
                        )}
                      </svg>
                    );
                  })()}
                </div>

                <div
                  style={{ height: `${100 - tuning.donutRatio}%` }}
                  className="flex-1 min-h-0 flex flex-col justify-around py-0.5 border-t border-border/40 overflow-hidden"
                >
                  {budgetItems.map((item, idx) => (
                    <div
                      key={item.symbol}
                      onMouseEnter={() => setHoveredIndex(idx)}
                      onMouseLeave={() => setHoveredIndex(null)}
                      className={cn(
                        "group flex flex-col gap-0.5 px-2 py-0.5 rounded transition-colors cursor-pointer font-mono",
                        hoveredIndex === idx ? "bg-secondary/70 ring-1 ring-primary/40 shadow-xs" : "hover:bg-white/[0.03]"
                      )}
                    >
                      <div className="flex justify-between items-center text-[9px]">
                        <span className="font-semibold text-foreground flex items-center gap-1.5">
                          <span className="size-1.5 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                          <span>{item.shortLabel || item.symbol}</span>
                          <span className="text-[7.5px] text-muted-foreground/80 font-normal">({item.sub})</span>
                        </span>
                        <span className="text-zinc-400 text-[8.5px]">
                          ${item.nominal_usdt.toLocaleString()}{" "}
                          <span className="font-bold text-foreground">({item.pct_share.toFixed(1)}%)</span>
                        </span>
                      </div>
                      <div className="w-full bg-zinc-800/70 h-1.5 rounded-full overflow-hidden relative">
                        <div
                          className="h-full rounded-full transition-all duration-300"
                          style={{
                            width: `${Math.min(100, item.pct_share)}%`,
                            background: getBarGradient(item.color),
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 底部微卡 */}
            <div className="grid grid-cols-2 gap-1.5 font-mono text-[8.5px] pt-1.5 border-t border-border/40 shrink-0">
              <div className="flex items-center justify-between px-2.5 py-1 rounded bg-secondary/40 border border-border/40">
                <span className="text-muted-foreground">保證金佔用率</span>
                <div className="flex items-center gap-1.5 font-bold">
                  <span className="text-foreground">14.2%</span>
                  <span className="text-up bg-up/10 px-1 py-0.2 rounded text-[7.5px] font-bold">SAFE</span>
                </div>
              </div>
              <div className="flex items-center justify-between px-2.5 py-1 rounded bg-secondary/40 border border-border/40">
                <span className="text-muted-foreground">總預算上限 (3x)</span>
                <span className="text-foreground font-bold">$37,500.00</span>
              </div>
            </div>
          </div>
        )}

        {/* ==================== 視圖 2 & 3：幣種持倉 / Bot 策略（標準上環下條，項目少空間充裕） ==================== */}
        {(viewMode === "holdings" || viewMode === "bots") && (
          <div className="w-full h-full flex flex-col justify-between overflow-hidden">
            {/* 上半部：Donut 環圖 + 微折引線標籤 + SVG 同心 HUD */}
            <div className="flex-1 min-h-0 w-full relative overflow-hidden flex items-center justify-center">
              <svg width={W} height={svgH_std} viewBox={`0 0 ${W} ${svgH_std}`} className="w-full h-full block select-none">
                <circle cx={cx_std} cy={cy_std} r={tuning.radius - tuning.strokeWidth / 2} fill="none" stroke="#1c2027" strokeWidth={tuning.strokeWidth} />

                {donutSlices.map((slice, idx) => {
                  if (slice.pct_share <= 0) return null;
                  const isHov = hoveredIndex === idx;
                  return (
                    <circle
                      key={slice.symbol}
                      cx={cx_std}
                      cy={cy_std}
                      r={tuning.radius - tuning.strokeWidth / 2}
                      fill="none"
                      stroke={slice.color}
                      strokeWidth={isHov ? tuning.strokeWidth + 3 : tuning.strokeWidth}
                      strokeDasharray={slice.strokeDasharray}
                      strokeDashoffset={slice.strokeDashoffset}
                      className="cursor-pointer transition-all duration-150"
                      style={{
                        transform: "rotate(-90deg)",
                        transformOrigin: `${cx_std}px ${cy_std}px`,
                        filter: isHov ? `drop-shadow(0 0 8px ${slice.color}90)` : undefined,
                      }}
                      onMouseEnter={() => setHoveredIndex(idx)}
                      onMouseLeave={() => setHoveredIndex(null)}
                    />
                  );
                })}

                {/* 微折短鉤引線與外部標籤 */}
                {tuning.showCallout &&
                  donutSlices.map((slice, idx) => {
                    if (!slice.hasCallout) return null;
                    const c = slice.callout;
                    const isHov = hoveredIndex === idx;
                    return (
                      <g key={`callout-${slice.symbol}`} className="pointer-events-none transition-opacity duration-150">
                        <polyline
                          points={`${c.x1},${c.y1} ${c.x2},${c.y2} ${c.x3},${c.y2}`}
                          fill="none"
                          stroke={slice.color}
                          strokeWidth="1.25"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          className={isHov ? "opacity-100 stroke-[1.6]" : "opacity-85"}
                        />
                        <circle cx={c.x3} cy={c.y2} r="1.5" fill={slice.color} />
                        <text
                          x={c.textX}
                          y={c.y2 - 3}
                          textAnchor={c.isRight ? "start" : "end"}
                          className="font-mono font-bold select-none"
                          fill="#ffffff"
                          fontSize={Math.max(9, Math.min(10.5, W * 0.028))}
                        >
                          {slice.shortLabel || slice.symbol} {slice.pct_share.toFixed(1)}%
                        </text>
                        <text
                          x={c.textX}
                          y={c.y2 + 9}
                          textAnchor={c.isRight ? "start" : "end"}
                          className="font-mono select-none"
                          fill="#94a3b8"
                          fontSize={Math.max(8, Math.min(9, W * 0.023))}
                        >
                          ${slice.nominal_usdt.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
                        </text>
                      </g>
                    );
                  })}

                {/* 中央智慧 HUD */}
                {activeHoverItem ? (
                  <g className="pointer-events-none select-none">
                    <text x={cx_std} y={cy_std - 12} textAnchor="middle" fill="#94a3b8" fontSize="9" fontFamily="monospace" letterSpacing="0.05em">
                      {activeHoverItem.shortLabel || activeHoverItem.symbol}
                    </text>
                    <text x={cx_std} y={cy_std + 4} textAnchor="middle" fill={activeHoverItem.color} fontSize="16" fontWeight="bold" fontFamily="monospace">
                      {activeHoverItem.pct_share.toFixed(1)}%
                    </text>
                    <text x={cx_std} y={cy_std + 18} textAnchor="middle" fill="#cbd5e1" fontSize="9" fontFamily="monospace">
                      ${activeHoverItem.nominal_usdt.toFixed(1)}
                    </text>
                  </g>
                ) : (
                  <g className="pointer-events-none select-none">
                    <text x={cx_std} y={cy_std - 12} textAnchor="middle" fill="#94a3b8" fontSize="8.5" fontFamily="monospace" letterSpacing="0.08em">
                      {viewMode === "holdings" && "持倉總額"}
                      {viewMode === "bots" && "活躍機器人"}
                    </text>
                    <text x={cx_std} y={cy_std + 4} textAnchor="middle" fill={viewMode === "bots" ? "#10b981" : "#e8b45e"} fontSize="15.5" fontWeight="bold" fontFamily="monospace">
                      {viewMode === "holdings" && "$809.7"}
                      {viewMode === "bots" && "3 隻運作"}
                    </text>
                    <text x={cx_std} y={cy_std + 18} textAnchor="middle" fill="#94a3b8" fontSize="8.5" fontFamily="monospace">
                      {viewMode === "holdings" && "多頭 3x"}
                      {viewMode === "bots" && "多空比 3.4x"}
                    </text>
                  </g>
                )}
              </svg>
            </div>

            {/* 下半部：多條長條進度圖列表 */}
            <div className="flex-1 min-h-0 flex flex-col justify-between pt-1.5 border-t border-border/50 gap-1.5 overflow-hidden">
              <div className="flex-1 min-h-0 flex flex-col justify-around gap-1 overflow-y-auto pr-0.5">
                {currentItems.map((item, idx) => (
                  <div
                    key={item.symbol}
                    onMouseEnter={() => setHoveredIndex(idx)}
                    onMouseLeave={() => setHoveredIndex(null)}
                    className={cn(
                      "group flex flex-col gap-1 px-2 py-1 rounded transition-colors cursor-pointer font-mono",
                      hoveredIndex === idx
                        ? "bg-secondary/70 ring-1 ring-primary/40 shadow-xs"
                        : "hover:bg-white/[0.03]"
                    )}
                  >
                    <div className="flex justify-between items-center text-[10px]">
                      <span className="font-semibold text-foreground flex items-center gap-1.5">
                        <span
                          className="size-1.5 rounded-full shrink-0"
                          style={{
                            backgroundColor: item.color,
                            boxShadow: `0 0 6px ${item.color}80`,
                          }}
                        />
                        <span>{item.shortLabel || item.symbol}</span>
                        <span className="text-[8.5px] text-muted-foreground/80 font-normal">({item.sub})</span>
                      </span>
                      <span className="text-zinc-400 text-[9.5px]">
                        ${item.nominal_usdt.toFixed(1)}{" "}
                        <span className="font-bold text-foreground">({item.pct_share.toFixed(1)}%)</span>
                      </span>
                    </div>

                    <div className="w-full bg-zinc-800/70 h-2 rounded-full overflow-hidden relative">
                      <div
                        className="h-full rounded-full transition-all duration-300"
                        style={{
                          width: `${Math.min(100, item.pct_share)}%`,
                          background: getBarGradient(item.color),
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              {/* 結構化風控指標微卡片 */}
              <div className="grid grid-cols-2 gap-1.5 font-mono text-[8.5px] pt-1.5 border-t border-border/40 shrink-0">
                {viewMode === "holdings" && (
                  <>
                    <div className="flex items-center justify-between px-2.5 py-1 rounded bg-secondary/40 border border-border/40">
                      <span className="text-muted-foreground">單幣預算防線</span>
                      <div className="flex items-center gap-1 font-bold">
                        <span className="text-foreground">BTC 28%/50%</span>
                        <span className="text-up bg-up/10 px-1 py-0.2 rounded text-[7.5px]">SAFE</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between px-2.5 py-1 rounded bg-secondary/40 border border-border/40">
                      <span className="text-muted-foreground">多空淨敞口</span>
                      <span className="text-foreground font-semibold">+$810 <span className="text-up font-bold">(多74%)</span></span>
                    </div>
                  </>
                )}

                {viewMode === "bots" && (
                  <>
                    <div className="flex items-center justify-between px-2.5 py-1 rounded bg-secondary/40 border border-border/40">
                      <span className="text-muted-foreground">多頭主力 Bot</span>
                      <div className="flex items-center gap-1 font-bold">
                        <span className="text-foreground">Tabby + Calico</span>
                        <span className="text-emerald-400 bg-emerald-400/10 px-1 py-0.2 rounded text-[7.5px]">$809.7</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between px-2.5 py-1 rounded bg-secondary/40 border border-border/40">
                      <span className="text-muted-foreground">避險對沖 Bot</span>
                      <span className="text-foreground font-semibold">Shiro <span className="text-rose-400 font-bold">-$240 (23%)</span></span>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ==================== 方案 4：多空雙向標尺（0 基準雙向尺規 + Bot 積木塊 + 金色指針） ==================== */}
        {viewMode === "exposure" && (
          <div className="w-full h-full flex flex-col justify-between overflow-hidden p-1 font-mono">
            {/* 標尺表頭刻度（優化居中 0 基準防擠壓碰撞） */}
            <div className="flex items-center text-[9px] text-muted-foreground/80 pb-1 border-b border-border/50 shrink-0">
              <span className="w-16 shrink-0 font-medium">標的 / 漲跌</span>
              <div className="flex-1 relative flex items-center justify-between px-1 text-[8px]">
                <span className="text-rose-400 shrink-0">← 空頭</span>
                <span className="absolute left-1/2 -translate-x-1/2 text-muted-foreground whitespace-nowrap">0 基準 (±50%)</span>
                <span className="text-emerald-400 shrink-0">多頭 →</span>
              </div>
              <span className="w-20 shrink-0 text-right font-medium">淨額 · 佔比</span>
            </div>

            {/* 標的雙向標尺列表 */}
            <div className="flex-1 flex flex-col justify-around py-1 gap-1.5 min-h-0">
              {DEFAULT_SYMBOLS.map((s) => {
                const netPct = (s.net / TOTAL_EQUITY) * 100;
                return (
                  <div key={s.symbol} className="flex items-center gap-2">
                    {/* 1. 標的代號與 24h 漲跌 */}
                    <div className="w-16 shrink-0 flex flex-col">
                      <span className="text-[10.5px] font-bold text-foreground leading-tight">
                        {s.base}
                      </span>
                      <span
                        className={cn(
                          "text-[9px] leading-tight",
                          s.chg >= 0 ? "text-emerald-400" : "text-rose-400"
                        )}
                      >
                        {s.chg >= 0 ? "+" : ""}{s.chg.toFixed(2)}%
                      </span>
                    </div>

                    {/* 2. 雙向長條尺規 */}
                    <div className="flex-1 h-5.5 bg-background/80 rounded border border-border/60 relative flex overflow-hidden">
                      {/* 空頭區 (向左) */}
                      <div className="w-1/2 h-full flex justify-end overflow-hidden pr-[1px]">
                        {s.legs
                          .filter((l) => l.side === "short")
                          .map((leg) => {
                            const p = (leg.notional / TOTAL_EQUITY) * 100;
                            const clamped = Math.min(p, SCALE_PCT);
                            const widthPct = `${((clamped / SCALE_PCT) * 100).toFixed(1)}%`;
                            return (
                              <div
                                key={leg.id}
                                style={{ width: widthPct }}
                                className="h-full bg-rose-500/35 border-r border-rose-400/60 flex items-center justify-end px-1 transition-all cursor-pointer"
                                title={`${leg.botName} · 空頭 ${Math.round(leg.notional).toLocaleString()} USDT`}
                              >
                                <span className="text-[8px] text-rose-200/90 truncate">
                                  {leg.botName}
                                </span>
                              </div>
                            );
                          })}
                      </div>

                      {/* 多頭區 (向右) */}
                      <div className="w-1/2 h-full flex justify-start overflow-hidden pl-[1px]">
                        {s.legs
                          .filter((l) => l.side === "long")
                          .map((leg) => {
                            const p = (leg.notional / TOTAL_EQUITY) * 100;
                            const clamped = Math.min(p, SCALE_PCT);
                            const widthPct = `${((clamped / SCALE_PCT) * 100).toFixed(1)}%`;
                            return (
                              <div
                                key={leg.id}
                                style={{ width: widthPct }}
                                className="h-full bg-emerald-500/35 border-l border-emerald-400/60 flex items-center justify-start px-1 transition-all cursor-pointer"
                                title={`${leg.botName} · 多頭 ${Math.round(leg.notional).toLocaleString()} USDT`}
                              >
                                <span className="text-[8px] text-emerald-200/90 truncate">
                                  {leg.botName}
                                </span>
                              </div>
                            );
                          })}
                      </div>

                      {/* 中央 0 基準線 */}
                      <div className="absolute left-1/2 top-0 bottom-0 w-[1px] bg-border/90 z-10 pointer-events-none" />

                      {/* 淨曝險三角指針 */}
                      {s.legs.length > 0 && (
                        <div
                          style={{
                            left: `${(50 + (Math.max(-SCALE_PCT, Math.min(SCALE_PCT, netPct)) / SCALE_PCT) * 50).toFixed(1)}%`,
                          }}
                          className="absolute top-0 -translate-x-1/2 z-20 pointer-events-none"
                        >
                          <div className="w-0 h-0 border-l-[3px] border-l-transparent border-r-[3px] border-r-transparent border-t-[4.5px] border-t-amber-400" />
                        </div>
                      )}
                    </div>

                    {/* 3. 淨額與佔比 */}
                    <div className="w-20 shrink-0 flex flex-col items-end">
                      <span className={cn("text-[10px] font-bold leading-tight", s.net >= 0 ? "text-emerald-400" : "text-rose-400")}>
                        {s.net >= 0 ? "+" : ""}{Math.round(s.net).toLocaleString()}
                      </span>
                      <span className="text-[8px] text-muted-foreground leading-tight">
                        {netPct >= 0 ? "+" : ""}{netPct.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* 底部風控微卡列（原汁原味） */}
            <div className="grid grid-cols-4 gap-1 pt-1.5 border-t border-border/50 text-[8px] shrink-0">
              <div className="flex flex-col px-1.5 py-0.5 rounded bg-secondary/40 border border-border/40">
                <span className="text-muted-foreground">多頭總額</span>
                <span className="text-emerald-400 font-bold text-[9px]">$19,195</span>
              </div>
              <div className="flex flex-col px-1.5 py-0.5 rounded bg-secondary/40 border border-border/40">
                <span className="text-muted-foreground">空頭總額</span>
                <span className="text-rose-400 font-bold text-[9px]">$3,185</span>
              </div>
              <div className="flex flex-col px-1.5 py-0.5 rounded bg-secondary/40 border border-border/40">
                <span className="text-muted-foreground">淨槓桿比率</span>
                <span className="text-foreground font-semibold text-[9px]">0.40x / 3.0x</span>
              </div>
              <div className="flex flex-col px-1.5 py-0.5 rounded bg-secondary/40 border border-border/40">
                <span className="text-muted-foreground">可用保證金</span>
                <span className="text-amber-400 font-bold text-[9px]">$37,587</span>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
