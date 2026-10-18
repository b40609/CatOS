import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from "recharts";
import { Sparkles, Trophy } from "lucide-react";

export interface TrialPoint {
  trialNumber: number;
  fastPeriod: number;
  slowPeriod: number;
  atrMultiplier: number;
  sharpe: number;
  totalReturn: number;
  maxDrawdown: number;
  isPareto: boolean;
  isBest?: boolean;
}

export const PARETO_TRIALS: TrialPoint[] = [
  { trialNumber: 42, fastPeriod: 12, slowPeriod: 34, atrMultiplier: 2.5, sharpe: 2.45, totalReturn: 26.8, maxDrawdown: 3.8, isPareto: true, isBest: true },
  { trialNumber: 65, fastPeriod: 14, slowPeriod: 38, atrMultiplier: 3.0, sharpe: 2.08, totalReturn: 19.6, maxDrawdown: 3.5, isPareto: true },
  { trialNumber: 28, fastPeriod: 10, slowPeriod: 30, atrMultiplier: 2.0, sharpe: 2.21, totalReturn: 22.4, maxDrawdown: 4.2, isPareto: true },
  { trialNumber: 84, fastPeriod: 16, slowPeriod: 45, atrMultiplier: 2.8, sharpe: 1.75, totalReturn: 14.1, maxDrawdown: 4.6, isPareto: false },
  { trialNumber: 91, fastPeriod: 11, slowPeriod: 32, atrMultiplier: 2.2, sharpe: 1.68, totalReturn: 13.5, maxDrawdown: 4.9, isPareto: false },
  { trialNumber: 15, fastPeriod: 8, slowPeriod: 25, atrMultiplier: 1.8, sharpe: 1.92, totalReturn: 17.3, maxDrawdown: 5.1, isPareto: false },
  { trialNumber: 19, fastPeriod: 9, slowPeriod: 28, atrMultiplier: 2.1, sharpe: 1.84, totalReturn: 15.2, maxDrawdown: 4.8, isPareto: false },
  { trialNumber: 52, fastPeriod: 15, slowPeriod: 40, atrMultiplier: 2.6, sharpe: 2.02, totalReturn: 18.9, maxDrawdown: 4.1, isPareto: false },
  { trialNumber: 73, fastPeriod: 13, slowPeriod: 36, atrMultiplier: 2.4, sharpe: 2.18, totalReturn: 21.0, maxDrawdown: 4.0, isPareto: true },
  { trialNumber: 88, fastPeriod: 17, slowPeriod: 48, atrMultiplier: 3.2, sharpe: 1.58, totalReturn: 11.8, maxDrawdown: 5.4, isPareto: false },
  { trialNumber: 95, fastPeriod: 7, slowPeriod: 22, atrMultiplier: 1.6, sharpe: 1.62, totalReturn: 12.5, maxDrawdown: 5.3, isPareto: false },
];

interface ParetoScatterChartProps {
  selectedTrialNumber?: number;
  onSelectTrial?: (trial: TrialPoint) => void;
}

export function ParetoScatterChart({ selectedTrialNumber = 42, onSelectTrial }: ParetoScatterChartProps) {

  return (
    <div className="rounded-xl border border-border/80 bg-surface/90 overflow-hidden shadow-xs backdrop-blur-md">
      <div className="flex items-center justify-between border-b border-border/80 px-3.5 py-2 bg-secondary/30">
        <div className="flex items-center gap-2">
          <Sparkles className="size-3.5 text-primary" />
          <span className="text-xs font-semibold text-foreground">
            帕累托前沿二維搜尋散佈圖 (Optuna Pareto Frontier)
          </span>
          <span className="text-[10px] font-mono text-muted-foreground hidden sm:inline">
            · 回撤 vs 夏普比率最佳權衡
          </span>
        </div>

        <div className="flex items-center gap-2 text-[10px] font-mono">
          <span className="flex items-center gap-1 text-primary">
            <span className="size-2 rounded-full bg-primary" />
            帕累托最優解 (Top Frontier)
          </span>
          <span className="text-border">|</span>
          <span className="flex items-center gap-1 text-muted-foreground">
            <span className="size-2 rounded-full bg-muted-foreground/60" />
            一般試驗 (Trials)
          </span>
        </div>
      </div>

      <div className="p-3">
        <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground mb-1.5 px-1">
          <span>Y 軸：夏普比率 (Sharpe Ratio ↑ 越高越好)</span>
          <span>X 軸：最大回撤 (Max Drawdown % ↓ 越低越好)</span>
        </div>

        <div className="h-[200px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" opacity={0.3} />
              <XAxis
                type="number"
                dataKey="maxDrawdown"
                name="Max Drawdown"
                unit="%"
                domain={[3.0, 6.0]}
                tick={{ fontSize: 9, fill: "var(--color-muted-foreground)" }}
                tickFormatter={(v) => `-${v.toFixed(1)}%`}
              />
              <YAxis
                type="number"
                dataKey="sharpe"
                name="Sharpe Ratio"
                domain={[1.4, 2.6]}
                tick={{ fontSize: 9, fill: "var(--color-muted-foreground)" }}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload as TrialPoint;
                    return (
                      <div className="rounded-lg border border-border bg-popover p-2 text-xs font-mono shadow-md">
                        <div className="flex items-center justify-between gap-2 border-b border-border/50 pb-1">
                          <span className="font-bold text-primary flex items-center gap-1">
                            {data.isBest && <Trophy className="size-3 text-gold" />}
                            Trial #{data.trialNumber}
                          </span>
                          <span className="text-[10px] text-muted-foreground">
                            {data.isPareto ? "★ 帕累托最優" : "一般採樣"}
                          </span>
                        </div>
                        <div className="mt-1.5 space-y-0.5 text-[10.5px]">
                          <div>夏普值: <strong className="text-up font-bold">{data.sharpe}</strong></div>
                          <div>最大回撤: <strong className="text-down font-bold">-{data.maxDrawdown}%</strong></div>
                          <div>總收益: <strong className="text-foreground">+{data.totalReturn}%</strong></div>
                          <div className="text-[9.5px] text-muted-foreground pt-0.5">
                            fast={data.fastPeriod}, slow={data.slowPeriod}, atr={data.atrMultiplier}
                          </div>
                        </div>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Scatter
                name="Trials"
                data={PARETO_TRIALS}
                onClick={(node) => {
                  if (onSelectTrial) onSelectTrial(node.payload as TrialPoint);
                }}
              >
                {PARETO_TRIALS.map((entry, index) => {
                  const isSelected = entry.trialNumber === selectedTrialNumber;
                  const isPareto = entry.isPareto;
                  return (
                    <Cell
                      key={`cell-${index}`}
                      fill={
                        isSelected
                          ? "var(--color-gold-bright)"
                          : isPareto
                            ? "var(--color-primary)"
                            : "var(--color-muted-foreground)"
                      }
                      stroke={isSelected ? "#ffffff" : isPareto ? "var(--color-gold)" : "transparent"}
                      strokeWidth={isSelected ? 2 : 1}
                      r={isSelected ? 7 : isPareto ? 5.5 : 3.5}
                      className="cursor-pointer transition-all hover:scale-125"
                    />
                  );
                })}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>

        {/* 底部已選中 Trial 的精簡參數徽章 */}
        <div className="mt-2 flex items-center justify-between rounded border border-border/60 bg-background/50 px-2.5 py-1 text-[11px] font-mono">
          <span className="text-muted-foreground">
            當前選中：<strong className="text-primary font-bold">Trial #{selectedTrialNumber}</strong>
          </span>
          <span className="text-muted-foreground text-[10px]">
            點擊散佈點可即時載入該組超參數組合
          </span>
        </div>
      </div>
    </div>
  );
}
