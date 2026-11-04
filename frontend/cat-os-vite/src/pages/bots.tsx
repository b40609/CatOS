import { createFileRoute } from "@tanstack/react-router";
import { useEffect } from "react";
import { Pause, Play, Cpu, Layers, ShieldCheck, Clock, Server } from "lucide-react";
import { AppShell } from "@/components/catos/shell";
import { PulseBeacon } from "@/components/catos/pulse-beacon";
import { cn } from "@/lib/utils";
import { useInspectorStore } from "@/state/inspectorStore";
import { useCatStore } from "@/state/catStore";
import { ACTIVE_STATES, type BotViewDTO } from "@/contracts";
import { ACCOUNT_SOURCE_LABEL, BOT_STATE_LABEL, RISK_STATUS_META, useBotControls } from "@/components/catos/v0-bot-table";
import { formatClock, formatDateTime, formatDecimal, formatRatioPct, formatTimeframe, shortId, toneOf } from "@/lib/format";

export const Route = createFileRoute("/bots")({
  head: () => ({
    meta: [
      { title: "實例監控 (Fleet) — catOS Quant Terminal" },
      { name: "description", content: "catOS 實例監控：本機模擬 Bot 的 run 狀態、合約持倉、風控期間損益與控制面事件。" },
      { property: "og:title", content: "實例監控 (Fleet) — catOS Quant Terminal" },
      { property: "og:description", content: "監控本機模擬策略實例的 run 狀態、合約持倉與風控期間損益。" },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: BotManagement,
});

type StatusKind = "running" | "stopped" | "error";

function statusKind(bot: BotViewDTO): StatusKind {
  if (ACTIVE_STATES.has(bot.state)) return "running";
  if (bot.state === "failed" || bot.state === "recovery_required") return "error";
  return "stopped";
}

const STATUS_META: Record<StatusKind, { text: string; dot: string }> = {
  running: { text: "text-up", dot: "bg-up" },
  stopped: { text: "text-muted-foreground", dot: "bg-muted-foreground" },
  error: { text: "text-down", dot: "bg-down" },
};

function positionText(bot: BotViewDTO) {
  if (bot.position === null) return "無帳戶觀測";
  if (/^-?0+(\.0*)?$/.test(bot.position)) return "FLAT 0";
  const side = bot.position.startsWith("-") ? "SHORT" : "LONG";
  return `${side} ${formatDecimal(bot.position.replace(/^-/, ""), { digits: 0 })} 張`;
}

function Row({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex items-center justify-between">
      <span>{label}</span>
      <span className={cn("font-semibold", tone ?? "text-foreground")}>{value}</span>
    </div>
  );
}

function BotManagement() {
  const bots = useCatStore((s) => s.bots);
  const risk = useCatStore((s) => s.risk);
  const summary = useCatStore((s) => s.summary);
  const strategies = useCatStore((s) => s.strategies);
  const connection = useCatStore((s) => s.connection);
  const mode = useCatStore((s) => s.mode);
  const { selectedBotId, selectBot } = useInspectorStore();
  const controls = useBotControls();

  useEffect(() => {
    if (bots.length > 0 && !bots.some((b) => b.bot_id === selectedBotId)) selectBot(bots[0].bot_id);
  }, [bots, selectedBotId, selectBot]);

  const totalBots = bots.length;
  const runningBots = bots.filter((b) => statusKind(b) === "running").length;
  const stoppedBots = bots.filter((b) => statusKind(b) === "stopped").length;
  const errorBots = bots.filter((b) => statusKind(b) === "error").length;

  const selectedBot = bots.find((b) => b.bot_id === selectedBotId) ?? bots[0] ?? null;
  const botRisk = selectedBot && risk && risk.bot_id === selectedBot.bot_id ? risk : null;
  const strategy = selectedBot ? strategies.find((s) => s.strategy_id === selectedBot.strategy_id) ?? null : null;
  const statusMeta = botRisk ? RISK_STATUS_META[botRisk.derived.status] : null;

  const emptyText =
    connection.status === "mode_not_open" ? "此模式未開放（demo/live 不在 v1 範圍）"
    : connection.status === "unavailable" ? `模擬服務不可用：${connection.detail ?? "unknown"}`
    : connection.status === "error" ? `無法連線：${connection.detail ?? "network_error"}`
    : "等待模擬服務…";

  return (
    <AppShell>
      {/* 頂部摘要條 */}
      <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2 rounded border border-border/80 bg-surface/90 px-3 py-1.5 text-xs font-mono shadow-xs backdrop-blur-md">
        <div className="flex items-center gap-2.5">
          <span className="font-mono text-t1 font-bold text-primary bg-primary/10 border border-primary/25 rounded px-1.5 py-0.5 uppercase tracking-wider">FLEET</span>
          <span className="text-muted-foreground">總數: <strong className="text-foreground">{totalBots}</strong></span>
          <span className="text-border">|</span>
          <span className="text-up font-bold flex items-center gap-1"><PulseBeacon size={3.5} variant="up" /> 運行: {runningBots}</span>
          <span className="text-border">|</span>
          <span className="text-muted-foreground">停止: <strong className="text-foreground">{stoppedBots}</strong></span>
          <span className="text-border">|</span>
          <span className={cn("font-bold", errorBots > 0 ? "text-down" : "text-muted-foreground")}>異常: {errorBots}</span>
          <span className="text-border">|</span>
          <span className="text-muted-foreground">風控期間損益: <strong className={cn("font-bold", toneOf(summary?.period_pnl))}>
            {formatDecimal(summary?.period_pnl, { sign: true, prefix: "$" })}</strong></span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-t2 text-muted-foreground font-mono hidden md:inline">
            v1 固定 1 個登錄策略 · 1 Bot : 1 SWAP · {mode === "local" ? "本機模擬" : mode.toUpperCase()}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 items-start">
        {/* 左側：實例陣列 */}
        <div className="lg:col-span-7 rounded-xl border border-border/80 bg-surface/90 overflow-hidden shadow-sm">
          <div className="flex items-center justify-between border-b border-border/80 px-3.5 py-2.5 bg-secondary/30">
            <div className="flex items-center gap-2">
              <Server className="size-4 text-primary" />
              <span className="text-xs font-semibold text-foreground">策略實例陣列 (Strategy Bot Fleet)</span>
            </div>
            <span className="text-t2 font-mono text-muted-foreground">點選實例檢視 run 與風控投影</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-border/70 bg-secondary/10">
                  {["狀態", "實例代號", "綁定策略", "獨佔合約", "當前部位", "期間損益", "權益", "操作"].map((h) => (
                    <th key={h} className={cn("py-2 text-t2 font-mono uppercase text-muted-foreground font-medium whitespace-nowrap",
                      h === "期間損益" || h === "權益" ? "px-2" : "px-3")}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {bots.length === 0 && (
                  <tr><td colSpan={8} className="px-3 py-8 text-center text-muted-foreground font-mono">{emptyText}</td></tr>
                )}
                {bots.map((b) => {
                  const kind = statusKind(b);
                  const m = STATUS_META[kind];
                  const isSelected = b.bot_id === selectedBot?.bot_id;
                  const r = risk && risk.bot_id === b.bot_id ? risk : null;
                  return (
                    <tr key={b.bot_id} onClick={() => selectBot(b.bot_id)}
                        className={cn("cursor-pointer transition-colors", isSelected ? "bg-secondary/60" : "hover:bg-secondary/40")}>
                      <td className="px-3 py-2.5">
                        <span className="flex items-center gap-1.5">
                          {kind === "running" ? <PulseBeacon size={4} variant="up" /> : <span className={cn("size-1.5 rounded-full", m.dot)} />}
                          <span className={cn("font-mono text-t2 font-bold uppercase whitespace-nowrap", m.text)}>{b.state}</span>
                        </span>
                      </td>
                      <td className="font-mono px-3 py-2.5 text-foreground font-bold whitespace-nowrap">{b.bot_id}</td>
                      <td className="px-3 py-2.5 text-muted-foreground text-t3 whitespace-nowrap" title={`${b.strategy_id}@${b.strategy_version}`}>
                        <span className="block leading-tight">{b.strategy_name}</span>
                        <span className="block text-t1 font-mono leading-tight">{b.strategy_version}</span>
                      </td>
                      <td className="font-mono px-3 py-2.5 text-primary text-t3 font-semibold whitespace-nowrap">{b.inst_id ?? "不適用"} · {formatTimeframe(b.timeframe_ms)}</td>
                      <td className="font-mono px-3 py-2.5 text-foreground/90 text-t3 font-medium whitespace-nowrap">{positionText(b)}</td>
                      <td className={cn("font-mono px-2 py-2.5 font-bold text-t3 whitespace-nowrap", toneOf(r?.derived.period_pnl))}>
                        {formatDecimal(r?.derived.period_pnl, { sign: true, prefix: "$" })}
                      </td>
                      <td className="font-mono px-2 py-2.5 text-foreground text-t3 whitespace-nowrap">{formatDecimal(b.equity, { prefix: "$" }, "未啟動")}</td>
                      <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                        <span className="flex items-center gap-1">
                          <button title={controls.canStart ? "啟動新 run (POST /bots/start)" : "目前不可啟動"}
                                  disabled={!controls.canStart || kind === "running" || controls.busy !== null}
                                  onClick={() => void controls.start(b)}
                                  className="rounded border border-border p-1 text-up hover:border-up/60 hover:bg-up/10 transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed">
                            <Play className="size-2.5" />
                          </button>
                          <button title={controls.canStop ? "完成當前事件後停止 run" : "目前不可停止"}
                                  disabled={!controls.canStop || kind !== "running" || controls.busy !== null}
                                  onClick={() => void controls.stop(b)}
                                  className="rounded border border-border p-1 text-muted-foreground hover:border-primary/60 hover:bg-primary/10 transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed">
                            <Pause className="size-2.5" />
                          </button>
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {controls.error && (
            <div className="px-3 py-1.5 text-t1 font-mono text-rose-400 border-t border-border/60">命令失敗：{controls.error}</div>
          )}
        </div>

        {/* 右側：選中實例之 run、風控與保護投影 */}
        {selectedBot && (
          <div className="lg:col-span-5 rounded-xl border border-border/80 bg-surface/90 p-3.5 space-y-3 shadow-sm">
            <div className="flex items-center justify-between border-b border-border/70 pb-2.5">
              <div className="flex items-center gap-2">
                <Cpu className="size-4 text-primary" />
                <div>
                  <h3 className="text-xs font-bold font-mono text-foreground">{selectedBot.bot_id}</h3>
                  <p className="text-t2 text-muted-foreground font-mono">{selectedBot.inst_id ?? "不適用"} · {selectedBot.strategy_name}</p>
                </div>
              </div>
              <span className={cn("px-2 py-0.5 rounded text-t2 font-mono font-bold uppercase bg-secondary", STATUS_META[statusKind(selectedBot)].text)}>
                {BOT_STATE_LABEL[selectedBot.state] ?? selectedBot.state}
              </span>
            </div>

            {/* 最近決策 */}
            <div className="rounded border border-border/70 bg-secondary/40 p-2.5 space-y-1.5 font-mono text-xs">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="px-1.5 py-0.2 rounded bg-primary/15 text-primary text-t1 font-bold border border-primary/25">最近決策</span>
                  <span className="font-bold text-foreground text-t3">
                    {selectedBot.last_disposition ?? "尚無 signal"}{selectedBot.last_reason ? ` · ${selectedBot.last_reason}` : ""}
                  </span>
                </div>
                <div className="flex items-center gap-1 text-t1 text-muted-foreground">
                  <Clock className="size-3 text-primary/80" />
                  <span>合成時間:</span>
                  <span className="text-foreground font-semibold">{formatClock(selectedBot.last_synthetic_time_ms)}</span>
                </div>
              </div>
              <div className="flex items-center gap-3 text-t1 text-muted-foreground pt-0.5">
                <span>bars <strong className="text-foreground">{selectedBot.bars}</strong> / 預熱 <strong className="text-foreground">{selectedBot.warmup_bars}</strong></span>
                <span>成交 <strong className="text-foreground">{selectedBot.fills}</strong></span>
                <span>部位 <strong className="text-foreground">{positionText(selectedBot)}</strong></span>
                <span>mark <strong className="text-foreground">{formatDecimal(selectedBot.mark, { prefix: "$" })}</strong></span>
              </div>
            </div>

            {/* run 資訊 */}
            <div className="rounded border border-border/70 bg-secondary/30 p-2.5 space-y-2">
              <div className="flex items-center justify-between text-t2 font-bold text-muted-foreground uppercase">
                <div className="flex items-center gap-1.5"><Layers className="size-3.5 text-primary" /><span>本次 run</span></div>
                <span className="text-t1 font-mono text-primary font-semibold" title={selectedBot.current_run_id ?? undefined}>
                  {selectedBot.current_run_id ? `run ${shortId(selectedBot.current_run_id)}` : "無 run"} · 共 {selectedBot.run_count} 次
                </span>
              </div>
              <div className="space-y-1 text-t1 text-muted-foreground font-mono">
                <Row label="建立" value={formatDateTime(selectedBot.run_created_at_ms)} />
                <Row label="結束" value={formatDateTime(selectedBot.finished_at_ms)} />
                <Row label="Worker PID" value={selectedBot.worker_pid === null ? "不適用" : String(selectedBot.worker_pid)} />
                <Row label="帳戶來源" value={selectedBot.account_source ? ACCOUNT_SOURCE_LABEL[selectedBot.account_source] : "無帳戶觀測"} />
                <Row label="權益" value={formatDecimal(selectedBot.equity, { prefix: "$" }, "未啟動")} />
                <Row label="已實現 / 未實現" value={`${formatDecimal(selectedBot.realized_pnl, { sign: true }, "不適用")} / ${formatDecimal(selectedBot.unrealized_pnl, { sign: true }, "不適用")}`} />
                <Row label="手續費" value={formatDecimal(selectedBot.fees, { digits: 4 }, "不適用")} />
                <Row label="終態帶倉 (僅顯示)" value={selectedBot.ownership_retained ? "是" : "否"} tone={selectedBot.ownership_retained ? "text-amber-400" : undefined} />
                <Row label="錯誤" value={selectedBot.error ?? "無"} tone={selectedBot.error ? "text-rose-400" : undefined} />
                <Row label="製品雜湊" value={shortId(selectedBot.artifact_hash, 12)} />
                {strategy && <Row label="參數" value={JSON.stringify(selectedBot.parameters)} />}
              </div>
            </div>

            {/* 風控投影 */}
            <div className="rounded border border-border/70 bg-secondary/30 p-2.5 space-y-2 font-mono">
              <div className="flex items-center justify-between text-t2 font-bold text-muted-foreground uppercase">
                <div className="flex items-center gap-1.5"><ShieldCheck className="size-3.5 text-primary" /><span>帳戶風控 (R1 合成基準)</span></div>
                {statusMeta ? (
                  <span className={cn("px-1.5 py-0.2 rounded text-t1 font-bold border", statusMeta.className)}>
                    {statusMeta.label} · {botRisk?.derived.can_increase ? "可增倉" : "禁增倉"}
                  </span>
                ) : (
                  <span className="px-1.5 py-0.2 rounded text-t1 font-bold bg-zinc-400/10 text-zinc-300 border border-zinc-400/30">尚無觀測</span>
                )}
              </div>
              {botRisk ? (
                <>
                  <div className="grid grid-cols-2 gap-2 text-t2">
                    <div className="p-2 rounded bg-background/60 border border-border/60">
                      <span className="text-t1 text-muted-foreground block">風控期間損益</span>
                      <span className={cn("text-t4 font-bold block", toneOf(botRisk.derived.period_pnl))}>{formatDecimal(botRisk.derived.period_pnl, { sign: true, prefix: "$" })}</span>
                      <span className="text-t1 text-muted-foreground block">{formatRatioPct(botRisk.derived.period_pnl_ratio)} · 基準 {formatDecimal(botRisk.basis?.equity, { prefix: "$" })}</span>
                    </div>
                    <div className="p-2 rounded bg-background/60 border border-border/60">
                      <span className="text-t1 text-muted-foreground block">有效槓桿</span>
                      <span className="text-t4 font-bold text-foreground block">{formatDecimal(botRisk.derived.effective_leverage, { digits: 2 })}x</span>
                      <span className="text-t1 text-muted-foreground block">上限 {formatDecimal(botRisk.limits.leverage, { digits: 1 })}x · 單幣 {formatRatioPct(botRisk.limits.symbol_share, { sign: false })}</span>
                    </div>
                  </div>
                  <div className="space-y-1 text-t1 text-muted-foreground border-t border-border/40 pt-1.5">
                    <Row label="名目曝險 / 總預算" value={`${formatDecimal(botRisk.derived.notional, { prefix: "$" })} / ${formatDecimal(botRisk.derived.exposure_budget, { prefix: "$" })}`} />
                    <Row label="單幣預算上限" value={formatDecimal(botRisk.derived.symbol_budget, { prefix: "$" })} />
                    <Row label="mode / health / phase" value={`${botRisk.mode} / ${botRisk.health} / ${botRisk.phase}`} />
                    <Row label="鎖存原因" value={botRisk.reasons.length ? botRisk.reasons.join(", ") : "無"} tone={botRisk.reasons.length ? "text-amber-400" : undefined} />
                    <Row label="Soft / Hard 日損門檻" value={`${formatRatioPct(botRisk.limits.soft_loss, { sign: false })} / ${formatRatioPct(botRisk.limits.hard_loss, { sign: false })}`} />
                    <Row label="基準起算 (合成)" value={botRisk.basis ? formatDateTime(botRisk.basis.period_start_ms) : "尚無基準"} />
                    <Row label="觀測時點" value={`seq ${botRisk.seq} · ${formatClock(botRisk.time_ms)}`} />
                  </div>
                </>
              ) : (
                <p className="text-t2 text-muted-foreground">啟動模擬 run 後，此處顯示每根已收盤 K 線的風控觀測。</p>
              )}
              <div className="flex items-center justify-between text-t1 text-muted-foreground border-t border-border/40 pt-1.5">
                <span>交易所端停損 (P6)</span>
                <span className="text-zinc-300 font-semibold" title="protection = null：v1 local-sim 未配置 P6 保護">未啟用</span>
              </div>
              <div className="flex items-center justify-between text-t1 text-muted-foreground">
                <span>Kill Switch / 人工 re-arm</span>
                <span className="text-zinc-300 font-semibold" title="v1 不暴露 kill-switch / re-arm / 門檻修改 HTTP">未接線</span>
              </div>
            </div>

            <div className="flex gap-2 pt-1 font-mono">
              {statusKind(selectedBot) === "running" ? (
                <button disabled={!controls.canStop || controls.busy !== null} onClick={() => void controls.stop(selectedBot)}
                        className="flex-1 rounded border border-border/80 bg-secondary/60 hover:bg-secondary py-1.5 text-xs font-semibold text-foreground transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed">
                  {controls.busy ? "送出中…" : "暫停 (完成當前事件後停止)"}
                </button>
              ) : (
                <button disabled={!controls.canStart || controls.busy !== null} onClick={() => void controls.start(selectedBot)}
                        className="flex-1 rounded border border-primary/50 bg-primary/10 hover:bg-primary/20 py-1.5 text-xs font-semibold text-primary transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed">
                  {controls.busy ? "送出中…" : "恢復運行 (啟動新 run)"}
                </button>
              )}
              <button disabled title="v1 無重啟端點；停止後再啟動即為新 run"
                      className="flex-1 rounded border border-border/60 bg-secondary/30 py-1.5 text-xs font-semibold text-muted-foreground cursor-not-allowed">
                重啟 Worker · 未接線
              </button>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
