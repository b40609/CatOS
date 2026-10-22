import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import { CardHeaderTitle } from "./card-header-title";
import { cn } from "@/lib/utils";
import { useLiveMarketStore } from "@/state/liveMarketStore";
import { NumberTicker } from "./motion/number-ticker";
import {
  Sliders,
  Sparkles,
  Copy,
  RotateCcw,
  Check,
  Disc,
  Type,
  Ruler,
  Maximize2,
  MoveHorizontal,
  Layers,
} from "lucide-react";

// 定案配色：低彩度、高質感的幣種資料系列色
const cryptoColors = {
  btc: "#e8b45e",       // BTC 蜂蜜金
  in_flight: "#7faee2", // ETH / 在途凍結 雅緻瓦藍
  available: "#10b981", // 可用額度 翡翠綠 (安全緩衝)
  alt: "#8b8df8",       // SOL 沉穩淡靛
  mm: "#f59e0b",        // 維持保證金 琥珀橘
  im: "#38bdf8",        // 初始保證金 晴空藍
  free: "#34d399",      // 自由保證金 薄荷青
  long_btc: "#10b981",  // 多頭 BTC 翡翠綠
  long_eth: "#34d399",  // 多頭 ETH 薄荷青
  short_sol: "#f43f5e", // 空頭 SOL 玫瑰紅
};

/**
 * 4 大業界資產曝險與風控呈現候選方案：
 * 方案 A · 彭博／幣安 膠囊分段容量條 (Bloomberg PORT · 100% Zero-Waste 空間利用，無引線碰撞，標註 50% 單幣上限)
 * 方案 B · OKX 專業合約 180° 半圓風控儀表 (OKX Pro / IBKR 拱形儀表盤，節省 45% 高度，下方四格風控矩陣)
 * 方案 C · TradingView 極簡微隙甜甜圈 (TradingView · 零引線 + 同心動態 HUD 互動聚焦)
 * 方案 D · CatOS 雙向多空標尺 (CatOS 原創 · 0 基準多空積木尺規與淨敞口指針)
 */
export type AllocationCandidateMode =
  | "capsule_rail" // 方案 A：膠囊容量軌道 (Bloomberg PORT)
  | "half_gauge"   // 方案 B：半圓風控儀表 (OKX 專業版)
  | "clean_donut"  // 方案 C：零引線甜甜圈 (TradingView)
  | "exposure";    // 方案 D：雙向多空標尺 (CatOS 原創)

export const CANDIDATE_STORAGE_KEY = "catos_allocation_candidate_v2";

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

// 雙向多空標尺資料結構 (方案 D)
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

const SCALE_PCT = 50;

// ==================== 方案 C 專屬 8 大細節微調橫桿配置 ====================
export interface DonutTuningConfig {
  donutRatio: number;      // 左側圓環寬度佔比 (30% ~ 55%)，預設 42%
  radius: number;          // 圓環外半徑 (38px ~ 75px)，預設 58px
  strokeWidth: number;     // 環身厚度 (5px ~ 26px)，預設 12px
  sliceGap: number;        // 切片物理縫隙 (0px ~ 8px)，預設 3.5px
  hudFontSize: number;     // 中央 HUD 主字大小 (12px ~ 28px)，預設 20px
  hudYOffset: number;      // 中央 HUD 垂直偏移 (-15px ~ 15px)，預設 0px
  barHeight: number;       // 右側進度條高度 (3px ~ 10px)，預設 6px
  limitMarkLength: number; // 50% 刻度線長度 (0px ~ 12px)，預設 6px
}

export const DONUT_TUNING_STORAGE_KEY = "catos_donut_tuning_config_v1";
export const DONUT_TUNING_OPEN_KEY = "catos_donut_tuning_open_v1";

export const TUNING_PRESETS: Record<string, { name: string; tag: string; desc: string; config: DonutTuningConfig }> = {
  hero_tv: {
    name: "TV 大字主角",
    tag: "極致焦點",
    desc: "TradingView 風格 · 21px 醒目大字 · 10px 雅緻細環 · 4px 空靈微隙",
    config: {
      donutRatio: 42,
      radius: 58,
      strokeWidth: 10,
      sliceGap: 4.0,
      hudFontSize: 21,
      hudYOffset: 0,
      barHeight: 6,
      limitMarkLength: 6,
    },
  },
  balanced_pro: {
    name: "OKX Pro 風控",
    tag: "雙向平衡",
    desc: "OKX 專業合約風格 · 16px 緊密數據 · 13px 標準環身 · 3px 緊湊微隙",
    config: {
      donutRatio: 45,
      radius: 56,
      strokeWidth: 13,
      sliceGap: 3.0,
      hudFontSize: 16,
      hudYOffset: 0,
      barHeight: 6,
      limitMarkLength: 6,
    },
  },
  dense_thick: {
    name: "彭博厚實飽滿",
    tag: "沉穩厚實",
    desc: "Bloomberg PORT 風格 · 18px 飽滿粗環 · 2px 緊密微隙 · 7px 厚軌道",
    config: {
      donutRatio: 38,
      radius: 54,
      strokeWidth: 18,
      sliceGap: 2.0,
      hudFontSize: 18,
      hudYOffset: 0,
      barHeight: 7,
      limitMarkLength: 7,
    },
  },
};

export function AllocationDonutCard({ className }: { className?: string }) {
  // 候選方案：使用者偏好方案 C (TradingView 甜甜圈)，預設為 clean_donut
  const [candidateMode, setCandidateMode] = useState<AllocationCandidateMode>(() => {
    try {
      const saved = localStorage.getItem(CANDIDATE_STORAGE_KEY);
      if (saved && ["capsule_rail", "half_gauge", "clean_donut", "exposure"].includes(saved)) {
        return saved as AllocationCandidateMode;
      }
    } catch {
      // ignore
    }
    return "clean_donut";
  });

  const handleSelectCandidate = useCallback((mode: AllocationCandidateMode) => {
    setCandidateMode(mode);
    try {
      localStorage.setItem(CANDIDATE_STORAGE_KEY, mode);
    } catch {
      // ignore
    }
  }, []);

  // 視覺微調面板開關 (預設開啟，讓使用者一進來就能任意滑動微調橫桿)
  const [isTuningOpen, setIsTuningOpen] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem(DONUT_TUNING_OPEN_KEY);
      if (saved !== null) return saved === "true";
    } catch {
      // ignore
    }
    return true;
  });

  const toggleTuningOpen = useCallback(() => {
    setIsTuningOpen((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(DONUT_TUNING_OPEN_KEY, String(next));
      } catch {
        // ignore
      }
      return next;
    });
  }, []);

  // 8 大細節微調參數 (支援 localStorage 記憶)
  const [tuning, setTuning] = useState<DonutTuningConfig>(() => {
    try {
      const saved = localStorage.getItem(DONUT_TUNING_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        return { ...TUNING_PRESETS.hero_tv.config, ...parsed };
      }
    } catch {
      // ignore
    }
    return TUNING_PRESETS.hero_tv.config;
  });

  const [activePreset, setActivePreset] = useState<string>("hero_tv");

  const updateTuning = useCallback(<K extends keyof DonutTuningConfig>(key: K, value: DonutTuningConfig[K]) => {
    setTuning((prev) => {
      const next = { ...prev, [key]: value };
      try {
        localStorage.setItem(DONUT_TUNING_STORAGE_KEY, JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
    setActivePreset("custom");
  }, []);

  const applyPreset = useCallback((presetKey: string) => {
    const p = TUNING_PRESETS[presetKey];
    if (!p) return;
    setTuning(p.config);
    setActivePreset(presetKey);
    try {
      localStorage.setItem(DONUT_TUNING_STORAGE_KEY, JSON.stringify(p.config));
    } catch {
      // ignore
    }
  }, []);

  const [isCopied, setIsCopied] = useState(false);
  const copyParams = useCallback(() => {
    const json = JSON.stringify(tuning, null, 2);
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(json).then(() => {
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), 2000);
      });
    }
  }, [tuning]);

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
  }, [candidateMode]);

  const {
    tickers,
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

  // 雙向多空標尺動態行情 (方案 D)
  const symbolsExposure: SymbolExposure[] = useMemo(() => {
    return [
      {
        symbol: "BTC-USDT-SWAP",
        base: "BTC",
        chg: tickers.BTC.change24h,
        mark: tickers.BTC.price,
        legs: [
          { id: "l1", botId: "tabby", botName: "Tabby", side: "long", notional: btcNotional },
        ],
        long: btcNotional,
        short: 0,
        net: btcNotional,
      },
      {
        symbol: "ETH-USDT-SWAP",
        base: "ETH",
        chg: tickers.ETH.change24h,
        mark: tickers.ETH.price,
        legs: [
          { id: "l3", botId: "calico", botName: "Calico", side: "long", notional: ethNotional },
        ],
        long: ethNotional,
        short: 0,
        net: ethNotional,
      },
      {
        symbol: "SOL-USDT-SWAP",
        base: "SOL",
        chg: tickers.SOL.change24h,
        mark: tickers.SOL.price,
        legs: [
          { id: "l5", botId: "mochi", botName: "Mochi", side: "long", notional: solNotional },
        ],
        long: solNotional,
        short: 0,
        net: solNotional,
      },
    ];
  }, [tickers, btcNotional, ethNotional, solNotional]);

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
      {/* 1. 卡片頂部一體化 Header + 業界 4 大方案初選切換器 + 橫桿微調板按鈕 */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-secondary/50 border-b border-border/80 shrink-0 gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <CardHeaderTitle
            cardId="allocation"
            title="槓桿倍數與資產曝險"
          />
        </div>

        <div className="flex items-center gap-1.5 flex-wrap">
          {/* 微調控制橫桿板展開開關 */}
          <button
            type="button"
            onClick={toggleTuningOpen}
            className={cn(
              "flex items-center gap-1 rounded px-2 py-0.5 text-[9px] border transition-colors cursor-pointer shadow-2xs font-mono font-medium",
              isTuningOpen
                ? "bg-primary/20 text-primary border-primary/50 font-bold"
                : "bg-background/90 text-muted-foreground hover:text-foreground border-border/80"
            )}
            title="開啟/收合即時微調橫桿面板 (8大滑桿 + 3大風格預設)"
          >
            <Sliders className="size-2.5 text-primary" />
            <span>橫桿微調板 ({activePreset === 'custom' ? '自訂參數' : TUNING_PRESETS[activePreset]?.name || '自訂'})</span>
          </button>

          {/* 方案切換按鈕群 */}
          <div className="flex items-center bg-background/60 border border-border/60 rounded p-0.5 gap-0.5 shrink-0">
            {[
              { id: "capsule_rail" as const, label: "A 膠囊容量", title: "方案 A · 彭博／幣安 膠囊分段容量條 (100% Zero-Waste 空間利用，無引線碰撞，標註 50% 單幣上限)" },
              { id: "half_gauge" as const, label: "B 半圓儀表", title: "方案 B · OKX 專業版 180° 半圓風控儀表 (拱形指針儀表盤，節省 45% 高度，下方四格風控矩陣)" },
              { id: "clean_donut" as const, label: "C 零引線環", title: "方案 C · TradingView 零引線甜甜圈 (保留經典圓環，徹底移除外拋引線，同心 HUD 互動聚焦)" },
              { id: "exposure" as const, label: "D 多空標尺", title: "方案 D · CatOS 雙向多空標尺 (中央 0 基準尺規、多空積木塊與淨敞口金色指針)" },
            ].map((btn) => (
              <button
                key={btn.id}
                type="button"
                onClick={() => { handleSelectCandidate(btn.id); setHoveredIndex(null); }}
                title={btn.title}
                className={cn(
                  "px-2 py-0.5 text-[10px] font-mono font-medium rounded transition-colors cursor-pointer",
                  candidateMode === btn.id
                    ? "bg-secondary text-primary border border-border font-semibold shadow-xs"
                    : "text-muted-foreground hover:text-foreground border border-transparent"
                )}
              >
                {btn.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 2. 即時微調控制橫桿面板 (8 大滑桿 + 3 大風格預設 + 參數複製與重置) */}
      {isTuningOpen && (
        <div className="bg-secondary/40 border-b border-border/70 px-3 py-1.5 text-[9px] flex flex-col gap-1.5 shrink-0 font-mono">
          {/* 上排：風格預設快捷鍵 + 複製 + 重置 */}
          <div className="flex items-center justify-between gap-1.5 flex-wrap">
            <div className="flex items-center gap-1 flex-wrap">
              <span className="text-muted-foreground flex items-center gap-1 font-bold mr-1">
                <Sparkles className="size-2.5 text-primary" />
                預設：
              </span>
              {Object.entries(TUNING_PRESETS).map(([key, p]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => applyPreset(key)}
                  className={cn(
                    "px-1.5 py-0.5 rounded text-[8.5px] font-medium border transition-colors cursor-pointer",
                    activePreset === key
                      ? "bg-primary/25 text-primary border-primary/50 font-bold shadow-2xs"
                      : "bg-background/80 text-muted-foreground hover:text-foreground border-border/70"
                  )}
                  title={p.desc}
                >
                  {p.name} [{p.tag}]
                </button>
              ))}
              {activePreset === 'custom' && (
                <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold">
                  ● 自訂微調中
                </span>
              )}
            </div>

            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={copyParams}
                className="px-2 py-0.5 rounded text-[8.5px] bg-background/80 hover:bg-background text-zinc-300 hover:text-zinc-100 border border-border/70 flex items-center gap-1 cursor-pointer transition-colors shadow-2xs"
                title="複製目前自訂參數為 JSON"
              >
                {isCopied ? <Check className="size-2.5 text-emerald-400" /> : <Copy className="size-2.5 text-primary" />}
                <span>{isCopied ? '已複製參數!' : '複製目前參數'}</span>
              </button>
              <button
                type="button"
                onClick={() => applyPreset('hero_tv')}
                className="px-2 py-0.5 rounded text-[8.5px] bg-background/80 hover:bg-background text-zinc-400 hover:text-zinc-200 border border-border/70 flex items-center gap-1 cursor-pointer transition-colors"
                title="重置為 TradingView 大字主角預設"
              >
                <RotateCcw className="size-2.5" />
                <span>重置</span>
              </button>
            </div>
          </div>

          {/* 下排：8 個直觀微調橫桿 (Range Sliders) */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-1.5">
            {/* 1. 圓環半徑 R */}
            <div className="flex flex-col gap-0.5 bg-background/90 border border-border/70 rounded p-1 shadow-2xs">
              <div className="flex items-center justify-between text-[8px] text-muted-foreground">
                <span className="font-medium flex items-center gap-0.5">
                  <Disc className="size-2 text-primary shrink-0" />
                  <span>半徑 R</span>
                </span>
                <span className="text-primary font-bold">{tuning.radius}px</span>
              </div>
              <input
                type="range"
                min="38"
                max="75"
                step="1"
                value={tuning.radius}
                onChange={(e) => updateTuning('radius', parseFloat(e.target.value))}
                className="w-full h-1 bg-secondary rounded appearance-none cursor-pointer accent-primary"
                title="調整圓環外半徑 (38px ~ 75px)"
              />
            </div>

            {/* 2. 環身厚度 W */}
            <div className="flex flex-col gap-0.5 bg-background/90 border border-border/70 rounded p-1 shadow-2xs">
              <div className="flex items-center justify-between text-[8px] text-muted-foreground">
                <span className="font-medium flex items-center gap-0.5">
                  <Maximize2 className="size-2 text-primary shrink-0" />
                  <span>環厚 W</span>
                </span>
                <span className="text-primary font-bold">{tuning.strokeWidth}px</span>
              </div>
              <input
                type="range"
                min="5"
                max="26"
                step="1"
                value={tuning.strokeWidth}
                onChange={(e) => updateTuning('strokeWidth', parseFloat(e.target.value))}
                className="w-full h-1 bg-secondary rounded appearance-none cursor-pointer accent-primary"
                title="調整圓環環身厚度 (5px ~ 26px)"
              />
            </div>

            {/* 3. 左圓環寬度佔比 */}
            <div className="flex flex-col gap-0.5 bg-background/90 border border-border/70 rounded p-1 shadow-2xs">
              <div className="flex items-center justify-between text-[8px] text-muted-foreground">
                <span className="font-medium flex items-center gap-0.5">
                  <MoveHorizontal className="size-2 text-primary shrink-0" />
                  <span>左環佔比</span>
                </span>
                <span className="text-primary font-bold">{tuning.donutRatio}%</span>
              </div>
              <input
                type="range"
                min="30"
                max="55"
                step="1"
                value={tuning.donutRatio}
                onChange={(e) => updateTuning('donutRatio', parseFloat(e.target.value))}
                className="w-full h-1 bg-secondary rounded appearance-none cursor-pointer accent-primary"
                title="調整左側圓環寬度佔比 (30% ~ 55%)"
              />
            </div>

            {/* 4. 切片微隙 Gap */}
            <div className="flex flex-col gap-0.5 bg-background/90 border border-border/70 rounded p-1 shadow-2xs">
              <div className="flex items-center justify-between text-[8px] text-muted-foreground">
                <span className="font-medium flex items-center gap-0.5">
                  <Ruler className="size-2 text-primary shrink-0" />
                  <span>切片微隙</span>
                </span>
                <span className="text-primary font-bold">{tuning.sliceGap.toFixed(1)}px</span>
              </div>
              <input
                type="range"
                min="0"
                max="8"
                step="0.5"
                value={tuning.sliceGap}
                onChange={(e) => updateTuning('sliceGap', parseFloat(e.target.value))}
                className="w-full h-1 bg-secondary rounded appearance-none cursor-pointer accent-primary"
                title="調整切片物理微隙 (0px ~ 8px)"
              />
            </div>

            {/* 5. HUD 主字大小 */}
            <div className="flex flex-col gap-0.5 bg-background/90 border border-border/70 rounded p-1 shadow-2xs">
              <div className="flex items-center justify-between text-[8px] text-muted-foreground">
                <span className="font-medium flex items-center gap-0.5">
                  <Type className="size-2 text-primary shrink-0" />
                  <span>HUD 字號</span>
                </span>
                <span className="text-primary font-bold">{tuning.hudFontSize}px</span>
              </div>
              <input
                type="range"
                min="12"
                max="28"
                step="1"
                value={tuning.hudFontSize}
                onChange={(e) => updateTuning('hudFontSize', parseFloat(e.target.value))}
                className="w-full h-1 bg-secondary rounded appearance-none cursor-pointer accent-primary"
                title="調整中央 HUD 主字大小 (12px ~ 28px)"
              />
            </div>

            {/* 6. HUD 垂直偏移 Y */}
            <div className="flex flex-col gap-0.5 bg-background/90 border border-border/70 rounded p-1 shadow-2xs">
              <div className="flex items-center justify-between text-[8px] text-muted-foreground">
                <span className="font-medium flex items-center gap-0.5">
                  <Layers className="size-2 text-primary shrink-0" />
                  <span>HUD 位移</span>
                </span>
                <span className="text-primary font-bold">{tuning.hudYOffset >= 0 ? `+${tuning.hudYOffset}` : tuning.hudYOffset}px</span>
              </div>
              <input
                type="range"
                min="-15"
                max="15"
                step="1"
                value={tuning.hudYOffset}
                onChange={(e) => updateTuning('hudYOffset', parseFloat(e.target.value))}
                className="w-full h-1 bg-secondary rounded appearance-none cursor-pointer accent-primary"
                title="調整中央 HUD 垂直偏移 (-15px ~ 15px)"
              />
            </div>

            {/* 7. 右側進度條高度 */}
            <div className="flex flex-col gap-0.5 bg-background/90 border border-border/70 rounded p-1 shadow-2xs">
              <div className="flex items-center justify-between text-[8px] text-muted-foreground">
                <span className="font-medium flex items-center gap-0.5">
                  <Ruler className="size-2 text-primary shrink-0" />
                  <span>條列高度</span>
                </span>
                <span className="text-primary font-bold">{tuning.barHeight}px</span>
              </div>
              <input
                type="range"
                min="3"
                max="10"
                step="1"
                value={tuning.barHeight}
                onChange={(e) => updateTuning('barHeight', parseFloat(e.target.value))}
                className="w-full h-1 bg-secondary rounded appearance-none cursor-pointer accent-primary"
                title="調整右側進度條高度 (3px ~ 10px)"
              />
            </div>

            {/* 8. 50% 上限刻度線長 */}
            <div className="flex flex-col gap-0.5 bg-background/90 border border-border/70 rounded p-1 shadow-2xs">
              <div className="flex items-center justify-between text-[8px] text-muted-foreground">
                <span className="font-medium flex items-center gap-0.5">
                  <Ruler className="size-2 text-primary shrink-0" />
                  <span>50% 刻度</span>
                </span>
                <span className="text-primary font-bold">{tuning.limitMarkLength}px</span>
              </div>
              <input
                type="range"
                min="0"
                max="12"
                step="1"
                value={tuning.limitMarkLength}
                onChange={(e) => updateTuning('limitMarkLength', parseFloat(e.target.value))}
                className="w-full h-1 bg-secondary rounded appearance-none cursor-pointer accent-primary"
                title="調整 50% 刻度長度 (0px 隱藏 ~ 12px 醒目)"
              />
            </div>
          </div>
        </div>
      )}

      {/* 2. 核心繪圖與內容展示區 */}
      <div ref={containerRef} className="flex-1 min-h-0 w-full h-full relative overflow-hidden p-2.5">

        {/* ==================== 方案 A · 彭博／幣安 膠囊分段容量條 (Zero-Waste 100% 空間利用) ==================== */}
        {candidateMode === "capsule_rail" && (
          <div className="w-full h-full flex flex-col justify-between overflow-hidden font-mono">
            {/* 頂部一體化膠囊容量軌道 */}
            <div className="flex flex-col gap-1.5 pb-2 border-b border-border/60 shrink-0">
              <div className="flex items-center justify-between text-[10.5px]">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-foreground">總曝險容量分段</span>
                  <span className="text-[9px] text-muted-foreground">(100% = 權益 × 3.0x 上限)</span>
                </div>
                <div className="flex items-center gap-1.5 font-bold">
                  <span className="text-muted-foreground text-[9.5px]">當前有效槓桿:</span>
                  <span className="text-primary text-[11px]">{effectiveLeverage.toFixed(2)}x</span>
                  <span className="text-muted-foreground text-[9px]">/ 3.00x</span>
                  <span className="text-emerald-400 text-[9px] bg-emerald-400/10 px-1 py-0.2 rounded border border-emerald-400/20">
                    已用 {((effectiveLeverage / 3.0) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* 橫向膠囊軌道 + 50% 單幣上限安全警戒線 */}
              <div className="h-6 w-full rounded-md bg-zinc-900 border border-border/80 flex overflow-hidden relative shadow-inner p-0.5 gap-0.5">
                {budgetItems.map((item, idx) => (
                  <div
                    key={item.symbol}
                    style={{ width: `${item.pct_share}%` }}
                    onMouseEnter={() => setHoveredIndex(idx)}
                    onMouseLeave={() => setHoveredIndex(null)}
                    title={`${item.label} · $${Math.round(item.nominal_usdt).toLocaleString()} (${item.pct_share.toFixed(1)}%)`}
                    className={cn(
                      "h-full rounded-xs transition-all cursor-pointer flex items-center justify-center relative overflow-hidden",
                      hoveredIndex === idx && "ring-1 ring-white/60 brightness-115 scale-[1.02] z-10"
                    )}
                  >
                    <div
                      className="absolute inset-0"
                      style={{ background: getBarGradient(item.color) }}
                    />
                    {item.pct_share >= 8 && (
                      <span className="relative z-10 text-[9px] font-bold text-black/85 drop-shadow-xs px-1 truncate">
                        {item.shortLabel || item.symbol} {item.pct_share.toFixed(0)}%
                      </span>
                    )}
                  </div>
                ))}

                {/* 50% 單幣上限警戒標線 */}
                <div
                  style={{ left: "50%" }}
                  className="absolute top-0 bottom-0 w-[2px] bg-rose-400 z-20 pointer-events-none shadow-[0_0_8px_rgba(244,63,94,0.9)]"
                  title="CatOS 風控硬指標：單幣曝險預算上限為 50%"
                />
              </div>

              {/* 標尺兩端與 50% 刻度說明 */}
              <div className="flex items-center justify-between text-[8px] text-muted-foreground px-0.5">
                <span>0.0x (空倉)</span>
                <span className="text-rose-400 font-semibold flex items-center gap-1">
                  ▲ 50% 單幣安全上限警戒 (1.5x)
                </span>
                <span>3.0x (上限)</span>
              </div>
            </div>

            {/* 下半部：高密度資產風控矩陣清單 */}
            <div className="flex-1 min-h-0 flex flex-col justify-around py-1 gap-1 overflow-y-auto">
              {budgetItems.map((item, idx) => {
                const isHovered = hoveredIndex === idx;
                const isAvailable = item.symbol === "可用";
                const isQuotaSafe = item.pct_share <= 50;

                return (
                  <div
                    key={item.symbol}
                    onMouseEnter={() => setHoveredIndex(idx)}
                    onMouseLeave={() => setHoveredIndex(null)}
                    className={cn(
                      "flex items-center justify-between px-2 py-1 rounded transition-colors cursor-pointer",
                      isHovered ? "bg-secondary/70 ring-1 ring-primary/40 shadow-xs" : "hover:bg-white/[0.03]"
                    )}
                  >
                    {/* 1. 幣種名稱與說明 */}
                    <div className="flex items-center gap-2 w-32 shrink-0">
                      <span className="size-2 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                      <div className="flex flex-col min-w-0">
                        <span className="text-[11px] font-bold text-foreground leading-tight truncate">
                          {item.shortLabel || item.symbol}
                        </span>
                        <span className="text-[8px] text-muted-foreground leading-tight truncate">
                          {item.sub}
                        </span>
                      </div>
                    </div>

                    {/* 2. 名義金額與佔比 */}
                    <div className="flex flex-col items-end w-28 shrink-0">
                      <span className="text-[11px] font-bold text-foreground leading-tight">
                        <NumberTicker value={item.nominal_usdt} decimals={0} prefix="$" />
                      </span>
                      <span className="text-[8.5px] text-muted-foreground leading-tight">
                        佔總曝險 {item.pct_share.toFixed(1)}%
                      </span>
                    </div>

                    {/* 3. 單幣上限 (50%) 進度條 */}
                    <div className="flex-1 max-w-[140px] hidden sm:flex flex-col gap-0.5 px-2">
                      <div className="flex justify-between text-[7.5px] text-muted-foreground">
                        <span>單幣限額進度</span>
                        <span>{isAvailable ? "—" : `${(item.pct_share).toFixed(1)}% / 50%`}</span>
                      </div>
                      <div className="w-full bg-zinc-800 h-1.5 rounded-full overflow-hidden">
                        <div
                          className={cn("h-full rounded-full transition-all duration-300", isQuotaSafe ? "bg-emerald-400" : "bg-rose-400")}
                          style={{ width: `${isAvailable ? 0 : Math.min(100, (item.pct_share / 50) * 100)}%` }}
                        />
                      </div>
                    </div>

                    {/* 4. 風控 Badge */}
                    <div className="w-16 shrink-0 text-right">
                      <span className={cn(
                        "px-1.5 py-0.5 rounded text-[8.5px] font-bold border",
                        isAvailable
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                          : isQuotaSafe
                          ? "bg-emerald-400/10 text-emerald-300 border-emerald-400/25"
                          : "bg-rose-400/10 text-rose-300 border-rose-400/30"
                      )}>
                        {isAvailable ? "BUFFER" : isQuotaSafe ? "SAFE" : "ALERT"}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ==================== 方案 B · OKX 專業合約 180° 半圓風控儀表 (Radial Arc Gauge) ==================== */}
        {candidateMode === "half_gauge" && (
          <div className="w-full h-full flex flex-col justify-between overflow-hidden font-mono">
            {/* 上半部：180° 上半圓拱形儀表盤 */}
            <div className="w-full h-[54%] relative flex items-center justify-center shrink-0">
              {(() => {
                const topH = Math.floor(H * 0.54);
                const cx = Math.floor(W / 2);
                const cy = topH - 12;
                const r = Math.min(cx - 30, cy - 16, 68);
                const strokeWidth = 13;
                const arcLength = Math.PI * r;

                // 累計各切片
                let accumulatedL = 0;
                const f = Math.min(1.0, effectiveLeverage / 3.0);
                const needleAngleRad = Math.PI - f * Math.PI;
                const needleLen = r - 10;
                const nx = cx + needleLen * Math.cos(needleAngleRad);
                const ny = cy - needleLen * Math.sin(needleAngleRad);

                return (
                  <svg
                    width={W}
                    height={topH}
                    viewBox={`0 0 ${W} ${topH}`}
                    className="w-full h-full block select-none overflow-visible"
                  >
                    {/* 底部灰色底軌 */}
                    <path
                      d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
                      fill="none"
                      stroke="#1e222d"
                      strokeWidth={strokeWidth}
                      strokeLinecap="round"
                    />

                    {/* 各幣種分段切片（沿著 180° 上半圓彩虹拱排列） */}
                    {budgetItems.map((item, idx) => {
                      const sliceLen = (item.pct_share / 100) * arcLength;
                      const offset = -accumulatedL;
                      accumulatedL += sliceLen;

                      return (
                        <path
                          key={item.symbol}
                          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
                          fill="none"
                          stroke={item.color}
                          strokeWidth={hoveredIndex === idx ? strokeWidth + 3 : strokeWidth}
                          strokeDasharray={`${Math.max(0, sliceLen - 2.5)} ${arcLength}`}
                          strokeDashoffset={offset}
                          className="cursor-pointer transition-all duration-150"
                          style={{
                            filter: hoveredIndex === idx ? `drop-shadow(0 0 8px ${item.color}90)` : undefined,
                          }}
                          onMouseEnter={() => setHoveredIndex(idx)}
                          onMouseLeave={() => setHoveredIndex(null)}
                        />
                      );
                    })}

                    {/* 50% 單幣上限中點標示 (拱頂) */}
                    <circle cx={cx} cy={cy - r} r="2.5" fill="#f43f5e" />
                    <text x={cx} y={cy - r - 6} textAnchor="middle" fill="#f43f5e" fontSize="7.5" fontWeight="bold">
                      50% 單幣上限 (1.5x)
                    </text>

                    {/* 刻度標籤 */}
                    <text x={cx - r - 4} y={cy + 8} textAnchor="end" fill="#94a3b8" fontSize="8">0.0x</text>
                    <text x={cx + r + 4} y={cy + 8} textAnchor="start" fill="#94a3b8" fontSize="8">3.0x</text>

                    {/* 槓桿金色指針 */}
                    <line
                      x1={cx}
                      y1={cy}
                      x2={nx}
                      y2={ny}
                      stroke="#e8b45e"
                      strokeWidth="2"
                      strokeLinecap="round"
                      className="transition-all duration-300"
                    />
                    <circle cx={cx} cy={cy} r="4" fill="#e8b45e" />

                    {/* 儀表中央大字 HUD */}
                    {activeHoverItem ? (
                      <g className="pointer-events-none select-none">
                        <text x={cx} y={cy - 28} textAnchor="middle" fill="#94a3b8" fontSize="8.5">
                          {activeHoverItem.shortLabel || activeHoverItem.symbol}
                        </text>
                        <text x={cx} y={cy - 12} textAnchor="middle" fill={activeHoverItem.color} fontSize="15" fontWeight="bold">
                          {activeHoverItem.pct_share.toFixed(1)}%
                        </text>
                        <text x={cx} y={cy + 2} textAnchor="middle" fill="#cbd5e1" fontSize="8">
                          ${Math.round(activeHoverItem.nominal_usdt).toLocaleString()}
                        </text>
                      </g>
                    ) : (
                      <g className="pointer-events-none select-none">
                        <text x={cx} y={cy - 28} textAnchor="middle" fill="#94a3b8" fontSize="8">
                          有效槓桿 / 上限
                        </text>
                        <text x={cx} y={cy - 12} textAnchor="middle" fill="#e8b45e" fontSize="14" fontWeight="bold">
                          {effectiveLeverage.toFixed(2)}x / 3.0x
                        </text>
                        <text x={cx} y={cy + 2} textAnchor="middle" fill="#94a3b8" fontSize="8">
                          已用 {((effectiveLeverage / 3.0) * 100).toFixed(1)}% 容量
                        </text>
                      </g>
                    )}
                  </svg>
                );
              })()}
            </div>

            {/* 下半部：4 格高密度風控數據卡片矩陣 */}
            <div className="flex-1 min-h-0 flex flex-col justify-around pt-1 border-t border-border/50">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 text-[8.5px]">
                <div className="flex flex-col p-1.5 rounded bg-secondary/40 border border-border/50">
                  <span className="text-muted-foreground text-[8px]">單幣最大曝險</span>
                  <span className="text-foreground font-bold text-[10px] mt-0.5">
                    BTC {(btcNotional / (totalEquity * 3.0) * 100).toFixed(1)}%
                  </span>
                  <span className="text-emerald-400 text-[7.5px]">安全 (上限 50%)</span>
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
        )}

        {/* ==================== 方案 C · TradingView 極簡微隙甜甜圈 (C-Pro 橫桿即時微調版) ==================== */}
        {candidateMode === "clean_donut" && (
          <div className="w-full h-full flex flex-col justify-between overflow-hidden font-mono">
            {/* 上半部核心：左側 Donut 圓環 (帶 50% 刻度 + 同心 HUD) + 右側雙層風控條列 */}
            <div className="flex-1 min-h-0 flex items-center justify-between gap-2 overflow-hidden pt-0.5">
              {/* 左側 Donut 圓環 (可由 donutRatio 橫桿動態自適應寬度，半徑與厚度即時連動) */}
              <div
                style={{ width: `${tuning.donutRatio}%` }}
                className="h-full flex items-center justify-center relative shrink-0 transition-all duration-75"
              >
                {(() => {
                  const donutColW = Math.max(80, Math.floor(W * (tuning.donutRatio / 100)));
                  const cx = Math.floor(donutColW / 2);
                  const contentH = Math.max(100, H - (isTuningOpen ? 55 : 65));
                  const cy = Math.floor(contentH / 2) + tuning.hudYOffset;

                  const strokeWidth = tuning.strokeWidth;
                  // 根據使用者設定的 radius 繪製，同時確保不溢出 SVG 容器
                  const r = Math.min(
                    cx - Math.ceil(strokeWidth / 2) - 3,
                    cy - Math.ceil(strokeWidth / 2) - 3,
                    tuning.radius
                  );
                  const circumference = 2 * Math.PI * r;
                  const sliceGap = tuning.sliceGap;

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

                      {/* 50% 單幣上限安全刻度線 (圓周 180° / 6 點鐘位置) */}
                      {tuning.limitMarkLength > 0 && (
                        <>
                          <circle cx={cx} cy={cy + r} r="2.5" fill="#f43f5e" />
                          <line
                            x1={cx}
                            y1={cy + r - strokeWidth / 2 - tuning.limitMarkLength / 2}
                            x2={cx}
                            y2={cy + r + strokeWidth / 2 + tuning.limitMarkLength / 2}
                            stroke="#f43f5e"
                            strokeWidth="1.5"
                          />
                          <text
                            x={cx}
                            y={cy + r + strokeWidth / 2 + tuning.limitMarkLength / 2 + 9}
                            textAnchor="middle"
                            fill="#f43f5e"
                            fontSize="7.5"
                            fontWeight="bold"
                          >
                            50% 上限
                          </text>
                        </>
                      )}

                      {/* 中央純淨同心 HUD (主字大小與垂直位移即時連動) */}
                      {activeHoverItem ? (
                        <g className="pointer-events-none select-none">
                          <text
                            x={cx}
                            y={cy - Math.floor(tuning.hudFontSize * 0.7)}
                            textAnchor="middle"
                            fill="#94a3b8"
                            fontSize="8.5"
                            fontFamily="monospace"
                          >
                            {activeHoverItem.shortLabel || activeHoverItem.symbol}
                          </text>
                          <text
                            x={cx}
                            y={cy + Math.floor(tuning.hudFontSize * 0.25)}
                            textAnchor="middle"
                            fill={activeHoverItem.color}
                            fontSize={tuning.hudFontSize}
                            fontWeight="bold"
                            fontFamily="monospace"
                          >
                            {activeHoverItem.pct_share.toFixed(1)}%
                          </text>
                          <text
                            x={cx}
                            y={cy + Math.floor(tuning.hudFontSize * 0.95)}
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
                            y={cy - Math.floor(tuning.hudFontSize * 0.7)}
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
                            y={cy + Math.floor(tuning.hudFontSize * 0.25)}
                            textAnchor="middle"
                            fill="#e8b45e"
                            fontSize={tuning.hudFontSize}
                            fontWeight="bold"
                            fontFamily="monospace"
                            style={{ filter: "drop-shadow(0 0 8px rgba(232, 180, 94, 0.35))" }}
                          >
                            {effectiveLeverage.toFixed(2)}x
                          </text>
                          <text
                            x={cx}
                            y={cy + Math.floor(tuning.hudFontSize * 0.95)}
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

              {/* 右側 5 條高密度進度資訊棧 (寬度與高度即時連動) */}
              <div
                style={{ width: `${100 - tuning.donutRatio}%` }}
                className="h-full flex flex-col justify-around py-0.5 overflow-hidden pl-1 transition-all duration-75"
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

                      {/* 雙層進度軌道 (帶 50% 單幣上限安全輔助刻度，高度由 barHeight 橫桿控制) */}
                      <div
                        style={{ height: `${tuning.barHeight}px` }}
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
        )}

        {/* ==================== 方案 D · CatOS 雙向多空標尺 (0 基準雙向尺規 + Bot 積木塊 + 金色指針) ==================== */}
        {candidateMode === "exposure" && (
          <div className="w-full h-full flex flex-col justify-between overflow-hidden p-1 font-mono">
            {/* 標尺表頭刻度 */}
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
              {symbolsExposure.map((s) => {
                const netPct = (s.net / totalEquity) * 100;
                return (
                  <div key={s.symbol} className="flex items-center gap-2">
                    {/* 標的代號與 24h 漲跌 */}
                    <div className="w-16 shrink-0 flex flex-col">
                      <span className="text-[10.5px] font-bold text-foreground leading-tight">
                        {s.base}
                      </span>
                      <span
                        className={cn(
                          "text-[9px] leading-tight flex items-center",
                          s.chg >= 0 ? "text-emerald-400" : "text-rose-400"
                        )}
                      >
                        {s.chg >= 0 ? "+" : ""}<NumberTicker value={s.chg} decimals={2} suffix="%" />
                      </span>
                    </div>

                    {/* 雙向長條尺規 */}
                    <div className="flex-1 h-5.5 bg-background/80 rounded border border-border/60 relative flex overflow-hidden">
                      {/* 空頭區 (向左) */}
                      <div className="w-1/2 h-full flex justify-end overflow-hidden pr-[1px]">
                        {s.legs
                          .filter((l) => l.side === "short")
                          .map((leg) => {
                            const p = (leg.notional / totalEquity) * 100;
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
                            const p = (leg.notional / totalEquity) * 100;
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
                          className="absolute top-0 -translate-x-1/2 z-20 pointer-events-none transition-all duration-300"
                        >
                          <div className="w-0 h-0 border-l-[3px] border-l-transparent border-r-[3px] border-r-transparent border-t-[4.5px] border-t-amber-400" />
                        </div>
                      )}
                    </div>

                    {/* 淨額與佔比 */}
                    <div className="w-20 shrink-0 flex flex-col items-end">
                      <span className={cn("text-[10px] font-bold leading-tight flex items-center", s.net >= 0 ? "text-emerald-400" : "text-rose-400")}>
                        {s.net >= 0 ? "+" : ""}<NumberTicker value={Math.round(s.net)} decimals={0} />
                      </span>
                      <span className="text-[8px] text-muted-foreground leading-tight flex items-center">
                        {netPct >= 0 ? "+" : ""}<NumberTicker value={netPct} decimals={1} suffix="%" />
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* 底部風控微卡列 */}
            <div className="grid grid-cols-4 gap-1 pt-1.5 border-t border-border/50 text-[8px] shrink-0">
              <div className="flex flex-col px-1.5 py-0.5 rounded bg-secondary/40 border border-border/40">
                <span className="text-muted-foreground">多頭總額</span>
                <span className="text-emerald-400 font-bold text-[9px] flex items-center">
                  <NumberTicker value={symbolsExposure.reduce((acc, s) => acc + s.long, 0)} decimals={0} prefix="$" />
                </span>
              </div>
              <div className="flex flex-col px-1.5 py-0.5 rounded bg-secondary/40 border border-border/40">
                <span className="text-muted-foreground">空頭總額</span>
                <span className="text-rose-400 font-bold text-[9px] flex items-center">
                  <NumberTicker value={symbolsExposure.reduce((acc, s) => acc + s.short, 0)} decimals={0} prefix="$" />
                </span>
              </div>
              <div className="flex flex-col px-1.5 py-0.5 rounded bg-secondary/40 border border-border/40">
                <span className="text-muted-foreground">淨槓桿比率</span>
                <span className="text-foreground font-semibold text-[9px] flex items-center gap-0.5">
                  <NumberTicker value={effectiveLeverage} decimals={2} suffix="x" /> / 3.0x
                </span>
              </div>
              <div className="flex flex-col px-1.5 py-0.5 rounded bg-secondary/40 border border-border/40">
                <span className="text-muted-foreground">可用保證金</span>
                <span className="text-amber-400 font-bold text-[9px] flex items-center">
                  <NumberTicker value={Math.max(0, totalEquity * 0.93)} decimals={0} prefix="$" />
                </span>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
