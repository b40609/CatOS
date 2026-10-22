import { useState, useRef, type ReactNode } from "react";
import { INSPECTOR_BOTS } from "@/state/inspectorStore";
import { useLiveMarketStore } from "@/state/liveMarketStore";
import { NumberTicker } from "../motion/number-ticker";
import { cn } from "@/lib/utils";
import {
  ShieldCheck,
  Layers,
  X,
  CheckCircle2,
  AlertTriangle,
  Lock,
  Sparkles,
} from "lucide-react";

interface PopoverPeekProps {
  botId: string;
  type: "intent" | "p6" | "pnl";
  children: ReactNode;
  className?: string;
}

export function PopoverPeek({ botId, type, children, className }: PopoverPeekProps) {
  const [isOpen, setIsOpen] = useState(false);
  const triggerRef = useRef<HTMLDivElement>(null);
  const bot = INSPECTOR_BOTS[botId] ?? INSPECTOR_BOTS.tabby;

  return (
    <div
      ref={triggerRef}
      className={cn("relative inline-block", className)}
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
      onClick={(e) => {
        e.stopPropagation();
        setIsOpen((prev) => !prev);
      }}
    >
      {children}

      {/* 浮動氣泡本體 (Pop-over) */}
      {isOpen && (
        <div className="absolute left-0 top-full mt-1.5 z-50 w-72 rounded-lg border border-primary/40 bg-surface/95 backdrop-blur-md p-2.5 shadow-2xl text-foreground font-mono text-xs animate-in fade-in zoom-in-95 duration-100 pointer-events-none select-none">
          {/* 小箭頭裝飾 */}
          <div className="absolute -top-1 left-4 size-2 bg-surface rotate-45 border-l border-t border-primary/40" />

          {/* 氣泡標頭 */}
          <div className="flex items-center justify-between border-b border-border/60 pb-1.5 mb-1.5">
            <span className="text-[10px] font-bold text-primary flex items-center gap-1">
              {type === "intent" && <Layers className="size-3" />}
              {type === "p6" && <ShieldCheck className="size-3" />}
              <span>方案 D · {type === "intent" ? "策略意圖速覽" : type === "p6" ? "P6 防線雷達" : "盈虧深度"}</span>
            </span>
            <span className="text-[9px] text-muted-foreground">{bot.symbol}</span>
          </div>

          {/* 氣泡內容 */}
          {type === "intent" && (
            <div className="space-y-1.5">
              <div className="text-[10.5px] font-bold text-foreground leading-snug">
                {bot.intentSummary}
              </div>
              <div className="text-[9.5px] text-muted-foreground flex items-center justify-between">
                <span>目標: {bot.targetPosText}</span>
                <span>名義: ${bot.notional.toLocaleString()}</span>
              </div>
              <div className="pt-1 border-t border-border/40 text-[9px] text-primary">
                五階段鏈: 資料OK ➔ 意圖OK ➔ 風控OK ➔ 委託OK ➔ 對帳OK
              </div>
            </div>
          )}

          {type === "p6" && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-muted-foreground">停損觸發價</span>
                <span className="text-xs font-bold text-primary">{bot.p6StopPrice}</span>
              </div>
              <div className="flex items-center justify-between text-[9.5px]">
                <span className="text-muted-foreground">距 Mark 安全距離</span>
                <span className="text-emerald-400 font-bold">{bot.p6DistPct}</span>
              </div>
              <div className="flex items-center justify-between text-[9.5px]">
                <span className="text-muted-foreground">Tick 取整方向</span>
                <span className="text-foreground">{bot.p6Rounding}</span>
              </div>
              <div className="pt-1 border-t border-border/40 text-[9px] text-muted-foreground">
                OKX 交易所條件停損 · 斷線硬防線保護中
              </div>
            </div>
          )}

          {type === "pnl" && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-muted-foreground">未實現損益</span>
                <span className="text-xs font-bold text-emerald-400">+${bot.upnl.toFixed(2)} (+{bot.upnlPct}%)</span>
              </div>
              <div className="flex items-center justify-between text-[9.5px]">
                <span className="text-muted-foreground">進場 / 標記價</span>
                <span className="text-foreground">{bot.entryPrice} / {bot.markPrice}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * 方案 D · 錨點懸浮氣泡卡 (Linear / GitHub Peek 終端卡片)
 * 解決 overflow 遮蔽與未響應問題，採用 fixed 錨點定位與平滑過渡
 */
export function BotAnchorPopoverCard({
  botId,
  anchorRect,
  onClose,
}: {
  botId: string;
  anchorRect: DOMRect | null;
  onClose: () => void;
}) {
  const bot = INSPECTOR_BOTS[botId] ?? INSPECTOR_BOTS.tabby;
  const { botsLive } = useLiveMarketStore();
  const live = botsLive[botId];
  const currentUpnl = live?.upnl ?? bot.upnl;
  const currentNotional = live?.notional ?? bot.notional;

  // 計算視窗安全邊界座標，杜絕任何 overflow 切邊
  const top = anchorRect
    ? Math.max(70, Math.min(anchorRect.top - 10, window.innerHeight - 440))
    : 120;

  const left = anchorRect
    ? anchorRect.right + 12 + 360 < window.innerWidth
      ? anchorRect.right + 12
      : Math.max(16, anchorRect.left - 372)
    : 380;

  return (
    <div
      style={{
        position: "fixed",
        top: `${top}px`,
        left: `${left}px`,
        zIndex: 60,
      }}
      className="w-[360px] rounded-xl border border-primary/50 bg-surface/95 backdrop-blur-xl shadow-2xl p-3 font-mono text-xs text-foreground animate-in fade-in zoom-in-95 duration-150 select-none ring-1 ring-primary/20"
      onClick={(e) => e.stopPropagation()}
    >
      {/* 氣泡頂部 Header */}
      <div className="flex items-center justify-between border-b border-border/80 pb-2 mb-2.5">
        <div className="flex items-center gap-2">
          <span className="p-1 rounded bg-primary/15 text-primary border border-primary/30">
            <Sparkles className="size-3.5" />
          </span>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-foreground text-xs leading-none">{bot.name}</span>
              <span className="text-[9px] px-1 py-0.2 rounded bg-primary/10 text-primary border border-primary/20">
                方案 D · 懸浮氣泡
              </span>
            </div>
            <div className="text-[9.5px] text-muted-foreground mt-0.5">
              {bot.symbol} · {bot.timeframe} · {bot.strategyId}
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="size-5 rounded hover:bg-secondary flex items-center justify-center text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
          title="關閉氣泡"
        >
          <X className="size-3.5" />
        </button>
      </div>

      {/* 1. 策略目標意圖 (Intent Summary) */}
      <div className="p-2.5 rounded-lg border border-border/80 bg-secondary/30 mb-2.5">
        <div className="flex items-center justify-between text-[9.5px] text-muted-foreground mb-1">
          <span className="font-bold text-primary flex items-center gap-1">
            <Layers className="size-3" />
            <span>策略目標意圖</span>
          </span>
          <span className="text-[9px] text-emerald-400 font-semibold">
            {bot.status === "running" ? "● 運作中" : "○ 已暫停"}
          </span>
        </div>
        <div className="text-[11px] font-bold text-foreground leading-snug">
          {bot.intentSummary}
        </div>
        <div className="mt-1.5 pt-1.5 border-t border-border/40 flex items-center justify-between text-[9.5px] text-muted-foreground">
          <span>目標: <strong className="text-foreground">{bot.targetPosText}</strong></span>
          <span>名義: <strong className="text-foreground">${currentNotional.toLocaleString()}</strong></span>
          <span>
            未實現:{" "}
            <NumberTicker
              value={Math.abs(currentUpnl)}
              prefix={currentUpnl >= 0 ? "+$" : "-$"}
              decimals={2}
              duration={300}
              className={currentUpnl >= 0 ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"}
            />
          </span>
        </div>
      </div>

      {/* 2. 五階段生命週期 (Pipeline Stages) */}
      <div className="mb-2.5">
        <div className="text-[9.5px] font-bold text-muted-foreground uppercase mb-1.5 flex items-center justify-between">
          <span>五階段執行鏈 (Pipeline)</span>
          <span className="text-[8.5px] text-primary">已收盤決策 ➔ 次根撮合</span>
        </div>
        <div className="grid grid-cols-5 gap-1 text-center">
          {bot.stages.map((stage, idx) => {
            const isOk = stage.status === "OK";
            const isWarning = stage.status === "WARNING";
            const isBlocked = stage.status === "BLOCKED";

            return (
              <div
                key={stage.name}
                className={cn(
                  "p-1 rounded border text-[8.5px] flex flex-col justify-between",
                  isOk && "bg-background/60 border-border/70",
                  isWarning && "bg-amber-400/10 border-amber-400/40 text-amber-200",
                  isBlocked && "bg-rose-400/10 border-rose-400/40 text-rose-200"
                )}
                title={`${stage.name}: ${stage.detail}`}
              >
                <div className="flex items-center justify-center gap-0.5 mb-0.5">
                  <span className="text-[8px] text-muted-foreground">0{idx + 1}</span>
                  {isOk && <CheckCircle2 className="size-2.5 text-emerald-400" />}
                  {isWarning && <AlertTriangle className="size-2.5 text-amber-400" />}
                  {isBlocked && <Lock className="size-2.5 text-rose-400" />}
                </div>
                <div className="font-bold text-foreground leading-tight">{stage.name}</div>
                <div className="text-[8px] text-primary truncate mt-0.5">{stage.subtext}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 3. P6 災難停損防線 (Disaster Stop Loss) */}
      <div className="p-2 rounded-lg border border-border/80 bg-secondary/30 mb-2">
        <div className="flex items-center justify-between text-[9.5px] mb-1">
          <span className="font-bold text-foreground flex items-center gap-1">
            <ShieldCheck className="size-3 text-primary" />
            <span>P6 災難停損防線</span>
          </span>
          <span className={cn(
            "px-1.5 py-0.2 rounded text-[8.5px] font-bold border",
            bot.p6Status === "ACTIVE"
              ? "bg-emerald-400/10 text-emerald-400 border-emerald-400/30"
              : "bg-amber-400/10 text-amber-300 border-amber-400/30"
          )}>
            {bot.p6Status === "ACTIVE" ? "生效防護中" : "更新待確認"}
          </span>
        </div>
        <div className="grid grid-cols-3 gap-1.5 text-[9.5px] mt-1 pt-1 border-t border-border/40">
          <div>
            <span className="text-muted-foreground block text-[8.5px]">觸發價格</span>
            <span className="font-bold text-primary">{bot.p6StopPrice}</span>
          </div>
          <div>
            <span className="text-muted-foreground block text-[8.5px]">安全距離</span>
            <span className="font-bold text-emerald-400">{bot.p6DistPct}</span>
          </div>
          <div>
            <span className="text-muted-foreground block text-[8.5px]">取整方向</span>
            <span className="font-bold text-foreground truncate block">{bot.p6Rounding.split(" ")[0]}</span>
          </div>
        </div>
      </div>

      {/* 4. 風控審計微標籤 */}
      <div className="flex items-center justify-between text-[9px] text-muted-foreground pt-1 border-t border-border/40">
        <span>槓桿: <strong className="text-foreground">{bot.riskLeverage.split(" ")[0]}</strong></span>
        <span>單幣上限: <strong className="text-foreground">{bot.riskSingleAssetQuota.split(" ")[0]}</strong></span>
        <span>日損 Latch: <strong className="text-emerald-400">NORMAL</strong></span>
      </div>
    </div>
  );
}
