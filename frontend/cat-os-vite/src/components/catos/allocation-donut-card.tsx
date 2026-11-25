import { useState, useMemo, useRef, useEffect } from "react";
import { CardHeaderTitle } from "./card-header-title";
import { CardHeaderTabs } from "./card-header-tabs";
import { cn } from "@/lib/utils";
import { useCatStore } from "@/state/catStore";
import type { BotControlState, DecimalString, PositionDTO, RiskStatus } from "@/contracts";
import { formatDecimal, formatRatioPct, signOf, toPlotNumber } from "@/lib/format";

const COLORS = {
  position: "#e8b45e",
  second: "#7faee2",
  violet: "#8b8df8",
  budget: "#10b981",
  short: "#f43f5e",
  fee: "#71717a",
  neutral: "#a1a1aa",
  rem: "#3f3f46",
  muted: "#27272a",
};

const BOT_PALETTE = ["#e8b45e", "#7faee2", "#8b8df8", "#10b981", "#f59e0b"];

interface DonutItem {
  key: string;
  shortLabel: string;
  compactLabel?: string;
  sub: string;
  amount: DecimalString | null;
  amountStr: string;
  pct_share: number;
  color: string;
  badgeStr: string;
  compactBadge?: string;
  isLoss?: boolean;
  isMuted?: boolean;
  nearLimit?: boolean;
  hidePct?: boolean;
}

const VB_SIZE = 200;
const CX = 100;
const CY = 100;
const R = 74;
const STROKE_WIDTH = 14;
const CIRCUMFERENCE = 2 * Math.PI * R;
const SLICE_GAP = 2.6;
const HUD_INNER_WIDTH = 128;

export type DonutViewMode = "bots" | "allocation" | "delta" | "pnl" | "margin";
export type HudUnit = "pct" | "leverage" | "money";

const TABS: { id: DonutViewMode; label: string; shortLabel: string }[] = [
  { id: "bots", label: "策略", shortLabel: "策" },
  { id: "allocation", label: "幣種", shortLabel: "幣" },
  { id: "delta", label: "多空", shortLabel: "向" },
  { id: "pnl", label: "損益", shortLabel: "益" },
  { id: "margin", label: "保證金", shortLabel: "保" },
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

const DECIMAL_STR_RE = /^[+-]?(\d+)(?:\.(\d*))?$/;

/** 純字串 BigInt 計算 max(0, cap - |used|)，維持 Decimal 精確度、不經 float */
function subtractDecimalNonNegative(
  cap: DecimalString | null | undefined,
  used: DecimalString | null | undefined,
): DecimalString | null {
  if (!cap) return null;
  const parsePart = (v: string) => {
    const t = v.trim();
    const m = DECIMAL_STR_RE.exec(t);
    if (!m) {
      if (/^[+-]?0(?:\.0*)?E[+-]?\d+$/i.test(t)) return { neg: false, int: "0", frac: "" };
      return null;
    }
    return { neg: t.startsWith("-"), int: m[1], frac: m[2] ?? "" };
  };
  const a = parsePart(cap);
  if (!a) return null;
  const b = used ? parsePart(used) : { neg: false, int: "0", frac: "" };
  if (!b) return null;
  const scale = Math.max(a.frac.length, b.frac.length);
  const aBig = BigInt(a.int + a.frac.padEnd(scale, "0"));
  const bBig = BigInt(b.int + b.frac.padEnd(scale, "0"));
  const diff = aBig > bBig ? aBig - bBig : 0n;
  if (scale === 0) return diff.toString();
  const raw = diff.toString().padStart(scale + 1, "0");
  return `${raw.slice(0, raw.length - scale)}.${raw.slice(raw.length - scale)}`;
}

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
 * 曝險額度卡片 (1A 定案 · 比例驅動全形態自適應)
 * - 直式/窄高比例：自動切換為 Y 版經典上下排佈（上居中大圓環、下滿寬明細列）
 * - 超扁橫條：左小圓環＋右側 2 欄緊湊網格（一次看清不捲動）
 * - 標準／寬大橫式：圓環與明細尺寸隨容器實測寬高自由放大縮小，無硬性尺寸死鎖
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

  const { width: cardW, height: cardH } = dimensions;
  // 依容器寬高比自動判定三種形態
  const isVertical = (cardW < 450 && cardH >= 285) || (cardH >= 320 && cardH / Math.max(1, cardW) >= 0.78);
  const isFlat = !isVertical && cardH < 195;
  const isNarrow = cardW < 460;
  const isSuperNarrow = cardW < 340;
  const isLarge = !isVertical && !isFlat && cardW >= 740 && cardH >= 280;

  // 圓環動態直徑（方案 B：拿掉上下廢帶，讓圓環吃滿卡片垂直空間）
  const donutSizePx = useMemo(() => {
    if (isVertical) {
      return Math.round(Math.max(118, Math.min(220, cardW * 0.54, (cardH - 110) * 0.46)));
    }
    if (isFlat) {
      return Math.round(Math.max(92, Math.min(138, cardH - 46, cardW * 0.28)));
    }
    const availH = cardH - 76;
    const availW = cardW * 0.34;
    return Math.round(Math.max(120, Math.min(248, availH, availW)));
  }, [isVertical, isFlat, cardW, cardH]);

  const risk = useCatStore((s) => s.risk);
  const summary = useCatStore((s) => s.summary);
  const killSwitch = useCatStore((s) => s.killSwitch);
  const bots = useCatStore((s) => s.bots);
  const positions = useCatStore((s) => s.positions);
  const connectionStatus = useCatStore((s) => s.connection.status);

  const modeNotOpen = connectionStatus === "mode_not_open";
  const unavailableSub = modeNotOpen ? "v1 僅提供 local-sim" : "啟動模擬 run 後啟用";

  const derived = risk?.derived ?? null;
  const limits = risk?.limits ?? killSwitch?.default_limits ?? null;
  const notional = derived?.notional ?? null;
  const exposureBudget = derived?.exposure_budget ?? null;
  const symbolBudget = derived?.symbol_budget ?? null;
  const effectiveLeverage = derived?.effective_leverage ?? null;

  const capBudget = symbolBudget ?? exposureBudget;
  const capShare = shareOf(notional, capBudget);

  const posByBot = useMemo(() => {
    const map = new Map<string, PositionDTO>();
    for (const p of positions) map.set(p.bot_id, p);
    return map;
  }, [positions]);

  const leverageLimitText = limits ? `${formatDecimal(limits.leverage, { digits: 1 })}x` : TEXT_UNAVAILABLE;
  const symbolShareText = limits ? formatRatioPct(limits.symbol_share, { sign: false }) : TEXT_UNAVAILABLE;
  const softLossText = limits ? formatRatioPct(limits.soft_loss, { sign: false }) : TEXT_UNAVAILABLE;
  const hardLossText = limits ? formatRatioPct(limits.hard_loss, { sign: false }) : TEXT_UNAVAILABLE;

  const unavailableItems: DonutItem[] = useMemo(() => [
    {
      key: "cfg-lev",
      shortLabel: "帳戶有效槓桿上限",
      compactLabel: "槓桿上限",
      sub: "預設上限",
      amount: null,
      amountStr: leverageLimitText,
      pct_share: 0,
      color: COLORS.position,
      badgeStr: "全帳戶",
      isMuted: true,
      hidePct: true,
    },
    {
      key: "cfg-sym",
      shortLabel: "單一幣種預算占比",
      compactLabel: "單幣上限",
      sub: "集中度限制",
      amount: null,
      amountStr: symbolShareText,
      pct_share: 0,
      color: COLORS.second,
      badgeStr: "單幣上限",
      isMuted: true,
      hidePct: true,
    },
    {
      key: "cfg-loss",
      shortLabel: "日損風控鎖存門檻",
      compactLabel: "日損鎖存",
      sub: "Soft / Hard",
      amount: null,
      amountStr: `${softLossText} / ${hardLossText}`,
      pct_share: 0,
      color: COLORS.rem,
      badgeStr: "人工解除",
      isMuted: true,
      hidePct: true,
    },
  ], [leverageLimitText, symbolShareText, softLossText, hardLossText]);

  const remainingBudget = useMemo(
    () => subtractDecimalNonNegative(capBudget, notional),
    [capBudget, notional],
  );

  const remainingItem: DonutItem = useMemo(() => ({
    key: "remaining",
    shortLabel: "剩餘可用額度",
    compactLabel: "剩餘額度",
    sub: symbolBudget ? "距單幣上限" : "距總預算",
    amount: remainingBudget,
    amountStr: remainingBudget !== null ? formatDecimal(remainingBudget, { prefix: "$" }) : TEXT_UNAVAILABLE,
    pct_share: Math.max(0, 100 - capShare),
    color: COLORS.rem,
    badgeStr: symbolBudget ? "單幣緩衝" : "緩衝",
    compactBadge: "緩衝",
    isMuted: true,
  }), [symbolBudget, capShare, remainingBudget]);

  const botItems: DonutItem[] = useMemo(() => {
    if (!risk) return unavailableItems;
    const rows: DonutItem[] = [];

    bots.forEach((bot, idx) => {
      const pos = posByBot.get(bot.bot_id) ?? null;
      const posSign = signOf(pos?.position ?? bot.position);
      const hasPos = posSign === "positive" || posSign === "negative";
      const isShort = posSign === "negative";
      const botNotional = pos?.notional ?? (bot.bot_id === risk.bot_id ? notional : null);
      const share = shareOf(botNotional, capBudget);
      const sym = (pos?.inst_id ?? bot.inst_id ?? "").replace("-USDT-SWAP", "");
      const posBadge = hasPos && (pos?.position ?? bot.position)
        ? `${sym ? `${sym} ` : ""}${isShort ? "空" : "多"} ${formatDecimal(magnitude((pos?.position ?? bot.position) as string), { digits: 0 })} 張`
        : BOT_STATE_LABEL[bot.state] ?? bot.state;

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
  }, [risk, unavailableItems, bots, posByBot, notional, capBudget, remainingItem]);

  const allocationItems: DonutItem[] = useMemo(() => {
    if (!risk) return unavailableItems;

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
        instNotional = notional;
        pct = capShare;
      } else if (openCount === 1) {
        instNotional = info.openPositions[0].notional;
        pct = shareOf(instNotional, capBudget);
      } else {
        const plotSum = info.openPositions.reduce((acc, p) => {
          const n = toPlotNumber(p.notional);
          return acc + (Number.isFinite(n) ? Math.abs(n) : 0);
        }, 0);
        pct = sharePlot(plotSum, toPlotNumber(capBudget));
      }

      const isZero = openCount === 0;
      const color = isZero ? COLORS.rem : BOT_PALETTE[colorIdx++ % BOT_PALETTE.length];
      rows.push({
        key: `inst:${inst}`,
        shortLabel: inst,
        compactLabel: inst.replace("-USDT-SWAP", ""),
        sub: `${info.botCount} 策略`,
        amount: instNotional,
        amountStr: isZero ? "$0.00" : instNotional ? formatDecimal(instNotional, { prefix: "$" }) : `${openCount} 筆持倉`,
        pct_share: pct,
        color,
        badgeStr: isZero ? `空手 (${info.botCount} 策略)` : openCount > 1 ? `${openCount} 策略疊加` : leverageText(effectiveLeverage),
        compactBadge: isZero ? "空手" : `${openCount} 筆`,
        isMuted: isZero,
        nearLimit: !isZero && pct >= 80,
      });
    }

    rows.push(remainingItem);
    return rows;
  }, [risk, unavailableItems, bots, positions, notional, capBudget, capShare, effectiveLeverage, remainingItem]);

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

  const canToggleUnit = viewMode === "bots" || viewMode === "allocation" || viewMode === "delta";

  const topRightSummary = useMemo(() => {
    if (viewMode === "pnl") {
      if (!summary) return "尚未啟動";
      return `風控期間 ${formatDecimal(summary.period_pnl, { sign: true, prefix: "$" })}`;
    }
    if (!risk) return `上限 ${leverageLimitText} · 單幣 ${symbolShareText}`;
    if (viewMode === "margin") return "local-sim 無模型";
    if (viewMode === "delta") {
      const dirSign = signOf(risk.snapshot?.position ?? null);
      const dir = dirSign === "positive" ? "淨多" : dirSign === "negative" ? "淨空" : "空倉";
      return `${dir} · ${leverageText(effectiveLeverage)}`;
    }
    const singleCap = limits && risk.derived.exposure_budget && risk.derived.symbol_budget
      ? `${(toPlotNumber(limits.leverage) * toPlotNumber(limits.symbol_share)).toFixed(2)}x`
      : leverageLimitText;
    return `${leverageText(effectiveLeverage)} / ${singleCap}`;
  }, [viewMode, summary, risk, effectiveLeverage, limits, leverageLimitText, symbolShareText]);

  const renderDonut = () => {
    let accumulatedArc = 0;

    let hudValue = "";
    let hudSub = "";
    let hudValueColor = "#f8fafc";

    const hudUnavailable = viewMode === "pnl" ? summary === null : risk === null;
    if (hudUnavailable) {
      hudValue = modeNotOpen ? "未開放" : "0%";
      hudSub = modeNotOpen ? "v1 僅 local-sim" : "尚無風控觀測";
      hudValueColor = "#71717a";
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
    const compactHud = donutSizePx < 120;

    return (
      <div
        onClick={() => {
          if (canToggleUnit && !hudUnavailable) {
            setHudUnit((u) => nextHudUnit(u));
          }
        }}
        title={canToggleUnit && !hudUnavailable ? "點擊圓環循環切換顯示單位（% → x → $）" : undefined}
        style={{ width: donutSizePx, height: donutSizePx }}
        className={cn(
          "flex items-center justify-center relative shrink-0",
          canToggleUnit && !hudUnavailable && "cursor-pointer"
        )}
      >
        <svg viewBox={`0 0 ${VB_SIZE} ${VB_SIZE}`} className="w-full h-full select-none">
          <defs>
            <style>{`
              .hud-mono {
                font-family: var(--font-mono), ui-monospace, SFMono-Regular, Menlo, monospace;
                font-feature-settings: 'tnum';
              }
            `}</style>
          </defs>

          <circle cx={CX} cy={CY} r={R} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth={STROKE_WIDTH} />

          {currentItems.map((item, idx) => {
            if (item.pct_share <= 0) return null;
            const fullArc = (item.pct_share / 100) * CIRCUMFERENCE;
            const arcLen = Math.max(0, fullArc - SLICE_GAP);
            const dasharray = `${arcLen} ${CIRCUMFERENCE - arcLen}`;
            const dashoffset = -accumulatedArc - SLICE_GAP / 2;
            accumulatedArc += fullArc;

            const isHovered = hoveredIndex === idx;
            const sliceOpacity = hoveredIndex === null ? (item.isMuted ? 0.45 : 0.94) : isHovered ? 1 : 0.22;

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

          {activeHoverItem && !activeHoverItem.hidePct ? (
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
                fontSize={hudFontSize(`${Math.round(activeHoverItem.pct_share)}%`, 28)}
                fontWeight="700"
                className="hud-mono"
              >
                {Math.round(activeHoverItem.pct_share)}%
              </text>
              <text
                x={CX}
                y={CY + 27}
                textAnchor="middle"
                fill="#94a3b8"
                fontSize={hudFontSize(activeHoverItem.amountStr, 9.5)}
                className="hud-mono"
              >
                {shareCaption ? activeHoverItem.amountStr : activeHoverItem.badgeStr}
              </text>
            </g>
          ) : (
            <g className="pointer-events-none select-none">
              <text
                x={CX}
                y={compactHud ? CY + 8 : CY + 1}
                textAnchor="middle"
                fill={hudValueColor}
                fontSize={hudFontSize(hudValue, compactHud ? 30 : 33)}
                fontWeight="700"
                className="hud-mono"
              >
                {hudValue}
              </text>
              {!compactHud && (
                <text
                  x={CX}
                  y={CY + 22}
                  textAnchor="middle"
                  fill="#94a3b8"
                  fontSize={hudFontSize(hudSub, 11.5)}
                  fontWeight="500"
                  className="hud-mono"
                >
                  {hudSub}
                </text>
              )}
              {canToggleUnit && !hudUnavailable && !compactHud && (
                <g transform={`translate(${CX}, ${CY + 41})`}>
                  <text x={-18} y={0} textAnchor="middle" fill={hudUnit === "pct" ? "#e8b45e" : "#52525b"} fontSize="10.5" fontWeight={hudUnit === "pct" ? "700" : "500"} className="hud-mono">%</text>
                  <text x={-9} y={0} textAnchor="middle" fill="#3f3f46" fontSize="9.5" className="hud-mono">·</text>
                  <text x={0} y={0} textAnchor="middle" fill={hudUnit === "leverage" ? "#e8b45e" : "#52525b"} fontSize="10.5" fontWeight={hudUnit === "leverage" ? "700" : "500"} className="hud-mono">x</text>
                  <text x={9} y={0} textAnchor="middle" fill="#3f3f46" fontSize="9.5" className="hud-mono">·</text>
                  <text x={18} y={0} textAnchor="middle" fill={hudUnit === "money" ? "#e8b45e" : "#52525b"} fontSize="10.5" fontWeight={hudUnit === "money" ? "700" : "500"} className="hud-mono">$</text>
                </g>
              )}
            </g>
          )}
        </svg>
      </div>
    );
  };

  const riskEquity = risk?.snapshot?.risk_equity ?? risk?.snapshot?.equity ?? summary?.equity ?? null;

  const donutFootCaption = useMemo(() => {
    if (!risk && viewMode !== "pnl") return `上限 ${leverageLimitText} · 單幣 ${symbolShareText}`;
    if (viewMode === "pnl") {
      return summary?.basis_equity
        ? `基準 ${formatDecimal(summary.basis_equity, { prefix: "$" })}`
        : "尚無風控基準";
    }
    if (viewMode === "margin") return "local-sim 無保證金模型";
    return `上限 ${formatDecimal(capBudget, { prefix: "$" })} · ${topRightSummary}`;
  }, [risk, viewMode, leverageLimitText, symbolShareText, summary, capBudget, topRightSummary]);

  const kpiPair = useMemo(() => {
    if (viewMode === "pnl") {
      const periodPnl = summary?.period_pnl ?? null;
      const periodTone =
        signOf(periodPnl) === "positive"
          ? "text-emerald-400"
          : signOf(periodPnl) === "negative"
          ? "text-rose-400"
          : "text-foreground";
      return {
        left: {
          label: "風控期間損益",
          meta: summary?.period_pnl_ratio ? formatRatioPct(summary.period_pnl_ratio) : TEXT_UNAVAILABLE,
          value: formatDecimal(periodPnl, { sign: true, prefix: "$" }),
          sub: summary?.fees ? `手續費 ${formatDecimal(summary.fees, { prefix: "$" })}` : "尚未啟動",
          valueTone: periodTone,
        },
        right: {
          label: "已實現 / 未實現",
          meta: "帳本累計",
          value: formatDecimal(summary?.realized_pnl, { sign: true, prefix: "$" }),
          sub: `浮動 ${formatDecimal(summary?.unrealized_pnl, { sign: true, prefix: "$" })}`,
          valueTone: "text-foreground",
        },
      };
    }
    if (viewMode === "margin") {
      const marginOk = risk?.snapshot?.margin_ok;
      const verdict = marginOk === undefined ? TEXT_UNAVAILABLE : marginOk ? "通過" : "未通過";
      return {
        left: {
          label: "保證金檢查",
          meta: "margin_ok",
          value: verdict,
          sub: "布林事實檢核",
          valueTone: marginOk === false ? "text-rose-400" : "text-foreground",
        },
        right: {
          label: "帳戶結算模型",
          meta: "v1 規格",
          value: "cross + net",
          sub: `槓桿上限 ${leverageLimitText}`,
          valueTone: "text-foreground",
        },
      };
    }
    const remPct = Math.max(0, Math.round(100 - capShare));
    return {
      left: {
        label: viewMode === "delta" ? "淨方向曝險" : "已用曝險",
        meta: topRightSummary,
        value: risk ? formatDecimal(notional, { prefix: "$" }) : TEXT_UNAVAILABLE,
        sub: riskEquity ? `權益 ${formatDecimal(riskEquity, { prefix: "$", digits: 0 })}` : unavailableSub,
        valueTone: "text-foreground",
      },
      right: {
        label: "剩餘緩衝",
        meta: symbolBudget ? `單幣 ${symbolShareText} 上限` : `總上限 ${leverageLimitText}`,
        value: remainingBudget !== null ? formatDecimal(remainingBudget, { prefix: "$" }) : TEXT_UNAVAILABLE,
        sub: risk ? `${remPct}% 可用` : `Soft ${softLossText} / Hard ${hardLossText}`,
        valueTone: "text-foreground",
      },
    };
  }, [
    viewMode,
    summary,
    risk,
    leverageLimitText,
    capShare,
    topRightSummary,
    notional,
    riskEquity,
    unavailableSub,
    symbolBudget,
    symbolShareText,
    remainingBudget,
    softLossText,
    hardLossText,
  ]);

  const showKpiHeader = !isFlat && !isSuperNarrow && (isVertical ? cardH >= 340 : cardH >= 205);
  const compactKpi = cardH < 250;
  const isDenseList = compactKpi || currentItems.length >= 4;

  return (
    <div ref={containerRef} className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40 relative", className)}>
      {/* 1. 標題列：超窄自動隱藏狀態晶片並精簡 Tab，絕不擠爆 */}
      <div className="flex items-center justify-between px-3 h-9 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
        <CardHeaderTitle
          cardId="allocation"
          title="曝險額度"
          subtext={
            !isSuperNarrow ? (
              <span
                className={cn(
                  "px-1.5 py-0.5 rounded border text-t1 font-mono font-semibold leading-none shrink-0 whitespace-nowrap",
                  statusChip.className
                )}
                title={statusTooltip}
              >
                {statusChip.label}
              </span>
            ) : undefined
          }
        />

        <CardHeaderTabs
          items={TABS.map((tab) => ({
            id: tab.id,
            label: isSuperNarrow ? tab.shortLabel : tab.label,
          }))}
          value={viewMode}
          onChange={(id) => {
            setViewMode(id);
            setHoveredIndex(null);
          }}
        />
      </div>

      {/* 2. 主內容區（2026-11-25 定案方案 B：去上下廢帶＋右側雙格 KPI 頭＋佔比進度條） */}
      <div className={cn("flex-1 min-h-0 flex overflow-hidden font-mono", isFlat ? "px-3 py-1.5" : isDenseList ? "px-3.5 py-2" : "px-3.5 py-2.5")}>
        <div
          className={cn(
            "flex-1 min-h-0 flex w-full overflow-hidden",
            isVertical
              ? "flex-col items-center gap-2.5"
              : isFlat
              ? "flex-row items-center gap-3"
              : "flex-row items-stretch gap-4"
          )}
        >
          {/* 左側圓環＋底部精簡參數 */}
          <div className="flex flex-col items-center justify-center gap-1 shrink-0">
            {renderDonut()}
            {!isFlat && (
              <span
                className="text-t1 font-mono text-muted-foreground text-center leading-tight max-w-[230px] truncate"
                title={`${VIEW_CAPTION[viewMode]} · ${donutFootCaption}`}
              >
                {donutFootCaption}
              </span>
            )}
          </div>

          {/* 右側：頂部雙格 KPI 頭 ＋ 帶進度條的明細清單 */}
          <div
            className={cn(
              "flex-1 min-w-0 min-h-0 flex flex-col overflow-hidden",
              isVertical ? "w-full gap-1.5" : isFlat ? "justify-center" : isDenseList ? "gap-1.5" : "gap-2"
            )}
          >
            {showKpiHeader && (
              <div className="grid grid-cols-2 gap-2 shrink-0">
                {[kpiPair.left, kpiPair.right].map((kpi) => (
                  <div
                    key={kpi.label}
                    className={cn(
                      "rounded border border-border/75 bg-background/60 flex flex-col min-w-0",
                      isDenseList ? "px-2.5 py-1 gap-0.5" : "px-2.5 py-1.5 gap-0.5"
                    )}
                  >
                    <div className="flex items-center justify-between gap-1 text-t1 text-muted-foreground min-w-0">
                      <span className="font-sans truncate">{kpi.label}</span>
                      <span className="font-mono text-primary/90 shrink-0 tabular-nums truncate">{kpi.meta}</span>
                    </div>
                    <div className="flex items-baseline justify-between gap-1.5 min-w-0">
                      <span className={cn("font-mono font-bold tabular-nums leading-tight truncate", compactKpi ? "text-t4" : "text-sm", kpi.valueTone)}>
                        {kpi.value}
                      </span>
                      <span className="text-t1 font-mono text-muted-foreground/85 shrink-0 tabular-nums truncate">
                        {kpi.sub}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* 安全置中滾動區：內部用 my-auto，列數少時垂直置中、列數多時自動頂部對齊可完整捲動，不切首列 */}
            <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain custom-scrollbar pr-0.5 flex flex-col">
              <div
                className={cn(
                  "my-auto",
                  isFlat
                    ? "grid grid-cols-2 gap-x-2.5 gap-y-1"
                    : isDenseList
                    ? "flex flex-col gap-1"
                    : "flex flex-col gap-1.5"
                )}
              >
              {currentItems.map((item, idx) => {
                const isHovered = hoveredIndex === idx;
                const displayLabel = isNarrow || isFlat ? (item.compactLabel || item.shortLabel) : item.shortLabel;
                const displayBadge = isSuperNarrow || isFlat
                  ? undefined
                  : isNarrow
                  ? (item.compactBadge || item.badgeStr)
                  : item.badgeStr;
                const barWidth = Math.max(0, Math.min(100, item.pct_share));

                return (
                  <div
                    key={item.key}
                    onMouseEnter={() => setHoveredIndex(idx)}
                    onMouseLeave={() => setHoveredIndex(null)}
                    className={cn(
                      "flex flex-col rounded border transition-colors cursor-pointer shrink-0",
                      isFlat
                        ? "px-2 py-1 gap-1 bg-white/[0.02] border-white/[0.05]"
                        : isDenseList
                        ? "px-2 py-1 gap-1"
                        : isLarge
                        ? "px-2.5 py-1.5 gap-1.5"
                        : "px-2.5 py-1.5 gap-1",
                      item.isMuted
                        ? "bg-transparent border-white/[0.04]"
                        : "bg-white/[0.025] border-white/[0.06]",
                      isHovered ? "bg-white/[0.06] border-white/[0.12]" : "hover:bg-white/[0.04]"
                    )}
                  >
                    <div className="flex items-center justify-between gap-2 min-w-0">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className="size-2 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                        <span
                          className={cn(
                            "truncate font-sans leading-tight",
                            isLarge ? "text-t4" : "text-t3",
                            item.isMuted ? "text-muted-foreground" : "text-foreground font-semibold"
                          )}
                        >
                          {displayLabel}
                        </span>
                        {displayBadge && (
                          <span
                            className={cn(
                              "text-t1 font-mono shrink-0 whitespace-nowrap leading-tight",
                              item.nearLimit ? "text-amber-400 font-semibold" : "text-muted-foreground/80"
                            )}
                          >
                            {displayBadge}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <span
                          className={cn(
                            "tabular-nums leading-tight",
                            isLarge ? "text-t4" : isFlat ? "text-t2" : "text-t3",
                            item.isLoss ? "text-rose-400 font-semibold" : item.isMuted ? "text-muted-foreground/85" : "text-foreground font-medium"
                          )}
                        >
                          {item.amountStr}
                        </span>
                        {!item.hidePct && (
                          <span
                            className={cn(
                              "tabular-nums min-w-[34px] text-right leading-tight",
                              isLarge ? "text-t4" : isFlat ? "text-t2" : "text-t3",
                              item.nearLimit ? "text-amber-400 font-bold" : item.isMuted ? "text-muted-foreground/85" : "text-foreground font-semibold"
                            )}
                          >
                            {Math.round(item.pct_share)}%
                          </span>
                        )}
                      </div>
                    </div>

                    {!item.hidePct && (
                      <div className="h-1 w-full rounded-full bg-white/[0.07] overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-200"
                          style={{
                            width: `${barWidth}%`,
                            backgroundColor: item.color,
                            opacity: item.isMuted ? 0.55 : 0.95,
                          }}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
