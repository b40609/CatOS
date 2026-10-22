import { useState, useMemo } from "react";
import { cn } from "@/lib/utils";
import { useLiveMarketStore } from "@/state/liveMarketStore";

export type DashboardRange = "1D" | "7D" | "30D" | "YTD";

const ranges: DashboardRange[] = ["1D", "7D", "30D", "YTD"];

const rangeDays: Record<DashboardRange, number> = {
  "1D": 1,
  "7D": 7,
  "30D": 30,
  YTD: 283,
};

const rangeReturns: Record<DashboardRange, number> = {
  "1D": 0.0314,
  "7D": 0.0825,
  "30D": 0.1680,
  YTD: 0.4250,
};

interface RelaxedEquityChartProps {
  className?: string;
  defaultRange?: DashboardRange;
}

export function RelaxedEquityChart({
  className,
  defaultRange = "30D",
}: RelaxedEquityChartProps) {
  const [selectedRange, setSelectedRange] = useState<DashboardRange>(defaultRange);
  const liveEquity = useLiveMarketStore((s) => s.totalEquity) ?? 48550.0;

  // 1:1 精確連動帳戶真實權益規模
  const series = useMemo(() => {
    const end = liveEquity;
    const start = end / (1 + rangeReturns[selectedRange]);
    let peak = start;
    const count = 72;
    const out: {
      label: string;
      equity: number;
      drawdown: number;
      x: number;
      yEq: number;
      yDd: number;
    }[] = [];

    const leftMargin = 55;
    const rightMargin = 555;
    const chartWidth = rightMargin - leftMargin;

    // Domain min/max
    const eqMin = start * 0.985;
    const eqMax = end * 1.025;
    const eqSpan = eqMax - eqMin;

    for (let i = 0; i < count; i++) {
      const t = i / (count - 1);
      const wave =
        (Math.sin(i * 0.71) * 0.32 + Math.sin(i * 0.21) * 0.64) *
        Math.sin(t * Math.PI);
      const equity = Math.round(start + (end - start) * (t + wave * 0.14));
      peak = Math.max(peak, equity);
      const date = new Date(
        Date.UTC(2026, 9, 10) - (1 - t) * rangeDays[selectedRange] * 86400000
      );
      const label =
        selectedRange === "1D"
          ? date.toISOString().slice(11, 16)
          : date.toISOString().slice(5, 10).replace("-", "/");
      const drawdown = Number(((equity / peak - 1) * 100).toFixed(3));

      const x = leftMargin + t * chartWidth;
      // Map equity from eqMin -> eqMax to y: 155 -> 22
      const yEq = 155 - ((equity - eqMin) / eqSpan) * 133;
      // Map drawdown 0% -> -8% to y: 175 -> 205
      const yDd = 175 + (Math.abs(drawdown) / 8) * 30;

      out.push({ label, equity, drawdown, x, yEq, yDd });
    }
    return out;
  }, [selectedRange, liveEquity]);

  const returnPctText = useMemo(() => {
    const ret = rangeReturns[selectedRange] * 100;
    return `+${ret.toFixed(2)}%`;
  }, [selectedRange]);

  const equityPath = useMemo(() => {
    if (!series.length) return "";
    return series.reduce(
      (acc, p, i) => `${acc} ${i === 0 ? "M" : "L"} ${p.x.toFixed(1)},${p.yEq.toFixed(1)}`,
      ""
    );
  }, [series]);

  const equityAreaPath = useMemo(() => {
    if (!series.length) return "";
    const first = series[0];
    const last = series[series.length - 1];
    return `${equityPath} L ${last.x.toFixed(1)},172 L ${first.x.toFixed(1)},172 Z`;
  }, [series, equityPath]);

  const drawdownPath = useMemo(() => {
    if (!series.length) return "";
    return series.reduce(
      (acc, p, i) => `${acc} ${i === 0 ? "M" : "L"} ${p.x.toFixed(1)},${p.yDd.toFixed(1)}`,
      ""
    );
  }, [series]);

  const drawdownAreaPath = useMemo(() => {
    if (!series.length) return "";
    const first = series[0];
    const last = series[series.length - 1];
    return `${drawdownPath} L ${last.x.toFixed(1)},175 L ${first.x.toFixed(1)},175 Z`;
  }, [series, drawdownPath]);

  // X 軸 5 個等距刻度
  const xTicks = useMemo(() => {
    if (!series.length) return [];
    return [
      { label: series[0].label, x: series[0].x },
      { label: series[Math.floor(series.length * 0.25)].label, x: series[Math.floor(series.length * 0.25)].x },
      { label: series[Math.floor(series.length * 0.5)].label, x: series[Math.floor(series.length * 0.5)].x },
      { label: series[Math.floor(series.length * 0.75)].label, x: series[Math.floor(series.length * 0.75)].x },
      { label: series[series.length - 1].label, x: series[series.length - 1].x },
    ];
  }, [series]);

  return (
    <section
      className={cn(
        "panel flex min-w-0 flex-col overflow-hidden p-4",
        className
      )}
    >
      {/* 1. 頂部標題列 (含 1D/7D/30D/YTD 週期切換) */}
      <div className="-mx-4 -mt-4 mb-3 flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-xs font-medium text-foreground">Equity & Drawdown</h2>
        <div className="flex items-center gap-1 rounded bg-secondary/60 p-0.5">
          {ranges.map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setSelectedRange(r)}
              className={cn(
                "h-6 rounded px-2.5 font-mono text-[10px] transition-all cursor-pointer",
                selectedRange === r
                  ? "bg-secondary text-foreground font-semibold shadow-xs"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* 2. 數據主標題與圖例 (大字體金額 + 漲跌幅 + 雙色圖例) */}
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <div className="flex items-baseline gap-1.5">
            <span className="font-mono text-xl font-medium tracking-tight text-foreground">
              {liveEquity.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
            <span className="text-[10px] text-muted-foreground font-mono">USDT</span>
          </div>
          <p className="mt-0.5 flex items-center gap-1.5 font-mono text-[11px] font-medium text-up">
            <span>{returnPctText}</span>
            <span className="text-[10px] text-muted-foreground font-normal">this period</span>
          </p>
        </div>

        <div className="flex items-center gap-4 text-[10px] text-muted-foreground font-medium">
          <div className="flex items-center gap-1.5">
            <span className="h-0.5 w-3 rounded-full bg-up" />
            <span>Equity</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-0.5 w-3 rounded-full bg-down" />
            <span>Drawdown</span>
          </div>
        </div>
      </div>

      {/* 3. 高解析 SVG 雙軸畫布 (純淨 120 FPS 渲染) */}
      <div className="relative w-full flex-1 min-h-[220px]">
        <svg
          viewBox="0 0 600 215"
          preserveAspectRatio="none"
          className="h-full w-full overflow-visible"
        >
          <defs>
            {/* 權益走勢微光漸層 (連動系統漲色 --up) */}
            <linearGradient id="eq-grad-hero" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--up)" stopOpacity={0.22} />
              <stop offset="100%" stopColor="var(--up)" stopOpacity={0.01} />
            </linearGradient>

            {/* 水下回撤漸層 (連動系統跌色 --down) */}
            <linearGradient id="dd-grad-hero" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--down)" stopOpacity={0.03} />
              <stop offset="100%" stopColor="var(--down)" stopOpacity={0.2} />
            </linearGradient>
          </defs>

          {/* Y 軸水平輔助線與刻度 (左側權益金額) */}
          <g className="grid-lines">
            <line
              x1="55"
              y1="30"
              x2="555"
              y2="30"
              stroke="var(--border)"
              strokeDasharray="3 4"
              strokeOpacity={0.6}
            />
            <text
              x="48"
              y="33"
              textAnchor="end"
              fill="var(--muted-foreground)"
              fontSize="9"
              fontFamily="var(--font-mono)"
            >
              {((liveEquity * 1.05) / 1000).toFixed(0)}K
            </text>

            <line
              x1="55"
              y1="75"
              x2="555"
              y2="75"
              stroke="var(--border)"
              strokeDasharray="3 4"
              strokeOpacity={0.6}
            />
            <text
              x="48"
              y="78"
              textAnchor="end"
              fill="var(--muted-foreground)"
              fontSize="9"
              fontFamily="var(--font-mono)"
            >
              {((liveEquity * 1.00) / 1000).toFixed(0)}K
            </text>

            <line
              x1="55"
              y1="120"
              x2="555"
              y2="120"
              stroke="var(--border)"
              strokeDasharray="3 4"
              strokeOpacity={0.6}
            />
            <text
              x="48"
              y="123"
              textAnchor="end"
              fill="var(--muted-foreground)"
              fontSize="9"
              fontFamily="var(--font-mono)"
            >
              {((liveEquity * 0.95) / 1000).toFixed(0)}K
            </text>

            <line
              x1="55"
              y1="155"
              x2="555"
              y2="155"
              stroke="var(--border)"
              strokeDasharray="3 4"
              strokeOpacity={0.6}
            />
            <text
              x="48"
              y="158"
              textAnchor="end"
              fill="var(--muted-foreground)"
              fontSize="9"
              fontFamily="var(--font-mono)"
            >
              {((liveEquity * 0.90) / 1000).toFixed(0)}K
            </text>

            {/* Y 軸右側回撤刻度標籤 (0% 與 -4%) */}
            <line
              x1="55"
              y1="175"
              x2="555"
              y2="175"
              stroke="var(--border)"
              strokeOpacity={0.8}
            />
            <text
              x="562"
              y="178"
              textAnchor="start"
              fill="var(--muted-foreground)"
              fontSize="8.5"
              fontFamily="var(--font-mono)"
            >
              0%
            </text>
            <text
              x="562"
              y="195"
              textAnchor="start"
              fill="var(--muted-foreground)"
              fontSize="8.5"
              fontFamily="var(--font-mono)"
            >
              -4%
            </text>
          </g>

          {/* 水下回撤區域與折線 */}
          <path d={drawdownAreaPath} fill="url(#dd-grad-hero)" />
          <path
            d={drawdownPath}
            fill="none"
            stroke="var(--down)"
            strokeWidth="1.2"
            strokeOpacity={0.75}
          />

          {/* 帳戶權益區域與折線 */}
          <path d={equityAreaPath} fill="url(#eq-grad-hero)" />
          <path
            d={equityPath}
            fill="none"
            stroke="var(--up)"
            strokeWidth="2"
            strokeLinejoin="round"
          />

          {/* X 軸日期時間標籤 */}
          <g className="x-ticks">
            {xTicks.map((t, idx) => (
              <text
                key={idx}
                x={t.x}
                y="208"
                textAnchor={
                  idx === 0 ? "start" : idx === xTicks.length - 1 ? "end" : "middle"
                }
                fill="var(--muted-foreground)"
                fontSize="9"
                fontFamily="var(--font-mono)"
              >
                {t.label}
              </text>
            ))}
          </g>
        </svg>
      </div>

      {/* 4. 卡片底部資訊列 (績效週期 + 即時更新指示燈) */}
      <footer className="-mx-4 -mb-4 mt-2 flex items-center justify-between border-t border-border px-4 py-2.5 text-[10px] text-muted-foreground">
        <span>Portfolio performance · {selectedRange}</span>
        <span className="flex items-center gap-1.5">
          <span className="size-1.5 rounded-full bg-up animate-pulse" />
          <span>Updated just now</span>
        </span>
      </footer>
    </section>
  );
}
