import { useInspectorStore, INSPECTOR_BOTS } from "@/state/inspectorStore";
import { useLiveMarketStore } from "@/state/liveMarketStore";
import { CardHeaderTitle } from "../card-header-title";
import { NumberTicker } from "../motion/number-ticker";
import { BorderBeam } from "../motion/border-beam";
import { cn } from "@/lib/utils";
import {
  Layers,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Lock,
} from "lucide-react";

export function MasterDetailCard({ className }: { className?: string }) {
  const { selectedBotId } = useInspectorStore();
  const { botsLive, effectiveLeverage } = useLiveMarketStore();
  const bot = INSPECTOR_BOTS[selectedBotId] ?? INSPECTOR_BOTS.tabby;
  const live = botsLive[selectedBotId];
  const currentUpnl = live?.upnl ?? bot.upnl;
  const currentNotional = live?.notional ?? bot.notional;

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40 relative", className)}>
      {/* 邊框微光流動 */}
      <BorderBeam size={160} duration={6} borderWidth={1.5} colorFrom="var(--color-primary, #e8b45e)" />

      {/* 卡片標頭 */}
      <div className="flex items-center justify-between px-3 h-9 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
        <CardHeaderTitle
          cardId="activity_deck"
          title={`即時詳情偵測 · ${bot.name}`}
          subtext={
            <span className="text-[10px] font-mono text-primary ml-1">
              {bot.symbol} · {bot.timeframe}
            </span>
          }
        />
        <div className="flex items-center gap-1.5 text-[9.5px] font-mono text-muted-foreground">
          <span className="px-1.5 py-0.5 rounded bg-background/60 border border-border/60">
            即時連動
          </span>
        </div>
      </div>

      {/* 卡片內容 (高密度滾動區) */}
      <div className="flex-1 min-h-0 overflow-y-auto p-3 font-mono text-xs space-y-3">
        {/* 1. 意圖摘要橫幅 */}
        <div className="p-2.5 rounded-lg border border-border/70 bg-secondary/30">
          <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-1">
            <span className="uppercase font-bold text-primary">策略目標意圖</span>
            <span className="flex items-center gap-1 text-[9px] text-emerald-400">
              <span className="size-1.5 rounded-full bg-emerald-400 animate-ping" />
              即時撮合連動
            </span>
          </div>
          <div className="text-xs font-bold text-foreground leading-snug">
            {bot.intentSummary}
          </div>
          <div className="mt-1.5 pt-1.5 border-t border-border/40 flex items-center justify-between text-[10px] text-muted-foreground">
            <span>持倉目標: <strong className="text-foreground">{bot.targetPosText}</strong></span>
            <span>名義價值: <strong className="text-foreground">${currentNotional.toLocaleString()}</strong></span>
            <span>
              未實現:{" "}
              <NumberTicker
                value={Math.abs(currentUpnl)}
                prefix={currentUpnl >= 0 ? "+$" : "-$"}
                decimals={2}
                duration={400}
                className={currentUpnl >= 0 ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"}
              />
            </span>
          </div>
        </div>

        {/* 2. 五階段生命週期 (Pipeline Stages) */}
        <div className="p-2.5 rounded-lg border border-border/70 bg-secondary/30">
          <div className="flex items-center gap-1.5 text-[10px] font-bold text-muted-foreground uppercase mb-2">
            <Layers className="size-3 text-primary" />
            <span>五階段執行鏈條 (Pipeline)</span>
          </div>

          <div className="space-y-1.5">
            {bot.stages.map((stage, idx) => {
              const isOk = stage.status === "OK";
              const isWarning = stage.status === "WARNING";
              const isBlocked = stage.status === "BLOCKED";

              return (
                <div
                  key={stage.name}
                  className={cn(
                    "p-2 rounded border flex items-center justify-between text-[10px]",
                    isOk && "bg-background/50 border-border/60",
                    isWarning && "bg-amber-400/10 border-amber-400/40 text-amber-200",
                    isBlocked && "bg-rose-400/10 border-rose-400/40 text-rose-200"
                  )}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-[9px] text-muted-foreground font-bold">0{idx + 1}</span>
                    <span className="font-bold text-foreground truncate">{stage.name}</span>
                    <span className="text-[9.5px] text-primary hidden sm:inline">({stage.subtext})</span>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[9px] text-muted-foreground truncate max-w-[140px] hidden md:inline">
                      {stage.detail}
                    </span>
                    {isOk && <CheckCircle2 className="size-3 text-emerald-400" />}
                    {isWarning && <AlertTriangle className="size-3 text-amber-400" />}
                    {isBlocked && <Lock className="size-3 text-rose-400" />}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* 3. P6 災難停損保護防線 */}
        <div className="p-2.5 rounded-lg border border-border/70 bg-secondary/30">
          <div className="flex items-center justify-between text-[10px] font-bold text-muted-foreground uppercase mb-2">
            <div className="flex items-center gap-1.5">
              <ShieldCheck className="size-3 text-primary" />
              <span>P6 災難停損防線 (OKX 條件委託)</span>
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

          <div className="grid grid-cols-2 gap-2 text-[10.5px]">
            <div className="p-2 rounded bg-background/50 border border-border/60">
              <span className="text-[9px] text-muted-foreground block">停損觸發價格</span>
              <span className="text-xs font-bold text-primary block mt-0.5">{bot.p6StopPrice}</span>
              <span className="text-[9px] text-emerald-400 block mt-0.5">安全距離: {live?.p6DistPct ?? bot.p6DistPct}</span>
            </div>

            <div className="p-2 rounded bg-background/50 border border-border/60">
              <span className="text-[9px] text-muted-foreground block">Tick 取整方向</span>
              <span className="text-[10.5px] font-bold text-foreground block mt-0.5">{bot.p6Rounding}</span>
              <span className="text-[9px] text-muted-foreground block mt-0.5">專屬預算: {bot.p6BudgetPct}%</span>
            </div>
          </div>
        </div>

        {/* 4. 風控審計底線 */}
        <div className="p-2.5 rounded-lg border border-border/70 bg-secondary/30 flex items-center justify-between text-[10px] text-muted-foreground">
          <span>有效槓桿: <strong className="text-foreground">{effectiveLeverage.toFixed(2)}x (上限 3.0x)</strong></span>
          <span>單幣預算: <strong className="text-foreground">{bot.riskSingleAssetQuota}</strong></span>
          <span>日損鎖存: <strong className="text-emerald-400">NORMAL</strong></span>
        </div>
      </div>
    </div>
  );
}
