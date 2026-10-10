import { createFileRoute } from "@tanstack/react-router";
import { useState, useMemo } from "react";
import {
  Area,
  ComposedChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  ReferenceLine,
} from "recharts";
import {
  ArrowDownRight,
  Calendar,
  Clock,
  Scale,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { AppShell, Panel } from "@/components/catos/shell";
import { Button } from "@/components/ui/button";
import { fmtMoney } from "@/hooks/use-live";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/review")({
  head: () => ({
    meta: [
      { title: "策略覆盤與風控績效 · catOS Quant Terminal" },
      { name: "description", content: "catOS 策略覆盤中心：深度回撤分析、水下回撤圖、夏普比率、卡瑪比率與月度收益矩陣。" },
      { property: "og:title", content: "策略覆盤與風控績效 · catOS Quant Terminal" },
      { property: "og:description", content: "Quantitative Strategy Performance, Underwater Drawdown and Risk Analysis." },
    ],
  }),
  component: StrategyReviewPage,
});

type ReviewRange = "30D" | "90D" | "YTD" | "ALL";

interface DrawdownEvent {
  id: string;
  startDate: string;
  troughDate: string;
  recoveryDate: string;
  maxDrawdown: string;
  durationDays: number;
  recoveryDays: number;
  status: "RECOVERED" | "ACTIVE";
}

const DRAWDOWN_EVENTS: DrawdownEvent[] = [
  {
    id: "dd-01",
    startDate: "2026/09/12",
    troughDate: "2026/09/15",
    recoveryDate: "2026/09/19",
    maxDrawdown: "-3.82%",
    durationDays: 3,
    recoveryDays: 4,
    status: "RECOVERED",
  },
  {
    id: "dd-02",
    startDate: "2026/08/04",
    troughDate: "2026/08/07",
    recoveryDate: "2026/08/11",
    maxDrawdown: "-2.65%",
    durationDays: 3,
    recoveryDays: 4,
    status: "RECOVERED",
  },
  {
    id: "dd-03",
    startDate: "2026/07/18",
    troughDate: "2026/07/20",
    recoveryDate: "2026/07/22",
    maxDrawdown: "-1.85%",
    durationDays: 2,
    recoveryDays: 2,
    status: "RECOVERED",
  },
  {
    id: "dd-04",
    startDate: "2026/05/21",
    troughDate: "2026/05/24",
    recoveryDate: "2026/05/29",
    maxDrawdown: "-3.14%",
    durationDays: 3,
    recoveryDays: 5,
    status: "RECOVERED",
  },
];

const MONTHLY_RETURNS = [
  { month: "1月", returnPct: "+3.2%", positive: true },
  { month: "2月", returnPct: "+4.8%", positive: true },
  { month: "3月", returnPct: "+2.1%", positive: true },
  { month: "4月", returnPct: "+5.6%", positive: true },
  { month: "5月", returnPct: "-1.2%", positive: false },
  { month: "6月", returnPct: "+4.1%", positive: true },
  { month: "7月", returnPct: "+3.8%", positive: true },
  { month: "8月", returnPct: "+6.2%", positive: true },
  { month: "9月", returnPct: "+4.5%", positive: true },
  { month: "10月", returnPct: "+1.7%", positive: true },
];

function generateReviewSeries(range: ReviewRange) {
  const points = range === "30D" ? 60 : range === "90D" ? 90 : range === "YTD" ? 120 : 150;
  const startReturn = 0;
  const targetEndReturn = range === "30D" ? 12.46 : range === "90D" ? 22.8 : 34.8;
  
  let peak = 0;
  return Array.from({ length: points }, (_, i) => {
    const t = i / (points - 1);
    const wave = (Math.sin(i * 0.42) * 0.35 + Math.sin(i * 0.18) * 0.65) * Math.sin(t * Math.PI);
    const returnPct = Number((startReturn + (targetEndReturn - startReturn) * t + wave * 1.8).toFixed(2));
    peak = Math.max(peak, returnPct);
    const dd = Number((returnPct - peak).toFixed(2));

    const date = new Date(Date.UTC(2026, 9, 10) - (1 - t) * (points * 1.2) * 86400000);
    const m = date.getUTCMonth() + 1;
    const d = date.getUTCDate();
    const label = `${m}/${d}`;
    const equity = Math.round(10_000_000 * (1 + returnPct / 100));

    return {
      label,
      dateStr: `${date.getUTCFullYear()}/${m}/${d}`,
      returnPct,
      drawdown: dd,
      equity,
    };
  });
}

function StrategyReviewPage() {
  const { language } = useI18n();
  const [range, setRange] = useState<ReviewRange>("YTD");
  const series = useMemo(() => generateReviewSeries(range), [range]);

  return (
    <AppShell>
      <div className="space-y-4">
        {/* ==================== 頂部 4 大量化績效與風控指標卡 ==================== */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {/* 1. 策略累計收益 */}
          <div className="rounded-2xl border border-border/70 bg-secondary/35 p-4 shadow-sm backdrop-blur-md">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">
                {language === "zh-TW" ? "策略累計淨收益" : "Cumulative Net Return"}
              </span>
              <span className="grid size-7 place-items-center rounded-lg bg-up/10 text-up">
                <TrendingUp className="size-4" />
              </span>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-mono text-2xl font-bold tracking-tight text-up">+34.80%</span>
              <span className="text-[11px] font-mono text-muted-foreground">年化 42.15%</span>
            </div>
            <p className="mt-1 text-[10px] text-muted-foreground/80">
              實盤淨值：12,483,920.00 USDT
            </p>
          </div>

          {/* 2. 最大回撤 (Max Drawdown - 交易員核心關注重點) */}
          <div className="rounded-2xl border border-border/70 bg-secondary/35 p-4 shadow-sm backdrop-blur-md">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">
                {language === "zh-TW" ? "最大回撤深度 (Max DD)" : "Max Drawdown"}
              </span>
              <span className="grid size-7 place-items-center rounded-lg bg-down/10 text-down">
                <ArrowDownRight className="size-4" />
              </span>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-mono text-2xl font-bold tracking-tight text-down">-3.82%</span>
              <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-mono font-medium text-emerald-400">
                低風險
              </span>
            </div>
            <p className="mt-1 text-[10px] text-muted-foreground/80">
              風控警戒線：-10.00% · 距閾值 6.18%
            </p>
          </div>

          {/* 3. 夏普比率 (Sharpe Ratio) */}
          <div className="rounded-2xl border border-border/70 bg-secondary/35 p-4 shadow-sm backdrop-blur-md">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">
                {language === "zh-TW" ? "年化夏普比率 (Sharpe)" : "Sharpe Ratio"}
              </span>
              <span className="grid size-7 place-items-center rounded-lg bg-primary/10 text-primary">
                <Scale className="size-4" />
              </span>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-mono text-2xl font-bold tracking-tight text-foreground">2.45</span>
              <span className="text-[11px] font-mono text-primary font-medium">優於 92% 策略</span>
            </div>
            <p className="mt-1 text-[10px] text-muted-foreground/80">
              基準無風險利率：4.25% (USDT)
            </p>
          </div>

          {/* 4. 卡瑪比率 (Calmar Ratio - 收益/回撤比) */}
          <div className="rounded-2xl border border-border/70 bg-secondary/35 p-4 shadow-sm backdrop-blur-md">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">
                {language === "zh-TW" ? "卡瑪比率 (Calmar)" : "Calmar Ratio"}
              </span>
              <span className="grid size-7 place-items-center rounded-lg bg-primary/10 text-primary">
                <ShieldCheck className="size-4" />
              </span>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-mono text-2xl font-bold tracking-tight text-foreground">3.26</span>
              <span className="text-[11px] font-mono text-muted-foreground">盈虧比 2.18</span>
            </div>
            <p className="mt-1 text-[10px] text-muted-foreground/80">
              勝率：68.4% · 平均修復週期 3.5 天
            </p>
          </div>
        </div>

        {/* ==================== 核心大圖：雙軸累積淨值與水下回撤曲線 ==================== */}
        <Panel
          title={
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <span className="h-0.5 w-3 rounded-full bg-primary inline-block" />
                <span>
                  {language === "zh-TW" ? "策略累積淨值與水下回撤分析 (Underwater Analysis)" : "Equity & Underwater Drawdown"}
                </span>
              </span>
              <span className="text-[11px] font-normal text-muted-foreground/75 hidden md:inline">
                {language === "zh-TW" ? "上軸為策略收益率，下軸為回撤深度與修復水線" : "Top: Cumulative Return; Bottom: Underwater Drawdown"}
              </span>
            </div>
          }
          meta={
            <div className="flex items-center gap-1 rounded-lg bg-background/80 p-0.5 border border-border/50">
              {(["30D", "90D", "YTD", "ALL"] as ReviewRange[]).map((r) => (
                <Button
                  key={r}
                  variant="ghost"
                  size="sm"
                  aria-pressed={range === r}
                  onClick={() => setRange(r)}
                  className={cn(
                    "h-6 rounded px-2.5 num text-[10.5px] transition-all",
                    range === r ? "bg-secondary text-foreground font-semibold shadow-xs" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {r}
                </Button>
              ))}
            </div>
          }
        >
          {/* 圖例說明 */}
          <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground px-1">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5">
                <span className="h-0.5 w-3 bg-white" />
                <span className="text-foreground">{language === "zh-TW" ? "策略累積淨值 (Equity %)" : "Equity %"}</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-0.5 w-3 bg-down" />
                <span className="text-down">{language === "zh-TW" ? "水下回撤深度 (Underwater DD %)" : "Drawdown %"}</span>
              </span>
            </div>
            <div className="font-mono text-[11px] text-muted-foreground">
              最大回撤閾值: <span className="text-down font-bold">-10.00%</span>
            </div>
          </div>

          <div className="terminal-chart h-[320px] pt-1">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={series} margin={{ top: 12, right: 36, left: 10, bottom: 4 }}>
                <defs>
                  {/* 淨值微光 */}
                  <linearGradient id="review-equity-glow" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#ffffff" stopOpacity={0.12} />
                    <stop offset="100%" stopColor="#ffffff" stopOpacity={0.01} />
                  </linearGradient>
                  {/* 水下回撤漸變 */}
                  <linearGradient id="review-dd-fill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--down)" stopOpacity={0.05} />
                    <stop offset="100%" stopColor="var(--down)" stopOpacity={0.35} />
                  </linearGradient>
                </defs>

                <CartesianGrid stroke="var(--border)" vertical={false} strokeDasharray="3 4" strokeOpacity={0.4} />

                {/* 0% 基準線 */}
                <ReferenceLine yAxisId="equity" y={0} stroke="var(--border)" strokeDasharray="3 3" />
                {/* -10% 風控硬熔斷警戒線 */}
                <ReferenceLine
                  yAxisId="drawdown"
                  y={-10}
                  stroke="var(--down)"
                  strokeDasharray="4 4"
                  strokeOpacity={0.8}
                />

                <XAxis
                  dataKey="label"
                  interval={Math.floor(series.length / 7)}
                  tick={{ fill: "var(--muted-foreground)", fontSize: 10, fontFamily: "var(--font-mono)" }}
                  tickLine={false}
                  axisLine={false}
                  minTickGap={24}
                />

                {/* 左軸：策略淨值累積收益率 */}
                <YAxis
                  yAxisId="equity"
                  domain={['dataMin - 1', 'dataMax + 2']}
                  tick={{ fill: "var(--muted-foreground)", fontSize: 10, fontFamily: "var(--font-mono)" }}
                  tickFormatter={(v) => `+${Number(v).toFixed(0)}%`}
                  axisLine={false}
                  tickLine={false}
                  width={42}
                />

                {/* 右軸：水下回撤百分比 */}
                <YAxis
                  yAxisId="drawdown"
                  orientation="right"
                  domain={[-12, 0]}
                  ticks={[-10, -6, -3, 0]}
                  tick={{ fill: "var(--down)", fontSize: 10, fontFamily: "var(--font-mono)" }}
                  tickFormatter={(v) => `${Number(v).toFixed(0)}%`}
                  axisLine={false}
                  tickLine={false}
                  width={38}
                />

                <Tooltip
                  cursor={{ stroke: "rgba(255, 255, 255, 0.25)", strokeDasharray: "3 3" }}
                  content={({ active, payload }) => {
                    if (!active || !payload || !payload.length) return null;
                    const d = payload[0].payload;
                    return (
                      <div className="rounded-xl border border-border/80 bg-popover/95 p-3 shadow-2xl backdrop-blur-xl space-y-1">
                        <p className="font-mono text-[10px] text-muted-foreground">{d.dateStr}</p>
                        <div className="flex items-center justify-between gap-4 font-mono text-xs">
                          <span className="text-muted-foreground">{language === "zh-TW" ? "累積收益" : "Return"}:</span>
                          <span className="font-bold text-up">+{d.returnPct}%</span>
                        </div>
                        <div className="flex items-center justify-between gap-4 font-mono text-xs">
                          <span className="text-muted-foreground">{language === "zh-TW" ? "水下回撤" : "Drawdown"}:</span>
                          <span className="font-bold text-down">{d.drawdown}%</span>
                        </div>
                        <div className="flex items-center justify-between gap-4 font-mono text-[11px] pt-1 border-t border-border/40">
                          <span className="text-muted-foreground">淨值:</span>
                          <span className="text-foreground">{fmtMoney(d.equity)} USDT</span>
                        </div>
                      </div>
                    );
                  }}
                />

                {/* 淨值曲線 */}
                <Area
                  yAxisId="equity"
                  type="monotone"
                  dataKey="returnPct"
                  name="Equity"
                  stroke="#ffffff"
                  strokeWidth={2}
                  fill="url(#review-equity-glow)"
                  isAnimationActive={false}
                />

                {/* 水下回撤曲線 */}
                <Area
                  yAxisId="drawdown"
                  type="monotone"
                  dataKey="drawdown"
                  name="Drawdown"
                  stroke="var(--down)"
                  strokeWidth={1.5}
                  fill="url(#review-dd-fill)"
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        {/* ==================== 底部雙列：回撤事件清單 + 月度收益熱力矩陣 ==================== */}
        <div className="grid gap-4 lg:grid-cols-2">
          {/* 1. 歷史重大回撤與修復週期分析 */}
          <Panel
            title={
              <div className="flex items-center gap-2">
                <Clock className="size-4 text-down" />
                <span>{language === "zh-TW" ? "歷史回撤修復週期分析" : "Drawdown Recovery Cycles"}</span>
              </div>
            }
          >
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="border-b border-border/60 text-[10px] text-muted-foreground font-mono">
                  <tr>
                    <th className="py-2 pl-1">回撤區間</th>
                    <th className="py-2 text-right">最大深度</th>
                    <th className="py-2 text-right">觸底耗時</th>
                    <th className="py-2 text-right">修復天數</th>
                    <th className="py-2 pr-1 text-right">狀態</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40 font-mono text-[11px]">
                  {DRAWDOWN_EVENTS.map((ev) => (
                    <tr key={ev.id} className="hover:bg-secondary/20 transition-colors">
                      <td className="py-2.5 pl-1 text-foreground/90 font-medium">
                        {ev.startDate.slice(5)} ~ {ev.recoveryDate.slice(5)}
                      </td>
                      <td className="py-2.5 text-right font-bold text-down">
                        {ev.maxDrawdown}
                      </td>
                      <td className="py-2.5 text-right text-muted-foreground">
                        {ev.durationDays} 天
                      </td>
                      <td className="py-2.5 text-right text-foreground">
                        {ev.recoveryDays} 天
                      </td>
                      <td className="py-2.5 pr-1 text-right">
                        <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[9.5px] font-medium text-emerald-400">
                          已修復
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          {/* 2. 月度收益分佈矩陣 */}
          <Panel
            title={
              <div className="flex items-center gap-2">
                <Calendar className="size-4 text-primary" />
                <span>{language === "zh-TW" ? "2026 年度每月收益分佈" : "2026 Monthly Returns"}</span>
              </div>
            }
          >
            <div className="grid grid-cols-5 gap-2 pt-1 font-mono">
              {MONTHLY_RETURNS.map((m) => (
                <div
                  key={m.month}
                  className="rounded-xl border border-border/60 bg-secondary/30 p-2.5 text-center transition-all hover:bg-secondary/60"
                >
                  <span className="text-[10px] text-muted-foreground block font-sans">{m.month}</span>
                  <span
                    className={cn(
                      "text-xs font-bold mt-1 block",
                      m.positive ? "text-up" : "text-down"
                    )}
                  >
                    {m.returnPct}
                  </span>
                </div>
              ))}
            </div>

            <div className="mt-4 flex items-center justify-between border-t border-border/40 pt-3 text-[11px] text-muted-foreground font-mono">
              <span>正收益月份: <strong className="text-up">9 / 10 個月</strong> (90%)</span>
              <span>平均月度回報: <strong className="text-foreground">+3.48%</strong></span>
            </div>
          </Panel>
        </div>
      </div>
    </AppShell>
  );
}
