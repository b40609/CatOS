import { useState, useMemo, useRef, useEffect } from "react";
import { CardHeaderTitle } from "./card-header-title";
import { cn } from "@/lib/utils";
import { useCatStore } from "@/state/catStore";
import type { BotControlState, DecimalString, PositionDTO, RiskStatus } from "@/contracts";
import { formatDecimal, formatRatioPct, signOf, toPlotNumber } from "@/lib/format";

// 定案配色：低彩度、高質感的資料系列色
const COLORS = {
  position: "#e8b45e",  // 持倉 蜂蜜金
  budget: "#10b981",    // 未用預算 / 多頭 翡翠綠
  short: "#f43f5e",     // 空頭 / 虧損 玫瑰紅
  fee: "#71717a",       // 手續費 費用灰
  neutral: "#a1a1aa",   // 中性 鋅灰
  muted: "#27272a",     // 不適用 / 尚無觀測 啞光槽
};

// 策略實例依序循環的系列色（不綁定任何幣種）
const BOT_PALETTE = ["#e8b45e", "#7faee2", "#8b8df8", "#a1a1aa", "#f59e0b"];

interface DonutItem {
  key: string;
  shortLabel: string;
  compactLabel?: string; // 窄版極簡標籤
  sub: string;
  amount: DecimalString | null; // 後端 Decimal 字串；null 代表不適用
  amountStr: string;            // 顯示文字，一律由後端字串 formatDecimal 或明示文字而來
  pct_share: number;            // 0..100，僅供幾何（弧長／進度條／佔比標籤）
  color: string;
  badgeStr: string;
  compactBadge?: string;
  isLoss?: boolean;
  nearLimit?: boolean; // 逼近單幣上限提示
  hidePct?: boolean;   // 非比例型資料（布林事實／空狀態）不顯示百分比
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
const HUD_INNER_WIDTH = 140; // 環內可用文字寬度

export type DonutViewMode = "allocation" | "bots" | "delta" | "margin" | "pnl";
export type HudFocus = "money" | "leverage";

// 定案全 5 大核心維度分段標籤 (寬版完整名，窄版自動簡寫為 2 字標籤節省空間)
const TABS: { id: DonutViewMode; label: string; shortLabel: string }[] = [
  { id: "allocation", label: "幣種配置", shortLabel: "幣種" },
  { id: "bots", label: "策略實例", shortLabel: "實例" },
  { id: "delta", label: "多空部位曝險", shortLabel: "曝險" },
  { id: "margin", label: "保證金佔用", shortLabel: "保證金" },
  { id: "pnl", label: "損益分佈", shortLabel: "損益" },
];

const SHARE_CAPTION: Record<DonutViewMode, string> = {
  allocation: "佔預算",
  bots: "佔預算",
  delta: "佔總曝險",
  margin: "",
  pnl: "佔損益規模",
};

const BOT_STATE_LABEL: Record<BotControlState, string> = {
  starting: "啟動中",
  running: "運行中",
  stopping: "停止中",
  completed: "已完成",
  stopped: "已停止",
  failed: "失敗",
  recovery_required: "待恢復",
};

const RISK_STATUS_CHIP: Record<RiskStatus, { label: string; className: string }> = {
  normal: { label: "正常", className: "bg-emerald-500/15 border-emerald-500/35 text-emerald-400" },
  soft_latch: { label: "軟鎖存", className: "bg-amber-500/15 border-amber-500/35 text-amber-400" },
  hard_latch: { label: "硬鎖存", className: "bg-rose-500/15 border-rose-500/35 text-rose-400" },
  missing: { label: "缺基準", className: "bg-zinc-500/15 border-zinc-500/35 text-zinc-400" },
};
const NO_OBSERVATION_CHIP = { label: "尚無觀測", className: "bg-zinc-500/15 border-zinc-500/35 text-zinc-400" };

const TEXT_UNAVAILABLE = "不適用";
const TEXT_NO_RISK = "尚無風控觀測";
const TEXT_NO_RISK_SUB = "啟動模擬 run 後顯示";
const TEXT_MODE_NOT_OPEN = "此模式未開放（demo/live 不在 v1 範圍）";

/**
 * 圖形幾何專用：part 佔 whole 的百分比 (0..100)。
 * 這是本卡片唯一的 Decimal → float 轉換點（經 toPlotNumber），只用來決定弧長、
 * 進度條寬度與「佔比 x%」標籤；結果不得回流為任何金額、帳務或風控依據。
 * whole 為 null／0／非數字時回傳 0。
 */
function shareOf(part: DecimalString | null | undefined, whole: DecimalString | null | undefined): number {
  return sharePlot(toPlotNumber(part), toPlotNumber(whole));
}

/** shareOf 的數值核心；僅供損益分佈以 toPlotNumber 合計的幾何分母重用。 */
function sharePlot(part: number, whole: number): number {
  if (!Number.isFinite(part) || !Number.isFinite(whole) || whole === 0) return 0;
  const pct = (Math.abs(part) / Math.abs(whole)) * 100;
  if (!Number.isFinite(pct)) return 0;
  return Math.min(100, Math.max(0, pct));
}

/** 槓桿倍數文字：null → 不適用，否則 "1.23x"。 */
function leverageText(value: DecimalString | null | undefined): string {
  const text = formatDecimal(value, { digits: 2 });
  return text === TEXT_UNAVAILABLE ? text : `${text}x`;
}

/** 依字數讓 HUD 文字落在環內寬度（CJK 1em、其餘 0.62em），上限為原設計字級。 */
function hudFontSize(text: string, max: number): number {
  let units = 0;
  for (const ch of text) units += /[　-鿿＀-￯]/.test(ch) ? 1 : 0.62;
  if (units === 0) return max;
  return Math.max(8, Math.min(max, Math.floor(HUD_INNER_WIDTH / units)));
}

/**
 * 槓桿倍數與資產曝險卡片 (AllocationDonutCard)
 * - 徹底移除底部枯燥的 4 塊文字小框，將垂直空間 100% 留給圓環與清單
 * - 定案全 5 大維度即時切換：【幣種配置 | 策略實例 | 多空部位曝險 | 保證金佔用 | 損益分佈】
 * - 融合彭博高對比字體與微型進度刻度，支持【$ 金額主導】與【x 槓桿倍數】雙重直觀焦點
 * - 資料全部來自 useCatStore 的後端投影（risk／summary／bots／positions），金額不在前端運算
 */
export function AllocationDonutCard({ className }: { className?: string }) {
  const [viewMode, setViewMode] = useState<DonutViewMode>("allocation");
  const [hudFocus, setHudFocus] = useState<HudFocus>("leverage");
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

  const risk = useCatStore((s) => s.risk);
  const summary = useCatStore((s) => s.summary);
  const bots = useCatStore((s) => s.bots);
  const positions = useCatStore((s) => s.positions);
  const connectionStatus = useCatStore((s) => s.connection.status);

  const modeNotOpen = connectionStatus === "mode_not_open";
  const unavailableText = modeNotOpen ? TEXT_MODE_NOT_OPEN : TEXT_NO_RISK;
  const unavailableSub = modeNotOpen ? "v1 僅提供 local-sim" : TEXT_NO_RISK_SUB;

  const derived = risk?.derived ?? null;
  const limits = risk?.limits ?? null;
  const notional = derived?.notional ?? null;
  const exposureBudget = derived?.exposure_budget ?? null;
  const symbolBudget = derived?.symbol_budget ?? null;
  const effectiveLeverage = derived?.effective_leverage ?? null;

  // 幾何：名目佔總預算／單幣預算比例
  const notionalShare = shareOf(notional, exposureBudget);
  const symbolShare = shareOf(notional, symbolBudget);
  const nearSymbolLimit = symbolShare >= 80;

  // 空狀態：單一啞光切片 + 明示文字
  const unavailableItems: DonutItem[] = useMemo(() => [
    {
      key: "unavailable",
      shortLabel: unavailableText,
      compactLabel: modeNotOpen ? "未開放" : "尚無觀測",
      sub: unavailableSub,
      amount: null,
      amountStr: unavailableSub,
      pct_share: 100,
      color: COLORS.muted,
      badgeStr: "local-sim",
      compactBadge: "local",
      hidePct: true,
    },
  ], [unavailableText, unavailableSub, modeNotOpen]);

  // 「未用預算」共用項目（幣種配置／策略實例）
  const budgetItem: DonutItem = useMemo(() => ({
    key: "budget",
    shortLabel: "未用預算",
    compactLabel: "預算",
    sub: "緩衝",
    amount: null,
    amountStr: `預算 ${formatDecimal(exposureBudget, { prefix: "$" })}`,
    pct_share: Math.max(0, 100 - notionalShare),
    color: COLORS.budget,
    badgeStr: `單幣 ${formatDecimal(symbolBudget, { prefix: "$" })}`,
    compactBadge: "上限",
  }), [exposureBudget, symbolBudget, notionalShare]);

  // 持倉所屬合約（由 risk.bot_id 對應的 Bot／部位取得，不寫死幣種）
  const ownerBot = useMemo(() => bots.find((b) => b.bot_id === risk?.bot_id) ?? null, [bots, risk?.bot_id]);
  const ownerInstId = ownerBot?.inst_id
    ?? positions.find((p) => p.bot_id === risk?.bot_id)?.inst_id
    ?? null;

  // 1. 維度：幣種配置 (Notional Exposure · 名目曝險與預算佔比)
  const allocationItems: DonutItem[] = useMemo(() => {
    if (!risk) return unavailableItems;
    return [
      {
        key: "position",
        shortLabel: ownerInstId ? `${ownerInstId} 持倉` : "持倉",
        compactLabel: ownerInstId ?? "持倉",
        sub: "持倉",
        amount: notional,
        amountStr: formatDecimal(notional, { prefix: "$" }),
        pct_share: notionalShare,
        color: COLORS.position,
        badgeStr: `${leverageText(effectiveLeverage)} 槓桿`,
        compactBadge: leverageText(effectiveLeverage),
        nearLimit: nearSymbolLimit,
      },
      budgetItem,
    ];
  }, [risk, unavailableItems, ownerInstId, notional, notionalShare, effectiveLeverage, nearSymbolLimit, budgetItem]);

  // 2. 維度：策略實例 (Bot Allocation · 每個 Bot 一列，僅風控快照所屬 Bot 有名目)
  const botItems: DonutItem[] = useMemo(() => {
    if (!risk) return unavailableItems;
    const rows: DonutItem[] = bots.map((bot, idx) => {
      const owns = bot.bot_id === risk.bot_id;
      const amount = owns ? notional : null;
      return {
        key: `bot:${bot.bot_id}`,
        shortLabel: bot.bot_id,
        compactLabel: bot.bot_id,
        sub: bot.strategy_name,
        amount,
        amountStr: formatDecimal(amount, { prefix: "$" }),
        pct_share: owns ? notionalShare : 0,
        color: BOT_PALETTE[idx % BOT_PALETTE.length],
        badgeStr: BOT_STATE_LABEL[bot.state] ?? bot.state,
        compactBadge: BOT_STATE_LABEL[bot.state] ?? bot.state,
        nearLimit: owns && nearSymbolLimit,
      };
    });
    if (rows.length === 0) {
      rows.push({
        key: "no-bots",
        shortLabel: "尚無策略實例",
        compactLabel: "無實例",
        sub: "實例",
        amount: null,
        amountStr: TEXT_UNAVAILABLE,
        pct_share: 0,
        color: COLORS.neutral,
        badgeStr: "未啟用",
        hidePct: true,
      });
    }
    rows.push(budgetItem);
    return rows;
  }, [risk, unavailableItems, bots, notional, notionalShare, nearSymbolLimit, budgetItem]);

  // 3. 維度：多空部位曝險 (Long / Short Delta · 依 positions[] 方向拆分)
  const deltaItems: DonutItem[] = useMemo(() => {
    if (!risk) return unavailableItems;
    const open = positions.filter((p) => {
      const sign = signOf(p.position);
      return sign === "positive" || sign === "negative";
    });
    if (open.length === 0) {
      return [{
        key: "flat",
        shortLabel: "空倉",
        compactLabel: "空倉",
        sub: "FLAT",
        amount: null,
        amountStr: "無部位曝險",
        pct_share: 100,
        color: COLORS.neutral,
        badgeStr: "無方向",
        hidePct: true,
      }];
    }
    // 幾何分母：各部位名目絕對值合計（僅經 toPlotNumber，不作金額顯示）
    const gross = open.reduce((acc, p) => {
      const n = toPlotNumber(p.notional);
      return acc + (Number.isFinite(n) ? Math.abs(n) : 0);
    }, 0);
    return open.map((p: PositionDTO) => {
      const isLong = signOf(p.position) === "positive";
      const name = p.inst_id ?? p.bot_id;
      return {
        key: `pos:${p.bot_id}:${p.inst_id ?? ""}`,
        shortLabel: `${name} ${isLong ? "多頭" : "空頭"}`,
        compactLabel: isLong ? "多頭" : "空頭",
        sub: isLong ? "LONG" : "SHORT",
        amount: p.notional,
        amountStr: formatDecimal(p.notional, { prefix: "$" }),
        pct_share: sharePlot(toPlotNumber(p.notional), gross),
        color: isLong ? COLORS.budget : COLORS.short,
        badgeStr: `部位 ${formatDecimal(p.position, { sign: true, digits: 4 })}`,
        compactBadge: isLong ? "LONG" : "SHORT",
        isLoss: !isLong,
      };
    });
  }, [risk, unavailableItems, positions]);

  // 4. 維度：保證金佔用 — v1 local-sim 無保證金模型，只呈現 margin_ok 布林事實
  const marginItems: DonutItem[] = useMemo(() => {
    if (!risk) return unavailableItems;
    const marginOk = risk.snapshot?.margin_ok;
    const verdict = marginOk === undefined ? TEXT_UNAVAILABLE : marginOk ? "通過" : "未通過";
    return [{
      key: "margin_ok",
      shortLabel: `保證金檢查：${verdict}`,
      compactLabel: "保證金",
      sub: "margin_ok",
      amount: null,
      amountStr: verdict,
      pct_share: 100,
      color: marginOk === false ? COLORS.short : COLORS.muted,
      badgeStr: "local-sim 無保證金模型",
      compactBadge: verdict,
      isLoss: marginOk === false,
      hidePct: true,
    }];
  }, [risk, unavailableItems]);

  // 5. 維度：損益分佈 (PnL Contribution · 已實現／未實現／手續費)
  const pnlItems: DonutItem[] = useMemo(() => {
    if (!summary) return unavailableItems;
    const realized = summary.realized_pnl;
    const unrealized = summary.unrealized_pnl;
    const fees = summary.fees;
    // 幾何分母：三項絕對值合計（僅經 toPlotNumber，不作金額顯示）
    const parts = [realized, unrealized, fees].map((v) => {
      const n = toPlotNumber(v);
      return Number.isFinite(n) ? Math.abs(n) : 0;
    });
    const total = parts[0] + parts[1] + parts[2];
    const toneColor = (v: DecimalString) => {
      const sign = signOf(v);
      return sign === "positive" ? COLORS.budget : sign === "negative" ? COLORS.short : COLORS.neutral;
    };
    // 手續費為成本：後端字串非零且為正時，顯示加上 "-" 前綴（僅符號呈現，無運算）
    const feeSign = signOf(fees);
    const feeFormatted = formatDecimal(fees, { prefix: "$" });
    const feeStr = feeSign === "positive" ? `-${feeFormatted}` : feeFormatted;
    return [
      {
        key: "realized",
        shortLabel: "已實現損益",
        compactLabel: "已實現",
        sub: "REALIZED",
        amount: realized,
        amountStr: formatDecimal(realized, { sign: true, prefix: "$" }),
        pct_share: sharePlot(parts[0], total),
        color: toneColor(realized),
        badgeStr: "已結算",
        compactBadge: "已結",
        isLoss: signOf(realized) === "negative",
      },
      {
        key: "unrealized",
        shortLabel: "未實現損益",
        compactLabel: "未實現",
        sub: "UNREALIZED",
        amount: unrealized,
        amountStr: formatDecimal(unrealized, { sign: true, prefix: "$" }),
        pct_share: sharePlot(parts[1], total),
        color: toneColor(unrealized),
        badgeStr: "浮動",
        compactBadge: "浮動",
        isLoss: signOf(unrealized) === "negative",
      },
      {
        key: "fees",
        shortLabel: "手續費成本",
        compactLabel: "手續費",
        sub: "FEE",
        amount: fees,
        amountStr: feeStr,
        pct_share: sharePlot(parts[2], total),
        color: COLORS.fee,
        badgeStr: "累計成本",
        compactBadge: "成本",
        isLoss: feeSign !== "zero",
      },
    ];
  }, [summary, unavailableItems]);

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

  const activeHoverItem = hoveredIndex !== null ? currentItems[hoveredIndex] ?? null : null;

  // Header 風控狀態晶片
  const statusChip = risk ? RISK_STATUS_CHIP[risk.derived.status] ?? NO_OBSERVATION_CHIP : NO_OBSERVATION_CHIP;
  const statusTooltip = risk
    ? [risk.derived.can_increase ? "可增倉" : "禁增倉", risk.reasons.join(",")].filter(Boolean).join(" · ")
    : unavailableSub;

  const leverageLimitText = limits ? `${formatDecimal(limits.leverage, { digits: 1 })}x` : TEXT_UNAVAILABLE;
  const symbolShareText = limits ? formatRatioPct(limits.symbol_share, { sign: false }) : TEXT_UNAVAILABLE;

  // =========================================================================
  // 定案圓環：Paperpillar 聚光燈聚焦環 (純向量自適應渲染，依模式切換 HUD 資訊)
  // =========================================================================
  const renderSpotlightDonut = () => {
    let accumulatedArc = 0;

    // 中央 HUD 標題與數值計算 (依 Bloomberg / TradingView 金額與倍數雙錨定法則)
    let hudTitle = hudFocus === "leverage" ? "帳戶有效槓桿" : "名目持倉總值";
    let hudValue = hudFocus === "leverage"
      ? leverageText(effectiveLeverage)
      : formatDecimal(notional, { prefix: "$" });
    let hudValueColor = "#f8fafc"; // 專業中性珍珠白，高對比無光暈
    let hudSub = hudFocus === "leverage"
      ? `上限 ${leverageLimitText} · 單幣 ${symbolShareText}`
      : `總預算 ${formatDecimal(exposureBudget, { prefix: "$" })}`;
    let progressPct = notionalShare;
    let hudTag = hudFocus === "leverage" ? `${notionalShare.toFixed(0)}% 預算` : leverageText(effectiveLeverage);
    let progressColor = hudFocus === "money" ? "#e8b45e" : "#10b981";

    if (viewMode === "delta") {
      const dirSign = signOf(risk?.snapshot?.position ?? null);
      hudTitle = "淨方向";
      hudValue = dirSign === "positive" ? "多頭" : dirSign === "negative" ? "空頭" : "空倉";
      hudValueColor = dirSign === "positive" ? "#10b981" : dirSign === "negative" ? "#f43f5e" : "#a1a1aa";
      hudSub = `名目 ${formatDecimal(notional, { prefix: "$" })}`;
      progressPct = notionalShare;
      hudTag = `${notionalShare.toFixed(0)}% 預算`;
      progressColor = hudValueColor;
    } else if (viewMode === "margin") {
      hudTitle = "保證金佔用";
      hudValue = TEXT_UNAVAILABLE;
      hudValueColor = "#a1a1aa";
      hudSub = "local-sim 無保證金模型";
      progressPct = 0;
      hudTag = "v1";
      progressColor = COLORS.muted;
    } else if (viewMode === "pnl") {
      const pnl = summary?.period_pnl ?? null;
      const ratio = summary?.period_pnl_ratio ?? null;
      const sign = signOf(pnl);
      hudTitle = "風控期間損益";
      hudValue = formatDecimal(pnl, { sign: true, prefix: "$" });
      hudValueColor = sign === "positive" ? "#10b981" : sign === "negative" ? "#f43f5e" : "#f8fafc";
      hudSub = `${formatRatioPct(ratio)} · 權益 ${formatDecimal(summary?.equity ?? null, { prefix: "$" })}`;
      // 幾何：虧損比例相對硬熔斷門檻的進度（僅虧損時有意義）
      progressPct = sign === "negative" ? shareOf(ratio, limits?.hard_loss ?? null) : 0;
      hudTag = formatRatioPct(ratio);
      progressColor = hudValueColor;
    }

    // 空狀態覆寫（損益分佈看 summary，其餘看 risk）
    const hudUnavailable = viewMode === "pnl" ? summary === null : risk === null;
    if (hudUnavailable) {
      hudTitle = viewMode === "pnl" ? "風控期間損益" : hudTitle;
      hudValue = unavailableText;
      hudValueColor = "#a1a1aa";
      hudSub = unavailableSub;
      progressPct = 0;
      hudTag = "local-sim";
      progressColor = COLORS.muted;
    }

    const shareCaption = SHARE_CAPTION[viewMode];

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
                key={item.key}
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
                // 緊湊態：只保留核心清晰大百分比（非比例型項目改顯示其文字）
                <text
                  x={CX}
                  y={CY + 8}
                  textAnchor="middle"
                  fill="#f8fafc"
                  fontSize={activeHoverItem.hidePct ? hudFontSize(activeHoverItem.amountStr, 26) : 26}
                  fontWeight="600"
                  className="hud-text"
                >
                  {activeHoverItem.hidePct ? activeHoverItem.amountStr : `${activeHoverItem.pct_share.toFixed(1)}%`}
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
                    fontSize={hudFontSize(activeHoverItem.amountStr, 25)}
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
                    {activeHoverItem.hidePct || !shareCaption
                      ? (activeHoverItem.compactBadge || activeHoverItem.badgeStr)
                      : `${shareCaption} ${activeHoverItem.pct_share.toFixed(1)}% · ${activeHoverItem.compactBadge || activeHoverItem.badgeStr}`}
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
                  fontSize={hudFontSize(hudValue, 26)}
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
                    fontSize={hudFontSize(hudValue, 25)}
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
                    width={Math.max(2, 56 * (Math.min(100, progressPct) / 100))}
                    height={3}
                    rx={1.5}
                    fill={progressColor}
                  />

                  {/* 4. 底部輔助指標：弱化灰色、緊湊交代上限與預算 */}
                  <text
                    x={CX}
                    y={CY + 26}
                    textAnchor="middle"
                    fill="#64748b"
                    fontSize={hudFontSize(hudSub, 8)}
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
      {/* 1. 卡片頂部 Header：左側標題、風控狀態晶片與焦點切換器，右側高對比維度分段切換鈕 */}
      <div className="flex items-center justify-between px-3 h-9 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <CardHeaderTitle
            cardId="allocation"
            title="槓桿倍數與資產曝險"
            subtext={
              <span
                className={cn(
                  "px-1.5 py-0.5 rounded border text-t1 font-mono font-semibold leading-none shrink-0 whitespace-nowrap",
                  statusChip.className
                )}
                title={statusTooltip}
              >
                {statusChip.label}
              </span>
            }
          />

          {/* 核心焦點切換鈕：金額主導 vs 槓桿倍數 */}
          <div className="flex items-center gap-0.5 bg-background/60 border border-border/60 rounded p-0.5 shrink-0 text-t2 font-mono">
            <span className="text-amber-400 font-bold px-1 text-t1 sm:text-t1">焦點:</span>
            <button
              type="button"
              onClick={() => setHudFocus("leverage")}
              className={cn(
                "px-2 py-0.5 text-t2 font-mono rounded transition-colors cursor-pointer whitespace-nowrap shrink-0",
                hudFocus === "leverage"
                  ? "bg-secondary text-foreground font-semibold shadow-xs"
                  : "text-muted-foreground hover:text-foreground"
              )}
              title={`風控焦點：帳戶有效槓桿 (上限 ${leverageLimitText})`}
            >
              x 槓桿
            </button>
            <button
              type="button"
              onClick={() => setHudFocus("money")}
              className={cn(
                "px-2 py-0.5 text-t2 font-mono rounded transition-colors cursor-pointer whitespace-nowrap shrink-0",
                hudFocus === "money"
                  ? "bg-secondary text-foreground font-semibold shadow-xs"
                  : "text-muted-foreground hover:text-foreground"
              )}
              title="資產焦點：名目持倉總額與總曝險預算"
            >
              $ 名目
            </button>
          </div>
        </div>

        {/* 核心維度分段鈕 (幣種配置 | 策略實例 | 多空部位曝險 | 保證金佔用 | 損益分佈) */}
        <div className="flex items-center gap-0.5 bg-background/60 border border-border/60 rounded p-0.5 shrink-0 text-t2 font-mono">
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
                  "px-1.5 sm:px-2 py-0.5 rounded transition-all cursor-pointer font-medium select-none text-t2 sm:text-t3",
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
              const isNearLimit = item.nearLimit === true;
              const displayLabel = isNarrow ? (item.compactLabel || item.shortLabel) : item.shortLabel;
              const displayBadge = isSuperNarrow ? undefined : (isNarrow ? (item.compactBadge || item.badgeStr) : item.badgeStr);

              if (isCompact) {
                // 【超扁/極窄緊湊形態】：彭博/幣安標準單行背景長條圖 (Row Background Progress Fill)
                // 進度長條作為該行背景微光填色帶 + 底緣 2px 聚光線，文字置於上方，零額外縱向開銷，永不穿透！
                return (
                  <div
                    key={item.key}
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

                    {/* 首行內容：左側標籤 + 徽章 */}
                    <div className="relative z-10 flex items-center gap-1 sm:gap-1.5 min-w-0">
                      <span className="size-2 rounded-full shrink-0 shadow-xs" style={{ backgroundColor: item.color }} />
                      <span className="font-bold text-foreground text-t3 tracking-tight truncate shrink-0">{displayLabel}</span>
                      {displayBadge && (
                        <span className={cn(
                          "px-1 py-0.2 rounded border text-t1 font-mono shrink-0 leading-none",
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
                        "font-mono text-t3 font-medium tracking-tight",
                        item.isLoss ? "text-rose-400 font-semibold" : "text-foreground"
                      )}>
                        {item.amountStr}
                      </span>
                      {!item.hidePct && (
                        <span className="font-bold text-foreground text-t3 min-w-[34px] text-right font-mono">
                          {item.pct_share.toFixed(1)}%
                        </span>
                      )}
                      {isNearLimit && !isNarrow && (
                        <span className="px-1 py-0.2 rounded text-t1 font-bold bg-amber-500/20 text-amber-400 border border-amber-500/35 leading-none">
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
                  key={item.key}
                  onMouseEnter={() => setHoveredIndex(idx)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  className={cn(
                    "group flex flex-col justify-center px-2.5 py-1 sm:py-1.5 rounded-lg transition-all cursor-pointer border select-none min-h-0",
                    isHovered
                      ? "bg-white/[0.08] border-primary/45 shadow-xs"
                      : "bg-surface-raised/40 hover:bg-white/[0.04] border-white/[0.06]"
                  )}
                >
                  {/* 首行：標題、量化標籤、金額與佔比 */}
                  <div className="flex items-center justify-between gap-1.5 leading-none">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className="size-2 sm:size-2.5 rounded-full shrink-0 shadow-xs" style={{ backgroundColor: item.color }} />
                      <span className="font-bold text-foreground text-t3 sm:text-xs tracking-tight whitespace-nowrap shrink-0">{item.shortLabel}</span>
                      <span className={cn(
                        "px-1 sm:px-1.5 py-0.2 sm:py-0.5 rounded border text-t1 sm:text-t1 font-mono shrink-0 leading-none",
                        item.isLoss
                          ? "bg-rose-500/15 border-rose-500/30 text-rose-400 font-semibold"
                          : "bg-white/[0.06] border-white/[0.10] text-zinc-300"
                      )}>
                        {item.badgeStr}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <span className={cn(
                        "font-mono text-t3 sm:text-xs font-medium tracking-tight",
                        item.isLoss ? "text-rose-400 font-semibold" : "text-foreground"
                      )}>
                        {item.amountStr}
                      </span>
                      {!item.hidePct && (
                        <span className="font-bold text-foreground text-t3 sm:text-xs min-w-[38px] text-right font-mono">
                          {item.pct_share.toFixed(1)}%
                        </span>
                      )}
                      {/* 僅當逼近單幣上限時靜默提醒 */}
                      {isNearLimit && (
                        <span className="px-1 py-0.2 sm:px-1.5 sm:py-0.5 rounded text-t1 sm:text-t1 font-bold bg-amber-500/20 text-amber-400 border border-amber-500/35 leading-none">
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
