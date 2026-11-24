import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { ArrowUpRight, ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { CardHeaderTitle } from "./card-header-title";
import {
  ACCOUNT_SOURCE_LABEL,
  BOT_STATE_LABEL,
  RISK_STATUS_META,
  useBotControls,
} from "./v0-bot-table";
import { useCatStore } from "@/state/catStore";
import { useInspectorStore } from "@/state/inspectorStore";
import { StateAdapter } from "@/state/stateAdapter";
import { ACTIVE_STATES, type BotViewDTO, type PositionDTO } from "@/contracts";
import { formatDecimal, formatRatioPct, formatTimeframe, shortId, signOf, toPlotNumber, toneOf } from "@/lib/format";
import { useRouter } from "@/lib/router";

export type BotsPositionsFilter = "all" | "open" | "orders";

interface BotsPositionsCardProps {
  className?: string;
  showHeader?: boolean;
}

function magnitude(value: string): string {
  return value.trim().replace(/^[+-]/, "");
}

function shortTimeframe(ms: number | null | undefined): string {
  if (ms === 86_400_000) return "1D";
  return formatTimeframe(ms);
}

function settlementLabel(settlement: string | undefined): string {
  if (!settlement) return "不適用";
  if (settlement === "cross_net_mode") return "cross + net_mode";
  return settlement;
}

/**
 * 策略實例與持倉合一卡片 (4A 定案：單一寬表合一＋點擊列展開交易所風控明細)
 * - 高密度自適應欄位：1440px / 1920px 下操作鈕永遠完整可見、表頭零折行、免橫向捲軸
 * - 標題列與其他 4 卡統一純繁中風格
 */
export function BotsPositionsCard({ className, showHeader = true }: BotsPositionsCardProps) {
  const bots = useCatStore((s) => s.bots);
  const positions = useCatStore((s) => s.positions);
  const risk = useCatStore((s) => s.risk);
  const summary = useCatStore((s) => s.summary);
  const events = useCatStore((s) => s.events);
  const connection = useCatStore((s) => s.connection);
  const { selectedBotId, selectBot } = useInspectorStore();
  const { navigate } = useRouter();
  const controls = useBotControls();

  const [filter, setFilter] = useState<BotsPositionsFilter>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const [cardWidth, setCardWidth] = useState(760);

  useEffect(() => {
    const el = cardRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) setCardWidth(entry.contentRect.width);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const showRiskCol = cardWidth >= 560;
  const showPriceCol = cardWidth >= 740;
  const showSpark = cardWidth >= 860;
  const colSpan = 4 + (showPriceCol ? 1 : 0) + (showRiskCol ? 1 : 0);

  const posByBot = useMemo(() => {
    const map = new Map<string, PositionDTO>();
    for (const p of positions) map.set(p.bot_id, p);
    return map;
  }, [positions]);

  const isOpenPos = (bot: BotViewDTO): boolean => {
    const p = posByBot.get(bot.bot_id);
    const val = p ? p.position : bot.position;
    if (!val) return false;
    const s = signOf(val);
    return s === "positive" || s === "negative";
  };

  const openCount = bots.filter(isOpenPos).length;
  const rows = filter === "open" ? bots.filter(isOpenPos) : bots;

  const sparkFor = useMemo(() => {
    const cache = new Map<string, { path: string; isGain: boolean }>();
    return (bot: BotViewDTO) => {
      const key = bot.current_run_id ?? "none";
      const cached = cache.get(key);
      if (cached) return cached;
      const pts = StateAdapter.equityCurve(events, bot.current_run_id)
        .map((p) => toPlotNumber(p.equity))
        .filter((v) => !Number.isNaN(v));
      if (pts.length < 2) {
        const empty = { path: "", isGain: true };
        cache.set(key, empty);
        return empty;
      }
      const lo = Math.min(...pts);
      const hi = Math.max(...pts);
      const span = hi - lo || 1;
      const w = 48;
      const h = 16;
      const n = pts.length;
      let d = "";
      pts.forEach((pt, k) => {
        const x = (k / (n - 1)) * w;
        const y = 2 + ((hi - pt) / span) * (h - 4);
        d += `${k === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      });
      const value = { path: d, isGain: pts[pts.length - 1] >= pts[0] };
      cache.set(key, value);
      return value;
    };
  }, [events]);

  const emptyText =
    connection.status === "mode_not_open" ? "此模式未開放（demo/live 不在 v1 範圍）"
    : connection.status === "unavailable" ? `模擬服務不可用：${connection.detail ?? "unknown"}`
    : connection.status === "error" ? `無法連線：${connection.detail ?? "network_error"}`
    : bots.length === 0 ? "等待模擬服務…"
    : filter === "open" ? "目前無未平倉部位"
    : "無符合條件的實例";

  return (
    <div ref={cardRef} className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40", className)}>
      {showHeader && (
        <div className="flex items-center justify-between px-3 h-9 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
          <CardHeaderTitle
            cardId="bots"
            title="策略實例與持倉"
            subtext={
              <span className="px-1.5 py-0.5 rounded bg-background/60 border border-border/60 text-t1 font-mono text-muted-foreground leading-none">
                {openCount}/{bots.length} 持倉
              </span>
            }
          />
          <div className="flex items-center gap-0.5 bg-background/60 border border-border/60 rounded p-0.5 shrink-0 whitespace-nowrap">
            {(
              [
                { id: "all", label: `全部(${bots.length})` },
                { id: "open", label: `持倉中(${openCount})` },
                { id: "orders", label: "掛單(0)" },
              ] as const
            ).map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setFilter(f.id)}
                className={cn(
                  "px-2 py-0.5 text-t2 font-mono rounded transition-colors cursor-pointer whitespace-nowrap shrink-0",
                  filter === f.id
                    ? "bg-secondary text-foreground font-semibold shadow-xs border border-white/[0.12]"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
        <div className="flex-1 min-h-0 overflow-y-auto overflow-x-auto custom-scrollbar">
          {filter === "orders" ? (
            <div className="h-full flex flex-col items-center justify-center py-8 text-center text-muted-foreground px-4 font-mono">
              <span className="text-t3 text-foreground/80">v1 沒有在途掛單</span>
              <span className="text-t2 text-muted-foreground/70 mt-1">已收盤 K 線市價執行，無掛單簿</span>
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead className="border-b border-border/80 bg-background/40 text-t1 font-mono text-muted-foreground sticky top-0 z-10 backdrop-blur-sm">
                <tr>
                  <th className="py-2 pl-3 pr-2 font-medium whitespace-nowrap">實例 / 標的</th>
                  <th className="px-2 font-medium whitespace-nowrap">部位 / 名目</th>
                  {showPriceCol && <th className="px-2 text-right font-medium whitespace-nowrap">均價 / 標記</th>}
                  <th className="px-2 text-right font-medium whitespace-nowrap">未實現 / 權益</th>
                  {showRiskCol && <th className="px-2 text-right font-medium whitespace-nowrap">風控 / P6</th>}
                  <th className="py-2 pr-3 pl-2 text-right font-medium whitespace-nowrap">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40 text-xs">
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={colSpan} className="py-8 text-center text-muted-foreground font-mono text-t3">
                      {emptyText}
                    </td>
                  </tr>
                ) : (
                  rows.map((bot) => {
                    const pos = posByBot.get(bot.bot_id) ?? null;
                    const posVal = pos?.position ?? bot.position;
                    const posSign = signOf(posVal);
                    const hasPos = posSign === "positive" || posSign === "negative";
                    const isShort = posSign === "negative";
                    const isActive = ACTIVE_STATES.has(bot.state);
                    const isSelected = selectedBotId === bot.bot_id;
                    const isExpanded = expandedId === bot.bot_id;
                    const botRisk = risk && risk.bot_id === bot.bot_id ? risk : null;
                    const statusMeta = botRisk ? RISK_STATUS_META[botRisk.derived.status] : null;
                    const spark = sparkFor(bot);
                    const avgPx = pos?.average_entry ?? bot.average_entry;
                    const markPx = pos?.mark ?? bot.mark;
                    const unrealized = pos?.unrealized_pnl ?? bot.unrealized_pnl;
                    const notional = pos?.notional ?? (botRisk ? botRisk.derived.notional : null);
                    const busyKey = controls.busy;
                    const shortInst = (bot.inst_id ?? "不適用").replace("-USDT-SWAP", "");

                    return (
                      <Fragment key={bot.bot_id}>
                        <tr
                          onClick={() => {
                            selectBot(bot.bot_id);
                            setExpandedId((prev) => (prev === bot.bot_id ? null : bot.bot_id));
                          }}
                          className={cn(
                            "hover:bg-white/[0.03] transition-colors group cursor-pointer",
                            (isSelected || isExpanded) && "bg-white/[0.04]",
                            !isActive && "opacity-85"
                          )}
                          title="點擊展開均價、手續費、資金費率與交易所風控詳情"
                        >
                          {/* 1. 實例 / 標的 */}
                          <td className="py-2.5 pl-3 pr-2 max-w-[210px]">
                            <div className="flex items-center gap-1.5 min-w-0">
                              <span className="text-muted-foreground/60 shrink-0">
                                {isExpanded ? <ChevronDown className="size-3 text-primary" /> : <ChevronRight className="size-3" />}
                              </span>
                              <span
                                className={cn(
                                  "size-2 rounded-full shrink-0",
                                  isActive
                                    ? "bg-emerald-400 shadow-[0_0_6px_rgba(16,185,129,0.5)]"
                                    : bot.state === "failed" || bot.state === "recovery_required"
                                    ? "bg-rose-400"
                                    : "bg-muted-foreground/50"
                                )}
                              />
                              <div className="flex flex-col min-w-0">
                                <div className="flex items-center gap-1.5 min-w-0">
                                  <span className="text-t4 font-bold font-mono text-foreground leading-tight group-hover:text-primary transition-colors whitespace-nowrap">
                                    {bot.bot_id}
                                  </span>
                                  <span className="text-t1 font-mono text-muted-foreground whitespace-nowrap">
                                    {shortTimeframe(bot.timeframe_ms)} · {BOT_STATE_LABEL[bot.state] ?? bot.state}
                                  </span>
                                </div>
                                <div className="text-t1 text-muted-foreground leading-tight truncate mt-0.5">
                                  <span className="text-primary font-mono font-semibold">{shortInst}</span>
                                  <span className="mx-1 text-border">·</span>
                                  <span className="font-sans">{bot.strategy_name}</span>
                                </div>
                              </div>
                            </div>
                          </td>

                          {/* 2. 部位 / 名目 */}
                          <td className="px-2 py-2.5 font-mono">
                            {hasPos && posVal ? (
                              <div className="flex flex-col">
                                <div className="flex items-center gap-1.5">
                                  <span
                                    className={cn(
                                      "px-1.5 py-0.5 rounded text-t1 font-bold inline-flex items-center border leading-none whitespace-nowrap",
                                      isShort
                                        ? "bg-rose-400/10 text-rose-400 border-rose-400/25"
                                        : "bg-emerald-400/10 text-emerald-400 border-emerald-400/25"
                                    )}
                                  >
                                    {isShort ? "▼ 空" : "▲ 多"} {formatDecimal(magnitude(posVal), { digits: 0 })} 張
                                  </span>
                                  <span className={cn("text-t1 whitespace-nowrap", pos?.verified ? "text-emerald-400/80" : "text-amber-400/80")}>
                                    {pos?.verified ? "已對帳" : "未對帳"}
                                  </span>
                                </div>
                                <span className="text-t1 text-muted-foreground leading-tight mt-0.5 whitespace-nowrap tabular-nums">
                                  名目 {formatDecimal(notional, { prefix: "$" })}
                                </span>
                              </div>
                            ) : (
                              <div className="flex flex-col">
                                <span className="px-1.5 py-0.5 rounded border border-border/70 bg-background/50 text-t1 text-muted-foreground leading-none w-fit">
                                  空手
                                </span>
                                <span className="text-t1 text-muted-foreground/70 mt-0.5 truncate max-w-[160px] font-sans" title={bot.last_reason ?? undefined}>
                                  {bot.last_reason ?? "等待訊號"}
                                </span>
                              </div>
                            )}
                          </td>

                          {/* 3. 均價 / 標記（卡片寬度 >= 740px 直接顯示；較窄時可點擊列展開檢視） */}
                          {showPriceCol && (
                            <td className="px-2 py-2.5 text-right font-mono whitespace-nowrap tabular-nums">
                              <div className="flex flex-col items-end">
                                <span className="text-t3 font-medium text-foreground leading-tight">
                                  {hasPos ? formatDecimal(avgPx, { prefix: "$" }) : "空手"}
                                </span>
                                <span className="text-t1 text-muted-foreground leading-tight mt-0.5">
                                  {formatDecimal(markPx, { prefix: "$" })}
                                </span>
                              </div>
                            </td>
                          )}

                          {/* 4. 未實現 / 權益 */}
                          <td className="px-2 py-2.5 text-right font-mono whitespace-nowrap tabular-nums">
                            <div className="flex flex-col items-end">
                              <span className={cn("text-t4 font-bold leading-tight", toneOf(unrealized))}>
                                {formatDecimal(unrealized, { sign: true, prefix: "$" })}
                              </span>
                              <span className="text-t1 text-muted-foreground leading-tight mt-0.5">
                                {formatDecimal(bot.equity, { prefix: "$" }, "未啟動")}
                              </span>
                            </div>
                          </td>

                          {/* 5. 風控 / P6 */}
                          {showRiskCol && (
                            <td className="px-2 py-2.5 text-right font-mono whitespace-nowrap">
                              <div className="flex flex-col items-end gap-0.5">
                                {statusMeta ? (
                                  <span className={cn("px-1.5 py-0.5 rounded border text-t1 font-semibold leading-none whitespace-nowrap", statusMeta.className)}>
                                    {statusMeta.label}
                                    {botRisk?.derived.effective_leverage
                                      ? ` ${formatDecimal(botRisk.derived.effective_leverage, { digits: 2 })}x`
                                      : ""}
                                  </span>
                                ) : hasPos ? (
                                  <span className="px-1.5 py-0.5 rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-t1 font-semibold leading-none whitespace-nowrap">
                                    持倉中
                                  </span>
                                ) : (
                                  <span className="text-t2 text-muted-foreground">待命</span>
                                )}
                                <span className="text-t1 text-muted-foreground/75 whitespace-nowrap">
                                  {hasPos ? "P6 未配置" : "無部位"}
                                </span>
                              </div>
                            </td>
                          )}

                          {/* 6. 操作（微型走勢只於卡片 >= 860px 顯示，任意寬度保證按鈕不切邊） */}
                          <td className="py-2.5 pr-3 pl-2 text-right whitespace-nowrap">
                            <div className="flex items-center justify-end gap-1.5">
                              {showSpark && spark.path && (
                                <svg width={48} height={16} className="overflow-visible shrink-0">
                                  <path
                                    d={spark.path}
                                    fill="none"
                                    stroke={spark.isGain ? "var(--primary)" : "#f43f5e"}
                                    strokeWidth={1.5}
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                  />
                                </svg>
                              )}
                              {isActive ? (
                                <button
                                  type="button"
                                  disabled={!controls.canStop || busyKey !== null}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    void controls.stop(bot);
                                  }}
                                  title={controls.canStop ? "完成當前事件後停止此 run" : "目前不可停止"}
                                  className="px-2 py-0.5 rounded text-t2 font-mono border border-border/80 bg-background/60 text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
                                >
                                  {busyKey === `stop:${bot.bot_id}` ? "送出中" : "暫停"}
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  disabled={!controls.canStart || busyKey !== null}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    void controls.start(bot);
                                  }}
                                  title={controls.canStart ? "以固定模板啟動新 run" : "目前不可啟動"}
                                  className="px-2 py-0.5 rounded text-t2 font-mono border border-emerald-500/40 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
                                >
                                  {busyKey === `start:${bot.bot_id}` ? "送出中" : "恢復"}
                                </button>
                              )}
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  selectBot(bot.bot_id);
                                  navigate("/bots");
                                }}
                                title="開啟實例監控頁"
                                className="px-2 py-0.5 rounded text-t2 font-mono border border-primary/40 bg-primary/10 text-primary hover:bg-primary hover:text-primary-foreground transition-colors cursor-pointer inline-flex items-center gap-0.5 whitespace-nowrap"
                              >
                                <span>詳情</span>
                                <ArrowUpRight className="size-2.5" />
                              </button>
                            </div>
                          </td>
                        </tr>

                        {/* 原地展開：均價/標記、帳務與次要交易所風控明細 */}
                        {isExpanded && (
                          <tr className="bg-background/50">
                            <td colSpan={colSpan} className="px-4 py-2.5 border-b border-border/60">
                              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5 font-mono text-t1">
                                <div>
                                  <span className="text-muted-foreground block font-sans">均價 / 標記價</span>
                                  <span className="text-foreground font-semibold tabular-nums">
                                    {hasPos ? formatDecimal(avgPx, { prefix: "$" }) : "空手"} / {formatDecimal(markPx, { prefix: "$" })}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-muted-foreground block font-sans">已實現損益</span>
                                  <span className={cn("font-semibold tabular-nums", toneOf(bot.realized_pnl))}>
                                    {formatDecimal(bot.realized_pnl, { sign: true, prefix: "$" })}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-muted-foreground block font-sans">手續費累計</span>
                                  <span className="text-rose-400 font-semibold tabular-nums">
                                    {formatDecimal(bot.fees, { prefix: "$", digits: 4 })}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-muted-foreground block font-sans">風控期間損益</span>
                                  <span className={cn("font-semibold tabular-nums", toneOf(botRisk?.derived.period_pnl))}>
                                    {botRisk
                                      ? `${formatDecimal(botRisk.derived.period_pnl, { sign: true, prefix: "$" })} (${formatRatioPct(botRisk.derived.period_pnl_ratio)})`
                                      : "不適用"}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-muted-foreground block font-sans">資金費 / 強平墊</span>
                                  <span className="text-muted-foreground">合成 funding=0 · 無模型</span>
                                </div>
                                <div>
                                  <span className="text-muted-foreground block font-sans">帳戶來源 / run</span>
                                  <span className="text-foreground">
                                    {bot.account_source ? ACCOUNT_SOURCE_LABEL[bot.account_source] : "無觀測"} · {shortId(bot.current_run_id)}
                                  </span>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })
                )}
              </tbody>
            </table>
          )}
        </div>

        {controls.error && (
          <div className="px-3 py-1.5 text-t1 font-mono text-rose-400 border-t border-border/60 shrink-0">
            命令失敗：{controls.error}
          </div>
        )}

        {/* 底部狀態列 */}
        <div className="px-3 py-1.5 border-t border-border/70 bg-secondary/25 flex items-center justify-between gap-2 text-t1 font-mono text-muted-foreground shrink-0 flex-wrap">
          <div className="flex items-center gap-2">
            <span>持倉: <strong className="text-foreground">{openCount}</strong></span>
            <span className="text-border">|</span>
            <span>結算: <strong className="text-foreground">{settlementLabel(summary?.invariants.settlement)}</strong></span>
            <span className="text-border hidden xl:inline">|</span>
            <span className="text-muted-foreground/70 hidden xl:inline font-sans">點擊任一列展開風控明細</span>
          </div>
          <span>平倉出口 v1 未接線</span>
        </div>
      </div>
    </div>
  );
}
