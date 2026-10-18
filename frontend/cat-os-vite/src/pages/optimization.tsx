import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { SlidersHorizontal, Award, Sparkles, Download } from "lucide-react";
import { AppShell, PageHead, Panel } from "@/components/catos/shell";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/optimization")({
  head: () => ({
    meta: [
      { title: "參數優化 (Optimization) — catOS Quant Terminal" },
      { name: "description", content: "catOS 策略參數優化：Optuna 搜尋演算法、Pareto 帕累托前沿超參數尋優。" },
    ],
  }),
  component: OptimizationPage,
});

interface OptTrial {
  trialNumber: number;
  fastPeriod: number;
  slowPeriod: number;
  atrMultiplier: number;
  sharpe: string;
  totalReturn: string;
  maxDrawdown: string;
  isBest: boolean;
}

const TRIALS: OptTrial[] = [
  { trialNumber: 42, fastPeriod: 12, slowPeriod: 34, atrMultiplier: 2.5, sharpe: "2.45", totalReturn: "+26.8%", maxDrawdown: "-3.8%", isBest: true },
  { trialNumber: 28, fastPeriod: 10, slowPeriod: 30, atrMultiplier: 2.0, sharpe: "2.21", totalReturn: "+22.4%", maxDrawdown: "-4.2%", isBest: false },
  { trialNumber: 65, fastPeriod: 14, slowPeriod: 38, atrMultiplier: 3.0, sharpe: "2.08", totalReturn: "+19.6%", maxDrawdown: "-3.5%", isBest: false },
  { trialNumber: 15, fastPeriod: 8, slowPeriod: 25, atrMultiplier: 1.8, sharpe: "1.92", totalReturn: "+17.3%", maxDrawdown: "-5.1%", isBest: false },
  { trialNumber: 84, fastPeriod: 16, slowPeriod: 45, atrMultiplier: 2.8, sharpe: "1.75", totalReturn: "+14.1%", maxDrawdown: "-4.6%", isBest: false },
  { trialNumber: 91, fastPeriod: 11, slowPeriod: 32, atrMultiplier: 2.2, sharpe: "1.68", totalReturn: "+13.5%", maxDrawdown: "-4.9%", isBest: false },
];

function OptimizationPage() {
  const [selectedTrial, setSelectedTrial] = useState<OptTrial>(TRIALS[0]);
  const [exported, setExported] = useState(false);

  return (
    <AppShell>
      <PageHead
        code="RESEARCH // OPTIMIZATION"
        title="參數優化中心"
        desc="Optuna 貝氏最佳化引擎 · 帕累托前沿超參數尋優 · 嚴格隔離搜尋評分"
        right={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="h-7 text-xs border-border bg-surface hover:bg-surface-raised">
              <SlidersHorizontal className="size-3.5 mr-1" /> 載入搜尋空間
            </Button>
            <Button size="sm" className="h-7 text-xs bg-primary text-primary-foreground hover:bg-primary/90 font-medium">
              <Sparkles className="size-3.5 mr-1 fill-current" /> 發起優化任務
            </Button>
          </div>
        }
      />

      <div className="space-y-4">
        {/* ==================== 頂部優化任務全景狀態卡 ==================== */}
        <div className="rounded-xl border border-border/80 bg-surface/90 p-4 shadow-xs backdrop-blur-md">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <div>
              <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">目標策略</span>
              <p className="mt-1 text-sm font-semibold text-primary">EMA-ATR-Breakout</p>
              <span className="text-[10px] text-muted-foreground">單合約 BTC-USDT 15m</span>
            </div>

            <div>
              <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">搜尋演算法</span>
              <p className="mt-1 font-mono text-sm font-semibold text-foreground">TPE (Tree-structured Parzen)</p>
              <span className="text-[10px] text-muted-foreground">Optuna 貝氏採樣</span>
            </div>

            <div>
              <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">試驗進度 (Trials)</span>
              <div className="mt-1 flex items-center gap-2">
                <span className="font-mono text-sm font-bold text-foreground">100 / 100</span>
                <span className="rounded bg-primary/10 border border-primary/20 px-1.5 py-0.2 text-[9px] font-mono font-medium text-primary">
                  COMPLETED
                </span>
              </div>
              <span className="text-[10px] text-muted-foreground">並行 4 Workers 耗時 42s</span>
            </div>

            <div>
              <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">最佳評分 (Sharpe)</span>
              <div className="mt-1 flex items-baseline gap-1.5">
                <span className="font-mono text-xl font-bold text-up">2.45</span>
                <span className="font-mono text-xs text-primary font-medium">(Trial #42)</span>
              </div>
              <span className="text-[10px] text-muted-foreground">年化收益 +26.8% · 回撤 -3.8%</span>
            </div>
          </div>
        </div>

        {/* ==================== 下半部：左欄搜尋空間，右欄試驗排行榜 ==================== */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          {/* 左欄：搜尋空間與匯出 (5 欄) */}
          <div className="lg:col-span-5 space-y-4">
            <Panel
              title="搜尋空間定義 (Search Space)"
              meta={<span className="text-[10px] font-mono text-muted-foreground">3 個超參數維度</span>}
            >
              <div className="space-y-3">
                <div className="rounded-lg border border-border/60 bg-background/40 p-3">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-semibold text-foreground">fast_ema_period</span>
                    <span className="font-mono text-[10px] text-primary bg-primary/10 px-1.5 py-0.5 rounded">最佳值: 12</span>
                  </div>
                  <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                    IntRange(min=5, max=25, step=1)
                  </p>
                </div>

                <div className="rounded-lg border border-border/60 bg-background/40 p-3">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-semibold text-foreground">slow_ema_period</span>
                    <span className="font-mono text-[10px] text-primary bg-primary/10 px-1.5 py-0.5 rounded">最佳值: 34</span>
                  </div>
                  <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                    IntRange(min=20, max=60, step=2)
                  </p>
                </div>

                <div className="rounded-lg border border-border/60 bg-background/40 p-3">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-semibold text-foreground">atr_stop_multiplier</span>
                    <span className="font-mono text-[10px] text-primary bg-primary/10 px-1.5 py-0.5 rounded">最佳值: 2.5</span>
                  </div>
                  <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                    FloatRange(min=1.5, max=4.0, step=0.5)
                  </p>
                </div>

                <div className="pt-2">
                  <Button
                    onClick={() => {
                      setExported(true);
                      setTimeout(() => setExported(false), 2500);
                    }}
                    className="w-full text-xs font-semibold bg-primary text-primary-foreground hover:bg-primary/90 h-9"
                  >
                    <Download className="size-3.5 mr-1.5" />
                    {exported ? "已導出至 strategies/ema_atr_v1.3.py" : "導出 Trial #42 為新策略製品版本 (v1.3)"}
                  </Button>
                </div>
              </div>
            </Panel>

            <Panel title="P7 架構約束守則">
              <p className="text-xs text-muted-foreground leading-relaxed">
                交易計算與原始績效嚴格維持 Decimal 核心，僅允許將衍生搜尋評分（如夏普、索提諾）轉為 Float 傳遞給 Optuna 進行尋優；浮點數評分不得回流為帳務或風控之判定依據。
              </p>
            </Panel>
          </div>

          {/* 右欄：排行榜表格 (7 欄) */}
          <div className="lg:col-span-7">
            <Panel
              title="試驗排行榜 (Top Trials · 帕累托前沿)"
              meta={<span className="text-[10px] font-mono text-primary font-medium flex items-center gap-1"><Award className="size-3" />帕累托最優</span>}
            >
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead className="border-b border-border text-[10px] font-mono text-muted-foreground bg-background/30">
                    <tr>
                      <th className="py-2 px-3 font-normal">Trial #</th>
                      <th className="py-2 px-3 font-normal">Fast / Slow</th>
                      <th className="py-2 px-3 font-normal">ATR Multi</th>
                      <th className="py-2 px-3 text-right font-normal">夏普評分</th>
                      <th className="py-2 px-3 text-right font-normal">總收益</th>
                      <th className="py-2 px-3 text-right font-normal">最大回撤</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40 font-mono">
                    {TRIALS.map((t) => {
                      const isSelected = selectedTrial.trialNumber === t.trialNumber;
                      return (
                        <tr
                          key={t.trialNumber}
                          onClick={() => setSelectedTrial(t)}
                          className={cn(
                            "cursor-pointer transition-colors",
                            isSelected ? "bg-primary/10" : "hover:bg-secondary/30"
                          )}
                        >
                          <td className="py-2.5 px-3">
                            <span className={cn(
                              "inline-flex items-center gap-1 font-semibold",
                              t.isBest ? "text-primary" : "text-foreground"
                            )}>
                              #{t.trialNumber} {t.isBest && <span className="text-[9px] bg-primary text-primary-foreground px-1 rounded">BEST</span>}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-muted-foreground">{t.fastPeriod} / {t.slowPeriod}</td>
                          <td className="py-2.5 px-3 text-muted-foreground">{t.atrMultiplier.toFixed(1)}x</td>
                          <td className="py-2.5 px-3 text-right font-bold text-foreground">{t.sharpe}</td>
                          <td className="py-2.5 px-3 text-right text-up font-medium">{t.totalReturn}</td>
                          <td className="py-2.5 px-3 text-right text-down font-medium">{t.maxDrawdown}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Panel>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
