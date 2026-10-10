import { useLiveNumber, fmtMoney, fmtSigned } from "@/hooks/use-live";
import { derivativesSnapshot } from "@/lib/mock/data";

export function DerivativesMetrics() {
  const { value: funding } = useLiveNumber(derivativesSnapshot.fundingPct, 0.01, 3200);
  const { value: openInterest } = useLiveNumber(derivativesSnapshot.openInterestB, 0.001, 2800);
  const { value: liquidations } = useLiveNumber(derivativesSnapshot.liquidationsM, 0.006, 3600);
  const longLiquidations = liquidations * derivativesSnapshot.longLiquidationsM / derivativesSnapshot.liquidationsM;
  const shortLiquidations = liquidations - longLiquidations;

  return (
    <section aria-label="加密衍生品市場指標" className="grid gap-3 sm:grid-cols-3">
      <div className="panel min-w-0 px-4 py-3.5">
        <p className="label-xs">funding rate · 資金費率</p>
        <p className="num mt-2 text-xl text-warn">{fmtSigned(funding, 4)}%</p>
        <p className="mt-1.5 text-[0.7rem] text-muted-foreground">永續合約 · 8 小時加權平均</p>
      </div>
      <div className="panel min-w-0 px-4 py-3.5">
        <p className="label-xs">open interest · 未平倉量</p>
        <p className="num mt-2 text-xl text-gold-bright">₮ {fmtMoney(openInterest, 2)}B</p>
        <p className="mt-1.5 text-[0.7rem] text-muted-foreground">BTC / ETH / SOL / DOGE 合計</p>
      </div>
      <div className="panel min-w-0 px-4 py-3.5">
        <p className="label-xs">liquidations · 爆倉量</p>
        <p className="num mt-2 text-xl text-down">₮ {fmtMoney(liquidations, 1)}M</p>
        <p className="mt-1.5 text-[0.7rem] text-muted-foreground">
          24H · 多單 {fmtMoney(longLiquidations, 1)}M / 空單 {fmtMoney(shortLiquidations, 1)}M
        </p>
      </div>
    </section>
  );
}