import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Play, History, CheckCircle2, TrendingUp, ArrowDownRight, Scale, Activity, ArrowUpRight, ArrowDownLeft } from "lucide-react";
import { AppShell, PageHead, Panel } from "@/components/catos/shell";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/backtest")({
  head: () => ({
    meta: [
      { title: "歷史回測 (Backtest) — catOS Quant Terminal" },
      { name: "description", content: "catOS 歷史回測工作區：單合約、單週期、Closed Bar 策略回測與績效評估。" },
    ],
  }),
  component: BacktestPage,
});

interface BacktestRun {
  id: string;
  strategyName: string;
  symbol: string;
  timeframe: string;
  startDate: string;
  endDate: string;
  totalReturn: string;
  sharpe: string;
  maxDrawdown: string;
  winRate: string;
  tradesCount: number;
  status: "completed" | "running";
}

const HISTORY_RUNS: BacktestRun[] = [
  {
    id: "bt-20261004-01",
    strategyName: "EMA 雙均線突破 (EMA Cross)",
    symbol: "BTC-USDT-SWAP",
    timeframe: "15m (Closed Bar)",
    startDate: "2026-09-01",
    endDate: "2026-09-30",
    totalReturn: "+18.42%",
    sharpe: "2.14",
    maxDrawdown: "-4.15%",
    winRate: "58.3%",
    tradesCount: 48,
    status: "completed",
  },
  {
    id: "bt-20261004-02",
    strategyName: "ATR 波動區間突破 (ATR Volatility)",
    symbol: "ETH-USDT-SWAP",
    timeframe: "1h (Closed Bar)",
    startDate: "2026-08-15",
    endDate: "2026-09-30",
    totalReturn: "+12.08%",
    sharpe: "1.86",
    maxDrawdown: "-5.20%",
    winRate: "52.1%",
    tradesCount: 34,
    status: "completed",
  },
  {
    id: "bt-20261004-03",
    strategyName: "RSI 均值回歸極值 (RSI Mean Reversion)",
    symbol: "SOL-USDT-SWAP",
    timeframe: "15m (Closed Bar)",
    startDate: "2026-09-15",
    endDate: "2026-09-30",
    totalReturn: "+7.85%",
    sharpe: "1.62",
    maxDrawdown: "-3.80%",
    winRate: "61.5%",
    tradesCount: 26,
    status: "completed",
  },
];

const SAMPLE_FILLS = [
  { id: "1", time: "2026-09-30 18:00", side: "BUY", price: "64,280.00", qty: "0.15 BTC", pnl: "+240.50", fee: "1.92" },
  { id: "2", time: "2026-09-29 14:15", side: "SELL", price: "65,120.00", qty: "0.15 BTC", pnl: "+512.30", fee: "1.95" },
  { id: "3", time: "2026-09-28 09:30", side: "BUY", price: "63,890.00", qty: "0.15 BTC", pnl: "-85.20", fee: "1.91" },
  { id: "4", time: "2026-09-27 21:45", side: "SELL", price: "64,450.00", qty: "0.15 BTC", pnl: "+182.00", fee: "1.93" },
  { id: "5", time: "2026-09-26 11:00", side: "BUY", price: "63,200.00", qty: "0.15 BTC", pnl: "+310.40", fee: "1.89" },
];

function BacktestPage() {
  const [selectedRun, setSelectedRun] = useState<BacktestRun>(HISTORY_RUNS[0]);

  return (
    <AppShell>
      <PageHead
        code="RESEARCH // BACKTEST"
        title="歷史回測中心"
        desc="單合約單週期 Closed Bar 策略回測 · Decimal 精準結算 · 零盤中偷窺"
        right={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="h-7 text-xs border-border bg-surface hover:bg-surface-raised">
              <History className="size-3.5 mr-1" /> 匯入行情
            </Button>
            <Button size="sm" className="h-7 text-xs bg-primary text-primary-foreground hover:bg-primary/90 font-medium">
              <Play className="size-3.5 mr-1 fill-current" /> 發起新回測
            </Button>
          </div>
        }
      />

      <div className="space-y-4">
        {/* ==================== 頂部 4 大核心 KPI 指標卡 ==================== */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {/* 1. 總回報率 */}
          <div className="rounded-xl border border-border/80 bg-surface/90 p-3.5 shadow-xs backdrop-blur-md">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground font-medium">累計總回報率</span>
              <span className="grid size-6 place-items-center rounded bg-up/10 text-up">
                <TrendingUp className="size-3.5" />
              </span>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-mono text-2xl font-bold text-up">{selectedRun.totalReturn}</span>
              <span className="text-[10px] font-mono text-muted-foreground">年化 34.2%</span>
            </div>
            <p className="mt-1 text-[10px] text-muted-foreground truncate font-mono">
              測試標的：{selectedRun.symbol}
            </p>
          </div>

          {/* 2. 夏普比率 */}
          <div className="rounded-xl border border-border/80 bg-surface/90 p-3.5 shadow-xs backdrop-blur-md">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground font-medium">夏普比率 (Sharpe)</span>
              <span className="grid size-6 place-items-center rounded bg-primary/10 text-primary">
                <Scale className="size-3.5" />
              </span>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-mono text-2xl font-bold text-foreground">{selectedRun.sharpe}</span>
              <span className="text-[10px] font-mono text-primary font-medium">超額收益顯著</span>
            </div>
            <p className="mt-1 text-[10px] text-muted-foreground truncate font-mono">
              無風險分母：2.0% · 波動率 11.2%
            </p>
          </div>

          {/* 3. 最大回撤 */}
          <div className="rounded-xl border border-border/80 bg-surface/90 p-3.5 shadow-xs backdrop-blur-md">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground font-medium">最大歷史回撤 (Max DD)</span>
              <span className="grid size-6 place-items-center rounded bg-down/10 text-down">
                <ArrowDownRight className="size-3.5" />
              </span>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-mono text-2xl font-bold text-down">{selectedRun.maxDrawdown}</span>
              <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[9px] font-mono font-medium text-emerald-400">
                安全可控
              </span>
            </div>
            <p className="mt-1 text-[10px] text-muted-foreground truncate font-mono">
              風控警戒臨界：-10.0% · 裕度 5.85%
            </p>
          </div>

          {/* 4. 勝率與交易次數 */}
          <div className="rounded-xl border border-border/80 bg-surface/90 p-3.5 shadow-xs backdrop-blur-md">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground font-medium">交易勝率 / 總單數</span>
              <span className="grid size-6 place-items-center rounded bg-secondary text-foreground">
                <Activity className="size-3.5" />
              </span>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-mono text-2xl font-bold text-foreground">{selectedRun.winRate}</span>
              <span className="text-[11px] font-mono text-muted-foreground">({selectedRun.tradesCount} 筆交易)</span>
            </div>
            <p className="mt-1 text-[10px] text-muted-foreground truncate font-mono">
              盈虧比：1.84 · 平均持倉 3.2h
            </p>
          </div>
        </div>

        {/* ==================== 主體分割：左欄回測歷史與參數，右欄模擬成交流 ==================== */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          {/* 左欄：回測任務列表 (4 欄) */}
          <div className="lg:col-span-5 space-y-4">
            <Panel
              title="歷史回測清單 (Backtest Runs)"
              meta={<span className="text-[10px] text-muted-foreground font-mono">{HISTORY_RUNS.length} 項紀錄</span>}
            >
              <div className="space-y-2">
                {HISTORY_RUNS.map((run) => {
                  const isSelected = selectedRun.id === run.id;
                  return (
                    <div
                      key={run.id}
                      onClick={() => setSelectedRun(run)}
                      className={cn(
                        "group cursor-pointer rounded-lg border p-3 transition-all",
                        isSelected
                          ? "border-primary bg-primary/5 shadow-xs"
                          : "border-border/60 bg-surface/40 hover:border-border hover:bg-surface/70"
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <CheckCircle2 className={cn("size-3.5", isSelected ? "text-primary" : "text-muted-foreground")} />
                          <span className="font-medium text-xs text-foreground">{run.strategyName}</span>
                        </div>
                        <span className="font-mono text-[10px] text-primary">{run.totalReturn}</span>
                      </div>
                      <div className="mt-2 flex items-center justify-between text-[10px] font-mono text-muted-foreground">
                        <span>{run.symbol} · {run.timeframe}</span>
                        <span>{run.startDate} ~ {run.endDate}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Panel>

            <Panel title="回測執行約束與參數 (Constraints)">
              <div className="space-y-2.5 text-xs">
                <div className="flex items-center justify-between border-b border-border/50 pb-2">
                  <span className="text-muted-foreground">K 線週期取樣</span>
                  <span className="font-mono text-foreground font-medium">Closed Bar（嚴禁未收盤即時值）</span>
                </div>
                <div className="flex items-center justify-between border-b border-border/50 pb-2">
                  <span className="text-muted-foreground">預熱根數 (Warmup Bars)</span>
                  <span className="font-mono text-foreground font-medium">50 根（不計入績效）</span>
                </div>
                <div className="flex items-center justify-between border-b border-border/50 pb-2">
                  <span className="text-muted-foreground">手續費費率</span>
                  <span className="font-mono text-foreground font-medium">Maker 0.02% · Taker 0.05%</span>
                </div>
                <div className="flex items-center justify-between border-b border-border/50 pb-2">
                  <span className="text-muted-foreground">滑點模型</span>
                  <span className="font-mono text-foreground font-medium">明示滑價 1 Tick（次根開盤成交）</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">保證金模式</span>
                  <span className="font-mono text-foreground font-medium">USDT-M SWAP · cross + net_mode</span>
                </div>
              </div>
            </Panel>
          </div>

          {/* 右欄：回測成交明細 (7 欄) */}
          <div className="lg:col-span-7">
            <Panel
              title={`模擬逐筆成交記錄 (${selectedRun.strategyName})`}
              meta={<span className="text-[10px] font-mono text-muted-foreground">嚴格遵循 Decimal 計算</span>}
            >
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead className="border-b border-border text-[10px] font-mono text-muted-foreground bg-background/30">
                    <tr>
                      <th className="py-2 px-3 font-normal">時間 (UTC+8)</th>
                      <th className="py-2 px-3 font-normal">方向</th>
                      <th className="py-2 px-3 text-right font-normal">成交價</th>
                      <th className="py-2 px-3 text-right font-normal">數量</th>
                      <th className="py-2 px-3 text-right font-normal">手續費</th>
                      <th className="py-2 px-3 text-right font-normal">淨損益</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40 font-mono">
                    {SAMPLE_FILLS.map((f) => (
                      <tr key={f.id} className="hover:bg-secondary/30 transition-colors">
                        <td className="py-2.5 px-3 text-[11px] text-muted-foreground">{f.time}</td>
                        <td className="py-2.5 px-3">
                          <span className={cn(
                            "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-semibold",
                            f.side === "BUY" ? "bg-up/10 text-up" : "bg-down/10 text-down"
                          )}>
                            {f.side === "BUY" ? <ArrowDownLeft className="size-2.5" /> : <ArrowUpRight className="size-2.5" />}
                            {f.side}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-right font-medium text-foreground">{f.price}</td>
                        <td className="py-2.5 px-3 text-right text-muted-foreground">{f.qty}</td>
                        <td className="py-2.5 px-3 text-right text-muted-foreground">{f.fee} USDT</td>
                        <td className={cn(
                          "py-2.5 px-3 text-right font-medium",
                          f.pnl.startsWith("+") ? "text-up" : "text-down"
                        )}>
                          {f.pnl} USDT
                        </td>
                      </tr>
                    ))}
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
