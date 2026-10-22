import { INSPECTOR_BOTS } from "@/state/inspectorStore";
import { useLiveMarketStore } from "@/state/liveMarketStore";
import { cn } from "@/lib/utils";
import {
  Layers,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Lock,
  ChevronUp,
} from "lucide-react";

interface InlineBotRowProps {
  botId: string;
  colSpan?: number;
  onCollapse: () => void;
}

export function InlineBotRow({ botId, colSpan = 6, onCollapse }: InlineBotRowProps) {
  const bot = INSPECTOR_BOTS[botId] ?? INSPECTOR_BOTS.tabby;
  const { botsLive, effectiveLeverage } = useLiveMarketStore();
  const live = botsLive[botId];

  return (
    <tr className="bg-secondary/40 border-b-2 border-primary/40 select-none animate-in fade-in duration-150">
      <td colSpan={colSpan} className="p-3">
        <div className="rounded-lg border border-border/80 bg-background/80 p-3 font-mono text-xs shadow-inner">
          {/* 頂部標頭與收合按鈕 */}
          <div className="flex items-center justify-between border-b border-border/60 pb-2 mb-2.5">
            <div className="flex items-center gap-2">
              <span className="px-1.5 py-0.5 rounded bg-primary/15 text-primary text-[10px] font-bold border border-primary/25">
                策略生命週期與防線
              </span>
              <span className="font-bold text-foreground">{bot.name}</span>
              <span className="text-[10px] text-muted-foreground">({bot.symbol} · {bot.timeframe} · {bot.strategyId})</span>
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={onCollapse}
                className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-secondary hover:bg-secondary/80 text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                <span>收合</span>
                <ChevronUp className="size-3" />
              </button>
            </div>
          </div>

          {/* 意圖說明橫條 */}
          <div className="p-2 rounded bg-secondary/50 border border-border/60 mb-2.5 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-primary font-bold uppercase">即時意圖</span>
              <span className="text-[11px] font-semibold text-foreground">{bot.intentSummary}</span>
            </div>
            <div className="text-[10px] text-muted-foreground flex items-center gap-2">
              <span>評估: {bot.dataEvalTime}</span>
              <span>·</span>
              <span>目標: {bot.targetPosText} (${(live?.notional ?? bot.notional).toLocaleString()})</span>
            </div>
          </div>

          {/* 兩欄高密度並排：五階段流程鏈 + P6防線與風控 */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-2.5">
            {/* 左側 7 欄：五階段管線 */}
            <div className="lg:col-span-7 p-2.5 rounded border border-border/70 bg-secondary/30 flex flex-col justify-between">
              <div className="flex items-center gap-1.5 text-[10px] font-bold text-muted-foreground uppercase mb-2">
                <Layers className="size-3 text-primary" />
                <span>五階段執行鏈條 (Pipeline)</span>
              </div>

              <div className="grid grid-cols-5 gap-1.5 text-center">
                {bot.stages.map((stage, idx) => {
                  const isOk = stage.status === "OK";
                  const isWarning = stage.status === "WARNING";
                  const isBlocked = stage.status === "BLOCKED";

                  return (
                    <div
                      key={stage.name}
                      className={cn(
                        "p-1.5 rounded border text-[9.5px] flex flex-col justify-between min-h-[70px]",
                        isOk && "bg-background/60 border-border/60",
                        isWarning && "bg-amber-400/10 border-amber-400/40 text-amber-200",
                        isBlocked && "bg-rose-400/10 border-rose-400/40 text-rose-200"
                      )}
                    >
                      <div>
                        <div className="flex items-center justify-between mb-0.5">
                          <span className="text-[8.5px] text-muted-foreground">0{idx + 1}</span>
                          {isOk && <CheckCircle2 className="size-2.5 text-emerald-400" />}
                          {isWarning && <AlertTriangle className="size-2.5 text-amber-400" />}
                          {isBlocked && <Lock className="size-2.5 text-rose-400" />}
                        </div>
                        <div className="font-bold text-foreground leading-tight">{stage.name}</div>
                      </div>
                      <div className="text-[8.5px] text-primary truncate mt-1">{stage.subtext}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 右側 5 欄：P6 災難停損防線與風控 */}
            <div className="lg:col-span-5 p-2.5 rounded border border-border/70 bg-secondary/30 flex flex-col justify-between">
              <div className="flex items-center justify-between text-[10px] font-bold text-muted-foreground uppercase mb-1.5">
                <div className="flex items-center gap-1.5">
                  <ShieldCheck className="size-3 text-primary" />
                  <span>P6 災難停損防線</span>
                </div>
                <span
                  className={cn(
                    "px-1.5 py-0.2 rounded text-[8.5px] font-bold border",
                    bot.p6Status === "ACTIVE"
                      ? "bg-emerald-400/10 text-emerald-400 border-emerald-400/30"
                      : "bg-amber-400/10 text-amber-300 border-amber-400/30"
                  )}
                >
                  {bot.p6Status === "ACTIVE" ? "生效防護中" : "更新待確認"}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-1.5 text-[10px]">
                <div className="p-1.5 rounded bg-background/50 border border-border/60">
                  <span className="text-[8.5px] text-muted-foreground block">觸發停損價</span>
                  <span className="text-[11px] font-bold text-primary block">{bot.p6StopPrice}</span>
                  <span className="text-[8.5px] text-emerald-400 block">{live?.p6DistPct ?? bot.p6DistPct} (距 Mark 價)</span>
                </div>
                <div className="p-1.5 rounded bg-background/50 border border-border/60">
                  <span className="text-[8.5px] text-muted-foreground block">Tick 取整 / 預算</span>
                  <span className="text-[10px] font-bold text-foreground block">{bot.p6Rounding}</span>
                  <span className="text-[8.5px] text-muted-foreground block">預算 {bot.p6BudgetPct}% 總曝險</span>
                </div>
              </div>

              <div className="mt-1.5 pt-1.5 border-t border-border/50 flex items-center justify-between text-[9px] text-muted-foreground">
                <span>槓桿: {effectiveLeverage.toFixed(2)}x (上限 3.0x)</span>
                <span>單幣: {bot.riskSingleAssetQuota}</span>
                <span>日損: NORMAL</span>
              </div>
            </div>
          </div>
        </div>
      </td>
    </tr>
  );
}
