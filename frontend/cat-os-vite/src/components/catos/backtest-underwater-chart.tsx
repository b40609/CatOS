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

// Real curve interfaces and empty state support

export interface BacktestUnderwaterChartProps {
  equityCurve?: { time_ms: number; equity: string }[];
  drawdownCurve?: { time_ms: number; drawdown_pct: string }[];
  currentEquity?: string;
  returnPct?: string;
  maxDrawdownPct?: string;
  dataNotice?: string;
  loading?: boolean;
}

export function BacktestUnderwaterChart({
  equityCurve,
  drawdownCurve,
  currentEquity,
  returnPct,
  maxDrawdownPct,
  dataNotice,
  loading = false,
}: BacktestUnderwaterChartProps = {}) {
  const [activeTab, setActiveTab] = useState<"curve" | "heatmap">("curve");

  const hasData = Array.isArray(equityCurve) && equityCurve.length > 0;

  // Format real curves if provided
  const chartData = hasData
    ? equityCurve.map((point, index) => {
        const ddPoint = drawdownCurve && drawdownCurve[index];
        const ddVal = ddPoint ? -Math.abs(parseFloat(ddPoint.drawdown_pct) || 0) : 0;
        const d = new Date(point.time_ms);
        const timeLabel = isNaN(d.getTime())
          ? `#${index + 1}`
          : `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`;
        return {
          date: timeLabel,
          equity: parseFloat(point.equity) || 0,
          dd: ddVal,
        };
      })
    : [];

  const displayEquity = currentEquity || "--";
  const displayReturn = returnPct ? `${parseFloat(returnPct) >= 0 ? '+' : ''}${returnPct}%` : "--";
  const displayMaxDd = maxDrawdownPct ? `-${Math.abs(parseFloat(maxDrawdownPct))}%` : "--";

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
            · Decimal 核心精確曲線
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

      {loading ? (
        <div className="p-8 text-center text-xs font-mono text-muted-foreground flex flex-col items-center justify-center gap-2">
          <div className="size-4 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <span>回測數據計算中 / 載入中...</span>
        </div>
      ) : !hasData ? (
        <div className="p-8 text-center text-xs font-mono text-muted-foreground flex flex-col items-center justify-center gap-1.5">
          <TrendingUp className="size-5 text-muted-foreground/40" />
          <span className="text-foreground font-medium">暫無回測曲線數據</span>
          <span className="text-[11px] text-muted-foreground">
            請點擊右上角「發起新回測」或於左側歷史清單選取已完成任務
          </span>
        </div>
      ) : activeTab === "curve" ? (
        <div className="p-3 space-y-2">
          {/* 上半部：累積淨值曲線 (Equity Curve) */}
          <div>
            <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground mb-1">
              <span className="flex items-center gap-1.5">
                <span className="size-2 rounded-full bg-emerald-400" />
                累積帳戶權益 (Cumulative Equity, USDT)
                {dataNotice && (
                  <span className="text-[10px] text-amber-400/80 font-normal">
                    · {dataNotice}
                  </span>
                )}
              </span>
              <span className="text-up font-bold">當前 {displayEquity} ({displayReturn})</span>
            </div>
            <div className="h-[125px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--color-up)" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="var(--color-up)" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" opacity={0.3} />
                  <XAxis dataKey="date" hide />
                  <YAxis domain={["dataMin - 10", "dataMax + 10"]} tick={{ fontSize: 9, fill: "var(--color-muted-foreground)" }} />
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
              <span className="text-down font-bold">最大回撤 {displayMaxDd}</span>
            </div>
            <div className="h-[80px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 2, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="underwaterGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--color-down)" stopOpacity={0.0} />
                      <stop offset="95%" stopColor="var(--color-down)" stopOpacity={0.4} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" opacity={0.3} />
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: "var(--color-muted-foreground)" }} />
                  <YAxis domain={["dataMin", 0]} tick={{ fontSize: 9, fill: "var(--color-muted-foreground)" }} tickFormatter={(v) => `${v}%`} />
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
        <div className="p-6 text-center text-xs font-mono text-muted-foreground flex flex-col items-center justify-center gap-1.5">
          <Calendar className="size-5 text-muted-foreground/40" />
          <span className="text-foreground font-medium">單日 96 根 K 線合成取樣（無跨月份歷史資料）</span>
          <span className="text-[11px] text-muted-foreground">
            月度跨期熱力收益矩陣需載入長週期多月行情；後端當前契約為單一合成資料集。
          </span>
        </div>
      )}
    </div>
  );
}
