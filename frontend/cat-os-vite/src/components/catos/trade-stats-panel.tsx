import { Panel } from "@/components/catos/shell";
import type { TradeStats } from "@/adapters/research-api-adapter";
import { cn } from "@/lib/utils";
import { formatDecimal, formatRatioPct, toneOf } from "@/lib/format";

const USDT = { digits: 2, sign: true, suffix: " USDT" } as const;

function Cell({ label, value, tone, hint }: { label: string; value: string; tone?: string; hint?: string }) {
  return (
    <div className="rounded border border-border/50 bg-surface/40 px-2.5 py-1.5" title={hint}>
      <span className="block text-t2 text-muted-foreground">{label}</span>
      <span className={cn("font-mono text-sm text-foreground", tone)}>{value}</span>
    </div>
  );
}

/** Closed round trips after costs; win rate is shown beside payoff and expectancy, never alone. */
export function TradeStatsPanel({ stats }: { stats: TradeStats }) {
  const pct = (value: string | null) => formatRatioPct(value, { sign: false });
  const side = (label: string, s: TradeStats["long"]) =>
    `${label} ${s.trips} 筆 · 勝率 ${pct(s.win_rate)} · ${formatDecimal(s.net_pnl, USDT)}`;
  return (
    <Panel title="往返交易統計（扣成本）" meta={<span className="text-t2 font-mono text-muted-foreground">{stats.closed_trips} 筆已平倉</span>}>
      <div data-testid="backtest-trade-stats" data-win-rate={stats.win_rate ?? ""} className="space-y-2 text-xs">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Cell label="勝率" value={`${pct(stats.win_rate)}（${stats.wins} 勝 ${stats.losses} 敗）`} />
          <Cell label="平均賺／平均賠" value={`${formatDecimal(stats.average_win, USDT)} ／ ${formatDecimal(stats.average_loss, USDT)}`} />
          <Cell label="賺賠比（平均）" value={formatDecimal(stats.payoff_ratio, { digits: 2 })}
            hint="平均賺 ÷ 平均賠；勝率高但賺賠比低，期望值可能是負的" />
          <Cell label="獲利因子" value={formatDecimal(stats.profit_factor, { digits: 2 })}
            hint="總賺 ÷ 總賠；大於 1 才是賺錢" />
          <Cell label="每筆期望值" value={formatDecimal(stats.expectancy, USDT)} tone={toneOf(stats.expectancy)} />
          <Cell label="最大連虧" value={`${stats.max_consecutive_losses} 筆`} />
          <Cell label="平均持倉" value={stats.average_hold_hours === null ? "不適用"
            : `${formatDecimal(stats.average_hold_hours, { digits: 1 })} 小時`} />
          <Cell label="最大單筆賺／賠" value={`${formatDecimal(stats.largest_win, USDT)} ／ ${formatDecimal(stats.largest_loss, USDT)}`} />
        </div>
        <p className="font-mono text-t2 text-muted-foreground">{side("多單", stats.long)} ｜ {side("空單", stats.short)}</p>
        {stats.open_trip && (
          <p className="text-t2 text-amber-400/90">
            期末還有一筆未平倉的{stats.open_trip.side > 0 ? "多單" : "空單"}，含未實現損益 {formatDecimal(stats.open_trip.net_pnl_with_unrealized, USDT)}，不計入勝負。
          </p>
        )}
        <p className="text-t2 text-muted-foreground">{stats.notice}</p>
      </div>
    </Panel>
  );
}
