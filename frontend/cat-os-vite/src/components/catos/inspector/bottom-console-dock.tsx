import { useInspectorStore, INSPECTOR_BOTS } from "@/state/inspectorStore";
import { cn } from "@/lib/utils";
import {
  Terminal,
  Minimize2,
  Maximize2,
  X,
  Layers,
  ShieldCheck,
  Activity,
  CheckCircle2,
  AlertTriangle,
  Lock,
} from "lucide-react";

export function BottomConsoleDock() {
  const {
    presentationMode,
    selectedBotId,
    isBottomDockOpen,
    isBottomDockMaximized,
    bottomDockTab,
    toggleBottomDock,
    setBottomDockMaximized,
    setBottomDockTab,
  } = useInspectorStore();

  const isVisible = (presentationMode === "bottom_dock" || presentationMode === "all_active") && isBottomDockOpen;
  const bot = INSPECTOR_BOTS[selectedBotId] ?? INSPECTOR_BOTS.tabby;

  if (!isVisible) {
    // 當關閉時，若處於方案 A，在右下角保留一個微型還原標籤
    if (presentationMode === "bottom_dock" || presentationMode === "all_active") {
      return (
        <button
          type="button"
          onClick={() => toggleBottomDock(true)}
          className="fixed bottom-10 right-6 z-40 flex items-center gap-2 px-3 py-1.5 rounded-t-lg bg-surface/95 border border-border border-b-0 shadow-lg text-[11px] font-mono font-semibold text-primary hover:bg-secondary transition-all cursor-pointer"
        >
          <Terminal className="size-3.5" />
          <span>展開 Console ({bot.name})</span>
        </button>
      );
    }
    return null;
  }

  return (
    <div
      className={cn(
        "fixed inset-x-0 bottom-0 z-40 bg-surface/95 backdrop-blur-md border-t border-border shadow-2xl flex flex-col transition-all duration-200 select-none",
        isBottomDockMaximized ? "h-[55vh]" : "h-64"
      )}
    >
      {/* 頂部 Dock Header 工具列 */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-secondary/70 border-b border-border/80 shrink-0 text-xs">
        {/* 左側：Bot 資訊與分頁切換 */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 font-mono">
            <Terminal className="size-3.5 text-primary" />
            <span className="font-bold text-foreground">{bot.name}</span>
            <span className="text-[10px] text-muted-foreground">({bot.symbol} · {bot.timeframe})</span>
            <span
              className={cn(
                "px-1.5 py-0.2 rounded text-[9.5px] font-mono font-bold border",
                bot.status === "running"
                  ? "bg-emerald-400/10 text-emerald-400 border-emerald-400/30"
                  : "bg-muted text-muted-foreground border-border"
              )}
            >
              {bot.status === "running" ? "運作中" : "已暫停"}
            </span>
          </div>

          <div className="h-3 w-px bg-border/80 mx-1" />

          {/* 多頁籤切換 Tabs */}
          <div className="flex items-center gap-1 font-mono text-[11px]">
            <button
              type="button"
              onClick={() => setBottomDockTab("stages")}
              className={cn(
                "px-2.5 py-1 rounded transition-colors flex items-center gap-1.5 cursor-pointer",
                bottomDockTab === "stages"
                  ? "bg-primary/20 text-primary font-bold border border-primary/30"
                  : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground"
              )}
            >
              <Layers className="size-3" />
              <span>五階段生命鏈</span>
            </button>

            <button
              type="button"
              onClick={() => setBottomDockTab("p6")}
              className={cn(
                "px-2.5 py-1 rounded transition-colors flex items-center gap-1.5 cursor-pointer",
                bottomDockTab === "p6"
                  ? "bg-primary/20 text-primary font-bold border border-primary/30"
                  : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground"
              )}
            >
              <ShieldCheck className="size-3" />
              <span>P6 災難停損防線</span>
            </button>

            <button
              type="button"
              onClick={() => setBottomDockTab("risk")}
              className={cn(
                "px-2.5 py-1 rounded transition-colors flex items-center gap-1.5 cursor-pointer",
                bottomDockTab === "risk"
                  ? "bg-primary/20 text-primary font-bold border border-primary/30"
                  : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground"
              )}
            >
              <Activity className="size-3" />
              <span>風控審計與日損 Latch</span>
            </button>
          </div>
        </div>

        {/* 右側：縮放與關閉控制按鈕 */}
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <span className="text-[10px] font-mono mr-2 hidden md:inline">
            業界原型: TradingView / VS Code 底部 Console
          </span>

          <button
            type="button"
            onClick={() => setBottomDockMaximized(!isBottomDockMaximized)}
            className="p-1 rounded hover:bg-secondary hover:text-foreground transition-colors cursor-pointer"
            title={isBottomDockMaximized ? "還原高度" : "最大化面板"}
          >
            {isBottomDockMaximized ? <Minimize2 className="size-3.5" /> : <Maximize2 className="size-3.5" />}
          </button>

          <button
            type="button"
            onClick={() => toggleBottomDock(false)}
            className="p-1 rounded hover:bg-secondary hover:text-foreground transition-colors cursor-pointer"
            title="收起 Console"
          >
            <X className="size-3.5" />
          </button>
        </div>
      </div>

      {/* 底部內容本體 */}
      <div className="flex-1 min-h-0 overflow-y-auto p-3 font-mono text-xs">
        {/* TAB 1: 五階段執行鏈 */}
        {bottomDockTab === "stages" && (
          <div className="flex flex-col h-full justify-between gap-3">
            {/* 意圖摘要橫幅 */}
            <div className="p-2.5 rounded-lg border border-border/80 bg-background/50 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="px-1.5 py-0.5 rounded bg-primary/15 text-primary text-[10px] font-bold border border-primary/25">
                  策略意圖
                </span>
                <span className="font-semibold text-foreground">{bot.intentSummary}</span>
              </div>
              <div className="text-[10px] text-muted-foreground flex items-center gap-3">
                <span>評估時標: {bot.dataEvalTime}</span>
                <span>持倉目標: {bot.targetPosText} (名義價值 ${bot.notional.toLocaleString()})</span>
              </div>
            </div>

            {/* 橫向五階段管線卡片 */}
            <div className="grid grid-cols-5 gap-2 flex-1">
              {bot.stages.map((stage, idx) => {
                const isOk = stage.status === "OK";
                const isWarning = stage.status === "WARNING";
                const isBlocked = stage.status === "BLOCKED";

                return (
                  <div
                    key={stage.name}
                    className={cn(
                      "p-2.5 rounded-lg border flex flex-col justify-between transition-all relative",
                      isOk && "bg-secondary/40 border-border/80",
                      isWarning && "bg-amber-400/10 border-amber-400/40 text-amber-200",
                      isBlocked && "bg-rose-400/10 border-rose-400/40 text-rose-200"
                    )}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] text-muted-foreground font-bold">階段 0{idx + 1}</span>
                        {isOk && <CheckCircle2 className="size-3.5 text-emerald-400" />}
                        {isWarning && <AlertTriangle className="size-3.5 text-amber-400 animate-pulse" />}
                        {isBlocked && <Lock className="size-3.5 text-rose-400" />}
                      </div>
                      <div className="text-[12px] font-bold text-foreground mb-0.5">{stage.name}</div>
                      <div className="text-[10px] text-primary font-semibold">{stage.subtext}</div>
                    </div>
                    <div className="text-[9.5px] text-muted-foreground mt-2 border-t border-border/40 pt-1.5 leading-tight">
                      {stage.detail}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* TAB 2: P6 災難停損防線 */}
        {bottomDockTab === "p6" && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 h-full">
            <div className="p-3 rounded-lg border border-border bg-background/50 flex flex-col justify-between">
              <div>
                <span className="text-[10px] text-muted-foreground uppercase font-bold">P6 停損防線狀態</span>
                <div className="flex items-center gap-2 mt-1">
                  <span
                    className={cn(
                      "size-2 rounded-full",
                      bot.p6Status === "ACTIVE" ? "bg-emerald-400" : "bg-amber-400 animate-pulse"
                    )}
                  />
                  <span className="text-sm font-bold text-foreground">
                    {bot.p6Status === "ACTIVE" ? "正常生效防護中" : "防線更新中 (待確認)"}
                  </span>
                </div>
              </div>
              <p className="text-[10px] text-muted-foreground mt-2">
                來源: {bot.p6Source}。作為主機故障斷線時交易所端最後硬防線。
              </p>
            </div>

            <div className="p-3 rounded-lg border border-border bg-background/50 flex flex-col justify-between">
              <div>
                <span className="text-[10px] text-muted-foreground uppercase font-bold">停損觸發價格</span>
                <div className="text-base font-bold text-primary mt-1">{bot.p6StopPrice}</div>
              </div>
              <p className="text-[10px] text-muted-foreground mt-2">
                距 Mark 標記價安全距離: <strong className="text-emerald-400">{bot.p6DistPct}</strong>
              </p>
            </div>

            <div className="p-3 rounded-lg border border-border bg-background/50 flex flex-col justify-between">
              <div>
                <span className="text-[10px] text-muted-foreground uppercase font-bold">Tick 取整方向規範</span>
                <div className="text-xs font-bold text-foreground mt-1">{bot.p6Rounding}</div>
              </div>
              <p className="text-[10px] text-muted-foreground mt-2">
                多倉強制向上取整 (CEIL)，提早觸發防護，嚴禁向外放寬。
              </p>
            </div>

            <div className="p-3 rounded-lg border border-border bg-background/50 flex flex-col justify-between">
              <div>
                <span className="text-[10px] text-muted-foreground uppercase font-bold">災難停損專屬預算</span>
                <div className="text-sm font-bold text-foreground mt-1">{bot.p6BudgetPct}% 總持倉曝險</div>
              </div>
              <p className="text-[10px] text-muted-foreground mt-2">
                當平均成本改變或新成交時自動聯動修正，失敗即禁止增倉。
              </p>
            </div>
          </div>
        )}

        {/* TAB 3: 風控審計與日損 Latch */}
        {bottomDockTab === "risk" && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 h-full">
            <div className="p-3 rounded-lg border border-border bg-background/50 flex flex-col justify-between">
              <div>
                <span className="text-[10px] text-muted-foreground uppercase font-bold">有效槓桿倍數審計</span>
                <div className="text-sm font-bold text-foreground mt-1">{bot.riskLeverage}</div>
              </div>
              <p className="text-[10px] text-muted-foreground mt-2">
                事前風控計算包含在途委託與 UNKNOWN 狀態，杜絕穿倉超限。
              </p>
            </div>

            <div className="p-3 rounded-lg border border-border bg-background/50 flex flex-col justify-between">
              <div>
                <span className="text-[10px] text-muted-foreground uppercase font-bold">單幣曝險預算占比</span>
                <div className="text-sm font-bold text-foreground mt-1">{bot.riskSingleAssetQuota}</div>
              </div>
              <p className="text-[10px] text-muted-foreground mt-2">
                總曝險預算 = 有效槓桿上限 × 風控權益。單幣上限預設 50%。
              </p>
            </div>

            <div className="p-3 rounded-lg border border-border bg-background/50 flex flex-col justify-between">
              <div>
                <span className="text-[10px] text-muted-foreground uppercase font-bold">日損鎖存 (Latch) 機制</span>
                <div className="text-sm font-bold text-emerald-400 mt-1">NORMAL (正常運作)</div>
              </div>
              <p className="text-[10px] text-muted-foreground mt-2">
                Soft 10% 禁增倉、Hard 20% 市價清倉。一旦觸發必須人工解除，跨日重啟不自動恢復。
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
