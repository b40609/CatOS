import { useState } from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { TrendingUp, AlertTriangle, Calendar } from "lucide-react";
import { cn } from "@/lib/utils";

// 合成 30 天的回測淨值與水下載回撤數據
const BACKTEST_CURVE_DATA = [
  { date: "09/01", equity: 10000, dd: 0.0 },
  { date: "09/03", equity: 10240, dd: 0.0 },
  { date: "09/05", equity: 10180, dd: -0.58 },
  { date: "09/07", equity: 10450, dd: 0.0 },
  { date: "09/09", equity: 10320, dd: -1.24 },
  { date: "09/11", equity: 10150, dd: -2.87 },
  { date: "09/13", equity: 10015, dd: -4.15 }, // Max Drawdown Peak
  { date: "09/15", equity: 10350, dd: -0.95 },
  { date: "09/17", equity: 10580, dd: 0.0 },
  { date: "09/19", equity: 10820, dd: 0.0 },
  { date: "09/21", equity: 10740, dd: -0.74 },
  { date: "09/23", equity: 11100, dd: 0.0 },
  { date: "09/25", equity: 11350, dd: 0.0 },
  { date: "09/27", equity: 11240, dd: -0.97 },
  { date: "09/29", equity: 11680, dd: 0.0 },
  { date: "09/30", equity: 11842, dd: 0.0 },
];

const MONTHLY_MATRIX = [
  {
    year: "2026",
    months: [
      { m: "1月", v: 3.42 },
      { m: "2月", v: 2.15 },
      { m: "3月", v: -1.04 },
      { m: "4月", v: 4.80 },
      { m: "5月", v: -0.62 },
      { m: "6月", v: 3.12 },
      { m: "7月", v: 2.85 },
      { m: "8月", v: -1.45 },
      { m: "9月", v: 6.20 },
      { m: "10月", v: 1.84 },
    ],
    ytd: 23.45,
  },
  {
    year: "2025",
    months: [
      { m: "1月", v: 4.10 },
      { m: "2月", v: -2.30 },
      { m: "3月", v: 5.60 },
      { m: "4月", v: 1.20 },
      { m: "5月", v: 3.40 },
      { m: "6月", v: -0.90 },
      { m: "7月", v: 4.50 },
      { m: "8月", v: 2.10 },
      { m: "9月", v: -1.80 },
      { m: "10月", v: 3.90 },
      { m: "11月", v: 6.40 },
      { m: "12月", v: 2.50 },
    ],
    ytd: 31.80,
  },
];

export function BacktestUnderwaterChart() {
  const [activeTab, setActiveTab] = useState<"curve" | "heatmap">("curve");

  return (
    <div className="rounded-xl border border-border/80 bg-surface/90 overflow-hidden shadow-xs backdrop-blur-md">
      {/* 標頭與模式切換 */}
      <div className="flex items-center justify-between border-b border-border/80 px-3.5 py-2 bg-secondary/30">
        <div className="flex items-center gap-2">
          <TrendingUp className="size-3.5 text-primary" />
          <span className="text-xs font-semibold text-foreground">
            回測深度量化分析 (Quant Equity & Underwater)
          </span>
          <span className="text-[10px] font-mono text-muted-foreground hidden sm:inline">
            · Jesse / Freqtrade 標準
          </span>
        </div>

        <div className="flex items-center gap-1 bg-background/60 border border-border/60 rounded p-0.5">
          <button
            type="button"
            onClick={() => setActiveTab("curve")}
            className={cn(
              "px-2 py-0.5 text-[10.5px] font-mono rounded transition-colors cursor-pointer",
              activeTab === "curve"
                ? "bg-secondary text-primary font-bold shadow-xs"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            雙層淨值與回撤曲線
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("heatmap")}
            className={cn(
              "px-2 py-0.5 text-[10.5px] font-mono rounded transition-colors cursor-pointer flex items-center gap-1",
              activeTab === "heatmap"
                ? "bg-secondary text-primary font-bold shadow-xs"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Calendar className="size-3" />
            月度收益熱力矩陣
          </button>
        </div>
      </div>

      {activeTab === "curve" ? (
        <div className="p-3 space-y-2">
          {/* 上半部：累積淨值曲線 (Equity Curve) */}
          <div>
            <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground mb-1">
              <span className="flex items-center gap-1.5">
                <span className="size-2 rounded-full bg-emerald-400" />
                累積帳戶權益 (Cumulative Equity, USDT)
              </span>
              <span className="text-up font-bold">當前 11,842.00 USDT (+18.42%)</span>
            </div>
            <div className="h-[125px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={BACKTEST_CURVE_DATA} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--color-up)" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="var(--color-up)" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" opacity={0.3} />
                  <XAxis dataKey="date" hide />
                  <YAxis domain={["dataMin - 100", "dataMax + 100"]} tick={{ fontSize: 9, fill: "var(--color-muted-foreground)" }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "var(--color-surface)", borderColor: "var(--color-border)", fontSize: "11px", fontFamily: "var(--font-mono)" }}
                    formatter={(v: number) => [`$${v.toLocaleString()} USDT`, "權益"]}
                  />
                  <Area type="monotone" dataKey="equity" stroke="var(--color-up)" strokeWidth={1.8} fill="url(#equityGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 下半部：水下載回撤曲線 (Underwater Drawdown) */}
          <div className="pt-2 border-t border-border/50">
            <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground mb-1">
              <span className="flex items-center gap-1.5 text-down">
                <AlertTriangle className="size-3" />
                水下載歷史回撤 (Underwater Drawdown %)
              </span>
              <span className="text-down font-bold">歷史最深回撤 -4.15% (修復耗時 4 天)</span>
            </div>
            <div className="h-[80px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={BACKTEST_CURVE_DATA} margin={{ top: 2, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="underwaterGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--color-down)" stopOpacity={0.0} />
                      <stop offset="95%" stopColor="var(--color-down)" stopOpacity={0.4} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" opacity={0.3} />
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: "var(--color-muted-foreground)" }} />
                  <YAxis domain={[-5, 0]} tick={{ fontSize: 9, fill: "var(--color-muted-foreground)" }} tickFormatter={(v) => `${v}%`} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "var(--color-surface)", borderColor: "var(--color-border)", fontSize: "11px", fontFamily: "var(--font-mono)" }}
                    formatter={(v: number) => [`${v.toFixed(2)}%`, "距峰頂回撤"]}
                  />
                  <Area type="monotone" dataKey="dd" stroke="var(--color-down)" strokeWidth={1.5} fill="url(#underwaterGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      ) : (
        /* 月度收益熱力矩陣 (Monthly Heatmap) */
        <div className="p-3 overflow-x-auto">
          <table className="w-full text-center border-collapse text-xs font-mono">
            <thead>
              <tr className="border-b border-border/70 text-[10px] text-muted-foreground">
                <th className="py-1.5 px-2 text-left font-normal">年份</th>
                {["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"].map((m) => (
                  <th key={m} className="py-1.5 px-1 font-normal">{m}月</th>
                ))}
                <th className="py-1.5 px-2 font-bold text-primary">YTD 年化</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {MONTHLY_MATRIX.map((row) => (
                <tr key={row.year} className="hover:bg-secondary/20">
                  <td className="py-2 px-2 text-left font-bold text-foreground">{row.year}</td>
                  {Array.from({ length: 12 }).map((_, idx) => {
                    const item = row.months[idx];
                    if (!item) {
                      return <td key={idx} className="py-2 px-1 text-muted-foreground/30">-</td>;
                    }
                    const isPositive = item.v >= 0;
                    return (
                      <td key={idx} className="py-2 px-1">
                        <span
                          className={cn(
                            "inline-block w-full rounded py-1 text-[10.5px] font-semibold transition-transform hover:scale-105",
                            isPositive
                              ? "bg-up/15 text-up border border-up/30"
                              : "bg-down/15 text-down border border-down/30"
                          )}
                        >
                          {isPositive ? `+${item.v.toFixed(1)}%` : `${item.v.toFixed(1)}%`}
                        </span>
                      </td>
                    );
                  })}
                  <td className="py-2 px-2 font-bold text-primary text-xs">
                    +{row.ytd.toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
