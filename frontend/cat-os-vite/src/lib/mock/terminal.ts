export const dashboardRanges = ["1D", "7D", "30D", "YTD"] as const;
export type DashboardRange = (typeof dashboardRanges)[number];

const rangeDays: Record<DashboardRange, number> = { "1D": 1, "7D": 7, "30D": 30, YTD: 283 };
const rangeReturns: Record<DashboardRange, number> = { "1D": 0.0047, "7D": 0.0382, "30D": 0.1246, YTD: 0.348 };

export function getEquitySeries(range: DashboardRange) {
  const end = 12_483_920;
  const start = end / (1 + rangeReturns[range]);
  let peak = start;
  return Array.from({ length: 72 }, (_, i) => {
    const t = i / 71;
    const wave = (Math.sin(i * 0.71) * 0.32 + Math.sin(i * 0.21) * 0.64) * Math.sin(t * Math.PI);
    const equity = Math.round(start + (end - start) * (t + wave * 0.14));
    peak = Math.max(peak, equity);
    const date = new Date(Date.UTC(2026, 9, 10) - (1 - t) * rangeDays[range] * 86400000);
    const label = range === "1D" ? date.toISOString().slice(11, 16) : date.toISOString().slice(5, 10).replace("-", "/");
    return { label, equity, drawdown: Number(((equity / peak - 1) * 100).toFixed(3)) };
  });
}

export const openPositions = [
  { symbol: "BTC-PERP", code: "BTC", side: "LONG", size: 1.24, entry: 62_840, mark: 64_182.5, strategy: "CAT-MOM-01", venue: "Binance" },
  { symbol: "ETH-PERP", code: "ETH", side: "SHORT", size: 4.2, entry: 3_228.4, mark: 3_182.6, strategy: "CAT-VOL-09", venue: "OKX" },
  { symbol: "SOL-PERP", code: "SOL", side: "LONG", size: 18.5, entry: 138.72, mark: 142.38, strategy: "CAT-NLP-05", venue: "Binance" },
  { symbol: "ETH-USDT", code: "ETH", side: "LONG", size: 2.8, entry: 3_201.8, mark: 3_182.6, strategy: "CAT-MR-07", venue: "OKX" },
] as const;

export function positionPnl(position: { side: string; size: number; entry: number; mark: number }) {
  return (position.mark - position.entry) * position.size * (position.side === "SHORT" ? -1 : 1);
}

export const recentFills = [
  { id: "tf1", time: "10:02:18", symbol: "BTC-PERP", side: "BUY" as const, qty: 0.35, price: 64_182.5, pnl: 812.4 },
  { id: "tf2", time: "10:01:54", symbol: "ETH-PERP", side: "SELL" as const, qty: 1.2, price: 3_182.6, pnl: 461.9 },
  { id: "tf3", time: "10:00:32", symbol: "SOL-PERP", side: "BUY" as const, qty: 12, price: 142.38, pnl: -48.2 },
  { id: "tf4", time: "09:58:41", symbol: "BTC-PERP", side: "SELL" as const, qty: 0.2, price: 64_120.8, pnl: 284.7 },
  { id: "tf5", time: "09:56:05", symbol: "ETH-USDT", side: "BUY" as const, qty: 2.8, price: 3_201.8, pnl: -53.76 },
];