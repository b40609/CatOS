import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { usePreviewStore } from './preview-store';
import { Bot, ShieldCheck, ExternalLink, Zap, Layers, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

export function SharedInspectorSheet() {
  const {
    activeInspector,
    closeInspector,
    bots,
    positions,
    events,
    jumpToBot,
    jumpToOrder,
    jumpToProtection,
    jumpToEvent,
  } = usePreviewStore();

  const isOpen = activeInspector.type !== null && activeInspector.id !== null;

  const currentBot = activeInspector.type === 'bot'
    ? bots.find((b) => b.id === activeInspector.id)
    : null;

  const currentEvent = activeInspector.type === 'event'
    ? events.find((e) => e.id === activeInspector.id)
    : null;

  const currentPosition = activeInspector.type === 'protection'
    ? positions.find((p) => p.id === activeInspector.id || p.botId === activeInspector.id)
    : null;

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && closeInspector()}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-lg bg-surface/95 border-l border-border p-0 flex flex-col backdrop-blur-md z-50 text-foreground overflow-hidden"
      >
        {/* ===================== 1. BOT INSPECTOR ===================== */}
        {activeInspector.type === 'bot' && currentBot && (
          <div className="flex-1 flex flex-col min-h-0">
            <SheetHeader className="p-4 border-b border-border/80 bg-secondary/30 shrink-0 text-left">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={cn(
                    "size-2.5 rounded-full shrink-0",
                    currentBot.status === 'paused' ? "bg-muted-foreground" : currentBot.warning ? "bg-amber-400" : "bg-emerald-400"
                  )} />
                  <SheetTitle className="text-base font-bold text-foreground">
                    {currentBot.name} · 策略目標意圖
                  </SheetTitle>
                </div>
                <span className={cn(
                  "px-2 py-0.5 rounded text-[10px] font-mono border",
                  currentBot.status === 'paused'
                    ? "bg-muted text-muted-foreground border-border"
                    : currentBot.warning
                    ? "bg-amber-400/10 text-amber-300 border-amber-400/30 font-semibold"
                    : "bg-emerald-400/10 text-emerald-400 border-emerald-400/30"
                )}>
                  {currentBot.status === 'paused' ? '已手動暫停' : currentBot.warning ? '風控受限' : '正常運作'}
                </span>
              </div>
              <SheetDescription className="text-xs text-muted-foreground font-mono flex items-center gap-2 mt-1">
                <span>{currentBot.symbol}</span>
                <span>·</span>
                <span>{currentBot.timeframe}</span>
                <span>·</span>
                <span>{currentBot.strategyId}</span>
              </SheetDescription>
            </SheetHeader>

            <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4 text-xs font-mono">
              {/* 一行意圖總結 */}
              <div className={cn(
                "p-3 rounded-lg border",
                currentBot.warning ? "bg-amber-500/10 border-amber-500/30 text-amber-200" : "bg-secondary/40 border-border"
              )}>
                <div className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider mb-1">
                  當前策略意圖摘要
                </div>
                <div className="text-sm font-semibold text-foreground">
                  {currentBot.intentSummary}
                </div>
              </div>

              {/* 基本盤口數據 */}
              <div className="grid grid-cols-2 gap-2">
                <div className="p-2.5 rounded bg-background/50 border border-border/60">
                  <span className="text-[10px] text-muted-foreground block">資料評估時間</span>
                  <span className="text-xs font-bold text-foreground mt-0.5 block">{currentBot.dataTime}</span>
                  <span className="text-[9.5px] text-muted-foreground mt-0.5 block">{currentBot.bar}</span>
                </div>
                <div className="p-2.5 rounded bg-background/50 border border-border/60">
                  <span className="text-[10px] text-muted-foreground block">目前部位 → 目標部位</span>
                  <span className="text-xs font-bold text-foreground mt-0.5 block">{currentBot.currentPos} → {currentBot.targetPos}</span>
                  <span className="text-[9.5px] text-primary mt-0.5 block">名義價值 ${currentBot.notional.toLocaleString()}</span>
                </div>
              </div>

              {/* 五階段流程圖 (資料 → 意圖 → 風控 → 委託 → 對帳) */}
              <div className="p-3 rounded-lg border border-border bg-background/30">
                <div className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider mb-2 flex items-center gap-1.5">
                  <Layers className="size-3 text-primary" />
                  <span>五階段執行鏈 (Pipeline Stages)</span>
                </div>
                <div className="grid grid-cols-5 gap-1 text-center">
                  {currentBot.stages.map(([stage, val], idx) => (
                    <div
                      key={stage}
                      className={cn(
                        "p-1.5 rounded border text-[9px] flex flex-col justify-between",
                        currentBot.warning && idx >= 2
                          ? "bg-amber-400/10 border-amber-400/30 text-amber-300 font-semibold"
                          : "bg-secondary/40 border-border/60 text-muted-foreground"
                      )}
                    >
                      <span className="text-[8px] opacity-75">{idx + 1}. {stage}</span>
                      <span className="text-[9.5px] mt-1 text-foreground font-medium truncate" title={val}>{val}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* 核心結構化欄位 */}
              <div className="space-y-2.5">
                <div className="p-2.5 rounded border border-border/60 bg-background/40">
                  <span className="text-[10px] text-muted-foreground font-bold block mb-1">【判定條件】</span>
                  <p className="text-[11px] leading-relaxed text-foreground">{currentBot.condition}</p>
                </div>

                <div className={cn(
                  "p-2.5 rounded border",
                  currentBot.warning ? "border-amber-400/30 bg-amber-400/5 text-amber-200" : "border-border/60 bg-background/40"
                )}>
                  <span className="text-[10px] font-bold block mb-1 text-muted-foreground">【風控限制】</span>
                  <p className="text-[11px] leading-relaxed">{currentBot.riskLimit}</p>
                </div>

                <div className="p-2.5 rounded border border-border/60 bg-background/40">
                  <span className="text-[10px] text-muted-foreground font-bold block mb-1">【委託與對帳狀態】</span>
                  <p className="text-[11px] leading-relaxed text-foreground">{currentBot.orderRecon}</p>
                </div>

                <div className="p-2.5 rounded border border-border/60 bg-background/40">
                  <span className="text-[10px] text-muted-foreground font-bold block mb-1">【下一步動作 (Next Action)】</span>
                  <p className="text-[11px] leading-relaxed text-foreground">{currentBot.nextStep}</p>
                </div>
              </div>

              {/* 關聯跳轉動作區 */}
              <div className="pt-2 border-t border-border/80 flex flex-col gap-2">
                <span className="text-[10px] text-muted-foreground font-bold">快速跳轉追查：</span>
                <div className="flex flex-wrap gap-2">
                  {currentBot.relatedPositionId && (
                    <button
                      type="button"
                      onClick={() => jumpToProtection(currentBot.relatedPositionId!)}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded border border-primary/30 bg-primary/10 text-primary hover:bg-primary/20 text-xs font-semibold cursor-pointer transition-colors"
                    >
                      <ShieldCheck className="size-3" />
                      <span>查看 P6 災難保護狀態</span>
                    </button>
                  )}

                  {currentBot.relatedOrderId && (
                    <button
                      type="button"
                      onClick={() => jumpToOrder(currentBot.relatedOrderId!)}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded border border-amber-400/30 bg-amber-400/10 text-amber-300 hover:bg-amber-400/20 text-xs font-semibold cursor-pointer transition-colors"
                    >
                      <Zap className="size-3" />
                      <span>查看 UNKNOWN 在途委託</span>
                    </button>
                  )}

                  {currentBot.relatedEventId && (
                    <button
                      type="button"
                      onClick={() => jumpToEvent(currentBot.relatedEventId!)}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded border border-border bg-secondary/60 text-muted-foreground hover:text-foreground hover:bg-secondary text-xs cursor-pointer transition-colors"
                    >
                      <ExternalLink className="size-3" />
                      <span>查看日誌警報詳情</span>
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ===================== 2. EVENT INSPECTOR ===================== */}
        {activeInspector.type === 'event' && currentEvent && (
          <div className="flex-1 flex flex-col min-h-0">
            <SheetHeader className="p-4 border-b border-border/80 bg-secondary/30 shrink-0 text-left">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={cn(
                    "px-1.5 py-0.5 rounded text-[9px] font-bold",
                    currentEvent.category === 'ALERT'
                      ? "bg-amber-400/15 text-amber-300 border border-amber-400/40"
                      : currentEvent.category === 'FILL'
                      ? "bg-emerald-400/10 text-emerald-400 border border-emerald-400/30"
                      : "bg-sky-400/10 text-sky-300 border border-sky-400/30"
                  )}>
                    {currentEvent.category}
                  </span>
                  <SheetTitle className="text-base font-bold text-foreground">
                    {currentEvent.title}
                  </SheetTitle>
                </div>
                <span className={cn(
                  "px-2 py-0.5 rounded text-[10px] font-mono border",
                  currentEvent.resolution === 'open'
                    ? "bg-amber-500/15 text-amber-300 border-amber-500/40 font-bold animate-pulse"
                    : "bg-secondary text-muted-foreground border-border"
                )}>
                  {currentEvent.resolution === 'open' ? '未解除' : '已解除 · 歷程'}
                </span>
              </div>
              <SheetDescription className="text-xs text-muted-foreground font-mono flex items-center gap-2 mt-1">
                <span>時間: {currentEvent.time}</span>
                <span>·</span>
                <span>來源: {currentEvent.source}</span>
                {currentEvent.botName && <span>· 關聯 Bot: {currentEvent.botName}</span>}
              </SheetDescription>
            </SheetHeader>

            <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4 text-xs font-mono">
              {/* 核心事件詳情 */}
              <div className="p-3 rounded-lg border border-border bg-background/50">
                <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider block mb-1">
                  詳細事件說明
                </span>
                <p className="text-[11.5px] leading-relaxed text-foreground">
                  {currentEvent.detail}
                </p>
              </div>

              {/* 影響與處理狀態 */}
              {currentEvent.impact && (
                <div className="p-3 rounded-lg border border-amber-400/30 bg-amber-400/5">
                  <span className="text-[10px] text-amber-400 font-bold block mb-1">
                    【風險影響 (Impact)】
                  </span>
                  <p className="text-[11px] leading-relaxed text-amber-200">
                    {currentEvent.impact}
                  </p>
                </div>
              )}

              {currentEvent.nextStep && (
                <div className="p-3 rounded-lg border border-border/70 bg-background/40">
                  <span className="text-[10px] text-muted-foreground font-bold block mb-1">
                    【處理狀態與處置指引】
                  </span>
                  <p className="text-[11px] leading-relaxed text-foreground">
                    {currentEvent.nextStep}
                  </p>
                  <div className="mt-2 text-[9.5px] text-muted-foreground/80 border-t border-border/40 pt-1.5">
                    * 依專案紅線：系統嚴禁提供無後端支援的偽按鈕，不可用「已讀」解除真實風險。
                  </div>
                </div>
              )}

              {/* 關聯跳轉動作區 */}
              <div className="pt-2 border-t border-border/80 flex flex-col gap-2">
                <span className="text-[10px] text-muted-foreground font-bold">關聯跳轉追查：</span>
                <div className="flex flex-col gap-2">
                  {currentEvent.botId && (
                    <button
                      type="button"
                      onClick={() => jumpToBot(currentEvent.botId!)}
                      className="w-full flex items-center justify-between px-3 py-2 rounded border border-border hover:border-primary/40 bg-secondary/30 hover:bg-secondary/60 text-xs cursor-pointer transition-colors"
                    >
                      <span className="flex items-center gap-2">
                        <Bot className="size-3.5 text-primary" />
                        <span>選取並定位關聯 Bot ({currentEvent.botName})</span>
                      </span>
                      <ChevronRight className="size-3.5 text-muted-foreground" />
                    </button>
                  )}

                  {currentEvent.relatedOrderId && (
                    <button
                      type="button"
                      onClick={() => jumpToOrder(currentEvent.relatedOrderId!)}
                      className="w-full flex items-center justify-between px-3 py-2 rounded border border-amber-400/30 hover:border-amber-400/60 bg-amber-400/10 hover:bg-amber-400/20 text-xs text-amber-300 font-semibold cursor-pointer transition-colors"
                    >
                      <span className="flex items-center gap-2">
                        <Zap className="size-3.5" />
                        <span>切換至部位卡掛單頁並定位 UNKNOWN 委託</span>
                      </span>
                      <ChevronRight className="size-3.5" />
                    </button>
                  )}

                  {currentEvent.relatedPositionId && (
                    <button
                      type="button"
                      onClick={() => jumpToProtection(currentEvent.relatedPositionId!)}
                      className="w-full flex items-center justify-between px-3 py-2 rounded border border-border hover:border-primary/40 bg-secondary/30 hover:bg-secondary/60 text-xs cursor-pointer transition-colors"
                    >
                      <span className="flex items-center gap-2">
                        <ShieldCheck className="size-3.5 text-emerald-400" />
                        <span>切換至持倉頁並定位 P6 保護狀態</span>
                      </span>
                      <ChevronRight className="size-3.5 text-muted-foreground" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ===================== 3. PROTECTION INSPECTOR ===================== */}
        {activeInspector.type === 'protection' && currentPosition && (
          <div className="flex-1 flex flex-col min-h-0">
            <SheetHeader className="p-4 border-b border-border/80 bg-secondary/30 shrink-0 text-left">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldCheck className={cn(
                    "size-4 shrink-0",
                    currentPosition.p6Status === 'CONFIRMED' ? "text-emerald-400" : "text-amber-400"
                  )} />
                  <SheetTitle className="text-base font-bold text-foreground">
                    {currentPosition.symbol} · P6 災難保護快照
                  </SheetTitle>
                </div>
                <span className={cn(
                  "px-2 py-0.5 rounded text-[10px] font-mono border",
                  currentPosition.p6Status === 'CONFIRMED'
                    ? "bg-emerald-400/10 text-emerald-400 border-emerald-400/30"
                    : "bg-amber-400/10 text-amber-300 border-amber-400/30 font-semibold animate-pulse"
                )}>
                  {currentPosition.p6Status === 'CONFIRMED' ? '保護已確認生效' : '更新待確認 · 禁增倉'}
                </span>
              </div>
              <SheetDescription className="text-xs text-muted-foreground font-mono flex items-center gap-2 mt-1">
                <span>Bot: {currentPosition.botName}</span>
                <span>·</span>
                <span>持有部位: {currentPosition.qty} {currentPosition.base}</span>
                <span>·</span>
                <span>名義價值: ${currentPosition.notional}</span>
              </SheetDescription>
            </SheetHeader>

            <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4 text-xs font-mono">
              {/* 關鍵保護數值比較 */}
              <div className="grid grid-cols-2 gap-2">
                <div className="p-3 rounded-lg border border-border/70 bg-background/50">
                  <span className="text-[10px] text-muted-foreground block mb-0.5">已確認生效價</span>
                  <span className={cn(
                    "text-sm font-bold block",
                    currentPosition.p6ActiveStopPrice.includes('未知') ? "text-amber-400" : "text-emerald-400"
                  )}>
                    {currentPosition.p6ActiveStopPrice}
                  </span>
                  <span className="text-[9px] text-muted-foreground mt-1 block">
                    {currentPosition.p6Status === 'CONFIRMED' ? '交易所端已實際生效' : '尚未取得可信終態'}
                  </span>
                </div>

                <div className="p-3 rounded-lg border border-border/70 bg-background/50">
                  <span className="text-[10px] text-muted-foreground block mb-0.5">更新目標價</span>
                  <span className="text-sm font-bold text-primary block">
                    {currentPosition.p6TargetStopPrice}
                  </span>
                  <span className="text-[9px] text-muted-foreground mt-1 block">
                    {currentPosition.p6Status === 'CONFIRMED' ? '與生效價完全一致' : '更新目標不能冒充生效價'}
                  </span>
                </div>
              </div>

              {/* 快照中繼資料 */}
              <div className="p-3 rounded-lg border border-border bg-background/30 space-y-2">
                <div className="flex justify-between items-center border-b border-border/40 pb-1.5">
                  <span className="text-muted-foreground">有效覆蓋數量：</span>
                  <span className="font-bold text-foreground">{currentPosition.p6CoveredQty}</span>
                </div>
                <div className="flex justify-between items-center border-b border-border/40 pb-1.5">
                  <span className="text-muted-foreground">最後確認時間：</span>
                  <span className="text-foreground">{currentPosition.p6ConfirmedAt}</span>
                </div>
                <div className="flex justify-between items-center border-b border-border/40 pb-1.5">
                  <span className="text-muted-foreground">資料來源快照：</span>
                  <span className="text-foreground">{currentPosition.p6Source}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">保護委託狀態：</span>
                  <span className={cn(
                    "font-semibold",
                    currentPosition.p6Status === 'CONFIRMED' ? "text-emerald-400" : "text-amber-400"
                  )}>
                    {currentPosition.p6OrderState}
                  </span>
                </div>
              </div>

              {/* 說明與下一步 */}
              <div className="space-y-2.5">
                <div className="p-2.5 rounded border border-border/60 bg-background/40">
                  <span className="text-[10px] text-muted-foreground font-bold block mb-1">【保護狀態說明】</span>
                  <p className="text-[11px] leading-relaxed text-foreground">{currentPosition.p6Detail}</p>
                </div>

                <div className={cn(
                  "p-2.5 rounded border",
                  currentPosition.p6Status === 'UPDATING' ? "border-amber-400/30 bg-amber-400/5 text-amber-200" : "border-border/60 bg-background/40"
                )}>
                  <span className="text-[10px] font-bold block mb-1 text-muted-foreground">【下一步指引】</span>
                  <p className="text-[11px] leading-relaxed">{currentPosition.p6NextStep}</p>
                </div>
              </div>

              {/* 關聯跳轉動作區 */}
              <div className="pt-2 border-t border-border/80 flex flex-col gap-2">
                <span className="text-[10px] text-muted-foreground font-bold">關聯跳轉追查：</span>
                <div className="flex flex-col gap-2">
                  <button
                    type="button"
                    onClick={() => jumpToBot(currentPosition.botId)}
                    className="w-full flex items-center justify-between px-3 py-2 rounded border border-border hover:border-primary/40 bg-secondary/30 hover:bg-secondary/60 text-xs cursor-pointer transition-colors"
                  >
                    <span className="flex items-center gap-2">
                      <Bot className="size-3.5 text-primary" />
                      <span>查看負責 Bot 詳情 ({currentPosition.botName})</span>
                    </span>
                    <ChevronRight className="size-3.5 text-muted-foreground" />
                  </button>

                  {currentPosition.relatedOrderId && (
                    <button
                      type="button"
                      onClick={() => jumpToOrder(currentPosition.relatedOrderId!)}
                      className="w-full flex items-center justify-between px-3 py-2 rounded border border-amber-400/30 hover:border-amber-400/60 bg-amber-400/10 hover:bg-amber-400/20 text-xs text-amber-300 font-semibold cursor-pointer transition-colors"
                    >
                      <span className="flex items-center gap-2">
                        <Zap className="size-3.5" />
                        <span>查看相關在途委託 (待對帳)</span>
                      </span>
                      <ChevronRight className="size-3.5" />
                    </button>
                  )}

                  {currentPosition.relatedEventId && (
                    <button
                      type="button"
                      onClick={() => jumpToEvent(currentPosition.relatedEventId!)}
                      className="w-full flex items-center justify-between px-3 py-2 rounded border border-border hover:border-primary/40 bg-secondary/30 hover:bg-secondary/60 text-xs cursor-pointer transition-colors"
                    >
                      <span className="flex items-center gap-2">
                        <ExternalLink className="size-3.5 text-primary" />
                        <span>查看戰情警報時間軸事件</span>
                      </span>
                      <ChevronRight className="size-3.5 text-muted-foreground" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
