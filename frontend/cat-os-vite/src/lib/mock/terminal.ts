export const dashboardRanges = ["1D", "7D", "30D", "YTD"] as const;
export type DashboardRange = (typeof dashboardRanges)[number];

const rangeDays: Record<DashboardRange, number> = { "1D": 1, "7D": 7, "30D": 30, YTD: 283 };
const rangeReturns: Record<DashboardRange, number> = { "1D": 0.0085, "7D": 0.0454, "30D": 0.1246, YTD: 0.348 };

// 確定性偽隨機生成器，保證走勢曲線細緻度穩定且富有量化交易高頻真實微鋸齒感
function pseudoNoise(seed: number) {
  const x = Math.sin(seed * 12.9898 + 78.233) * 43758.5453;
  return (x - Math.floor(x)) * 2 - 1;
}

export function getEquitySeries(range: DashboardRange) {
  const end = 12_483_920;
  const targetReturn = rangeReturns[range];
  const start = end / (1 + targetReturn);
  const totalPoints = 220;
  let peak = start;

  // 定義 5 個基準時間刻度錨點（精準復刻專業終端時間戳）
  const tickIndices = [0, 55, 110, 165, totalPoints - 1];

  let cumulativeJitter = 0;
  const rawValues: number[] = [];

  for (let i = 0; i < totalPoints; i++) {
    const t = i / (totalPoints - 1);

    // 1. 宏觀上升 Alpha 趨勢
    const macroTrend = Math.pow(t, 0.88);

    // 2. 中頻市場震盪波（幾次回調與突破階梯）
    const midWave =
      Math.sin(t * Math.PI * 4.2) * 0.0035 +
      Math.cos(t * Math.PI * 7.5) * 0.002 +
      Math.sin(t * Math.PI * 1.8) * 0.004;

    // 3. 高頻盤口成交微鋸齒（Micro-fluctuations · 呈現量化交易真實細緻紋理）
    const noise = pseudoNoise(i * 1.37) * 0.00095 + pseudoNoise(i * 3.71) * 0.00065;
    cumulativeJitter += noise * 0.35;
    cumulativeJitter = Math.max(-0.004, Math.min(0.004, cumulativeJitter));

    // 綜合收益率
    let curReturn = targetReturn * (macroTrend + midWave) + cumulativeJitter;
    if (i === 0) curReturn = 0;
    if (i === totalPoints - 1) curReturn = targetReturn;
    rawValues.push(curReturn);
  }

  return rawValues.map((ret, i) => {
    const t = i / (totalPoints - 1);
    const equity = Math.round(start * (1 + ret));
    peak = Math.max(peak, equity);

    const date = new Date(Date.UTC(2026, 9, 10, 9, 42) - (1 - t) * rangeDays[range] * 86400000);
    const m = date.getUTCMonth() + 1;
    const d = date.getUTCDate();
    const hh = String(date.getUTCHours()).padStart(2, "0");
    const mm = String(date.getUTCMinutes()).padStart(2, "0");
    const fullTime = `${date.getUTCFullYear()}/${m}/${d} ${hh}:${mm}`;
    const tickTime = `${m}/${d} ${hh}:${mm}`;

    // 僅在 5 個主要錨點輸出 X 軸標籤，保持圖表透氣乾淨
    const isMajorTick = tickIndices.includes(i);
    const label = isMajorTick ? (range === "1D" ? `${hh}:${mm}` : tickTime) : "";

    return {
      index: i,
      label,
      fullTime,
      tickTime,
      isMajorTick,
      equity,
      returnPct: Number((ret * 100).toFixed(2)),
      drawdown: Number(((equity / peak - 1) * 100).toFixed(3)),
    };
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