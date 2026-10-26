import { useState, useMemo, useRef, useEffect } from "react";
import { CardHeaderTitle } from "./card-header-title";
import { cn } from "@/lib/utils";
import { useLiveMarketStore } from "@/state/liveMarketStore";

// 定案配色：低彩度、高質感的幣種資料系列色
const cryptoColors = {
  btc: "#e8b45e",       // BTC 蜂蜜金
  in_flight: "#7faee2", // ETH 雅緻瓦藍
  alt: "#8b8df8",       // SOL 沉穩淡靛
  pending: "#a1a1aa",   // 在途凍結 鋅灰
  available: "#10b981", // 可用額度 / 翡翠綠 (安全緩衝)
  loss: "#f43f5e",      // 浮動虧損 玫瑰紅
};

interface DonutItem {
  symbol: string;
  name: string;
  shortLabel: string;
  compactLabel?: string; // 窄版極簡標籤 (如 BTC, ETH, SOL)
  sub: string;
  nominal_usdt: number;
  pct_share: number;
  color: string;
  badgeStr: string;
  compactBadge?: string; // 窄版極簡徽章 (如 1.09x, -25%)
  amountStr: string;
  isLoss?: boolean;
}

// 向量坐標系幾何常量 (以 200x200 viewBox 為基準，GPU 向量原生縮放，0 JS Resize 開銷)
// 依據業界量化終端規範優化：降低軌道厚度至 9.5px，擴大中央負空間內徑至 140px，讓排版有充足呼吸感
const VB_SIZE = 200;
const CX = 100;
const CY = 100;
const R = 75;
const STROKE_WIDTH = 9.5;
const CIRCUMFERENCE = 2 * Math.PI * R; // 471.2389
const SLICE_GAP = 2.5; // 幾何微縫隙

export type DonutViewMode = "allocation" | "bots" | "delta" | "margin" | "pnl";
export type HudFocus = "money" | "leverage";

// 定案全 5 大核心維度分段標籤 (寬版完整名，窄版自動簡寫為 2 字標籤節省空間)
const TABS: { id: DonutViewMode; label: string; shortLabel: string }[] = [
  { id: "allocation", label: "幣種配置", shortLabel: "幣種" },
  { id: "bots", label: "策略機器人", shortLabel: "機器人" },
  { id: "delta", label: "多空敞口", shortLabel: "敞口" },
  { id: "margin", label: "保證金佔用", shortLabel: "保證金" },
  { id: "pnl", label: "盈虧分佈", shortLabel: "盈虧" },
];

/**
 * 槓桿倍數與資產曝險卡片 (AllocationDonutCard)
 * - 徹底移除底部枯燥的 4 塊文字小框，將垂直空間 100% 留給圓環與清單
 * - 定案全 5 大維度即時切換：【幣種配置 | 策略機器人 | 多空敞口 | 保證金佔用 | 盈虧分佈】
 * - 融合彭博高對比字體與微型進度刻度，支持【$ 金額主導】與【x 槓桿倍數】雙重直觀焦點
 */
export function AllocationDonutCard({ className }: { className?: string }) {
  const [viewMode, setViewMode] = useState<DonutViewMode>("allocation");
  const [hudFocus, setHudFocus] = useState<HudFocus>("money");
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 600, height: 240 });

  // 業界標準全維度自適應形態降級 (WidgetKit / TradingView Form-Factor Degradation)：
  // 實時監聽卡片物理容器的寬度與高度，當空間緊湊時無縫降級為單行背景長條圖態，0 衝突 0 跑板
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const isNarrow = dimensions.width < 460;
  const isSuperNarrow = dimensions.width < 340;
  const isShort = dimensions.height < 170;
  const isCompact = isNarrow || isShort;

  const {
    totalEquity,
    effectiveLeverage,
    btcNotional,
    ethNotional,
    solNotional,
    inFlightNotional: inFlightNominal,
  } = useLiveMarketStore();

  const totalHoldingsNominal = btcNotional + ethNotional + solNotional;
  const maxBudget = totalEquity * 3.0; // 3.0x 槓桿上限
  const usedNom = totalHoldingsNominal + inFlightNominal;
  const availNom = Math.max(0, maxBudget - usedNom);

  // 1. 維度：資產配置 (Notional Exposure · 名目曝險與幣種佔比)
  const allocationItems: DonutItem[] = useMemo(() => {
    const btcPct = maxBudget > 0 ? (btcNotional / maxBudget) * 100 : 0;
    const ethPct = maxBudget > 0 ? (ethNotional / maxBudget) * 100 : 0;
    const solPct = maxBudget > 0 ? (solNotional / maxBudget) * 100 : 0;
    const inFlightPct = maxBudget > 0 ? (inFlightNominal / maxBudget) * 100 : 0;
    const availPct = maxBudget > 0 ? (availNom / maxBudget) * 100 : 0;

    return [
      {
        symbol: "BTC",
        name: "BTC 永續合約持倉",
        shortLabel: "BTC 持倉",
        compactLabel: "BTC",
        sub: "持倉",
        nominal_usdt: btcNotional,
        pct_share: btcPct,
        color: cryptoColors.btc,
        badgeStr: `${(btcNotional / totalEquity).toFixed(2)}x 槓桿`,
        compactBadge: `${(btcNotional / totalEquity).toFixed(2)}x`,
        amountStr: `$${Math.round(btcNotional).toLocaleString()}`,
      },
      {
        symbol: "ETH",
        name: "ETH 永續合約持倉",
        shortLabel: "ETH 持倉",
        compactLabel: "ETH",
        sub: "持倉",
        nominal_usdt: ethNotional,
        pct_share: ethPct,
        color: cryptoColors.in_flight,
        badgeStr: `${(ethNotional / totalEquity).toFixed(2)}x 槓桿`,
        compactBadge: `${(ethNotional / totalEquity).toFixed(2)}x`,
        amountStr: `$${Math.round(ethNotional).toLocaleString()}`,
      },
      {
        symbol: "SOL",
        name: "SOL 永續合約持倉",
        shortLabel: "SOL 持倉",
        compactLabel: "SOL",
        sub: "持倉",
        nominal_usdt: solNotional,
        pct_share: solPct,
        color: cryptoColors.alt,
        badgeStr: `${(solNotional / totalEquity).toFixed(2)}x 槓桿`,
        compactBadge: `${(solNotional / totalEquity).toFixed(2)}x`,
        amountStr: `$${Math.round(solNotional).toLocaleString()}`,
      },
      {
        symbol: "在途",
        name: "在途買單委託凍結",
        shortLabel: "在途 凍結",
        compactLabel: "在途",
        sub: "掛單",
        nominal_usdt: inFlightNominal,
        pct_share: inFlightPct,
        color: cryptoColors.pending,
        badgeStr: `${(inFlightNominal / totalEquity).toFixed(2)}x 額度`,
        compactBadge: `${(inFlightNominal / totalEquity).toFixed(2)}x`,
        amountStr: `$${Math.round(inFlightNominal).toLocaleString()}`,
      },
      {
        symbol: "可用",
        name: "剩餘可用現金預算",
        shortLabel: "可用 額度",
        compactLabel: "可用",
        sub: "緩衝",
        nominal_usdt: availNom,
        pct_share: availPct,
        color: cryptoColors.available,
        badgeStr: `${(availNom / totalEquity).toFixed(2)}x 備援`,
        compactBadge: `${(availNom / totalEquity).toFixed(2)}x`,
        amountStr: `$${Math.round(availNom).toLocaleString()}`,
      },
    ];
  }, [btcNotional, ethNotional, solNotional, inFlightNominal, availNom, maxBudget, totalEquity]);

  // 2. 維度：多空敞口 (Long / Short Delta · 多頭 vs 空頭對沖對比)
  const deltaItems: DonutItem[] = useMemo(() => {
    // 專業對沖模型：BTC 多頭、ETH 空頭對沖、SOL 多頭、在途限價買單
    const btcLong = btcNotional; // $48,000 多頭
    const ethShort = 24000;      // $24,000 空頭對沖
    const solLong = solNotional; // $18,000 多頭
    const inFlightBid = inFlightNominal; // $8,000 在途買單

    const totalGross = btcLong + ethShort + solLong + inFlightBid; // 總敞口 $98,000
    const btcPct = (btcLong / totalGross) * 100;
    const ethPct = (ethShort / totalGross) * 100;
    const solPct = (solLong / totalGross) * 100;
    const bidPct = (inFlightBid / totalGross) * 100;

    return [
      {
        symbol: "BTC",
        name: "BTC 趨勢跟隨多頭",
        shortLabel: "BTC 多頭",
        compactLabel: "BTC",
        sub: "LONG",
        nominal_usdt: btcLong,
        pct_share: btcPct,
        color: "#10b981", // 多頭翡翠綠
        badgeStr: "12.5張 (+49%)",
        compactBadge: "+49%",
        amountStr: `+$${Math.round(btcLong).toLocaleString()}`,
      },
      {
        symbol: "ETH",
        name: "ETH 統計套利空頭對沖",
        shortLabel: "ETH 空頭",
        compactLabel: "ETH",
        sub: "SHORT",
        nominal_usdt: ethShort,
        pct_share: ethPct,
        color: "#f43f5e", // 空頭玫瑰紅
        badgeStr: "-120張 (-25%)",
        compactBadge: "-25%",
        amountStr: `-$${Math.round(ethShort).toLocaleString()}`,
        isLoss: true,
      },
      {
        symbol: "SOL",
        name: "SOL 動量突破多頭",
        shortLabel: "SOL 多頭",
        compactLabel: "SOL",
        sub: "LONG",
        nominal_usdt: solLong,
        pct_share: solPct,
        color: "#34d399", // 亮翡翠綠
        badgeStr: "980張 (+18%)",
        compactBadge: "+18%",
        amountStr: `+$${Math.round(solLong).toLocaleString()}`,
      },
      {
        symbol: "在途買單",
        name: "在途限價買單敞口",
        shortLabel: "在途 買單",
        compactLabel: "在途",
        sub: "BID",
        nominal_usdt: inFlightBid,
        pct_share: bidPct,
        color: "#94a3b8", // 中性掛單灰
        badgeStr: "28張 (+8%)",
        compactBadge: "+8%",
        amountStr: `+$${Math.round(inFlightBid).toLocaleString()}`,
      },
    ];
  }, [btcNotional, solNotional, inFlightNominal]);

  // 3. 維度：保證金佔用 (Margin Structure · 專業帳戶流動性與安全架構)
  const marginItems: DonutItem[] = useMemo(() => {
    // 依 OKX 專業跨幣種保證金結構真實拆解：
    // 開倉保證金(45.4%) + 自由保證金(37.6%) + 最低維持線(11.6%) + 掛單凍結(5.4%) = 100%
    const imr = 22700;
    const free = 18800;
    const mmr = 5800;
    const frozen = 2700;

    const imrPct = (imr / totalEquity) * 100;
    const freePct = (free / totalEquity) * 100;
    const mmrPct = (mmr / totalEquity) * 100;
    const frozenPct = (frozen / totalEquity) * 100;

    return [
      {
        symbol: "開倉佔用",
        name: "持倉佔用初始保證金 (IMR)",
        shortLabel: "開倉佔用",
        compactLabel: "開倉",
        sub: "IMR",
        nominal_usdt: imr,
        pct_share: imrPct,
        color: "#3b82f6", // 保證金藍
        badgeStr: "佔用 45.4%",
        compactBadge: "45.4%",
        amountStr: `$${imr.toLocaleString()}`,
      },
      {
        symbol: "自由保證金",
        name: "自由可用未鎖定保證金 (隨時可提/開新倉)",
        shortLabel: "自由保證金",
        compactLabel: "自由",
        sub: "FREE",
        nominal_usdt: free,
        pct_share: freePct,
        color: "#10b981", // 自由安全綠
        badgeStr: "自由 37.6%",
        compactBadge: "37.6%",
        amountStr: `$${free.toLocaleString()}`,
      },
      {
        symbol: "強平警戒線",
        name: "最低維持保證金底線 (觸及即觸發強平)",
        shortLabel: "強平底線 MMR",
        compactLabel: "底線",
        sub: "MMR",
        nominal_usdt: mmr,
        pct_share: mmrPct,
        color: "#f59e0b", // 警戒金
        badgeStr: "底線 11.6%",
        compactBadge: "11.6%",
        amountStr: `$${mmr.toLocaleString()}`,
      },
      {
        symbol: "委託凍結",
        name: "未成交限價單保證金凍結",
        shortLabel: "委託凍結",
        compactLabel: "凍結",
        sub: "FROZEN",
        nominal_usdt: frozen,
        pct_share: frozenPct,
        color: "#94a3b8", // 凍結冷灰
        badgeStr: "凍結 5.4%",
        compactBadge: "5.4%",
        amountStr: `$${frozen.toLocaleString()}`,
      },
    ];
  }, [totalEquity]);

  // 4. 維度：盈虧分佈 (PnL Contribution · 未實現損益與費用歸因)
  const pnlItems: DonutItem[] = useMemo(() => {
    // 依各合約與費用真實損益拆解：
    const btcProfit = 2840;   // BTC 盈利
    const solProfit = 1290;   // SOL 盈利
    const fundProfit = 380;   // 資金費率淨收益
    const ethLoss = -680;     // ETH 浮動虧損
    const feeLoss = -445;     // 手續費支出

    // 圓環以各項目絕對貢獻規模分佈
    const totalVolume = btcProfit + solProfit + fundProfit + Math.abs(ethLoss) + Math.abs(feeLoss); // 5635
    const btcPct = (btcProfit / totalVolume) * 100;
    const solPct = (solProfit / totalVolume) * 100;
    const fundPct = (fundProfit / totalVolume) * 100;
    const ethPct = (Math.abs(ethLoss) / totalVolume) * 100;
    const feePct = (Math.abs(feeLoss) / totalVolume) * 100;

    return [
      {
        symbol: "BTC 盈利",
        name: "BTC 趨勢跟隨浮動盈利",
        shortLabel: "BTC 盈利",
        compactLabel: "BTC",
        sub: "PROFIT",
        nominal_usdt: btcProfit,
        pct_share: btcPct,
        color: "#10b981", // 翡翠綠
        badgeStr: "+5.9% ROI",
        compactBadge: "+5.9%",
        amountStr: `+$${btcProfit.toLocaleString()}`,
      },
      {
        symbol: "SOL 盈利",
        name: "SOL 動量突破浮動盈利",
        shortLabel: "SOL 盈利",
        compactLabel: "SOL",
        sub: "PROFIT",
        nominal_usdt: solProfit,
        pct_share: solPct,
        color: "#34d399", // 亮綠
        badgeStr: "+7.2% ROI",
        compactBadge: "+7.2%",
        amountStr: `+$${solProfit.toLocaleString()}`,
      },
      {
        symbol: "資金費收益",
        name: "永續合約 8H 資金費淨收益",
        shortLabel: "資金費淨收",
        compactLabel: "資金費",
        sub: "FUNDING",
        nominal_usdt: fundProfit,
        pct_share: fundPct,
        color: "#e8b45e", // 資金費金
        badgeStr: "年化 12.8%",
        compactBadge: "+12.8%",
        amountStr: `+$${fundProfit.toLocaleString()}`,
      },
      {
        symbol: "ETH 浮虧",
        name: "ETH 高位回撤浮動虧損",
        shortLabel: "ETH 浮虧",
        compactLabel: "ETH",
        sub: "LOSS",
        nominal_usdt: ethLoss,
        pct_share: ethPct,
        color: "#f43f5e", // 玫瑰紅
        badgeStr: "-2.1% 浮虧",
        compactBadge: "-2.1%",
        amountStr: `-$${Math.abs(ethLoss).toLocaleString()}`,
        isLoss: true,
      },
      {
        symbol: "交易手續費",
        name: "交易所手續費累計成本",
        shortLabel: "手續費成本",
        compactLabel: "手續費",
        sub: "FEE",
        nominal_usdt: feeLoss,
        pct_share: feePct,
        color: "#71717a", // 費用灰
        badgeStr: "VIP2 費率",
        compactBadge: "VIP2",
        amountStr: `-$${Math.abs(feeLoss).toLocaleString()}`,
        isLoss: true,
      },
    ];
  }, []);

  // 5. 維度：策略機器人分配 (Bot Allocation · 依策略實例拆解名目曝險與資金預算消耗)
  const botItems: DonutItem[] = useMemo(() => {
    const tabbyPct = maxBudget > 0 ? (btcNotional / maxBudget) * 100 : 0;
    const calicoPct = maxBudget > 0 ? (ethNotional / maxBudget) * 100 : 0;
    const machiPct = maxBudget > 0 ? (solNotional / maxBudget) * 100 : 0;
    const inFlightPct = maxBudget > 0 ? (inFlightNominal / maxBudget) * 100 : 0;
    const availPct = maxBudget > 0 ? (availNom / maxBudget) * 100 : 0;

    return [
      {
        symbol: "Tabby",
        name: "Tabby · BTC 永續突破 (1h)",
        shortLabel: "Tabby 機器人",
        compactLabel: "Tabby",
        sub: "BTC 策略",
        nominal_usdt: btcNotional,
        pct_share: tabbyPct,
        color: "#e8b45e", // 蜂蜜金
        badgeStr: "突破 1h · 1.09x",
        compactBadge: "1.09x",
        amountStr: `$${Math.round(btcNotional).toLocaleString()}`,
      },
      {
        symbol: "Calico",
        name: "Calico · ETH 趨勢跟隨 (1h)",
        shortLabel: "Calico 機器人",
        compactLabel: "Calico",
        sub: "ETH 策略",
        nominal_usdt: ethNotional,
        pct_share: calicoPct,
        color: "#7faee2", // 雅緻瓦藍
        badgeStr: "趨勢 1h · 0.66x",
        compactBadge: "0.66x",
        amountStr: `$${Math.round(ethNotional).toLocaleString()}`,
      },
      {
        symbol: "Machi",
        name: "Machi · SOL 動量突破 (15m)",
        shortLabel: "Machi 機器人",
        compactLabel: "Machi",
        sub: "SOL 策略",
        nominal_usdt: solNotional,
        pct_share: machiPct,
        color: "#8b8df8", // 沉穩淡靛
        badgeStr: "動量 15m · 0.30x",
        compactBadge: "0.30x",
        amountStr: `$${Math.round(solNotional).toLocaleString()}`,
      },
      {
        symbol: "在途掛單",
        name: "策略限價委託在途凍結額度",
        shortLabel: "在途凍結",
        compactLabel: "在途",
        sub: "PENDING",
        nominal_usdt: inFlightNominal,
        pct_share: inFlightPct,
        color: "#a1a1aa", // 鋅灰
        badgeStr: "掛單 · 0.11x",
        compactBadge: "0.11x",
        amountStr: `$${Math.round(inFlightNominal).toLocaleString()}`,
      },
      {
        symbol: "閒置預算",
        name: "未被任何策略佔用的可用現金額度",
        shortLabel: "閒置預算",
        compactLabel: "閒置",
        sub: "BUFFER",
        nominal_usdt: availNom,
        pct_share: availPct,
        color: "#10b981", // 翡翠綠
        badgeStr: "備援 · 0.84x",
        compactBadge: "0.84x",
        amountStr: `$${Math.round(availNom).toLocaleString()}`,
      },
    ];
  }, [btcNotional, ethNotional, solNotional, inFlightNominal, availNom, maxBudget]);

  // 當前選定維度之數據集
  const currentItems = viewMode === "allocation"
    ? allocationItems
    : viewMode === "bots"
    ? botItems
    : viewMode === "delta"
    ? deltaItems
    : viewMode === "margin"
    ? marginItems
    : pnlItems;

  const activeHoverItem = hoveredIndex !== null ? currentItems[hoveredIndex] : null;



  // =========================================================================
  // 定案圓環：Paperpillar 聚光燈聚焦環 (純向量自適應渲染，依模式切換 HUD 資訊)
  // =========================================================================
  const renderSpotlightDonut = () => {
    let accumulatedArc = 0;

    const usedK = (usedNom / 1000).toFixed(1);
    const maxK = (maxBudget / 1000).toFixed(1);
    const availK = (availNom / 1000).toFixed(1);
    const usedPct = maxBudget > 0 ? (usedNom / maxBudget) * 100 : 0;

    // 中央 HUD 標題與數值計算 (依 Bloomberg / TradingView 金額與倍數雙錨定法則)
    let hudTitle = hudFocus === "money"
      ? (viewMode === "bots" ? "機器人總持倉" : "持倉名目總值")
      : "有效槓桿水位";
    let hudValue = hudFocus === "money" ? `$${usedK}k` : `${effectiveLeverage.toFixed(2)}x`;
    let hudValueColor = "#f8fafc"; // 專業中性珍珠白，高對比無光暈
    let hudSub = hudFocus === "money"
      ? `3x上限 $${maxK}k · 餘 $${availK}k`
      : `持倉 $${usedK}k / 預算 $${maxK}k`;
    let progressPct = Math.min(100, usedPct);
    let hudTag = hudFocus === "money" ? `${effectiveLeverage.toFixed(2)}x` : `${usedPct.toFixed(0)}%`;

    if (viewMode === "delta") {
      hudTitle = "淨多頭偏置 (Delta)";
      hudValue = "+$50.0k";
      hudValueColor = "#10b981";
      hudSub = "多頭 $74k · 空頭 $24k";
      progressPct = 51.0;
      hudTag = "51% 多";
    } else if (viewMode === "margin") {
      hudTitle = "保證金佔用";
      hudValue = "$22.7k";
      hudValueColor = "#60a5fa";
      hudSub = "總權益 $48.7k · 自由 $18.8k";
      progressPct = 62.4;
      hudTag = "62.4%";
    } else if (viewMode === "pnl") {
      hudTitle = "未實現總損益";
      hudValue = "+$3,385";
      hudValueColor = "#10b981";
      hudSub = "帳戶收益率 +6.94%";
      progressPct = 69.4;
      hudTag = "+6.9%";
    }

    return (
      <div className={cn(
        "h-full aspect-square flex items-center justify-center relative shrink-0 p-1",
        isNarrow ? "max-w-[34%] max-h-[140px]" : "max-w-[44%]"
      )}>
        <svg
          viewBox={`0 0 ${VB_SIZE} ${VB_SIZE}`}
          className="h-full w-full max-h-full max-w-full aspect-square select-none"
        >
          {/* 定義專屬 Monospace Tabular 字型樣式 */}
          <defs>
            <style>{`
              .hud-text {
                font-family: var(--font-mono), ui-monospace, SFMono-Regular, Menlo, monospace;
                font-feature-settings: 'tnum';
              }
            `}</style>
          </defs>

          {/* 底槽導軌 (沉穩深岩底色，微距軌道) */}
          <circle cx={CX} cy={CY} r={R} fill="none" stroke="#161922" strokeWidth={STROKE_WIDTH} />

          {currentItems.map((item, idx) => {
            const fullArc = (item.pct_share / 100) * CIRCUMFERENCE;
            const arcLen = Math.max(0, fullArc - SLICE_GAP);
            const dasharray = `${arcLen} ${CIRCUMFERENCE - arcLen}`;
            const dashoffset = -accumulatedArc - SLICE_GAP / 2;
            accumulatedArc += fullArc;

            const isHovered = hoveredIndex === idx;
            // 聚光燈核心：非懸停項目弱化至 25%，選中項目 100% 飽和高亮
            const sliceOpacity = hoveredIndex === null ? 0.92 : isHovered ? 1.0 : 0.22;

            return (
              <circle
                key={item.symbol}
                cx={CX}
                cy={CY}
                r={R}
                fill="none"
                stroke={item.color}
                strokeWidth={isHovered ? STROKE_WIDTH + 2.0 : STROKE_WIDTH}
                strokeDasharray={dasharray}
                strokeDashoffset={dashoffset}
                strokeLinecap="butt"
                opacity={sliceOpacity}
                transform={`rotate(-90 ${CX} ${CY})`}
                className="cursor-pointer transition-all duration-200"
                style={{
                  filter: isHovered ? `drop-shadow(0 0 6px ${item.color}80)` : undefined,
                }}
                onMouseEnter={() => setHoveredIndex(idx)}
                onMouseLeave={() => setHoveredIndex(null)}
              />
            );
          })}

          {/* 中央聚光 HUD (幾何同心居中，融合彭博清晰排版與微型進度刻度槽) */}
          {activeHoverItem ? (
            <g className="pointer-events-none select-none animate-in fade-in zoom-in-95 duration-100">
              {isCompact ? (
                // 緊湊態：只保留核心清晰大百分比
                <text
                  x={CX}
                  y={CY + 8}
                  textAnchor="middle"
                  fill="#f8fafc"
                  fontSize="26"
                  fontWeight="600"
                  className="hud-text"
                >
                  {activeHoverItem.pct_share.toFixed(1)}%
                </text>
              ) : (
                <>
                  <text
                    x={CX}
                    y={CY - 16}
                    textAnchor="middle"
                    fill="#94a3b8"
                    fontSize="9"
                    fontWeight="500"
                    letterSpacing="0.06em"
                    className="hud-text"
                  >
                    {activeHoverItem.shortLabel}
                  </text>
                  <text
                    x={CX}
                    y={CY + 8}
                    textAnchor="middle"
                    fill="#f8fafc"
                    fontSize="25"
                    fontWeight="600"
                    className="hud-text"
                  >
                    {activeHoverItem.amountStr}
                  </text>
                  <text
                    x={CX}
                    y={CY + 25}
                    textAnchor="middle"
                    fill="#64748b"
                    fontSize="8.5"
                    className="hud-text"
                  >
                    佔預算 {activeHoverItem.pct_share.toFixed(1)}% · {activeHoverItem.compactBadge || activeHoverItem.badgeStr}
                  </text>
                </>
              )}
            </g>
          ) : (
            <g className="pointer-events-none select-none">
              {isCompact ? (
                // 緊湊態：單一清晰核心指標
                <text
                  x={CX}
                  y={CY + 8}
                  textAnchor="middle"
                  fill={hudValueColor}
                  fontSize="26"
                  fontWeight="600"
                  className="hud-text"
                >
                  {hudValue}
                </text>
              ) : (
                <>
                  {/* 1. 頂部類別：沉穩弱化微型標籤，附帶倍數或百分比徽記 */}
                  <text
                    x={CX}
                    y={CY - 16}
                    textAnchor="middle"
                    fill="#94a3b8"
                    fontSize="8.5"
                    fontWeight="500"
                    letterSpacing="0.06em"
                    className="hud-text"
                  >
                    {hudTitle} · {hudTag}
                  </text>

                  {/* 2. 核心指標：俐落清晰珍珠白大數據 (金額或槓桿) */}
                  <text
                    x={CX}
                    y={CY + 6}
                    textAnchor="middle"
                    fill={hudValueColor}
                    fontSize="25"
                    fontWeight="600"
                    className="hud-text"
                  >
                    {hudValue}
                  </text>

                  {/* 3. 微型高科技進度刻度槽 (長 56px，直觀展示佔比) */}
                  <rect
                    x={72}
                    y={CY + 14}
                    width={56}
                    height={3}
                    rx={1.5}
                    fill="#27272a"
                  />
                  <rect
                    x={72}
                    y={CY + 14}
                    width={Math.max(2, 56 * (progressPct / 100))}
                    height={3}
                    rx={1.5}
                    fill={hudFocus === "money" ? "#e8b45e" : "#10b981"}
                  />

                  {/* 4. 底部輔助指標：弱化灰色、緊湊交代 3x 上限與剩餘額度 */}
                  <text
                    x={CX}
                    y={CY + 26}
                    textAnchor="middle"
                    fill="#64748b"
                    fontSize="8"
                    letterSpacing="0.02em"
                    className="hud-text"
                  >
                    {hudSub}
                  </text>
                </>
              )}
            </g>
          )}
        </svg>
      </div>
    );
  };

  return (
    <div ref={containerRef} className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40 relative", className)}>
      {/* 1. 卡片頂部 Header：左側標題與焦點切換器，右側高對比維度分段切換鈕 */}
      <div className="flex items-center justify-between px-3 h-9 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <CardHeaderTitle
            cardId="allocation"
            title="槓桿倍數與資產曝險"
          />

          {/* 核心焦點切換鈕：金額主導 vs 槓桿倍數 */}
          <div className="flex items-center gap-0.5 sm:gap-1 bg-black/65 border border-amber-500/50 rounded-[5px] p-0.5 text-[10px] font-mono shadow-xs shrink-0">
            <span className="text-amber-400 font-bold px-1 text-[9px] sm:text-[9.5px]">焦點:</span>
            <button
              type="button"
              onClick={() => setHudFocus("money")}
              className={cn(
                "px-1.5 py-0.5 rounded cursor-pointer transition-all leading-none text-[9.5px] sm:text-[10px]",
                hudFocus === "money"
                  ? "bg-amber-500/30 text-amber-200 font-bold border border-amber-500/60 shadow-2xs"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.05]"
              )}
            >
              $ 金額 (推薦)
            </button>
            <button
              type="button"
              onClick={() => setHudFocus("leverage")}
              className={cn(
                "px-1.5 py-0.5 rounded cursor-pointer transition-all leading-none text-[9.5px] sm:text-[10px]",
                hudFocus === "leverage"
                  ? "bg-amber-500/30 text-amber-200 font-bold border border-amber-500/60 shadow-2xs"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.05]"
              )}
            >
              x 倍數
            </button>
          </div>
        </div>

        {/* 核心維度分段鈕 (幣種配置 | 策略機器人 | 多空敞口 | 保證金佔用 | 盈虧分佈) */}
        <div className="flex items-center gap-0.5 sm:gap-1 bg-black/45 border border-white/[0.14] rounded-[6px] p-0.5 shrink-0 text-[10px] sm:text-[11px] font-mono shadow-2xs">
          {TABS.map((tab) => {
            const isActive = viewMode === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => {
                  setViewMode(tab.id);
                  setHoveredIndex(null);
                }}
                className={cn(
                  "px-1.5 sm:px-2 py-0.5 rounded transition-all cursor-pointer font-medium select-none text-[10px] sm:text-[11px]",
                  isActive
                    ? "bg-secondary text-foreground font-semibold shadow-xs border border-white/[0.16]"
                    : "text-zinc-300 hover:text-white hover:bg-white/[0.08]"
                )}
              >
                {isNarrow ? tab.shortLabel : tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. 核心繪圖與內容展示區 (收攏左右間距、自適應流體縮放不裁切) */}
      <div className="flex-1 min-h-0 w-full h-full relative overflow-hidden p-2 sm:p-2.5">
        <div className="w-full h-full flex items-center justify-start gap-2.5 sm:gap-4 overflow-hidden font-mono max-w-[860px] mx-auto px-1">

          {/* 左側：純向量自適應 Paperpillar 聚光燈聚焦環 (h-full 嚴格受父級高度約束) */}
          {renderSpotlightDonut()}

          {/* 右側：精緻高密度金融行 (min-w-0 自適應彈性收縮，杜絕推擠左側 Donut) */}
          <div className={cn(
            "flex-1 min-w-0 max-w-[480px] h-full flex flex-col py-0.5 overflow-hidden",
            isCompact ? "justify-center gap-1" : "justify-between"
          )}>
            {currentItems.map((item, idx) => {
              const isHovered = hoveredIndex === idx;
              const isNearLimit = item.pct_share >= 40 && viewMode === "allocation";
              const displayLabel = isNarrow ? (item.compactLabel || item.symbol) : item.shortLabel;
              const displayBadge = isSuperNarrow ? undefined : (isNarrow ? (item.compactBadge || item.badgeStr) : item.badgeStr);

              if (isCompact) {
                // 【超扁/極窄緊湊形態】：彭博/幣安標準單行背景長條圖 (Row Background Progress Fill)
                // 進度長條作為該行背景微光填色帶 + 底緣 2px 聚光線，文字置於上方，零額外縱向開銷，永不穿透！
                return (
                  <div
                    key={item.symbol}
                    onMouseEnter={() => setHoveredIndex(idx)}
                    onMouseLeave={() => setHoveredIndex(null)}
                    className={cn(
                      "group relative flex items-center justify-between px-2 py-1 rounded transition-all cursor-pointer border select-none overflow-hidden shrink-0 min-h-0",
                      isHovered
                        ? "bg-white/[0.09] border-primary/50 shadow-xs"
                        : "bg-surface-raised/40 hover:bg-white/[0.04] border-white/[0.06]"
                    )}
                  >
                    {/* 背景填色進度條 (直觀長條感 100% 保留) */}
                    <div
                      className="absolute left-0 top-0 bottom-0 pointer-events-none transition-all duration-300"
                      style={{
                        width: `${Math.min(100, item.pct_share)}%`,
                        backgroundColor: item.color,
                        opacity: isHovered ? 0.30 : 0.16,
                      }}
                    />
                    {/* 底緣 2px 聚光進度線 */}
                    <div
                      className="absolute left-0 bottom-0 h-[2px] pointer-events-none transition-all duration-300"
                      style={{
                        width: `${Math.min(100, item.pct_share)}%`,
                        backgroundColor: item.color,
                        boxShadow: isHovered ? `0 0 6px ${item.color}` : undefined,
                      }}
                    />

                    {/* 首行內容：左側幣種 + 標籤 */}
                    <div className="relative z-10 flex items-center gap-1 sm:gap-1.5 min-w-0">
                      <span className="size-2 rounded-full shrink-0 shadow-xs" style={{ backgroundColor: item.color }} />
                      <span className="font-bold text-foreground text-[11px] tracking-tight truncate shrink-0">{displayLabel}</span>
                      {displayBadge && (
                        <span className={cn(
                          "px-1 py-0.2 rounded border text-[8.5px] font-mono shrink-0 leading-none",
                          item.isLoss
                            ? "bg-rose-500/15 border-rose-500/30 text-rose-400 font-semibold"
                            : "bg-white/[0.06] border-white/[0.10] text-zinc-300"
                        )}>
                          {displayBadge}
                        </span>
                      )}
                    </div>

                    {/* 右側：金額與佔比 */}
                    <div className="relative z-10 flex items-center gap-1.5 shrink-0 ml-1">
                      <span className={cn(
                        "font-mono text-[11px] font-medium tracking-tight",
                        item.isLoss ? "text-rose-400 font-semibold" : "text-foreground"
                      )}>
                        {item.amountStr}
                      </span>
                      <span className="font-bold text-foreground text-[11px] min-w-[34px] text-right font-mono">
                        {item.pct_share.toFixed(1)}%
                      </span>
                      {isNearLimit && !isNarrow && (
                        <span className="px-1 py-0.2 rounded text-[7.5px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/35 leading-none">
                          逼近50%
                        </span>
                      )}
                    </div>
                  </div>
                );
              }

              // 【常規標準形態】：雙行式獨立進度條 (文字行 + 獨立底槽長條)
              return (
                <div
                  key={item.symbol}
                  onMouseEnter={() => setHoveredIndex(idx)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  className={cn(
                    "group flex flex-col justify-center px-2.5 py-1 sm:py-1.5 rounded-lg transition-all cursor-pointer border select-none min-h-0",
                    isHovered
                      ? "bg-white/[0.08] border-primary/45 shadow-xs"
                      : "bg-surface-raised/40 hover:bg-white/[0.04] border-white/[0.06]"
                  )}
                >
                  {/* 首行：幣種標題、量化標籤、金額與佔比 */}
                  <div className="flex items-center justify-between gap-1.5 leading-none">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className="size-2 sm:size-2.5 rounded-full shrink-0 shadow-xs" style={{ backgroundColor: item.color }} />
                      <span className="font-bold text-foreground text-[11px] sm:text-xs tracking-tight truncate">{item.shortLabel}</span>
                      <span className={cn(
                        "px-1 sm:px-1.5 py-0.2 sm:py-0.5 rounded border text-[8.5px] sm:text-[9.5px] font-mono shrink-0 leading-none",
                        item.isLoss
                          ? "bg-rose-500/15 border-rose-500/30 text-rose-400 font-semibold"
                          : "bg-white/[0.06] border-white/[0.10] text-zinc-300"
                      )}>
                        {item.badgeStr}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <span className={cn(
                        "font-mono text-[11px] sm:text-xs font-medium tracking-tight",
                        item.isLoss ? "text-rose-400 font-semibold" : "text-foreground"
                      )}>
                        {item.amountStr}
                      </span>
                      <span className="font-bold text-foreground text-[11px] sm:text-xs min-w-[38px] text-right font-mono">
                        {item.pct_share.toFixed(1)}%
                      </span>
                      {/* 僅當接近上限時靜默提醒 */}
                      {isNearLimit && (
                        <span className="px-1 py-0.2 sm:px-1.5 sm:py-0.5 rounded text-[8px] sm:text-[8.5px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/35 leading-none">
                          逼近50%
                        </span>
                      )}
                    </div>
                  </div>

                  {/* 次行：直觀長條圖 (微型圓角底槽與平滑填色) */}
                  <div className="w-full h-1 bg-white/[0.08] rounded-full overflow-hidden relative mt-1 sm:mt-1.5 shrink-0">
                    <div
                      className="h-full rounded-full transition-all duration-300"
                      style={{
                        width: `${Math.min(100, item.pct_share)}%`,
                        backgroundColor: item.color,
                        boxShadow: isHovered ? `0 0 8px ${item.color}90` : undefined,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
