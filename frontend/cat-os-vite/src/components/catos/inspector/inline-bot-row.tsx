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
  ArrowRight,
  Clock,
} from "lucide-react";

interface InlineBotRowProps {
  botId: string;
  colSpan?: number;
  onCollapse: () => void;
}

export function InlineBotRow({ botId, colSpan = 6, onCollapse }: InlineBotRowProps) {
  const bot = INSPECTOR_BOTS[botId] ?? INSPECTOR_BOTS.tabby;
  const { botsLive } = useLiveMarketStore();
  const live = botsLive[botId];

  const liveMarkPrice = bot.markPrice;

  return (
    <tr className="bg-secondary/40 border-b border-border/80 select-none animate-in fade-in duration-150">
      <td colSpan={colSpan} className="p-2 sm:p-2.5">
        <div className="rounded border border-border/80 bg-background/90 p-2.5 sm:p-3 font-mono text-xs shadow-inner space-y-2.5">
          
          {/* ==================== 1. 頂部即時意圖與通道標尺 (零冗餘 · 整合收合按鈕) ==================== */}
          <div className="rounded border border-border/70 bg-secondary/40 p-2 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex flex-col gap-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="px-1.5 py-0.2 rounded bg-primary/15 text-primary text-[9.5px] font-bold border border-primary/25 shrink-0">
                  即時意圖
                </span>
                <span className="font-bold text-foreground text-[11px] truncate">
                  {bot.intentSummary}
                </span>
                <span className="text-muted-foreground text-[10px]">
                  · 目標持倉: <strong className="text-foreground">{bot.targetPosText}</strong>
                </span>
              </div>

              {/* 價格通道與觸發標尺 (Price Trigger Ladder) */}
              {bot.lowerExitPrice && bot.lowerExitPrice !== "—" && (
                <div className="flex items-center gap-1.5 text-[9px] text-muted-foreground pt-0.5">
                  <span className="text-rose-400 font-semibold">[平倉下軌 {bot.lowerExitPrice}]</span>
                  <span className="text-border">──────</span>
                  <span className="text-primary font-bold">(現價 {liveMarkPrice} · 續抱)</span>
                  <span className="text-border">──────</span>
                  <span className="text-emerald-400 font-semibold">[加倉上軌 {bot.upperAddPrice}]</span>
                </div>
              )}
            </div>

            <div className="flex items-center gap-2.5 shrink-0 self-end sm:self-center">
              <div className="flex items-center gap-1 text-[9.5px] text-muted-foreground bg-background/60 border border-border/60 px-2 py-0.5 rounded">
                <Clock className="size-3 text-primary/80" />
                <span>下次決策:</span>
                <span className="text-foreground font-semibold">{bot.nextEvalCountdown ?? "15m 收盤"}</span>
              </div>
              <button
                type="button"
                onClick={onCollapse}
                className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-secondary hover:bg-secondary/80 text-muted-foreground hover:text-foreground border border-border/60 transition-colors cursor-pointer"
                title="收合詳情面板"
              >
                <span>收合</span>
                <ChevronUp className="size-3" />
              </button>
            </div>
          </div>

          {/* ==================== 2. 核心兩欄高密度並排：五階段管線 vs 交易所強制停損與風控 ==================== */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-2.5 items-stretch">
            
            {/* 左側 7 欄：五階段管線流向與無截斷依據清單 */}
            <div className="lg:col-span-7 p-2.5 rounded border border-border/70 bg-secondary/30 flex flex-col justify-between">
              <div>
                {/* 管線標頭與延遲統計 */}
                <div className="flex items-center justify-between text-[10px] font-bold text-muted-foreground uppercase mb-2">
                  <div className="flex items-center gap-1.5">
                    <Layers className="size-3 text-primary" />
                    <span>五階段執行鏈條 (Pipeline Trace)</span>
                  </div>
                  <span className="text-[9px] font-mono text-primary font-semibold">
                    {bot.traceLatency ?? "總延遲 48ms (OKX 28ms · 本地 20ms)"}
                  </span>
                </div>

                {/* 橫向緊湊流向指示器 (帶箭頭) */}
                <div className="flex items-center justify-between gap-1 p-1.5 rounded bg-background/50 border border-border/60 mb-2 overflow-x-auto custom-scrollbar">
                  {bot.stages.map((stage, idx) => {
                    const isOk = stage.status === "OK";
                    const isWarning = stage.status === "WARNING";
                    const isBlocked = stage.status === "BLOCKED";

                    return (
                      <div key={stage.name} className="flex items-center gap-1 shrink-0">
                        <div className={cn(
                          "flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium border",
                          isOk && "bg-emerald-400/10 border-emerald-400/25 text-emerald-300",
                          isWarning && "bg-amber-400/10 border-amber-400/30 text-amber-300",
                          isBlocked && "bg-rose-400/10 border-rose-400/30 text-rose-300"
                        )}>
                          <span>0{idx + 1}</span>
                          <span>{stage.name}</span>
                          {isOk && <CheckCircle2 className="size-2.5 text-emerald-400" />}
                          {isWarning && <AlertTriangle className="size-2.5 text-amber-400" />}
                          {isBlocked && <Lock className="size-2.5 text-rose-400" />}
                        </div>
                        {idx < bot.stages.length - 1 && (
                          <ArrowRight className="size-2.5 text-muted-foreground/60 shrink-0" />
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* 五階段具體依據清單 (完全無截斷 · 純文本直觀展示) */}
                <div className="space-y-1 text-[9.5px] leading-tight">
                  <div className="flex items-baseline justify-between border-b border-border/30 pb-1">
                    <span className="text-muted-foreground shrink-0 w-24">01 資料評估</span>
                    <span className="text-foreground/90 font-medium text-right truncate">
                      {bot.stages[0]?.detail ?? "15m Closed Bar 基準確認，杜絕盤中偷窺"}
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between border-b border-border/30 pb-1">
                    <span className="text-muted-foreground shrink-0 w-24">02 策略意圖</span>
                    <span className="text-foreground/90 font-medium text-right truncate">
                      {bot.stages[1]?.detail ?? "發出多頭目標持倉意圖"}
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between border-b border-border/30 pb-1">
                    <span className="text-muted-foreground shrink-0 w-24">03 風控審核</span>
                    <span className="text-foreground/90 font-medium text-right truncate">
                      {bot.stages[2]?.detail ?? "E_risk 100% 通過，無超限"}
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between border-b border-border/30 pb-1">
                    <span className="text-muted-foreground shrink-0 w-24">04 交易所委託</span>
                    <span className="text-foreground/90 font-medium text-right truncate">
                      {bot.stages[3]?.detail ?? "OKX SWAP net_mode (tag: 41cb53c54d6dABDE)"}
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between pt-0.5">
                    <span className="text-muted-foreground shrink-0 w-24">05 帳務對帳</span>
                    <span className="text-foreground/90 font-medium text-right truncate">
                      {bot.stages[4]?.detail ?? "SQLite WAL 本地雙向一致，零漂移"}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* 右側 5 欄：交易所強制停損與帳戶風控細節 */}
            <div className="lg:col-span-5 p-2.5 rounded border border-border/70 bg-secondary/30 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between text-[10px] font-bold text-muted-foreground uppercase mb-1.5">
                  <div className="flex items-center gap-1.5">
                    <ShieldCheck className="size-3 text-primary" />
                    <span>交易所強制停損 (OKX 端整倉保護)</span>
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

                {/* P6 核心參數標牌 */}
                <div className="grid grid-cols-2 gap-1.5 text-[9.5px] mb-2">
                  <div className="p-1.5 rounded bg-background/60 border border-border/60">
                    <span className="text-[8.5px] text-muted-foreground block">觸發停損價</span>
                    <span className="text-[11.5px] font-bold text-foreground block">{bot.p6StopPrice}</span>
                    <span className="text-[8.5px] text-emerald-400 block">{live?.p6DistPct ?? bot.p6DistPct} (距 Mark 價)</span>
                  </div>
                  <div className="p-1.5 rounded bg-background/60 border border-border/60">
                    <span className="text-[8.5px] text-muted-foreground block">交易所委託憑證</span>
                    <span className="text-[10px] font-semibold text-primary block truncate">{bot.algoOrderId ?? "algo_41cb_948201"}</span>
                    <span className="text-[8.5px] text-muted-foreground block">基準成本: {bot.costBasis ?? bot.entryPrice}</span>
                  </div>
                </div>

                {/* 風控額度與槓桿貢獻清單 */}
                <div className="space-y-1 text-[9px] text-muted-foreground border-t border-border/40 pt-1.5">
                  <div className="flex items-center justify-between">
                    <span>單幣預算占用:</span>
                    <span className="text-foreground font-semibold">{bot.p6BudgetPct}% / 上限 50.0%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>剩餘可加倉額度:</span>
                    <span className="text-emerald-400 font-semibold">{bot.remainingQuota ?? "$30,205 USDT"}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>帳戶槓桿貢獻:</span>
                    <span className="text-foreground font-semibold">{bot.leverageContrib ?? "+0.76x (總槓桿 2.13x / 3.0x)"}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>今日風控狀態:</span>
                    <span className="text-up font-semibold">NORMAL (未觸發 10% 軟鎖存)</span>
                  </div>
                </div>
              </div>
            </div>

          </div>

        </div>
      </td>
    </tr>
  );
}
