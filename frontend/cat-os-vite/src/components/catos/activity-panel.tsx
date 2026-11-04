import { useState } from "react";
import { cn } from "@/lib/utils";
import { CardHeaderTitle } from "./card-header-title";
import { useCatStore } from "@/state/catStore";
import type { BotControlState, PositionDTO } from "@/contracts";
import { formatDecimal, signOf, toneOf } from "@/lib/format";

export type ActivityTab = "positions" | "orders";

interface ActivityPanelProps {
  className?: string;
  showHeader?: boolean;
}

const RUN_STATE_LABEL: Record<BotControlState, string> = {
  starting: "啟動中",
  running: "執行中",
  stopping: "停止中",
  completed: "已完成",
  stopped: "已停止",
  failed: "失敗",
  recovery_required: "待恢復",
};

const RUN_STATE_TONE: Record<BotControlState, string> = {
  starting: "border-amber-400/30 text-amber-400",
  running: "border-emerald-400/30 text-emerald-400",
  stopping: "border-amber-400/30 text-amber-400",
  completed: "border-border/80 text-muted-foreground",
  stopped: "border-border/80 text-muted-foreground",
  failed: "border-rose-400/30 text-rose-400",
  recovery_required: "border-rose-400/30 text-rose-400",
};

const NA_CLASS = "text-t3 text-muted-foreground leading-tight";
const NA_SUB_CLASS = "text-t1 text-muted-foreground/70 leading-tight mt-0.5";

/** Explicit not-applicable cell: primary state text + reason line, tooltip explains why. */
function NotApplicableCell({ label, reason, title }: { label: string; reason: string; title: string }) {
  return (
    <div className="flex flex-col items-end" title={title}>
      <span className={NA_CLASS}>{label}</span>
      <span className={NA_SUB_CLASS}>{reason}</span>
    </div>
  );
}

function settlementLabel(settlement: string | undefined): string {
  if (!settlement) return "不適用";
  if (settlement === "cross_net_mode") return "cross + net_mode";
  return settlement;
}

function magnitude(value: string): string {
  return value.trim().replace(/^[+-]/, "");
}

function PositionRowView({ p }: { p: PositionDTO }) {
  const sign = signOf(p.position);
  const isShort = sign === "negative";
  const sideLabel = isShort ? "▼ 空" : "▲ 多";

  return (
    <tr className="hover:bg-secondary/30 transition-colors group">
      {/* 1. 合約標的 + 方向標籤 + 實質持倉 */}
      <td className="py-2.5 pl-3 pr-2">
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5">
            <span
              className={cn(
                "px-1 py-0.2 rounded text-t1 font-bold font-mono inline-flex items-center",
                isShort
                  ? "bg-rose-400/10 text-rose-400 border border-rose-400/25"
                  : "bg-emerald-400/10 text-emerald-400 border border-emerald-400/25"
              )}
            >
              {sideLabel}
            </span>
            <span className="text-t4 font-bold text-foreground leading-tight whitespace-nowrap">
              {p.inst_id ?? "不適用"}
            </span>
            <span
              className={cn(
                "px-1 py-0.2 rounded border text-t1 font-mono leading-tight whitespace-nowrap",
                RUN_STATE_TONE[p.run_state]
              )}
              title={`run_state: ${p.run_state}`}
            >
              {RUN_STATE_LABEL[p.run_state]}
            </span>
          </div>
          <span className="text-t2 font-mono text-muted-foreground leading-tight pl-0.5 mt-0.5 whitespace-nowrap">
            {formatDecimal(magnitude(p.position), { digits: 0 })} 張
            <span className="mx-1 text-border">·</span>
            名目 {formatDecimal(p.notional, { prefix: "$" })}
            <span className="mx-1 text-border">·</span>
            <span
              className={cn(p.verified ? "text-emerald-400/80" : "text-amber-400/80")}
              title={p.verified ? "部位已對帳" : "部位尚未對帳或對帳狀態未知"}
            >
              {p.verified ? "已對帳" : "未對帳"}
            </span>
          </span>
        </div>
      </td>

      {/* 2. 開倉均價與最新標記價 */}
      <td className="px-2 py-2.5 text-right font-mono">
        <div className="flex flex-col items-end">
          <span className="text-t3 font-medium text-foreground leading-tight">
            {formatDecimal(p.average_entry, { prefix: "$" })}
          </span>
          <span
            className={cn("text-t1 leading-tight mt-0.5", p.mark === null ? "text-muted-foreground/70" : "text-muted-foreground")}
            title={p.mark === null ? "本輪尚無標記價觀測" : "最新標記價"}
          >
            {formatDecimal(p.mark, { prefix: "$" })}
          </span>
        </div>
      </td>

      {/* 3. 未實現損益 (金額；ROE 無保證金模型) */}
      <td className="px-2 py-2.5 text-right font-mono">
        <div className="flex flex-col items-end">
          <span className={cn("text-t4 font-bold leading-tight", toneOf(p.unrealized_pnl))}>
            {formatDecimal(p.unrealized_pnl, { sign: true, prefix: "$" })}
          </span>
          <span className={NA_SUB_CLASS} title="local-sim 無保證金模型，無法計算 ROE">
            ROE 不適用
          </span>
        </div>
      </td>

      {/* 4. 資金費率 */}
      <td className="px-2 py-2.5 text-right hidden sm:table-cell font-mono">
        <NotApplicableCell
          label="不適用"
          reason="合成 funding=0"
          title="合成資料 funding = explicit_zero，無費率與結算倒數"
        />
      </td>

      {/* 5. 強平安全墊 */}
      <td className="px-2 py-2.5 text-right hidden md:table-cell font-mono">
        <NotApplicableCell
          label="不適用"
          reason="無保證金模型"
          title="local-sim 無保證金模型，無強平價與安全墊"
        />
      </td>

      {/* 6. 交易所強制停損 (P6) */}
      <td className="px-2 py-2.5 text-right font-mono">
        <NotApplicableCell
          label="未啟用"
          reason="P6 未配置"
          title="P6 交易所端整倉停損保護未配置（protection = null）"
        />
      </td>

      {/* 7. 操作出口：v1 無平倉端點 */}
      <td className="py-2.5 pr-3 pl-2 text-right font-mono">
        <div className="flex flex-col items-end gap-0.5">
          <button
            type="button"
            disabled
            aria-disabled="true"
            className="px-2.5 py-0.5 rounded text-t2 font-mono border border-border/80 bg-background/40 text-muted-foreground cursor-not-allowed opacity-60"
            title="未接線：v1 local-sim 尚無平倉端點"
          >
            平倉
          </button>
          <span className="text-t1 text-muted-foreground/70 leading-tight">未接線</span>
        </div>
      </td>
    </tr>
  );
}

export function ActivityPanel({ className, showHeader = true }: ActivityPanelProps) {
  const positions = useCatStore((s) => s.positions);
  const summary = useCatStore((s) => s.summary);
  const bots = useCatStore((s) => s.bots);
  const connection = useCatStore((s) => s.connection);

  const [tab, setTab] = useState<ActivityTab>("positions");

  const modeNotOpen = connection.status === "mode_not_open";
  const noRunYet = bots.length === 0 || !summary;

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40", className)}>
      {/* 1. 一體化 Header 與 Tab 切換 */}
      {showHeader && (
        <div className="flex items-center justify-between px-3 h-9 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
          <CardHeaderTitle
            cardId="positions"
            title="持倉明細與交易所風控"
          />

          <div className="flex items-center gap-0.5 bg-background/60 border border-border/60 rounded p-0.5 shrink-0 whitespace-nowrap flex-nowrap">
            <button
              type="button"
              onClick={() => setTab("positions")}
              className={cn(
                "px-2 py-0.5 text-t2 font-mono rounded transition-colors cursor-pointer whitespace-nowrap shrink-0",
                tab === "positions"
                  ? "bg-secondary text-foreground font-semibold shadow-xs"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              持倉({positions.length})
            </button>
            <button
              type="button"
              onClick={() => setTab("orders")}
              className={cn(
                "px-2 py-0.5 text-t2 font-mono rounded transition-colors inline-flex items-center gap-1 cursor-pointer whitespace-nowrap shrink-0",
                tab === "orders"
                  ? "bg-secondary text-foreground font-semibold shadow-xs"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <span className="whitespace-nowrap">掛單(0)</span>
            </button>
          </div>
        </div>
      )}

      {/* 2. 內容展示區 */}
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-auto flex flex-col justify-between min-w-0 max-w-full">
        {modeNotOpen ? (
          <div className="flex-1 flex items-center justify-center py-12 text-center text-muted-foreground">
            <span className="text-xs font-mono">此模式未開放（demo/live 不在 v1 範圍）</span>
          </div>
        ) : (
          <>
            {/* ================= Tab 1: 持倉明細 ================= */}
            {tab === "positions" && (
              <table className="w-full text-left border-collapse table-auto min-w-[540px]">
                <thead className="border-b border-border/80 bg-background/40 text-t1 font-mono text-muted-foreground sticky top-0 z-10 backdrop-blur-sm">
                  <tr>
                    <th className="py-2.5 pl-3 pr-2 font-medium">合約 / 部位</th>
                    <th className="px-2 text-right font-medium">開倉 / 標記價</th>
                    <th className="px-2 text-right font-medium">未實現損益</th>
                    <th className="px-2 text-right font-medium hidden sm:table-cell">資金費率</th>
                    <th className="px-2 text-right font-medium hidden md:table-cell">強平安全墊</th>
                    <th className="px-2 text-right font-medium">交易所強制停損</th>
                    <th className="py-2.5 pr-3 pl-2 text-right font-medium">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40 text-xs">
                  {positions.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-muted-foreground font-mono text-xs">
                        {noRunYet ? "尚未啟動模擬 run" : "目前無未平倉部位"}
                      </td>
                    </tr>
                  ) : (
                    positions.map((p) => <PositionRowView key={`${p.run_id}:${p.bot_id}`} p={p} />)
                  )}
                </tbody>
              </table>
            )}

            {/* ================= Tab 2: 在途掛單 (v1 無資料來源) ================= */}
            {tab === "orders" && (
              <div className="flex-1 flex flex-col items-center justify-center py-12 text-center text-muted-foreground px-4">
                <span className="text-xs font-mono">v1 沒有在途掛單</span>
                <span className="text-t2 font-mono text-muted-foreground/60 mt-1">
                  local-sim 的策略意圖在同一根 bar 內以合成成交終結，沒有在途掛單
                </span>
              </div>
            )}
          </>
        )}

        {/* 底部摘要與模式說明條 */}
        <div className="flex items-center justify-between px-3 py-1.5 border-t border-border/80 bg-secondary/30 text-t2 font-mono text-muted-foreground shrink-0">
          <div className="flex items-center gap-3 whitespace-nowrap">
            <span>持倉筆數: <strong className="text-foreground">{positions.length}</strong></span>
            <span className="text-border">|</span>
            <span title={summary ? `invariants.settlement = ${summary.invariants.settlement}` : "尚無 summary，無法得知保證金模式"}>
              保證金模式:{" "}
              <strong className={summary ? "text-emerald-400" : "text-muted-foreground"}>
                {settlementLabel(summary?.invariants.settlement)}
              </strong>
            </span>
            <span className="text-border">|</span>
            <span title="v1 local-sim 無平倉端點">
              緊急處置: <strong className="text-muted-foreground">平倉出口 v1 未接線</strong>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
