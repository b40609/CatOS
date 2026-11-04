import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { CardHeaderTitle } from "./card-header-title";
import { useInspectorStore } from "@/state/inspectorStore";
import { useCatStore } from "@/state/catStore";
import { StateAdapter, stateAdapter } from "@/state/stateAdapter";
import { ACTIVE_STATES, type BotViewDTO } from "@/contracts";
import { formatDecimal, formatRatioPct, formatTimeframe, toPlotNumber, toneOf } from "@/lib/format";
import { useRouter } from "@/lib/router";
import { ArrowUpRight } from "lucide-react";

interface V0BotTableProps {
  className?: string;
  showHeader?: boolean;
}

export const RISK_STATUS_META: Record<string, { label: string; className: string }> = {
  normal: { label: "正常", className: "bg-emerald-400/10 text-emerald-400 border-emerald-400/30" },
  soft_latch: { label: "軟鎖存", className: "bg-amber-400/10 text-amber-400 border-amber-400/30" },
  hard_latch: { label: "硬鎖存", className: "bg-rose-400/10 text-rose-400 border-rose-400/30" },
  missing: { label: "缺基準", className: "bg-zinc-400/10 text-zinc-300 border-zinc-400/30" },
};

export const BOT_STATE_LABEL: Record<string, string> = {
  starting: "啟動中", running: "運行中", stopping: "停止中", completed: "已完成",
  stopped: "已停止", failed: "失敗", recovery_required: "待恢復",
};

export const ACCOUNT_SOURCE_LABEL: Record<string, string> = {
  final_account: "最終帳戶", signal: "決策前視圖", signal_fill: "含同根成交",
};

/** 由 Bot 狀態與服務能力決定可用的控制動作；demo/live 一律停用。 */
export function useBotControls() {
  const service = useCatStore((s) => s.service);
  const mode = useCatStore((s) => s.mode);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (key: string, action: () => Promise<void>) => {
    setBusy(key);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  return {
    busy, error,
    canStart: mode === "local" && !!service?.capabilities.start,
    canStop: mode === "local" && !!service?.capabilities.stop,
    start: (bot: BotViewDTO) => run(`start:${bot.bot_id}`, () => stateAdapter.startBot(bot.bot_id)),
    stop: (bot: BotViewDTO) => bot.current_run_id
      ? run(`stop:${bot.bot_id}`, () => stateAdapter.stopBot(bot.current_run_id as string))
      : Promise.resolve(),
  };
}

export function V0BotTable({ className, showHeader = true }: V0BotTableProps) {
  const bots = useCatStore((s) => s.bots);
  const risk = useCatStore((s) => s.risk);
  const events = useCatStore((s) => s.events);
  const connection = useCatStore((s) => s.connection);
  const [botFilter, setBotFilter] = useState<"all" | "running" | "stopped">("all");
  const { selectedBotId, selectBot } = useInspectorStore();
  const { navigate } = useRouter();
  const controls = useBotControls();

  const runningCount = bots.filter((b) => ACTIVE_STATES.has(b.state)).length;
  const rows = bots.filter((b) => botFilter === "all" ? true
    : botFilter === "running" ? ACTIVE_STATES.has(b.state) : !ACTIVE_STATES.has(b.state));

  // Sparkline：本次 run 的 signal.account.equity 序列（幾何用途的浮點轉換）
  const sparkFor = useMemo(() => {
    const cache = new Map<string, { path: string; isGain: boolean }>();
    return (bot: BotViewDTO) => {
      const key = bot.current_run_id ?? "none";
      const cached = cache.get(key);
      if (cached) return cached;
      const pts = StateAdapter.equityCurve(events, bot.current_run_id).map((p) => toPlotNumber(p.equity)).filter((v) => !Number.isNaN(v));
      if (pts.length < 2) { const empty = { path: "", isGain: true }; cache.set(key, empty); return empty; }
      const lo = Math.min(...pts), hi = Math.max(...pts), span = hi - lo || 1;
      const w = 56, h = 16, n = pts.length;
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
    : bots.length === 0 ? "等待模擬服務…" : "此篩選無實例";

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40", className)}>
      {showHeader && (
        <div className="flex items-center justify-between px-3 h-9 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
          <CardHeaderTitle cardId="bots" title="策略實例監控矩陣" />
          <div className="flex items-center gap-0.5 bg-background/60 border border-border/60 rounded p-0.5 shrink-0 whitespace-nowrap flex-nowrap">
            {[
              { id: "all", label: `全部(${bots.length})` },
              { id: "running", label: `運作(${runningCount})` },
              { id: "stopped", label: `停止(${bots.length - runningCount})` },
            ].map((f) => (
              <button key={f.id} type="button" onClick={() => setBotFilter(f.id as typeof botFilter)}
                className={cn("px-2 py-0.5 text-t2 font-mono rounded transition-colors cursor-pointer whitespace-nowrap shrink-0",
                  botFilter === f.id ? "bg-secondary text-foreground font-semibold shadow-xs" : "text-muted-foreground hover:text-foreground")}>
                {f.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-auto min-w-0 max-w-full">
        <table className="w-full text-left border-collapse table-auto min-w-[540px]">
          <thead className="border-b border-border/80 bg-background/40 text-t1 font-mono text-muted-foreground sticky top-0 z-10 backdrop-blur-sm">
            <tr>
              <th className="py-2.5 pl-3 pr-2 font-medium">實例 / 標的</th>
              <th className="px-2 font-medium">策略模型 / 曝險</th>
              <th className="px-2 text-right font-medium">風控期間損益</th>
              <th className="px-2 text-right font-medium hidden sm:table-cell">權益</th>
              <th className="px-2 font-medium hidden md:table-cell">風控狀態</th>
              <th className="py-2.5 pr-3 pl-2 text-right font-medium">走勢與操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40 text-xs">
            {rows.length === 0 && (
              <tr><td colSpan={6} className="py-8 text-center text-muted-foreground font-mono text-xs">{emptyText}</td></tr>
            )}
            {rows.map((bot) => {
              const isActive = ACTIVE_STATES.has(bot.state);
              const isSelected = selectedBotId === bot.bot_id;
              const botRisk = risk && risk.bot_id === bot.bot_id ? risk : null;
              const statusMeta = botRisk ? RISK_STATUS_META[botRisk.derived.status] : null;
              const spark = sparkFor(bot);
              const busyKey = controls.busy;
              return (
                <tr key={bot.bot_id} onClick={() => selectBot(bot.bot_id)}
                  className={cn("hover:bg-secondary/30 transition-all group cursor-pointer",
                    isSelected && "bg-secondary/40", !isActive && "opacity-80")}
                  title="點擊選取此實例">
                  <td className="py-2.5 pl-3 pr-2">
                    <div className="flex items-center gap-2">
                      <span className={cn("w-2 h-2 rounded-full shrink-0",
                        isActive ? "bg-emerald-400 shadow-[0_0_6px_var(--emerald-400)]"
                        : bot.state === "failed" || bot.state === "recovery_required" ? "bg-rose-400" : "bg-muted-foreground/50")} />
                      <div className="flex flex-col min-w-0">
                        <span className="text-t4 font-bold text-foreground leading-tight group-hover:text-primary transition-colors whitespace-nowrap">
                          {bot.bot_id}
                        </span>
                        <div className="flex items-center gap-1 text-t1 font-mono text-muted-foreground leading-tight">
                          <span className="text-primary font-semibold whitespace-nowrap">{bot.inst_id ?? "不適用"}</span>
                          <span>{formatTimeframe(bot.timeframe_ms)}</span>
                          <span>· {BOT_STATE_LABEL[bot.state] ?? bot.state}</span>
                        </div>
                      </div>
                    </div>
                  </td>

                  <td className="px-2 py-2.5">
                    <div className="flex flex-col gap-0.5">
                      <span className="text-t3 font-semibold text-foreground leading-tight">{bot.strategy_name}</span>
                      <span className="text-t1 font-mono text-muted-foreground leading-tight">
                        {botRisk
                          ? `名目 ${formatDecimal(botRisk.derived.notional, { prefix: "$" })} · 單幣上限 ${formatDecimal(botRisk.derived.symbol_budget, { prefix: "$" })}`
                          : "尚無風控觀測"}
                      </span>
                    </div>
                  </td>

                  <td className="px-2 py-2.5 text-right font-mono">
                    <div className="flex flex-col items-end">
                      <span className={cn("text-t4 font-bold leading-tight", toneOf(botRisk?.derived.period_pnl))}>
                        {formatDecimal(botRisk?.derived.period_pnl, { sign: true, prefix: "$" })}
                      </span>
                      <span className={cn("text-t1 leading-tight font-semibold", toneOf(botRisk?.derived.period_pnl_ratio))}>
                        {formatRatioPct(botRisk?.derived.period_pnl_ratio)}
                      </span>
                    </div>
                  </td>

                  <td className="px-2 py-2.5 text-right font-mono hidden sm:table-cell">
                    <div className="flex flex-col items-end">
                      <span className="text-t3 font-bold leading-tight text-foreground">
                        {formatDecimal(bot.equity, { prefix: "$" }, "未啟動")}
                      </span>
                      <span className="text-t1 text-muted-foreground leading-tight">
                        {bot.account_source ? ACCOUNT_SOURCE_LABEL[bot.account_source] : "無帳戶觀測"}
                      </span>
                    </div>
                  </td>

                  <td className="px-2 py-2.5 font-mono hidden md:table-cell">
                    {statusMeta ? (
                      <div className="flex items-center gap-1.5 leading-tight">
                        <span className={cn("px-1.5 py-0.2 rounded border text-t1 font-semibold whitespace-nowrap", statusMeta.className)}>
                          {statusMeta.label} (槓桿 {formatDecimal(botRisk?.derived.effective_leverage, { digits: 2 })}x)
                        </span>
                      </div>
                    ) : (
                      <span className="text-t2 text-muted-foreground">尚無觀測</span>
                    )}
                  </td>

                  <td className="py-2.5 pr-3 pl-2 text-right">
                    <div className="flex items-center justify-end gap-2">
                      {spark.path ? (
                        <svg width={56} height={16} className="overflow-visible shrink-0 hidden xl:block">
                          <path d={spark.path} fill="none" stroke={spark.isGain ? "var(--primary)" : "#f43f5e"}
                                strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      ) : null}
                      {isActive ? (
                        <button type="button" disabled={!controls.canStop || busyKey !== null}
                          onClick={(e) => { e.stopPropagation(); void controls.stop(bot); }}
                          title={controls.canStop ? "完成當前事件後停止此 run" : "目前不可停止"}
                          className="px-2 py-0.5 rounded text-t2 font-mono border border-border/80 bg-background/60 text-muted-foreground hover:text-foreground hover:bg-secondary transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap">
                          {busyKey === `stop:${bot.bot_id}` ? "送出中" : "暫停"}
                        </button>
                      ) : (
                        <button type="button" disabled={!controls.canStart || busyKey !== null}
                          onClick={(e) => { e.stopPropagation(); void controls.start(bot); }}
                          title={controls.canStart ? "以固定模板啟動新 run (POST /bots/start)" : "槽位占用、來源漂移或非本機模式時不可啟動"}
                          className="px-2 py-0.5 rounded text-t2 font-mono border border-emerald-500/40 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap">
                          {busyKey === `start:${bot.bot_id}` ? "送出中" : "恢復"}
                        </button>
                      )}
                      <button type="button"
                        onClick={(e) => { e.stopPropagation(); selectBot(bot.bot_id); navigate("/bots"); }}
                        title="開啟實例監控頁"
                        className="px-2 py-0.5 rounded text-t2 font-mono border border-primary/40 bg-primary/10 text-primary hover:bg-primary hover:text-primary-foreground transition-all cursor-pointer flex items-center gap-0.5 whitespace-nowrap">
                        <span>詳情</span>
                        <ArrowUpRight className="size-2.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {controls.error && (
          <div className="px-3 py-1.5 text-t1 font-mono text-rose-400 border-t border-border/60">命令失敗：{controls.error}</div>
        )}
      </div>
    </div>
  );
}
