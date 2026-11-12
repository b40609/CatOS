import { Panel } from "@/components/catos/shell";
import type { CostBreakdown, CostTotal } from "@/adapters/research-api-adapter";
import { cn } from "@/lib/utils";
import { formatDecimal, signOf, toneOf } from "@/lib/format";

/** One shape for a single run and for a sum of walk-forward windows. */
export interface CostView {
  price_pnl: string;
  fees: string;
  slippage: string;
  funding_paid: string;
  net_pnl: string;
  traded_notional: string;
  fill_count: number;
  cost_bps_per_side: string | null;
  break_even_bps_per_side: string | null;
  liquidation_cost?: string;
  buy_hold_pnl: string;
  underlying_return_pct: string | null;
  assumed_funding_paid: string | null;
  net_with_assumption: string | null;
  scenario_notice: string | null;
}

export function costViewFromBreakdown(costs: CostBreakdown): CostView {
  const scenario = costs.funding_scenario;
  return {
    ...costs,
    buy_hold_pnl: costs.buy_hold.pnl,
    underlying_return_pct: costs.buy_hold.underlying_return_pct,
    assumed_funding_paid: scenario?.assumed_paid ?? null,
    net_with_assumption: scenario?.net_pnl_with_assumption ?? null,
    scenario_notice: scenario?.notice ?? null,
  };
}

export function costViewFromTotal(total: CostTotal, scenarioNotice: string | null): CostView {
  return {
    ...total,
    underlying_return_pct: null,
    net_with_assumption: null,
    scenario_notice: total.assumed_funding_paid !== null ? scenarioNotice : null,
  };
}

/** Plain reading of the signs: where the loss (or profit) comes from. */
export function costVerdict(view: CostView): string {
  const price = signOf(view.price_pnl);
  if (view.fill_count === 0) return "沒有成交，無從拆解成本。";
  if (price !== "positive") return "扣成本前的價格損益已經不是正的：問題在訊號，降低成本也救不回來。";
  if (signOf(view.net_pnl) === "negative") return "扣成本前賺錢、扣成本後虧損：成本吃掉了優勢，需要降低交易頻率或成本。";
  return "扣成本前後都賺錢；每邊兩平成本和目前每邊成本的差距，就是對成本上升的緩衝。";
}

const USDT = { digits: 2, sign: true, suffix: " USDT" } as const;
const BPS = { digits: 2, suffix: " bps" } as const;

function Row({ label, value, tone, hint }: { label: string; value: string; tone?: string; hint?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border/50 py-1.5 last:border-b-0">
      <span className="text-muted-foreground" title={hint}>{label}</span>
      <span className={cn("font-mono text-foreground", tone)}>{value}</span>
    </div>
  );
}

export const LEGACY_COSTS_TEXT = "這筆結果沒有成本拆解（成本歸因上線前的舊紀錄）。";

export function CostBreakdownPanel({
  view, title = "成本拆解", meta, testId, emptyText = LEGACY_COSTS_TEXT, equitySized = false,
}: {
  view: CostView | null | undefined; title?: string; meta?: string; testId?: string; emptyText?: string;
  // Volatility-targeted strategies compare with 1x initial notional, not the same contracts.
  equitySized?: boolean;
}) {
  return (
    <Panel title={title} meta={meta ? <span className="text-t2 font-mono text-muted-foreground">{meta}</span> : undefined}>
      {!view ? (
        <p className="py-3 text-center text-xs text-muted-foreground">{emptyText}</p>
      ) : (
        <div data-testid={testId} data-price-pnl={view.price_pnl} data-net-pnl={view.net_pnl} className="text-xs">
          <p className="mb-2 rounded border border-border/60 bg-surface/40 px-2.5 py-1.5 text-muted-foreground">{costVerdict(view)}</p>
          <div className="grid grid-cols-1 gap-x-6 md:grid-cols-2">
            <div>
              <Row label="價格損益（成本前）" value={formatDecimal(view.price_pnl, USDT)} tone={toneOf(view.price_pnl)}
                hint="以成交那根 K 線的開盤價計，未扣手續費、滑價與資金費" />
              <Row label="手續費" value={formatDecimal(view.fees, { digits: 2, suffix: " USDT" })} />
              <Row label="滑價（含價格取整）" value={formatDecimal(view.slippage, { digits: 2, suffix: " USDT" })} />
              <Row label="資金費（資料集實際）" value={formatDecimal(view.funding_paid, { digits: 2, sign: true, suffix: " USDT" })}
                hint="正數為支出、負數為收入" />
              {view.liquidation_cost !== undefined && signOf(view.liquidation_cost) !== "zero" && (
                <Row label="強平清算費" value={formatDecimal(view.liquidation_cost, { digits: 2, sign: true, suffix: " USDT" })}
                  hint="保證金模型強平時收的清算費，扣除保險基金補足的穿倉；負數表示保險基金補足的比清算費多" />
              )}
              <Row label="淨損益" value={formatDecimal(view.net_pnl, USDT)} tone={toneOf(view.net_pnl)} />
            </div>
            <div>
              <Row label="成交筆數／名目" value={`${view.fill_count} 筆 · ${formatDecimal(view.traded_notional, { digits: 0, suffix: " USDT" })}`} />
              <Row label="每邊成本" value={formatDecimal(view.cost_bps_per_side, BPS)} hint="（手續費＋滑價）÷ 成交名目" />
              <Row label="每邊兩平成本" value={formatDecimal(view.break_even_bps_per_side, BPS)}
                tone={toneOf(view.break_even_bps_per_side)} hint="淨損益為 0 時，每邊最多能承受的手續費＋滑價" />
              <Row label={equitySized ? "買進持有（期初 1 倍名目、成本前）" : "買進持有（同張數、成本前）"}
                value={formatDecimal(view.buy_hold_pnl, USDT)} tone={toneOf(view.buy_hold_pnl)}
                hint={equitySized ? "同一評估期間、以期初本金 1 倍名目做多不動；未計手續費與資金費"
                  : "同一評估期間、同張數做多不動；未計手續費與資金費"} />
              {view.underlying_return_pct !== null && (
                <Row label="標的漲跌" value={formatDecimal(view.underlying_return_pct, { digits: 2, sign: true, suffix: "%" })} />
              )}
            </div>
          </div>
          {view.assumed_funding_paid !== null && (
            <div className="mt-2 rounded border border-amber-400/30 bg-amber-400/5 px-2.5 py-1.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-amber-400/90">假設資金費（未涵蓋期間）</span>
                <span className="font-mono">
                  {formatDecimal(view.assumed_funding_paid, { digits: 2, sign: true, suffix: " USDT" })}
                  {view.net_with_assumption !== null && (
                    <> · 淨損益 <span className={toneOf(view.net_with_assumption)}>{formatDecimal(view.net_with_assumption, USDT)}</span></>
                  )}
                </span>
              </div>
              {view.scenario_notice && <p className="mt-1 text-t2 text-muted-foreground">{view.scenario_notice}</p>}
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}
