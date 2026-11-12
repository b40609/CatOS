import { Panel } from "@/components/catos/shell";
import type { DailyLossLimitCount, DailyLossLimits } from "@/adapters/research-api-adapter";
import { cn } from "@/lib/utils";
import { formatDecimal } from "@/lib/format";

function pct(value: string | null | undefined) {
  return formatDecimal(value, { digits: 2, suffix: "%" });
}

function LimitCell({ name, count }: { name: string; count: DailyLossLimitCount }) {
  const hit = count.days > 0;
  return (
    <div className="rounded border border-border/50 bg-surface/40 px-2.5 py-1.5"
         data-testid={`loss-limit-${name.toLowerCase()}`} data-days={count.days}>
      <span className="block text-t2 text-muted-foreground">{name} {pct(count.limit_pct)}</span>
      <span className={cn("font-mono text-sm", hit ? "text-amber-400" : "text-foreground")}>
        {count.days} 天
      </span>
      <span className="ml-1.5 font-mono text-t2 text-muted-foreground">
        每年 {count.per_year ?? "--"} 天 · 首次 {count.first_day ?? "無"}
      </span>
      {count.listed.length > 0 && (
        <details className="mt-1 text-t2">
          <summary className="cursor-pointer text-muted-foreground">觸發日清單{count.truncated ? `（前 ${count.listed.length} 天）` : ""}</summary>
          <ul className="mt-1 max-h-32 overflow-y-auto font-mono text-muted-foreground">
            {count.listed.map((entry) => (
              <li key={entry.day}>{entry.day} · 虧 {pct(entry.loss_pct)}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

/** Diagnostic only: how many Taipei days would hit Soft/Hard; fills and PnL are unchanged. */
export function DailyLossLimitsPanel({ value }: { value: DailyLossLimits | undefined }) {
  if (!value) {
    return (
      <Panel title="套用 Soft／Hard 日損門檻的觸發次數">
        <p data-testid="backtest-loss-limits-missing" className="text-xs text-muted-foreground">
          舊紀錄沒有日損門檻診斷，重跑回測才會有。
        </p>
      </Panel>
    );
  }
  const worst = value.max_daily_loss;
  return (
    <Panel
      title="套用 Soft／Hard 日損門檻的觸發次數"
      meta={<span className="text-t2 font-mono text-muted-foreground">
        {value.days_evaluated} 個台北日 · {value.years ?? "--"} 年
      </span>}
    >
      <div data-testid="backtest-loss-limits" className="space-y-2 text-xs">
        <p className="text-t2 text-muted-foreground">
          最大單日虧損{" "}
          <strong className="font-mono text-foreground">{worst ? `${pct(worst.loss_pct)}（${worst.day}）` : "--"}</strong>
          {value.first_day && <> · 期間 {value.first_day} 至 {value.last_day}</>}
          {value.stopped && (
            <span className="text-rose-400">
              {" "}· {value.stopped.day} {value.stopped.reason === "liquidation" ? "被強平" : "權益跌破 0"}，算觸發，之後不再計數
            </span>
          )}
        </p>
        {value.thresholds.map((item) => (
          <div key={item.key} data-testid={`loss-limits-${item.key}`} className="space-y-1">
            <p className={cn("text-t2", item.applied_to_risk ? "text-foreground" : "text-amber-400/90")}>{item.label}</p>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <LimitCell name="Soft" count={item.soft} />
              <LimitCell name="Hard" count={item.hard} />
            </div>
          </div>
        ))}
        {value.straddling_bars > 0 && (
          <p className="text-t2 text-amber-400/90">有 {value.straddling_bars} 根 K 線跨過台北午夜，歸入開盤所在的日。</p>
        )}
        <ul className="list-disc space-y-0.5 pl-4 text-t2 text-muted-foreground">
          {value.notice.map((line) => <li key={line}>{line}</li>)}
        </ul>
      </div>
    </Panel>
  );
}
