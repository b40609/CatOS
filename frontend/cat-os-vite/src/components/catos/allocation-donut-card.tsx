import { useState, useMemo, useRef, useEffect } from "react";
import { CardHeaderTitle } from "./card-header-title";
import { cn } from "@/lib/utils";
import { useCatStore } from "@/state/catStore";
import type { BotControlState, DecimalString, PositionDTO, RiskStatus } from "@/contracts";
import { formatDecimal, formatRatioPct, signOf, toPlotNumber } from "@/lib/format";

// 定案配色：Noir & Gold 低彩度金融色板
const COLORS = {
  position: "#e8b45e", // 蜂蜜金
  second: "#7faee2",   // 霧藍
  violet: "#8b8df8",   // 靜藍紫
  budget: "#10b981",   // 多頭 / 翡翠綠
  short: "#f43f5e",    // 空頭 / 虧損 玫瑰紅
  fee: "#71717a",      // 手續費 費用灰
  neutral: "#a1a1aa",  // 中性 鋅灰
  rem: "#3f3f46",      // 剩餘可用額度（啞灰槽）
  muted: "#27272a",    // 尚無觀測
};

const BOT_PALETTE = ["#e8b45e", "#7faee2", "#8b8df8", "#10b981", "#f59e0b"];

interface DonutItem {
  key: string;
  shortLabel: string;
  compactLabel?: string;
  sub: string;
  amount: DecimalString | null; // 後端 Decimal 字串；null 代表不適用或非單一金額
  amountStr: string;
  pct_share: number; // 0..100，僅供幾何（弧長／佔比標籤）
  color: string;
  badgeStr: string;
  compactBadge?: string;
  isLoss?: boolean;
  isMuted?: boolean;
  nearLimit?: boolean;
  hidePct?: boolean;
}

// 向量坐標系幾何常量 (200x200 viewBox，Y 版俐落厚環＋寬敞中央數字區)
const VB_SIZE = 200;
const CX = 100;
const CY = 100;
const R = 74;
const STROKE_WIDTH = 13.5;
const CIRCUMFERENCE = 2 * Math.PI * R;
const SLICE_GAP = 2.6;
const HUD_INNER_WIDTH = 132;

export type DonutViewMode = "bots" | "allocation" | "delta" | "pnl" | "margin";
export type HudUnit = "pct" | "leverage" | "money";

// 1A 定案 5 大視角：策略（預設）｜幣種｜多空｜損益｜保證金
const TABS: { id: DonutViewMode; label: string }[] = [
  { id: "bots", label: "策略" },
  { id: "allocation", label: "幣種" },
  { id: "delta", label: "多空" },
  { id: "pnl", label: "損益" },
  { id: "margin", label: "保證金" },
];

const VIEW_CAPTION: Record<DonutViewMode, string> = {
  bots: "依策略拆解單幣額度",
  allocation: "跨策略單幣集中度檢查",
  delta: "全帳戶多空方向淨曝險",
  pnl: "已實現與持倉浮盈結構",
  margin: "帳戶保證金模型狀態",
};

const SHARE_CAPTION: Record<DonutViewMode, string> = {
  bots: "佔額度",
  allocation: "佔單幣上限",
  delta: "佔總曝險",
  pnl: "佔損益規模",
  margin: "",
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
 * 這是本卡片唯一的 Decimal → float 轉換點（經 toPlotNumber），僅用於弧長與佔比標籤，
 * 結果不得回流為任何金額、帳務或風控依據。
 */
function shareOf(part: DecimalString | null | undefined, whole: DecimalString | null | undefined): number {
  return sharePlot(toPlotNumber(part), toPlotNumber(whole));
}

function sharePlot(part: number, whole: number): number {
  if (!Number.isFinite(part) || !Number.isFinite(whole) || whole === 0) return 0;
  const pct = (Math.abs(part) / Math.abs(whole)) * 100;
  if (!Number.isFinite(pct)) return 0;
  return Math.min(100, Math.max(0, pct));
}

function leverageText(value: DecimalString | null | undefined): string {
  const text = formatDecimal(value, { digits: 2 });
  return text === TEXT_UNAVAILABLE ? text : `${text}x`;
}

function magnitude(value: string): string {
  return value.trim().replace(/^[+-]/, "");
}

function hudFontSize(text: string, max: number): number {
  let units = 0;
  for (const ch of text) units += /[　-鿿＀-￯]/.test(ch) ? 1 : 0.62;
  if (units === 0) return max;
  return Math.max(9, Math.min(max, Math.floor(HUD_INNER_WIDTH / units)));
}

function nextHudUnit(unit: HudUnit): HudUnit {
  return unit === "pct" ? "leverage" : unit === "leverage" ? "money" : "pct";
}

/**
 * 曝險額度卡片 (1A 定案：Y 風格底版 × 5 大視角切換 × 點擊圓環切換 % / x / $)
 * - 標題列精簡無冗餘單位切換鈕，直接點擊圓環本體循環切換 % → x → $
 * - 預設「策略」視角：中央單一大數字＋副標、按策略拆解明細列、底部單行額度公式
 * - 所有金額皆直接格式化後端 Decimal 字串，不在前端進行帳務浮點運算
 */
export function AllocationDonutCard({ className }: { className?: string }) {
  const [viewMode, setViewMode] = useState<DonutViewMode>("bots");
  const [hudUnit, setHudUnit] = useState<HudUnit>("pct");
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 580, height: 260 });

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

  const isNarrow = dimensions.width < 450;
  const isSuperNarrow = dimensions.width < 340;
  const isShort = dimensions.height < 185;
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

  // 額度分母：優先使用單幣上限 symbol_budget，缺省回退總預算 exposure_budget
  const capBudget = symbolBudget ?? exposureBudget;
  const capShare = shareOf(notional, capBudget);
  const nearSymbolLimit = symbolBudget !== null && shareOf(notional, symbolBudget) >= 80;

  const posByBot = useMemo(() => {
    const map = new Map<string, PositionDTO>();
    for (const p of positions) map.set(p.bot_id, p);
    return map;
  }, [positions]);

  // 空狀態切片
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
      isMuted: true,
      hidePct: true,
    },
  ], [unavailableText, unavailableSub, modeNotOpen]);

  // 剩餘可用額度（啞灰槽，不對 Decimal 做前端加減，僅呈現上限基準與剩餘比例）
  const remainingItem: DonutItem = useMemo(() => ({
    key: "remaining",
    shortLabel: "剩餘可用額度",
    compactLabel: "未用額度",
    sub: symbolBudget ? "距單幣上限" : "距總預算",
    amount: null,
    amountStr: `上限 ${formatDecimal(capBudget, { prefix: "$" })}`,
    pct_share: Math.max(0, 100 - capShare),
    color: COLORS.rem,
    badgeStr: "未配置",
    compactBadge: "未用",
    isMuted: true,
  }), [symbolBudget, capBudget, capShare]);

  // 1. 視角：策略（預設，Y 結構：按策略實例拆解單幣額度）
  const botItems: DonutItem[] = useMemo(() => {
    if (!risk) return unavailableItems;
    const rows: DonutItem[] = [];

    bots.forEach((bot, idx) => {
      const pos = posByBot.get(bot.bot_id) ?? null;
      const posSign = signOf(pos?.position ?? bot.position);
      const hasPos = posSign === "positive" || posSign === "negative";
      const isShort = posSign === "negative";
      const botNotional = pos?.notional ?? (bot.bot_id === risk.bot_id ? notional : null);
      const share = hasPos ? shareOf(botNotional, capBudget) : shareOf(botNotional, capBudget);
      const sym = (pos?.inst_id ?? bot.inst_id ?? "").replace("-USDT-SWAP", "");
      const posBadge = hasPos && (pos?.position ?? bot.position)
        ? `${sym ? `${sym} ` : ""}${isShort ? "空" : "多"} ${formatDecimal(magnitude((pos?.position ?? bot.position) as string), { digits: 0 })} 張`
        : BOT_STATE_LABEL[bot.state] ?? bot.state;

      // 多策略時若某策略空手（0 名目），仍保留於清單但歸為淡色提示
      const isZero = !hasPos && (botNotional === null || signOf(botNotional) === "zero");
      rows.push({
        key: `bot:${bot.bot_id}`,
        shortLabel: bot.strategy_name || bot.bot_id,
        compactLabel: bot.bot_id,
        sub: bot.bot_id,
        amount: botNotional,
        amountStr: isZero ? "$0.00" : formatDecimal(botNotional, { prefix: "$" }),
        pct_share: isZero ? 0 : share,
        color: isZero ? COLORS.rem : BOT_PALETTE[idx % BOT_PALETTE.length],
        badgeStr: isZero ? `${sym ? `${sym} ` : ""}空手` : posBadge,
        compactBadge: isZero ? "空手" : posBadge,
        isMuted: isZero,
        nearLimit: bot.bot_id === risk.bot_id && nearSymbolLimit,
      });
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
        isMuted: true,
        hidePct: true,
      });
    }

    rows.push(remainingItem);
    return rows;
  }, [risk, unavailableItems, bots, posByBot, notional, capBudget, nearSymbolLimit, remainingItem]);

  // 2. 視角：幣種（跨策略單幣集中度）
  const allocationItems: DonutItem[] = useMemo(() => {
    if (!risk) return unavailableItems;

    // 依合約彙整策略數與持倉引用，不以 float 加總金額
    const byInst = new Map<string, { botCount: number; openPositions: PositionDTO[] }>();
    for (const bot of bots) {
      const inst = bot.inst_id ?? "未指定合約";
      const entry = byInst.get(inst) ?? { botCount: 0, openPositions: [] };
      entry.botCount += 1;
      byInst.set(inst, entry);
    }
    for (const p of positions) {
      const inst = p.inst_id ?? p.symbol ?? "未指定合約";
      const entry = byInst.get(inst) ?? { botCount: 0, openPositions: [] };
      const s = signOf(p.position);
      if (s === "positive" || s === "negative") entry.openPositions.push(p);
      byInst.set(inst, entry);
    }

    const activeInsts = [...byInst.entries()].filter(([, info]) => info.openPositions.length > 0);
    const rows: DonutItem[] = [];
    let colorIdx = 0;

    for (const [inst, info] of byInst.entries()) {
      const openCount = info.openPositions.length;
      let instNotional: DecimalString | null = null;
      let pct = 0;
      if (openCount === 0) {
        instNotional = null;
        pct = 0;
      } else if (activeInsts.length === 1) {
        // 全部持倉集中於單一合約：直接採用後端權威 risk.derived.notional（0 前端運算）
        instNotional = notional;
        pct = capShare;
      } else if (openCount === 1) {
        instNotional = info.openPositions[0].notional;
        pct = shareOf(instNotional, capBudget);
      } else {
        // 多合約同時各有多策略時，僅用幾何加總顯示比例、金額不以浮點加總
        const plotSum = info.openPositions.reduce((acc, p) => {
          const n = toPlotNumber(p.notional);
          return acc + (Number.isFinite(n) ? Math.abs(n) : 0);
        }, 0);
        pct = sharePlot(plotSum, toPlotNumber(capBudget));
      }

      const isZero = openCount === 0;
      const color = isZero ? COLORS.violet : BOT_PALETTE[colorIdx++ % BOT_PALETTE.length];
      rows.push({
        key: `inst:${inst}`,
        shortLabel: inst,
        compactLabel: inst.replace("-USDT-SWAP", ""),
        sub: `${info.botCount} 策略`,
        amount: instNotional,
        amountStr: isZero ? "$0.00" : instNotional ? formatDecimal(instNotional, { prefix: "$" }) : `${openCount} 筆持倉`,
        pct_share: pct,
        color: isZero ? COLORS.rem : color,
        badgeStr: isZero ? `空手 (${info.botCount} 策略)` : openCount > 1 ? `${openCount} 策略疊加` : `${leverageText(effectiveLeverage)}`,
        compactBadge: isZero ? "空手" : `${openCount} 筆`,
        isMuted: isZero,
        nearLimit: !isZero && pct >= 80,
      });
    }

    if (rows.length === 0) {
      rows.push({
        key: "position-fallback",
        shortLabel: "持倉曝險",
        compactLabel: "持倉",
        sub: "名目",
        amount: notional,
        amountStr: formatDecimal(notional, { prefix: "$" }),
        pct_share: capShare,
        color: COLORS.position,
        badgeStr: leverageText(effectiveLeverage),
        nearLimit: nearSymbolLimit,
      });
    }

    rows.push(remainingItem);
    return rows;
  }, [risk, unavailableItems, bots, positions, notional, capBudget, capShare, effectiveLeverage, nearSymbolLimit, remainingItem]);

  // 3. 視角：多空（方向淨曝險）
  const deltaItems: DonutItem[] = useMemo(() => {
    if (!risk) return unavailableItems;
    const open = positions.filter((p) => {
      const sign = signOf(p.position);
      return sign === "positive" || sign === "negative";
    });
    if (open.length === 0) {
      return [{
        key: "flat",
        shortLabel: "空倉（無方向曝險）",
        compactLabel: "空倉",
        sub: "FLAT",
        amount: null,
        amountStr: "$0.00",
        pct_share: 100,
        color: COLORS.rem,
        badgeStr: "無方向",
        isMuted: true,
        hidePct: true,
      }];
    }
    const gross = open.reduce((acc, p) => {
      const n = toPlotNumber(p.notional);
      return acc + (Number.isFinite(n) ? Math.abs(n) : 0);
    }, 0);
    return open.map((p: PositionDTO) => {
      const isLong = signOf(p.position) === "positive";
      const name = p.inst_id ? p.inst_id.replace("-USDT-SWAP", "") : p.bot_id;
      return {
        key: `pos:${p.bot_id}:${p.inst_id ?? ""}`,
        shortLabel: `${p.bot_id} · ${name} ${isLong ? "多頭" : "空頭"}`,
        compactLabel: `${p.bot_id} ${isLong ? "多" : "空"}`,
        sub: isLong ? "LONG" : "SHORT",
        amount: p.notional,
        amountStr: `${isLong ? "+" : "-"}${formatDecimal(p.notional, { prefix: "$" })}`,
        pct_share: sharePlot(toPlotNumber(p.notional), gross),
        color: isLong ? COLORS.budget : COLORS.short,
        badgeStr: `${isLong ? "多" : "空"} ${formatDecimal(magnitude(p.position), { digits: 0 })} 張`,
        compactBadge: isLong ? "LONG" : "SHORT",
        isLoss: !isLong,
      };
    });
  }, [risk, unavailableItems, positions]);

  // 4. 視角：損益（已實現／未實現／手續費結構）
  const pnlItems: DonutItem[] = useMemo(() => {
    if (!summary) return unavailableItems;
    const realized = summary.realized_pnl;
    const unrealized = summary.unrealized_pnl;
    const fees = summary.fees;
    const parts = [unrealized, realized, fees].map((v) => {
      const n = toPlotNumber(v);
      return Number.isFinite(n) ? Math.abs(n) : 0;
    });
    const total = parts[0] + parts[1] + parts[2];
    const toneColor = (v: DecimalString, positiveColor: string) => {
      const s = signOf(v);
      return s === "positive" ? positiveColor : s === "negative" ? COLORS.short : COLORS.neutral;
    };
    const feeSign = signOf(fees);
    const feeFormatted = formatDecimal(fees, { prefix: "$" });
    const feeStr = feeSign === "positive" ? `-${feeFormatted}` : feeFormatted;
    return [
      {
        key: "unrealized",
        shortLabel: "未實現浮盈",
        compactLabel: "未實現",
        sub: "UNREALIZED",
        amount: unrealized,
        amountStr: formatDecimal(unrealized, { sign: true, prefix: "$" }),
        pct_share: sharePlot(parts[0], total),
        color: toneColor(unrealized, COLORS.position),
        badgeStr: "持倉浮動",
        compactBadge: "浮動",
        isLoss: signOf(unrealized) === "negative",
      },
      {
        key: "realized",
        shortLabel: "已實現損益",
        compactLabel: "已實現",
        sub: "REALIZED",
        amount: realized,
        amountStr: formatDecimal(realized, { sign: true, prefix: "$" }),
        pct_share: sharePlot(parts[1], total),
        color: toneColor(realized, COLORS.budget),
        badgeStr: "已結算",
        compactBadge: "已結",
        isLoss: signOf(realized) === "negative",
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
        isMuted: true,
      },
    ];
  }, [summary, unavailableItems]);

  // 5. 視角：保證金（v1 local-sim 無保證金模型，誠實呈現 margin_ok 布林事實）
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
      color: marginOk === false ? COLORS.short : COLORS.rem,
      badgeStr: "local-sim 無保證金模型",
      compactBadge: verdict,
      isLoss: marginOk === false,
      isMuted: marginOk !== false,
      hidePct: true,
    }];
  }, [risk, unavailableItems]);

  const currentItems = viewMode === "bots"
    ? botItems
    : viewMode === "allocation"
    ? allocationItems
    : viewMode === "delta"
    ? deltaItems
    : viewMode === "pnl"
    ? pnlItems
    : marginItems;

  const activeHoverItem = hoveredIndex !== null ? currentItems[hoveredIndex] ?? null : null;

  const statusChip = risk ? RISK_STATUS_CHIP[risk.derived.status] ?? NO_OBSERVATION_CHIP : NO_OBSERVATION_CHIP;
  const statusTooltip = risk
    ? [risk.derived.can_increase ? "可增倉" : "禁增倉", risk.reasons.join(",")].filter(Boolean).join(" · ")
    : unavailableSub;

  const leverageLimitText = limits ? `${formatDecimal(limits.leverage, { digits: 1 })}x` : TEXT_UNAVAILABLE;
  const symbolShareText = limits ? formatRatioPct(limits.symbol_share, { sign: false }) : TEXT_UNAVAILABLE;
  const canToggleUnit = viewMode === "bots" || viewMode === "allocation" || viewMode === "delta";

  // 次標右側摘要
  const topRightSummary = useMemo(() => {
    if (viewMode === "pnl") {
      if (!summary) return TEXT_UNAVAILABLE;
      return `風控期間 ${formatDecimal(summary.period_pnl, { sign: true, prefix: "$" })}`;
    }
    if (!risk) return TEXT_UNAVAILABLE;
    if (viewMode === "margin") return "margin_ok";
    if (viewMode === "delta") {
      const dirSign = signOf(risk.snapshot?.position ?? null);
      const dir = dirSign === "positive" ? "淨多" : dirSign === "negative" ? "淨空" : "空倉";
      return `${dir} · ${leverageText(effectiveLeverage)}`;
    }
    const singleCap = limits && risk.derived.exposure_budget && risk.derived.symbol_budget
      ? `${(toPlotNumber(limits.leverage) * toPlotNumber(limits.symbol_share)).toFixed(2)}x`
      : leverageLimitText;
    return `${leverageText(effectiveLeverage)} / ${singleCap}`;
  }, [viewMode, summary, risk, effectiveLeverage, limits, leverageLimitText]);

  // 中央 HUD 數據計算（Y 風格：單一大數字＋簡潔副標）
  const renderDonut = () => {
    let accumulatedArc = 0;

    let hudValue = "";
    let hudSub = "";
    let hudValueColor = "#f8fafc";

    const hudUnavailable = viewMode === "pnl" ? summary === null : risk === null;
    if (hudUnavailable) {
      hudValue = modeNotOpen ? "未開放" : "尚無觀測";
      hudSub = unavailableSub;
      hudValueColor = "#a1a1aa";
    } else if (viewMode === "bots" || viewMode === "allocation") {
      if (hudUnit === "pct") {
        hudValue = `${Math.round(capShare)}%`;
        hudSub = viewMode === "allocation" ? "單幣集中度" : symbolBudget ? "單幣上限已用" : "總預算已用";
      } else if (hudUnit === "leverage") {
        hudValue = leverageText(effectiveLeverage);
        hudSub = `有效槓桿 · 上限 ${leverageLimitText}`;
      } else {
        hudValue = formatDecimal(notional, { prefix: "$" });
        hudSub = "名目總曝險";
      }
    } else if (viewMode === "delta") {
      const open = positions.filter((p) => {
        const s = signOf(p.position);
        return s === "positive" || s === "negative";
      });
      if (open.length === 0) {
        hudValue = "空倉";
        hudSub = "無方向曝險";
        hudValueColor = "#a1a1aa";
      } else {
        let longPlot = 0;
        let shortPlot = 0;
        for (const p of open) {
          const n = Math.abs(toPlotNumber(p.notional));
          if (!Number.isFinite(n)) continue;
          if (signOf(p.position) === "positive") longPlot += n;
          else shortPlot += n;
        }
        const totalPlot = longPlot + shortPlot;
        const isLongDom = longPlot >= shortPlot;
        const domPct = totalPlot > 0 ? Math.round((Math.max(longPlot, shortPlot) / totalPlot) * 100) : 0;
        hudValueColor = isLongDom ? "#10b981" : "#f43f5e";
        if (hudUnit === "pct") {
          hudValue = `${domPct}% ${isLongDom ? "多" : "空"}`;
          hudSub = "多空方向佔比";
        } else if (hudUnit === "leverage") {
          hudValue = leverageText(effectiveLeverage);
          hudSub = isLongDom ? "偏多有效槓桿" : "偏空有效槓桿";
        } else {
          hudValue = formatDecimal(notional, { prefix: "$" });
          hudSub = "名目總曝險";
        }
      }
    } else if (viewMode === "pnl") {
      const pnl = summary?.period_pnl ?? null;
      const ratio = summary?.period_pnl_ratio ?? null;
      const s = signOf(pnl);
      hudValue = formatDecimal(pnl, { sign: true, prefix: "$" });
      hudValueColor = s === "positive" ? "#10b981" : s === "negative" ? "#f43f5e" : "#f8fafc";
      hudSub = `風控期間 ${formatRatioPct(ratio)}`;
    } else {
      const marginOk = risk?.snapshot?.margin_ok;
      hudValue = marginOk === undefined ? TEXT_UNAVAILABLE : marginOk ? "通過" : "未通過";
      hudValueColor = marginOk === false ? "#f43f5e" : "#a1a1aa";
      hudSub = "local-sim 無保證金模型";
    }

    const shareCaption = SHARE_CAPTION[viewMode];

    return (
      <div
        onClick={() => {
          if (canToggleUnit && !hudUnavailable) {
            setHudUnit((u) => nextHudUnit(u));
          }
        }}
        title={canToggleUnit && !hudUnavailable ? "點擊圓環切換顯示單位（% / x / $）" : undefined}
        className={cn(
          "h-full aspect-square flex flex-col items-center justify-center relative shrink-0 group/donut",
          isNarrow ? "max-w-[36%] max-h-[146px]" : "max-w-[42%] max-h-[190px]",
          canToggleUnit && !hudUnavailable && "cursor-pointer"
        )}
      >
        <svg
          viewBox={`0 0 ${VB_SIZE} ${VB_SIZE}`}
          className="h-full w-full max-h-full max-w-full aspect-square select-none"
        >
          <defs>
            <style>{`
              .hud-mono {
                font-family: var(--font-mono), ui-monospace, SFMono-Regular, Menlo, monospace;
                font-feature-settings: 'tnum';
              }
            `}</style>
          </defs>

          {/* 啞光底槽 */}
          <circle cx={CX} cy={CY} r={R} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth={STROKE_WIDTH} />

          {currentItems.map((item, idx) => {
            if (item.pct_share <= 0) return null;
            const fullArc = (item.pct_share / 100) * CIRCUMFERENCE;
            const arcLen = Math.max(0, fullArc - SLICE_GAP);
            const dasharray = `${arcLen} ${CIRCUMFERENCE - arcLen}`;
            const dashoffset = -accumulatedArc - SLICE_GAP / 2;
            accumulatedArc += fullArc;

            const isHovered = hoveredIndex === idx;
            const sliceOpacity = hoveredIndex === null ? (item.isMuted ? 0.55 : 0.94) : isHovered ? 1 : 0.22;

            return (
              <circle
                key={item.key}
                cx={CX}
                cy={CY}
                r={R}
                fill="none"
                stroke={item.color}
                strokeWidth={isHovered ? STROKE_WIDTH + 2 : STROKE_WIDTH}
                strokeDasharray={dasharray}
                strokeDashoffset={dashoffset}
                strokeLinecap="butt"
                opacity={sliceOpacity}
                transform={`rotate(-90 ${CX} ${CY})`}
                className="transition-all duration-200"
                onMouseEnter={() => setHoveredIndex(idx)}
                onMouseLeave={() => setHoveredIndex(null)}
              />
            );
          })}

          {/* 中央 HUD：Y 風格單一大數字＋副標（懸停切片時聚焦該切片） */}
          {activeHoverItem ? (
            <g className="pointer-events-none select-none">
              <text
                x={CX}
                y={CY - 12}
                textAnchor="middle"
                fill="#94a3b8"
                fontSize={hudFontSize(activeHoverItem.shortLabel, 10)}
                fontWeight="500"
                className="hud-mono"
              >
                {activeHoverItem.shortLabel}
              </text>
              <text
                x={CX}
                y={CY + 10}
                textAnchor="middle"
                fill="#f8fafc"
                fontSize={hudFontSize(activeHoverItem.hidePct ? activeHoverItem.amountStr : `${Math.round(activeHoverItem.pct_share)}%`, 28)}
                fontWeight="700"
                className="hud-mono"
              >
                {activeHoverItem.hidePct ? activeHoverItem.amountStr : `${Math.round(activeHoverItem.pct_share)}%`}
              </text>
              <text
                x={CX}
                y={CY + 27}
                textAnchor="middle"
                fill="#94a3b8"
                fontSize={hudFontSize(activeHoverItem.amountStr, 9.5)}
                className="hud-mono"
              >
                {activeHoverItem.hidePct || !shareCaption ? activeHoverItem.badgeStr : activeHoverItem.amountStr}
              </text>
            </g>
          ) : (
            <g className="pointer-events-none select-none">
              <text
                x={CX}
                y={isCompact ? CY + 8 : CY + 4}
                textAnchor="middle"
                fill={hudValueColor}
                fontSize={hudFontSize(hudValue, isCompact ? 26 : 30)}
                fontWeight="700"
                className="hud-mono"
              >
                {hudValue}
              </text>
              {!isCompact && (
                <text
                  x={CX}
                  y={CY + 23}
                  textAnchor="middle"
                  fill="#94a3b8"
                  fontSize={hudFontSize(hudSub, 10)}
                  fontWeight="500"
                  className="hud-mono"
                >
                  {hudSub}
                </text>
              )}
            </g>
          )}
        </svg>

        {canToggleUnit && !hudUnavailable && !isCompact && (
          <span className="absolute -bottom-0.5 text-t1 font-mono text-muted-foreground/60 group-hover/donut:text-primary transition-colors pointer-events-none">
            點擊圓環切單位
          </span>
        )}
      </div>
    );
  };

  // 底部額度上限公式（僅有風控觀測且非極扁高度顯示）
  const riskEquity = risk?.snapshot?.risk_equity ?? risk?.snapshot?.equity ?? summary?.equity ?? null;
  const formulaLine = risk && !isShort
    ? viewMode === "pnl"
      ? `已實現 ${formatDecimal(summary?.realized_pnl, { sign: true, prefix: "$" })} · 未實現 ${formatDecimal(summary?.unrealized_pnl, { sign: true, prefix: "$" })} · 手續費 ${formatDecimal(summary?.fees, { prefix: "$" })}`
      : viewMode === "margin"
      ? "v1 local-sim 無保證金模型 · 僅驗證 margin_ok 布林事實"
      : `上限 = 權益 ${formatDecimal(riskEquity, { prefix: "$" })} × 總槓桿 ${leverageLimitText} × 單幣 ${symbolShareText} = ${formatDecimal(symbolBudget, { prefix: "$" })}`
    : null;

  return (
    <div ref={containerRef} className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40 relative", className)}>
      {/* 1. 標題列：精簡無單位按鈕，只留標題＋風控狀態＋5 視角切換 */}
      <div className="flex items-center justify-between px-3 h-9 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
        <CardHeaderTitle
          cardId="allocation"
          title="曝險額度"
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
                  "px-1.5 sm:px-2 py-0.5 rounded transition-colors cursor-pointer font-medium select-none text-t2 whitespace-nowrap",
                  isActive
                    ? "bg-secondary text-foreground font-semibold shadow-xs border border-white/[0.14]"
                    : "text-muted-foreground hover:text-foreground hover:bg-white/[0.06]"
                )}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. 主內容區：次標一行 + 左側可點圓環 + 右側 Y 風格精簡明細表 */}
      <div className="flex-1 min-h-0 flex flex-col px-3 py-2 overflow-hidden">
        {!isShort && (
          <div className="flex items-center justify-between gap-2 text-t2 font-mono text-muted-foreground mb-1.5 shrink-0">
            <span className="truncate">{VIEW_CAPTION[viewMode]}</span>
            <span className="font-semibold text-foreground shrink-0">{topRightSummary}</span>
          </div>
        )}

        <div className="flex-1 min-h-0 flex items-center gap-3 sm:gap-4 overflow-hidden font-mono">
          {renderDonut()}

          {/* 右側明細清單（Y 版乾淨表格行，無冗餘進度槽噪音） */}
          <div className="flex-1 min-w-0 h-full flex flex-col justify-center divide-y divide-white/[0.05] overflow-y-auto pr-0.5">
            {currentItems.map((item, idx) => {
              const isHovered = hoveredIndex === idx;
              const displayLabel = isNarrow ? (item.compactLabel || item.shortLabel) : item.shortLabel;
              const displayBadge = isSuperNarrow ? undefined : (isNarrow ? (item.compactBadge || item.badgeStr) : item.badgeStr);

              return (
                <div
                  key={item.key}
                  onMouseEnter={() => setHoveredIndex(idx)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  className={cn(
                    "flex items-center justify-between gap-2 px-1.5 py-1.5 rounded transition-colors cursor-pointer",
                    isHovered ? "bg-white/[0.07]" : "hover:bg-white/[0.03]"
                  )}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="size-2 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                    <span
                      className={cn(
                        "text-t3 truncate",
                        item.isMuted ? "text-muted-foreground" : "text-foreground font-semibold"
                      )}
                    >
                      {displayLabel}
                    </span>
                    {displayBadge && (
                      <span
                        className={cn(
                          "text-t1 shrink-0 whitespace-nowrap",
                          item.nearLimit ? "text-amber-400 font-semibold" : "text-muted-foreground/80"
                        )}
                      >
                        {displayBadge}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2.5 shrink-0">
                    <span
                      className={cn(
                        "text-t3 tabular-nums",
                        item.isLoss ? "text-rose-400 font-semibold" : item.isMuted ? "text-muted-foreground" : "text-foreground font-medium"
                      )}
                    >
                      {item.amountStr}
                    </span>
                    {!item.hidePct && (
                      <span
                        className={cn(
                          "text-t3 tabular-nums min-w-[34px] text-right",
                          item.nearLimit ? "text-amber-400 font-bold" : item.isMuted ? "text-muted-foreground" : "text-foreground font-semibold"
                        )}
                      >
                        {Math.round(item.pct_share)}%
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* 3. 底部單行額度公式 */}
        {formulaLine && (
          <div className="mt-1.5 pt-1.5 border-t border-border/60 text-t1 font-mono text-muted-foreground/75 truncate shrink-0">
            {formulaLine}
          </div>
        )}
      </div>
    </div>
  );
}
